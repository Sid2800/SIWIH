# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Endpoints del ciclo de sesión de mapeo: iniciar/estado/terminar/cancelar
y procesamiento por cama (procesar_cama_mapeo)."""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.utils.utilidades_request import parse_json_request
from servicio.models import Cama, Servicio

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    HistorialEstadoCama,
    MapeoSesionCama,
    MapeoSesionServicio,
    get_observacion_mapeo,
)

from ._constants import (
    OBSERVACION_CAMBIO_TRASLADO_MAPEO,
    OBSERVACION_SESION_SIN_OBSERVACIONES,
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
    _puede_gestionar_sesion_mapeo,
    _tiene_permiso_mapear,
    _validar_limite_intentos_salas,
)
from ._sesion import (
    _camas_mapeadas_sesion,
    _obtener_sesion_mapeo_activa,
    _obtener_servicios_ids_sesion,
    _registrar_detalle_mapeo,
    _registrar_historial_mapeo,
    _sincronizar_cama_en_ingreso_activo,
)


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

    if _es_rol_intentos_restringido(request.user):
        return JsonResponse(
            {"ok": False, "error": "Este rol no puede iniciar sesiones de mapeo."},
            status=403,
        )
    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    if sesion_activa:
        servicios_ids = _obtener_servicios_ids_sesion(sesion_activa)
        return JsonResponse(
            {
                "ok": True,
                "sesion_id": sesion_activa.id,
                "estado": sesion_activa.estado.codigo if sesion_activa.estado else None,
                "hora_inicio": timezone.localtime(sesion_activa.fecha_inicio).isoformat(),
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
    if not isinstance(servicio_ids, list):
        return JsonResponse({"ok": False, "error": "Debe indicar una lista valida de servicios."}, status=400)

    servicios_ids_normalizados = []
    for servicio_id in servicio_ids:
        try:
            servicios_ids_normalizados.append(int(servicio_id))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "La lista de servicios contiene valores invalidos."}, status=400)

    servicios_ids_normalizados = sorted(set(servicios_ids_normalizados))
    if not servicios_ids_normalizados:
        return JsonResponse({"ok": False, "error": "Debe seleccionar al menos un servicio para iniciar el mapeo."}, status=400)

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

    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado.codigo if sesion.estado else None,
            "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            "camas_mapeadas": [],
            "servicio_ids": servicios_validos_ids,
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
                "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            },
            "camas_mapeadas": _camas_mapeadas_sesion(sesion),
            "servicio_ids": _obtener_servicios_ids_sesion(sesion),
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
    total_camas_qs = Cama.objects.filter(
        sala__estado=1,
        sala__servicio__estado=1,
    )
    if servicios_ids_sesion:
        total_camas_qs = total_camas_qs.filter(sala__servicio_id__in=servicios_ids_sesion)
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
        faltantes_qs = (
            total_camas_qs.exclude(pk__in=camas_mapeadas_ids)
            .select_related("sala__servicio", "cubiculo__sala__servicio")
            .order_by("numero_cama")
        )
        for cama in faltantes_qs:
            cubiculo_obj = getattr(cama, "cubiculo", None)
            sala_real = getattr(cama, "sala", None)
            servicio_real = getattr(sala_real, "servicio", None) if sala_real else None
            camas_faltantes.append(
                {
                    "cama_id": cama.pk,
                    "numero_cama": str(cama.numero_cama),
                    "servicio": getattr(servicio_real, "nombre_servicio", "") or "SIN_SERVICIO",
                    "sala": getattr(sala_real, "nombre_sala", "") or "SIN_SALA",
                    "cubiculo": (
                        f"{cubiculo_obj.numero} - {cubiculo_obj.nombre_cubiculo}"
                        if cubiculo_obj
                        else "SIN_CUBICULO"
                    ),
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
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo finalizado correctamente.",
        }
    )


@login_required
@require_POST
def cancelar_mapeo(request):
    """Cancela la sesion activa de mapeo del usuario."""
    if not _puede_gestionar_sesion_mapeo(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    observacion_sesion = _normalizar_observacion_sesion(_obtener_observacion_desde_request(request))

    sesion.estado = get_estado_mapeo("CANCELADO", "ESTADO_SESION")
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
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo cancelado correctamente.",
        }
    )


# [2026-05-07] API: Procesar acción de mapeo en cama
# 2026-05-29 (Refactor B): la transaccion se delega en
# core.services.mapeo_camas_service.MapeoOperacionesMapaService.procesar_accion_mapeo
@login_required
@require_POST
def procesar_cama_mapeo(request):
    """
    Ciclo principal de mapeo por cama: evaluar -> decidir -> ejecutar -> registrar.
    """
    from django.core.exceptions import ValidationError as DjangoValidationError
    from core.services.mapeo_camas_service import MapeoOperacionesMapaService

    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    cama_id = request.POST.get("cama_id")
    accion = (request.POST.get("accion") or "").strip().upper()
    observacion = (request.POST.get("observacion") or "").strip()
    ingreso_observado_id = request.POST.get("ingreso_observado_id") or None
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar cama_id."}, status=400)

    acciones_validas = {
        "CONFIRMAR", "CONFIRMAR_ALTA", "CANCELAR_PREALTA",
        "CAMBIO_TRASLADO", "ASIGNACION", "ALTA_FORZADA",
    }
    if accion not in acciones_validas:
        return JsonResponse({"ok": False, "error": "Accion de mapeo no valida."}, status=400)

    if _es_rol_intentos_restringido(request.user):
        acciones_permitidas_rol = {"CONFIRMAR", "CAMBIO_TRASLADO", "CONFIRMAR_ALTA", "ALTA_FORZADA"}
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
    sala_real = cama.sala
    if servicios_ids_sesion and sala_real.servicio_id not in servicios_ids_sesion:
        return JsonResponse(
            {"ok": False, "error": "La cama seleccionada no pertenece a los servicios de esta sesion de mapeo."},
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
                estado__codigo__in=["OCUPADA", "PRE_ALTA"],
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

    if accion == "CAMBIO_TRASLADO":
        limite_error = _validar_limite_intentos_salas(request.user, [sala_real.id])
        if limite_error:
            return limite_error

    try:
        resultado = MapeoOperacionesMapaService.procesar_accion_mapeo(
            usuario=request.user,
            cama=cama,
            accion=accion,
            observacion=observacion,
            ingreso_observado=ingreso_observado,
            sesion=sesion,
        )
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    respuesta = {"ok": True, "mensaje": resultado["mensaje"]}
    if "estado_sistema" in resultado:
        respuesta["estado_sistema"] = resultado["estado_sistema"]
    return JsonResponse(respuesta)
