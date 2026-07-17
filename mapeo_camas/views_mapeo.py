# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Endpoints del ciclo de sesión de mapeo: iniciar/estado/terminar/cancelar
y procesamiento por cama (procesar_cama_mapeo)."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.utils.utilidades_fechas import hora_local_iso
from core.utils.utilidades_request import parse_json_request
from core.services.mapeo_camas_service import MapeoCamasService
from servicio.models import Cama, Servicio

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    HistorialEstadoCama,
    MapeoSesionCama,
    MapeoSesionServicio,
    get_observacion_mapeo,
)

from core.constants.mapeo_camas_constants import (
    OBSERVACION_CAMBIO_TRASLADO_MAPEO,
    OBSERVACION_SESION_SIN_OBSERVACIONES,
)
from .constants.view_constants import (
    ACCIONES_MAPEO_PERMITIDAS_ROL_RESTRINGIDO,
    ACCIONES_MAPEO_VALIDAS,
    ESTADOS_OCUPADA_PREALTA,
    MAPEO_CAMAS_SALA_NEONATOLOGIA_ID,
    MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID,
    MAPEO_CAMAS_SERVICIO_VIRTUAL_NEONATOLOGIA_ID,
)
from ._helpers import (
    _nombre_usuario,
    _normalizar_observacion_sesion,
    _obtener_observacion_desde_request,
    _resolver_ingreso_operativo,
    get_estado_mapeo,
)
from ._permisos import (
    _es_rol_intentos_restringido,
    _puede_cancelar_mapeo,
    _puede_gestionar_sesion_mapeo,
    _tiene_permiso_mapear,
    _validar_limite_intentos_salas,
)
from ._sesion import (
    _camas_mapeadas_sesion,
    _guardar_scope_sesion,
    _obtener_sesion_mapeo_activa,
    _obtener_salas_ids_sesion,
    _obtener_servicios_ids_sesion,
    _registrar_detalle_mapeo,
    _registrar_historial_mapeo,
    _sincronizar_cama_en_ingreso_activo,
)
from .validators import validar_accion_mapeo, validar_cama_id
from .validators import validar_id_opcional, validar_servicios_ids_mapeo


__all__ = [
    "iniciar_mapeo",
    "estado_mapeo",
    "terminar_mapeo",
    "cancelar_mapeo",
    "procesar_cama_mapeo",
]


# [2026-05-07] API: Iniciar nueva sesión de mapeo de camas
@login_required
@require_POST
def iniciar_mapeo(request):
    """Inicia una sesion de mapeo para el usuario actual."""
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    # [2026-06-11] El inicio de sesión se controla por MAPEO_CAMAS_MAPEAR_*.
    # Las restricciones de intentos se aplican durante movimientos/edición de camas.
    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    if sesion_activa:
        servicios_ids = _obtener_servicios_ids_sesion(sesion_activa)
        # 2026-06-04: reutiliza helper general de fechas (core.utils.utilidades_fechas.hora_local_iso).
        return JsonResponse(
            {
                "ok": True,
                "sesion_id": sesion_activa.id,
                "estado": sesion_activa.estado.codigo if sesion_activa.estado else None,
                "hora_inicio": hora_local_iso(sesion_activa.fecha_inicio),
                "camas_mapeadas": _camas_mapeadas_sesion(sesion_activa),
                "servicio_ids": servicios_ids,
                "mensaje": "Ya existe una sesion de mapeo en progreso.",
            }
        )

    try:
        payload = parse_json_request(request)
    except ValueError:
        payload = {}

    servicio_ids = payload.get("servicio_ids") or []
    sala_ids_scope = []
    # 2026-06-09: valida servicio_ids desde validators antes de consultar modelos.
    try:
        servicios_ids_normalizados = validar_servicios_ids_mapeo(servicio_ids)
    except ValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        if "lista valida de servicios" in msg:
            return JsonResponse({"ok": False, "error": "Debe indicar una lista valida de servicios."}, status=400)
        if "al menos un servicio" in msg:
            return JsonResponse({"ok": False, "error": "Debe seleccionar al menos un servicio para iniciar el mapeo."}, status=400)
        return JsonResponse({"ok": False, "error": "La lista de servicios contiene valores invalidos."}, status=400)

    # [2026-06-26 SCOPE] Regla de negocio:
    # - Neonatologia se inicia de forma aislada (scope de sala).
    # - No se permite mezclar Pediatria + Neonatologia en una misma sesion.
    seleccion_neonatologia = MAPEO_CAMAS_SERVICIO_VIRTUAL_NEONATOLOGIA_ID in servicios_ids_normalizados
    seleccion_pediatria = MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID in servicios_ids_normalizados
    if seleccion_neonatologia and seleccion_pediatria:
        return JsonResponse(
            {
                "ok": False,
                "error": "Neonatologia se mapea de forma aislada. Seleccione Pediatria o Neonatologia, pero no ambas.",
            },
            status=400,
        )
    if seleccion_neonatologia:
        # Convierte el servicio virtual de UI al servicio real para persistencia.
        servicios_ids_normalizados = [
            sid for sid in servicios_ids_normalizados
            if sid != MAPEO_CAMAS_SERVICIO_VIRTUAL_NEONATOLOGIA_ID
        ]
        servicios_ids_normalizados.append(MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID)
        servicios_ids_normalizados = sorted(set(servicios_ids_normalizados))
        sala_ids_scope = [MAPEO_CAMAS_SALA_NEONATOLOGIA_ID]

    servicios_validos_ids = list(
        Servicio.objects.filter(estado=1, id__in=servicios_ids_normalizados)
        .order_by("id")
        .values_list("id", flat=True)
    )
    if len(servicios_validos_ids) != len(servicios_ids_normalizados):
        return JsonResponse({"ok": False, "error": "Uno o más servicios seleccionados no están disponibles."}, status=400)

    sesion_en_conflicto = (
        MapeoSesionCama.objects.select_related("usuario")
        .filter(
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
            servicios_incluidos__servicio_id__in=servicios_validos_ids,
        )
        .exclude(usuario=request.user)
        .order_by("-fecha_inicio")
        .first()
    )
    if sesion_en_conflicto:
        servicios_conflicto_ids = list(
            MapeoSesionServicio.objects.filter(
                sesion_mapeo=sesion_en_conflicto,
                servicio_id__in=servicios_validos_ids,
            ).values_list("servicio_id", flat=True)
        )
        servicios_conflicto = list(
            Servicio.objects.filter(id__in=servicios_conflicto_ids)
            .order_by("nombre_servicio")
            .values_list("nombre_servicio", flat=True)
        )
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No se puede iniciar el mapeo. "
                    "Al menos un servicio seleccionado ya está siendo mapeado por otro usuario."
                ),
                "sesion_id": sesion_en_conflicto.id,
                "usuario": _nombre_usuario(sesion_en_conflicto.usuario),
                "servicios_en_conflicto": servicios_conflicto,
            },
            status=409,
        )

    with transaction.atomic():
        sesion = MapeoSesionCama.objects.create(
            usuario=request.user,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            observacion=get_observacion_mapeo(OBSERVACION_SESION_SIN_OBSERVACIONES),
            observacion_texto=None,
        )
        MapeoSesionServicio.objects.bulk_create([
            MapeoSesionServicio(sesion_mapeo=sesion, servicio_id=servicio_id)
            for servicio_id in servicios_validos_ids
        ])
        # [2026-06-26 SCOPE] Si aplica, guarda alcance técnico de sala en la sesion.
        _guardar_scope_sesion(sesion, sala_ids=sala_ids_scope)

    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if sesion.estado else None,
            "hora_inicio": hora_local_iso(sesion.fecha_inicio),
            "camas_mapeadas": [],
            "servicio_ids": servicios_validos_ids,
            "sala_ids": sala_ids_scope,
            "mensaje": "Mapeo iniciado correctamente.",
        },
        status=201,
    )


@login_required
@require_GET
def estado_mapeo(request):
    """Devuelve la sesion de mapeo activa y camas ya procesadas para restaurar UI."""
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": True, "sesion_activa": None, "camas_mapeadas": [], "servicio_ids": []})

    return JsonResponse(
        {
            "ok": True,
            "sesion_activa": {
                "id": sesion.id,
                "estado": sesion.estado.codigo if sesion.estado else None,
                "hora_inicio": hora_local_iso(sesion.fecha_inicio),
            },
            "camas_mapeadas": _camas_mapeadas_sesion(sesion),
            "servicio_ids": _obtener_servicios_ids_sesion(sesion),
            "sala_ids": _obtener_salas_ids_sesion(sesion),
        }
    )


@login_required
@require_POST
def terminar_mapeo(request):
    """Finaliza la sesion activa de mapeo del usuario."""
    if not _puede_gestionar_sesion_mapeo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    observacion_sesion = _normalizar_observacion_sesion(_obtener_observacion_desde_request(request))

    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion)
    salas_ids_sesion = _obtener_salas_ids_sesion(sesion)
    total_camas_qs = Cama.objects.filter(
        sala__estado=1,
        sala__servicio__estado=1,
    )
    if servicios_ids_sesion:
        total_camas_qs = total_camas_qs.filter(sala__servicio_id__in=servicios_ids_sesion)
    if salas_ids_sesion:
        total_camas_qs = total_camas_qs.filter(sala_id__in=salas_ids_sesion)
    elif MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID in servicios_ids_sesion:
        total_camas_qs = total_camas_qs.exclude(sala_id=MAPEO_CAMAS_SALA_NEONATOLOGIA_ID)
    total_camas_objetivo = total_camas_qs.count()
    camas_mapeadas_ids = list(
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values_list("cama_id", flat=True)
        .distinct()
    )
    total_camas_mapeadas = len(camas_mapeadas_ids)

    if total_camas_mapeadas < total_camas_objetivo:
        faltantes = total_camas_objetivo - total_camas_mapeadas
        camas_faltantes = []
        # 2026-06-09: optimiza serialización de faltantes con values().
        faltantes_qs = (
            total_camas_qs.exclude(pk__in=camas_mapeadas_ids)
            .values(
                "pk",
                "numero_cama",
                "sala__nombre_sala",
                "sala__servicio__nombre_servicio",
                "cubiculo__numero",
                "cubiculo__nombre_cubiculo",
            )
            .order_by("numero_cama")
        )
        for cama in faltantes_qs:
            cubiculo = "SIN_CUBICULO"
            if cama.get("cubiculo__numero") is not None and cama.get("cubiculo__nombre_cubiculo"):
                cubiculo = f"{cama['cubiculo__numero']} - {cama['cubiculo__nombre_cubiculo']}"
            camas_faltantes.append(
                {
                    "cama_id": cama["pk"],
                    "numero_cama": str(cama["numero_cama"]),
                    "servicio": cama.get("sala__servicio__nombre_servicio") or "SIN_SERVICIO",
                    "sala": cama.get("sala__nombre_sala") or "SIN_SALA",
                    "cubiculo": cubiculo,
                }
            )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    f"No se puede finalizar el mapeo. Faltan {faltantes} cama(s) por procesar."
                ),
                "faltantes": faltantes,
                "total_camas": total_camas_objetivo,
                "camas_mapeadas": total_camas_mapeadas,
                "camas_faltantes": camas_faltantes,
            },
            status=400,
        )

    # 2026-06-01: asegura atomic en actualización de cierre de sesión de mapeo.
    with transaction.atomic():
        sesion.estado = get_estado_mapeo("FINALIZADO", "ESTADO_SESION")
        sesion.fecha_fin = timezone.now()
        sesion.observacion = get_observacion_mapeo(OBSERVACION_SESION_SIN_OBSERVACIONES)
        sesion.observacion_texto = observacion_sesion
        sesion.save(update_fields=["estado", "fecha_fin", "observacion", "observacion_texto"])

    total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if hasattr(sesion.estado, "codigo") else str(sesion.estado),
            "hora_fin": hora_local_iso(sesion.fecha_fin),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo finalizado correctamente.",
        }
    )


@login_required
@require_POST
def cancelar_mapeo(request):
    """Cancela la sesion activa de mapeo del usuario."""
    if not _puede_cancelar_mapeo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    next_url = (request.POST.get("next") or "").strip()
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None
    with transaction.atomic():
        if sesion_mapeo_id:
            try:
                sesion_mapeo_id = int(sesion_mapeo_id)
            except (TypeError, ValueError):
                if next_url:
                    return redirect(next_url)
                return JsonResponse({"ok": False, "error": "La sesion indicada no es valida."}, status=400)

            sesion = (
                MapeoSesionCama.objects.select_for_update()
                .select_related("usuario")
                .filter(
                    pk=sesion_mapeo_id,
                    estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
                    fecha_fin__isnull=True,
                )
                .first()
            )
        else:
            sesion = (
                MapeoSesionCama.objects.select_for_update()
                .select_related("usuario")
                .filter(
                    usuario=request.user,
                    estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
                    fecha_fin__isnull=True,
                )
                .order_by("-fecha_inicio")
                .first()
            )

        if not sesion:
            if next_url:
                return redirect(next_url)
            return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

        observacion_sesion = _normalizar_observacion_sesion(_obtener_observacion_desde_request(request))

        sesion.estado = get_estado_mapeo("CANCELADO", "ESTADO_SESION")
        sesion.fecha_fin = timezone.now()
        sesion.observacion = get_observacion_mapeo(OBSERVACION_SESION_SIN_OBSERVACIONES)
        sesion.observacion_texto = observacion_sesion
        sesion.save(update_fields=["estado", "fecha_fin", "observacion", "observacion_texto"])

        total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
        respuesta = {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if hasattr(sesion.estado, "codigo") else str(sesion.estado),
            "hora_fin": hora_local_iso(sesion.fecha_fin),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo cancelado correctamente.",
        }

    if next_url:
        return redirect(next_url)

    return JsonResponse(respuesta)


# [2026-05-07] API: Procesar acción de mapeo en cama
# 2026-05-29 (Refactor B): la transaccion se delega en
# core.services.mapeo_camas_service.MapeoOperacionesMapaService.procesar_accion_mapeo
@login_required
@require_POST
def procesar_cama_mapeo(request):
    """
    Ciclo principal de mapeo por cama: evaluar -> decidir -> ejecutar -> registrar.
    """
    from core.services.mapeo_camas_service import MapeoOperacionesMapaService

    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    cama_id = request.POST.get("cama_id")
    accion = (request.POST.get("accion") or "").strip().upper()
    observacion = (request.POST.get("observacion") or "").strip()
    ingreso_observado_id = request.POST.get("ingreso_observado_id") or None
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None

    acciones_validas = ACCIONES_MAPEO_VALIDAS
    # 2026-06-04: valida request con validators de app antes de ORM/modelo.
    try:
        cama_id = validar_cama_id(cama_id)
        validar_accion_mapeo(accion, acciones_validas)
        # 2026-06-09: valida IDs opcionales de request antes de filtros ORM.
        ingreso_observado_id = validar_id_opcional(ingreso_observado_id, "ingreso_observado_id")
        sesion_mapeo_id = validar_id_opcional(sesion_mapeo_id, "sesion_mapeo_id")
    except ValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        if "cama_id" in msg:
            return JsonResponse({"ok": False, "error": "Debe indicar cama_id."}, status=400)
        if "ingreso_observado_id" in msg:
            return JsonResponse({"ok": False, "error": "ingreso_observado_id debe ser un entero válido."}, status=400)
        if "sesion_mapeo_id" in msg:
            return JsonResponse({"ok": False, "error": "sesion_mapeo_id debe ser un entero válido."}, status=400)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    if _es_rol_intentos_restringido(request.user):
        acciones_permitidas_rol = ACCIONES_MAPEO_PERMITIDAS_ROL_RESTRINGIDO
        if accion not in acciones_permitidas_rol:
            return JsonResponse(
                {"ok": False, "error": "Este rol solo puede confirmar, mover pacientes o liberar camas en el flujo de mapeo."},
                status=403,
            )

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo__sala__servicio").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    sesion = None
    if sesion_mapeo_id:
        sesion = MapeoSesionCama.objects.filter(
            pk=sesion_mapeo_id,
            usuario=request.user,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
        ).first()
    if not sesion:
        sesion = _obtener_sesion_mapeo_activa(request.user)

    if not sesion:
        return JsonResponse(
            {"ok": False, "error": "No hay una sesion de mapeo activa. Debe iniciar mapeo primero."},
            status=400,
        )

    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion)
    salas_ids_sesion = _obtener_salas_ids_sesion(sesion)
    sala_real = cama.sala
    if servicios_ids_sesion and sala_real.servicio_id not in servicios_ids_sesion:
        return JsonResponse(
            {"ok": False, "error": "La cama seleccionada no pertenece a los servicios de esta sesion de mapeo."},
            status=403,
        )
    if salas_ids_sesion and sala_real.id not in salas_ids_sesion:
        return JsonResponse(
            {"ok": False, "error": "La cama seleccionada no pertenece al alcance de salas de esta sesion de mapeo."},
            status=403,
        )
    if (
        not salas_ids_sesion
        and MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID in servicios_ids_sesion
        and sala_real.id == MAPEO_CAMAS_SALA_NEONATOLOGIA_ID
    ):
        return JsonResponse(
            {"ok": False, "error": "Neonatologia se mapea en sesion aislada. Inicie una sesion especifica para esa sala."},
            status=403,
        )

    ingreso_observado = None
    if ingreso_observado_id:
        ingreso_observado = _resolver_ingreso_operativo(ingreso_id=ingreso_observado_id)
        if not ingreso_observado:
            return JsonResponse({"ok": False, "error": "Ingreso observado no existe."}, status=404)

    # Validaciones HTTP-dependientes específicas de CAMBIO_TRASLADO con rol restringido.
    if accion == "CAMBIO_TRASLADO" and ingreso_observado and _es_rol_intentos_restringido(request.user):
        asig_ingreso_en_sistema = (
            AsignacionCamaPaciente.objects
            .select_related("cama__sala__servicio", "estado")
            .filter(
                ingreso_id=ingreso_observado.id,
                estado__codigo__in=ESTADOS_OCUPADA_PREALTA,
                estado__categoria="ESTADO_CAMA",
            )
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        if asig_ingreso_en_sistema and asig_ingreso_en_sistema.cama_id != cama.pk:
            servicio_actual_id = getattr(cama.sala, "servicio_id", None)
            servicio_origen_id = getattr(asig_ingreso_en_sistema.cama.sala, "servicio_id", None)
            if servicio_actual_id and servicio_origen_id and servicio_actual_id != servicio_origen_id:
                return JsonResponse(
                    {"ok": False, "error": "Este rol solo puede realizar cambios de cama dentro del mismo servicio."},
                    status=403,
                )

    # [2026-06-09 FEATURE] Si la cama figura ocupada y el paciente observado no está en otra cama,
    # corregir a VACIA con observacion para alinear estado fisico vs sistema.
    if accion == "CAMBIO_TRASLADO" and ingreso_observado:
        asig_actual = (
            AsignacionCamaPaciente.objects
            .select_related("estado", "ingreso")
            .filter(cama_id=cama.pk)
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        asig_ingreso_en_otra_cama = (
            AsignacionCamaPaciente.objects
            .select_related("estado")
            .filter(
                ingreso_id=ingreso_observado.id,
                estado__codigo__in=ESTADOS_OCUPADA_PREALTA,
                estado__categoria="ESTADO_CAMA",
            )
            .exclude(cama_id=cama.pk)
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        if (
            asig_actual
            and asig_actual.estado
            and asig_actual.estado.codigo in ESTADOS_OCUPADA_PREALTA
            and asig_ingreso_en_otra_cama is None
        ):
            resultado_liberacion = MapeoCamasService.liberar_cama_reasignacion_sin_origen(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                estado_anterior=asig_actual.estado,
                sesion_mapeo=sesion,
            )
            return JsonResponse(
                {
                    "ok": True,
                    "mensaje": "No se encontro al paciente en otra cama. La cama se actualizo a VACIA con observacion.",
                    "estado_sistema": resultado_liberacion["estado_vacia"].codigo,
                }
            )

    if accion == "CAMBIO_TRASLADO":
        limite_error = _validar_limite_intentos_salas(request.user, [sala_real.id])
        if limite_error:
            return limite_error

    try:
        # 2026-06-09: atomic defensivo en endpoint para asegurar escritura transaccional.
        with transaction.atomic():
            resultado = MapeoOperacionesMapaService.procesar_accion_mapeo(
                usuario=request.user,
                cama=cama,
                accion=accion,
                observacion=observacion,
                ingreso_observado=ingreso_observado,
                sesion=sesion,
            )
    except ValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    respuesta = {"ok": True, "mensaje": resultado["mensaje"]}
    if "estado_sistema" in resultado:
        respuesta["estado_sistema"] = resultado["estado_sistema"]
    return JsonResponse(respuesta)
