# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Vistas y APIs del mapa de camas: render principal, lectura del mapa,
buscadores y operaciones de edición (mover paciente, actualizar cama)."""

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from core.utils.utilidades_fechas import hora_local_iso
from core.constants.permisos import (
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
    MAPEO_CAMAS_MAPEAR_ROLES,
    MAPEO_CAMAS_MAPEAR_UNIDADES,
)
from core.mixins import UnidadRolRequiredMixin
from core.services.mapeo_camas_service import MapeoCamasService
from ingreso.models import Ingreso
from servicio.models import Cama, Cubiculo, Sala, Servicio

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    EstadoMapeo,
    HistorialEstadoCama,
    MapeoSesionCama,
    MapeoSesionServicio,
    MovimientoCama,
    get_observacion_mapeo,
)

from core.constants.mapeo_camas_constants import (
    OBSERVACION_CAMBIO_MANUAL_MAPA,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN,
)
from .constants.view_constants import (
    ESTADOS_CON_HISTORIAL_ALTA_VACIA,
    ESTADOS_EDICION_DIRECTA_ROL_RESTRINGIDO,
    ESTADOS_MANTIENEN_INGRESO_SIN_NUEVO,
    ESTADOS_OCUPADA_PREALTA,
)
from ._helpers import (
    _es_superadmin,
    _meta_ultima_actualizacion,
    _nombre_usuario,
    _paciente_payload,
    _resolver_ingreso_operativo,
    get_estado_mapeo,
)
from ._permisos import (
    _contar_cambios_manual_por_sala,
    _es_rol_intentos_restringido,
    _filtro_observaciones_movimiento_limite,
    _inicio_ventana_limite_sala,
    _max_cambios_para_usuario,
    _puede_editar_cama_en_mapa,
    _puede_gestionar_sesion_mapeo,
    _sala_real_id_desde_cama,
    _tiene_permiso_cambios_mapa,
    _tiene_permiso_historiales,
    _tiene_permiso_mapear,
    _validar_limite_intentos_salas,
)
from ._sesion import (
    _obtener_sesion_mapeo_activa,
    _obtener_servicios_ids_sesion,
    _registrar_detalle_mapeo,
    _registrar_historial_mapeo,
    _sincronizar_cama_en_ingreso_activo,
)
from .validators import (
    validar_cama_id,
    validar_ids_movimiento,
    validar_ingreso_requerido_para_ocupada,
    validar_transicion_vacia_a_prealta,
)


__all__ = [
    "_cama_payload",
    "_cubiculo_payload",
    "_sala_payload",
    "_servicio_payload",
    "MapeoCamasMapaView",
    "mapa_camas_data",
    "buscar_pacientes_mapa",
    "camas_disponibles_mapa",
    "mover_paciente_cama",
    "actualizar_cama_mapa",
]


# --- Helpers de serialización del mapa ---------------------------------------
# [2026-05-07] Helper para serializar datos de cama con asignación actual
def _cama_payload(cama, asig, cambios_realizados, max_cambios, meta_actualizacion):
    # [2026-05-25] Sin asignación/estado explícito, la cama se muestra VACIA.
    estado_codigo = asig.estado.codigo if (asig and asig.estado) else "VACIA"
    return {
        "numero_cama": cama.numero_cama,
        "estado_visual": estado_codigo,
        "asignacion_estado": estado_codigo,
        "paciente": _paciente_payload(asig.ingreso.paciente, ingreso_id=asig.ingreso_id) if (asig and asig.ingreso_id) else None,
        "cambios_realizados": cambios_realizados,
        "max_cambios": max_cambios,
        "ultima_actualizacion": meta_actualizacion.get("ultima_actualizacion", ""),
        "usuario_ultima_actualizacion": meta_actualizacion.get("usuario_ultima_actualizacion", ""),
    }


# [2026-05-07] Helper para serializar datos de cubículo
def _cubiculo_payload(cubiculo, camas_data):
    return {
        "id": cubiculo.id,
        "numero": cubiculo.numero,
        "nombre": cubiculo.nombre_cubiculo,
        "camas": camas_data,
    }


# [2026-05-07] Helper para serializar datos de sala
def _sala_payload(sala, cubiculos_data, camas_directas_data):
    return {
        "id": sala.id,
        "nombre": sala.nombre_sala,
        "nombre_corto": sala.nombre_corto_sala,
        "cubiculos": cubiculos_data,
        "camas_directas": camas_directas_data,
    }


# [2026-05-07] Helper para serializar datos de servicio
def _servicio_payload(servicio, salas_data, conflicto_mapeo=None):
    conflicto_mapeo = conflicto_mapeo or {}
    return {
        "id": servicio.id,
        "nombre": servicio.nombre_servicio,
        "nombre_corto": getattr(servicio, "nombre_corto", ""),
        "mapeo_bloqueado": bool(conflicto_mapeo.get("bloqueado", False)),
        "mapeo_usuario": conflicto_mapeo.get("usuario", ""),
        "mapeo_sesion_id": conflicto_mapeo.get("sesion_id"),
        "salas": salas_data,
    }


# =============================================================================
# MapeoCamasMapaView
# =============================================================================
# [2026-05-28] MC-PERM-001: el acceso al mapa es parte del flujo de mapeo.
class MapeoCamasMapaView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/mapa.html"
    required_roles = MAPEO_CAMAS_MAPEAR_ROLES
    required_unidades = MAPEO_CAMAS_MAPEAR_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        es_rol_intentos_restringido = _es_rol_intentos_restringido(self.request.user)
        context["titulo"] = "Mapa de Camas"
        context["subtitulo"] = "Asignacion por paciente y estado de cama"
        # [2026-05-26 FEATURE] Avisar de mapeos ajenos en progreso.
        sesiones_ajenas = list(
            MapeoSesionCama.objects.select_related("usuario")
            .prefetch_related(
                Prefetch(
                    "servicios_incluidos",
                    queryset=MapeoSesionServicio.objects.select_related("servicio").order_by("servicio__nombre_servicio"),
                )
            )
            .filter(
                estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
                fecha_fin__isnull=True,
            )
            .exclude(usuario=self.request.user)
            .order_by("-fecha_inicio")
        )
        context["sesiones_ajenas"] = [
            {
                "usuario": _nombre_usuario(sesion.usuario),
                "servicios": [
                    ss.servicio.nombre_servicio
                    for ss in sesion.servicios_incluidos.all()
                    if getattr(ss, "servicio", None)
                ],
            }
            for sesion in sesiones_ajenas
        ]
        context["puede_mapear"] = _puede_gestionar_sesion_mapeo(self.request.user)
        context["puede_hacer_cambios_mapa"] = _puede_editar_cama_en_mapa(self.request.user)
        context["puede_ver_historiales"] = _tiene_permiso_historiales(self.request.user)
        context["es_superusuario"] = bool(getattr(self.request.user, "is_superuser", False))
        context["es_rol_intentos_restringido"] = es_rol_intentos_restringido
        context["es_editor"] = context["puede_hacer_cambios_mapa"]
        return context


# =============================================================================
# mapa_camas_data
# =============================================================================
# [2026-05-28] MC-PERM-005: endpoint del flujo de mapeo, exige MAPEAR_*.
@login_required
@require_GET
def mapa_camas_data(request):
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion_activa)

    conflictos_servicio = {}
    sesiones_activas_servicio = (
        MapeoSesionServicio.objects.select_related("sesion_mapeo__usuario")
        .filter(
            sesion_mapeo__estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            sesion_mapeo__fecha_fin__isnull=True,
            servicio__estado=1,
        )
        .exclude(sesion_mapeo__usuario=request.user)
        .order_by("servicio_id", "-sesion_mapeo__fecha_inicio")
    )
    for sesion_servicio in sesiones_activas_servicio:
        if sesion_servicio.servicio_id in conflictos_servicio:
            continue
        conflictos_servicio[sesion_servicio.servicio_id] = {
            "bloqueado": True,
            "usuario": _nombre_usuario(sesion_servicio.sesion_mapeo.usuario),
            "sesion_id": sesion_servicio.sesion_mapeo_id,
        }

    # 2026-06-09: ORM pesado extraído a service reutilizable para adelgazar la vista.
    asignacion_por_cama = MapeoCamasService.obtener_ultimas_asignaciones_por_cama()
    historial_por_cama = MapeoCamasService.obtener_ultimos_historiales_por_cama()

    cambios_por_sala = {
        item["sala_real_id"]: item["total"]
        for item in HistorialEstadoCama.objects.filter(
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .filter(_filtro_observaciones_movimiento_limite())
        .annotate(sala_real_id=F("cama__sala_id"))
        .exclude(estado_anterior=F("estado_nuevo"))
        .values("sala_real_id")
        .annotate(total=Count("id"))
    }
    max_cambios_usuario = _max_cambios_para_usuario(request.user)

    camas_directas_qs = Cama.objects.filter(cubiculo__isnull=True).order_by("numero_cama")
    camas_cubiculo_qs = Cama.objects.order_by("numero_cama")

    cubiculos_qs = Cubiculo.objects.filter(estado=1).prefetch_related(
        Prefetch("camas", queryset=camas_cubiculo_qs)
    )

    salas_qs = (
        Sala.objects.filter(estado=1)
        .prefetch_related(
            Prefetch("cubiculos", queryset=cubiculos_qs),
            Prefetch("camas_sala", queryset=camas_directas_qs),
        )
        .order_by("nombre_sala")
    )

    servicios = Servicio.objects.filter(estado=1)
    if servicios_ids_sesion:
        servicios = servicios.filter(id__in=servicios_ids_sesion)
    servicios = servicios.prefetch_related(
        Prefetch("salas_servicio", queryset=salas_qs)
    ).order_by("nombre_servicio")

    data = []
    for servicio in servicios:
        salas_data = []
        for sala in servicio.salas_servicio.all():
            cubiculos_data = []
            for cubiculo in sala.cubiculos.all():
                camas_data = []
                for cama in cubiculo.camas.all():
                    if cama.sala_id != sala.id:
                        continue
                    asig = asignacion_por_cama.get(cama.numero_cama)
                    meta_actualizacion = _meta_ultima_actualizacion(historial_por_cama.get(cama.numero_cama))
                    camas_data.append(_cama_payload(
                        cama,
                        asig,
                        cambios_por_sala.get(sala.id, 0),
                        max_cambios_usuario,
                        meta_actualizacion
                    ))
                if camas_data:
                    cubiculos_data.append(_cubiculo_payload(cubiculo, camas_data))

            # [2026-05-22] Cubículos cruzados: camas de esta sala con cubículo de otra.
            cubiculos_cruzados = {}
            camas_cruzadas_qs = (
                Cama.objects.filter(sala_id=sala.id, cubiculo__isnull=False)
                .exclude(cubiculo__sala_id=sala.id)
                .select_related("cubiculo")
                .order_by("cubiculo__numero", "numero_cama")
            )
            for cama in camas_cruzadas_qs:
                cubiculo = cama.cubiculo
                if not cubiculo:
                    continue
                cubiculo_bucket = cubiculos_cruzados.setdefault(
                    cubiculo.pk,
                    {"cubiculo": cubiculo, "camas": []},
                )
                asig = asignacion_por_cama.get(cama.numero_cama)
                meta_actualizacion = _meta_ultima_actualizacion(historial_por_cama.get(cama.numero_cama))
                cubiculo_bucket["camas"].append(_cama_payload(
                    cama,
                    asig,
                    cambios_por_sala.get(sala.id, 0),
                    max_cambios_usuario,
                    meta_actualizacion
                ))

            for cubiculo_bucket in cubiculos_cruzados.values():
                cubiculos_data.append(_cubiculo_payload(
                    cubiculo_bucket["cubiculo"],
                    cubiculo_bucket["camas"],
                ))

            camas_directas_data = []
            for cama in sala.camas_sala.all():
                asig = asignacion_por_cama.get(cama.numero_cama)
                meta_actualizacion = _meta_ultima_actualizacion(historial_por_cama.get(cama.numero_cama))
                camas_directas_data.append(_cama_payload(
                    cama,
                    asig,
                    cambios_por_sala.get(sala.id, 0),
                    max_cambios_usuario,
                    meta_actualizacion
                ))
            if cubiculos_data or camas_directas_data:
                salas_data.append(_sala_payload(sala, cubiculos_data, camas_directas_data))
        if salas_data:
            data.append(_servicio_payload(servicio, salas_data, conflictos_servicio.get(servicio.id)))
    return JsonResponse({"servicios": data})


# =============================================================================
# buscar_pacientes_mapa
# =============================================================================
# [2026-05-28] MC-PERM-003: endpoint del flujo de mapeo expone PII; exige MAPEAR_*.
@login_required
@require_GET
def buscar_pacientes_mapa(request):
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    termino = (request.GET.get("q") or "").strip()
    tipo_busqueda = (request.GET.get("tipo") or "dni").strip().lower()
    resultados = MapeoCamasService.buscar_pacientes_para_mapa(termino=termino, tipo_busqueda=tipo_busqueda)
    return JsonResponse({"results": resultados})


# =============================================================================
# camas_disponibles_mapa
# =============================================================================
@login_required
@require_GET
def camas_disponibles_mapa(request):
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)
    excluir_cama = request.GET.get("excluir") or None
    servicio_restringido_id = None

    if _es_rol_intentos_restringido(request.user) and excluir_cama:
        try:
            cama_origen = Cama.objects.select_related("sala__servicio").get(numero_cama=excluir_cama)
            servicio_restringido_id = getattr(cama_origen.sala, "servicio_id", None)
        except Cama.DoesNotExist:
            servicio_restringido_id = None
    resultados = MapeoCamasService.obtener_camas_disponibles_para_mapa(
        excluir_cama=excluir_cama,
        servicio_restringido_id=servicio_restringido_id,
    )
    return JsonResponse({"results": resultados})


# =============================================================================
# 2026-05-29 (Refactor B): la lógica transaccional vive ahora en
# core.services.mapeo_camas_service.MapeoOperacionesMapaService.
# Esta view solo parsea el request, valida permisos/limites y arma el JSON.
# =============================================================================
@login_required
@require_POST
def mover_paciente_cama(request):
    from django.core.exceptions import ValidationError as DjangoValidationError
    from core.services.mapeo_camas_service import MapeoOperacionesMapaService

    if not _puede_editar_cama_en_mapa(request.user):
        return JsonResponse({"ok": False, "error": "Está en modo vista."}, status=403)

    cama_origen_id = request.POST.get("cama_origen_id")
    cama_destino_id = request.POST.get("cama_destino_id")
    # 2026-06-04: valida IDs de request con core.validators antes del flujo ORM/modelo.
    try:
        cama_origen_id, cama_destino_id = validar_ids_movimiento(cama_origen_id, cama_destino_id)
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    try:
        cama_origen = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_origen_id)
        cama_destino = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_destino_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Una de las camas indicadas no existe."}, status=404)

    if _es_rol_intentos_restringido(request.user):
        s_o = getattr(cama_origen.sala, "servicio_id", None)
        s_d = getattr(cama_destino.sala, "servicio_id", None)
        if s_o and s_d and s_o != s_d:
            return JsonResponse(
                {"ok": False, "error": "Este rol solo puede mover pacientes entre camas del mismo servicio."},
                status=403,
            )

    sala_origen_id = _sala_real_id_desde_cama(cama_origen)
    sala_destino_id = _sala_real_id_desde_cama(cama_destino)
    limite_error = _validar_limite_intentos_salas(request.user, [sala_origen_id, sala_destino_id])
    if limite_error:
        return limite_error

    try:
        # 2026-06-09: atomic defensivo en endpoint para asegurar escritura transaccional.
        with transaction.atomic():
            resultado = MapeoOperacionesMapaService.mover_paciente_entre_camas(
                usuario=request.user,
                cama_origen=cama_origen,
                cama_destino=cama_destino,
                sesion_mapeo=_obtener_sesion_mapeo_activa(request.user),
                es_superadmin=_es_superadmin(request.user),
            )
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    max_cambios_usuario = _max_cambios_para_usuario(request.user)
    ingreso_operativo = resultado["ingreso_operativo"]
    return JsonResponse({
        "ok": True,
        "mensaje": f"Paciente movido a la cama {cama_destino_id} correctamente.",
        "cama_origen": {
            "numero_cama": int(cama_origen_id),
            "estado_visual": resultado["estado_vacia"].codigo,
            "paciente": None,
            "cambios_realizados": _contar_cambios_manual_por_sala(resultado["sala_origen_id"]),
            "max_cambios": max_cambios_usuario,
            "ultima_actualizacion": hora_local_iso(resultado["historial_origen"].fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(resultado["historial_origen"].usuario),
        },
        "cama_destino": {
            "numero_cama": int(cama_destino_id),
            "estado_visual": resultado["estado_ocupada"].codigo,
            "paciente": _paciente_payload(ingreso_operativo.paciente, ingreso_id=ingreso_operativo.id),
            "cambios_realizados": _contar_cambios_manual_por_sala(resultado["sala_destino_id"]),
            "max_cambios": max_cambios_usuario,
            "ultima_actualizacion": hora_local_iso(resultado["historial_destino"].fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(resultado["historial_destino"].usuario),
        },
    })


# ===========================================================================
# 2026-05-29 (Refactor B): la transaccion se ejecuta en
# core.services.mapeo_camas_service.MapeoOperacionesMapaService.aplicar_actualizacion_manual_cama
# ===========================================================================
@login_required
@require_POST
def actualizar_cama_mapa(request):
    from django.core.exceptions import ValidationError as DjangoValidationError
    from core.services.mapeo_camas_service import MapeoOperacionesMapaService

    if not _puede_editar_cama_en_mapa(request.user):
        return JsonResponse({"ok": False, "error": "Está en modo vista."}, status=403)

    cama_id = request.POST.get("cama_id")
    estado_codigo = (request.POST.get("estado") or "").strip()
    ingreso_id = request.POST.get("ingreso_id") or None

    # 2026-06-04: valida entrada de request con core.validators antes de validaciones de modelo.
    try:
        cama_id = validar_cama_id(cama_id)
        validar_ingreso_requerido_para_ocupada(estado_codigo, ingreso_id)
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        if "cama_id" in msg:
            return JsonResponse({"ok": False, "error": "Debe indicar la cama."}, status=400)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    try:
        estado_nuevo_obj = EstadoMapeo.objects.get(codigo=estado_codigo, categoria="ESTADO_CAMA")
    except EstadoMapeo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Estado de cama no válido."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    asignacion = (
        AsignacionCamaPaciente.objects.select_related("ingreso", "estado")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )
    if not asignacion:
        estado_vacia_obj = EstadoMapeo.objects.get(codigo="VACIA", categoria="ESTADO_CAMA")
        # 2026-06-01: asegura atomic en creación inicial de asignación operativa.
        with transaction.atomic():
            asignacion = AsignacionCamaPaciente.objects.create(
                cama=cama, usuario_asignacion=request.user, estado=estado_vacia_obj, ingreso=None,
            )

    ingreso_nuevo = None
    if estado_codigo == "OCUPADA":
        ingreso_nuevo = _resolver_ingreso_operativo(ingreso_id=ingreso_id)
        if not ingreso_nuevo:
            return JsonResponse({"ok": False, "error": "El ingreso seleccionado no existe."}, status=404)

    if _es_rol_intentos_restringido(request.user):
        if estado_codigo not in ESTADOS_EDICION_DIRECTA_ROL_RESTRINGIDO:
            return JsonResponse(
                {"ok": False, "error": "Este rol solo puede hacer pre-altas o pasar la cama a vacia desde edicion directa."},
                status=403,
            )

    asig_previa_paciente = None
    if ingreso_nuevo and estado_codigo == "OCUPADA":
        asig_previa_paciente = (
            AsignacionCamaPaciente.objects
            .select_related("estado", "cama")
            .filter(
                ingreso=ingreso_nuevo,
                estado__codigo__in=ESTADOS_OCUPADA_PREALTA,
                estado__categoria="ESTADO_CAMA",
            )
            .exclude(cama_id=cama_id)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    if _es_rol_intentos_restringido(request.user) and asig_previa_paciente:
        return JsonResponse(
            {"ok": False, "error": "Este rol no puede reasignar pacientes desde la edicion directa. Debe usar movimiento de cama."},
            status=403,
        )

    if estado_codigo == "OCUPADA" and not ingreso_nuevo:
        return JsonResponse(
            {"ok": False, "error": "Para estado OCUPADA debe seleccionar un ingreso activo válido."}, status=400,
        )

    estado_anterior = asignacion.estado
    ingreso_anterior = asignacion.ingreso

    # 2026-06-04: valida transición de estado antes del flujo de persistencia.
    try:
        validar_transicion_vacia_a_prealta(
            estado_anterior.codigo if estado_anterior else None,
            estado_codigo,
        )
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)

    requiere_cierre_prealta = (
        estado_anterior and estado_anterior.codigo == "PRE_ALTA"
        and estado_codigo == "OCUPADA"
        and ingreso_anterior
        and (not ingreso_nuevo or ingreso_anterior.id != ingreso_nuevo.id)
    )
    requiere_cierre_ocupada_a_ocupada = (
        estado_anterior and estado_anterior.codigo == "OCUPADA"
        and estado_codigo == "OCUPADA"
        and ingreso_anterior and ingreso_nuevo
        and ingreso_anterior.id != ingreso_nuevo.id
    )
    requiere_registro_alta_a_vacia = (
        estado_codigo == "VACIA"
        and ingreso_anterior is not None
        and estado_anterior is not None
        and estado_anterior.codigo in ESTADOS_CON_HISTORIAL_ALTA_VACIA
    )

    if estado_codigo == "VACIA":
        ingreso_nuevo = None
    elif estado_codigo in ESTADOS_MANTIENEN_INGRESO_SIN_NUEVO and ingreso_nuevo is None:
        ingreso_nuevo = ingreso_anterior

    hubo_cambio = (
        estado_anterior.id != estado_nuevo_obj.id
        or (ingreso_anterior.id if ingreso_anterior else None) != (ingreso_nuevo.id if ingreso_nuevo else None)
    )
    cambios_realizados = _contar_cambios_manual_por_sala(_sala_real_id_desde_cama(cama))
    max_cambios_usuario = _max_cambios_para_usuario(request.user)

    if not hubo_cambio:
        _registrar_detalle_mapeo(
            usuario=request.user, cama=cama, asignacion=asignacion,
            tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION, hubo_cambio=False,
            observacion=get_observacion_mapeo("Confirmacion sin cambios desde mapa."),
        )
        return JsonResponse({
            "ok": True,
            "mensaje": "No se detectaron cambios para guardar.",
            "cama": {
                "numero_cama": int(cama_id),
                "estado_visual": asignacion.estado.codigo,
                "paciente": _paciente_payload(
                    asignacion.ingreso.paciente if asignacion.ingreso_id else None,
                    ingreso_id=asignacion.ingreso_id,
                ),
                "cambios_realizados": cambios_realizados,
                "max_cambios": max_cambios_usuario,
            },
        })

    try:
        # 2026-06-09: atomic defensivo en endpoint para asegurar escritura transaccional.
        with transaction.atomic():
            resultado = MapeoOperacionesMapaService.aplicar_actualizacion_manual_cama(
                usuario=request.user,
                cama=cama,
                estado_codigo=estado_codigo,
                estado_nuevo_obj=estado_nuevo_obj,
                ingreso_nuevo=ingreso_nuevo,
                sesion_mapeo=_obtener_sesion_mapeo_activa(request.user),
                asig_previa_paciente=asig_previa_paciente,
                asignacion=asignacion,
                estado_anterior=estado_anterior,
                ingreso_anterior=ingreso_anterior,
                requiere_cierre_prealta=bool(requiere_cierre_prealta),
                requiere_cierre_ocupada_a_ocupada=bool(requiere_cierre_ocupada_a_ocupada),
                requiere_registro_alta_a_vacia=bool(requiere_registro_alta_a_vacia),
            )
    except DjangoValidationError as exc:
        msg = exc.message if hasattr(exc, "message") else "; ".join(exc.messages)
        return JsonResponse({"ok": False, "error": msg}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    asignacion = resultado["asignacion"]
    historial = resultado["historial"]

    _registrar_detalle_mapeo(
        usuario=request.user, cama=cama, asignacion=asignacion,
        tipo_accion=(
            DetalleMapeoCama.TipoAccion.ALTA
            if estado_codigo == "ALTA" or requiere_registro_alta_a_vacia
            else DetalleMapeoCama.TipoAccion.CAMBIO
        ),
        hubo_cambio=True,
        observacion=get_observacion_mapeo("Actualización de cama desde mapa."),
    )

    cambios_realizados = _contar_cambios_manual_por_sala(_sala_real_id_desde_cama(cama))
    return JsonResponse({
        "ok": True,
        "mensaje": "Cambio de cama actualizado correctamente.",
        "cama": {
            "numero_cama": int(cama_id),
            "estado_visual": asignacion.estado.codigo,
            "paciente": _paciente_payload(
                asignacion.ingreso.paciente if asignacion.ingreso_id else None,
                ingreso_id=asignacion.ingreso_id,
            ),
            "cambios_realizados": cambios_realizados,
            "max_cambios": max_cambios_usuario,
            "ultima_actualizacion": hora_local_iso(historial.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
        },
    })
