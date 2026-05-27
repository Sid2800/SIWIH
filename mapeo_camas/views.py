from datetime import datetime, timedelta
import json 
from functools import lru_cache

from django.contrib.auth.decorators import login_required
from usuario.permisos import verificar_permisos_usuario
from core.constants.permisos import (
    MAPEO_CAMAS_INTENTOS_CAMBIO_ROLES as MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
    MAPEO_CAMAS_INTENTOS_CAMBIO_UNIDADES as MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    MAPEO_CAMAS_CAMBIOS_ROLES,
    MAPEO_CAMAS_CAMBIOS_UNIDADES,
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
    MAPEO_CAMAS_MAPEAR_ROLES,
    MAPEO_CAMAS_MAPEAR_UNIDADES,
    
)
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from ingreso.models import Ingreso
from core.mixins import UnidadRolRequiredMixin
from usuario.models import PerfilUnidad, AlcanceUsuario


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
from paciente.models import Paciente
from servicio.models import Cama, Cubiculo, Sala, Servicio


# =============================================================================
# Constantes de configuración operativa
# -----------------------------------------------------------------------------
# MAX_CAMBIOS_CAMA: número máximo de movimientos permitidos por sala dentro
# de la ventana temporal, para usuarios que no son superadmin.
# VENTANA_LIMITE_CAMBIOS_SALA_HORAS: tamaño de la ventana de tiempo (horas)
# que se usa para contabilizar los cambios manuales y resetear el conteo.
# Las constantes OBSERVACION_* son los textos fijos grabados en el historial,
# usados también como criterio de filtrado al contar cambios por sala.
# =============================================================================
MAX_CAMBIOS_CAMA = 5
# Parametro de ventana para reinicio del limite por sala (horas)
VENTANA_LIMITE_CAMBIOS_SALA_HORAS = 24
# Ventana para considerar altas recientes en el buscador de pacientes del mapa.
VENTANA_ALTAS_RECIENTES_HORAS = 24
OBSERVACION_CAMBIO_MANUAL_MAPA = "Cambio manual desde mapa"
OBSERVACION_CAMBIO_MANUAL_MAPA_DETALLE = "Cambio manual desde mapa (detalle)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA = "Movimiento de paciente entre camas (mapa)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE = "Movimiento de paciente entre camas (mapa detalle)"
OBSERVACION_CAMBIO_TRASLADO_MAPEO = "Cambio/traslado desde mapeo"
# Observacion para traslados de superadmin: queda registrado pero NO cuenta
# en _contar_cambios_manual_por_sala, por lo que no descuenta del límite.
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN = "Movimiento de paciente entre camas (superadmin)"
OBSERVACION_SESION_SIN_OBSERVACIONES = "Sin observaciones"
DETALLE_PAGE_SIZE_DEFAULT = 50
DETALLE_PAGE_SIZE_MAX = 200


# --- Helpers de serialización robustos para el mapa de camas ---
# [2026-05-07] Helper para serializar datos de cama con asignación actual
def _cama_payload(cama, asig, cambios_realizados, max_cambios, meta_actualizacion):
    # [2026-05-25] Regla operativa: si no hay asignacion/estado explicito,
    # la cama se muestra con estado primario VACIA.
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

# Helper global para obtener instancias de EstadoMapeo
@lru_cache(maxsize=64)
# [2026-05-07] Helper para obtener instancia de EstadoMapeo por código y categoría
def get_estado_mapeo(codigo, categoria):
    return EstadoMapeo.objects.get(codigo=codigo, categoria=categoria)
# =============================================================================
# [2026-05-07] API: Sincronizar camas con ingresos activos
# [2026-05-25] Restringida nuevamente solo a superusuario.
# =============================================================================
@login_required
def sincronizar_camas_superadmin(request):
    """
    Sincroniza AsignacionCamaPaciente para todos los ingresos activos con cama asignada.
    Solo accesible para superusuario.
    """
    # [2026-05-25] Seguridad: sincronización masiva inicial permitida solo a superusuario.
    if not getattr(request.user, "is_superuser", False):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Solo se permite POST."}, status=405)

    # Obtener el ÚLTIMO ingreso activo POR CAMA (más reciente para cada cama)
    from django.db.models import Max
    
    camas_ultimos_ingresos = (
        Ingreso.objects.filter(
            estado=1,
            fecha_egreso__isnull=True,
            cama_id__isnull=False,
            paciente_id__isnull=False,
        )
        .values("cama_id")
        .annotate(ingreso_id=Max("id"))
        .values_list("ingreso_id", flat=True)
    )
    
    ingresos = Ingreso.objects.filter(pk__in=camas_ultimos_ingresos).values(
        "id", "cama_id"
    )

    # [2026-05-25] Conjunto de camas con ingreso activo (ocupadas reales).
    camas_con_ingreso_activo = set(ingresos.values_list("cama_id", flat=True))

    from mapeo_camas.models import AsignacionCamaPaciente
    # [2026-05-25] Saneamiento previo: normaliza registros sin estado válido
    # para evitar que el flujo de ingreso falle por asignaciones huérfanas.
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_valido_subquery = EstadoMapeo.objects.filter(
        pk=OuterRef("estado_id"),
        categoria="ESTADO_CAMA",
    )
    asignaciones_reparadas = (
        AsignacionCamaPaciente.objects
        .annotate(estado_valido=Exists(estado_valido_subquery))
        .filter(Q(estado_id__isnull=True) | Q(estado_valido=False))
            .update(estado_id=estado_vacia.pk, ingreso_id=None)
    )

    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    asignaciones_actuales_qs = (
        AsignacionCamaPaciente.objects
        .select_related("estado")
        .order_by("cama_id", "-fecha_inicio", "-id")
    )
    ultima_asignacion_por_cama = {}
    for asig in asignaciones_actuales_qs:
        if asig.cama_id not in ultima_asignacion_por_cama:
            ultima_asignacion_por_cama[asig.cama_id] = asig

    sincronizados = 0
    omitidos = 0
    errores = 0
    errores_detalle = []

    for ingreso in ingresos:
        cama_id = ingreso["cama_id"]
        ingreso_id = ingreso["id"]
        asig_actual = ultima_asignacion_por_cama.get(cama_id)

        if (
            asig_actual
            and asig_actual.estado
            and asig_actual.estado.codigo == "OCUPADA"
            and asig_actual.ingreso_id == ingreso_id
        ):
            omitidos += 1
            continue

        try:
            # [2026-05-26 AUDIT] Sincronización ingreso-only sin dependencia del servicio legado por paciente_id.
            with transaction.atomic():
                asig_bloqueada = (
                    AsignacionCamaPaciente.objects
                    .select_for_update()
                    .filter(cama_id=cama_id)
                    .order_by("-fecha_inicio", "-id")
                    .first()
                )
                if (
                    asig_bloqueada
                    and asig_bloqueada.estado
                    and asig_bloqueada.estado.codigo == "OCUPADA"
                    and asig_bloqueada.ingreso_id == ingreso_id
                ):
                    omitidos += 1
                    ultima_asignacion_por_cama[cama_id] = asig_bloqueada
                    continue

                estado_anterior = asig_bloqueada.estado if asig_bloqueada else estado_vacia

                if asig_bloqueada:
                    asig_bloqueada.estado = estado_ocupada
                    asig_bloqueada.ingreso_id = ingreso_id
                    asig_bloqueada.usuario_asignacion = request.user
                    asig_bloqueada.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
                    asig_sync = asig_bloqueada
                else:
                    asig_sync = AsignacionCamaPaciente.objects.create(
                        cama_id=cama_id,
                        estado=estado_ocupada,
                        ingreso_id=ingreso_id,
                        usuario_asignacion=request.user,
                    )

                HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_ocupada,
                    ingreso_id=ingreso_id,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Ingreso (sync masivo)"),
                )

                ultima_asignacion_por_cama[cama_id] = asig_sync

            sincronizados += 1
        except Exception as exc:
            errores += 1
            errores_detalle.append(f"Ingreso #{ingreso_id} — cama #{cama_id}: {exc}")

    # [2026-05-25] Registrar también camas desocupadas en VACIA.
    # Si una cama activa no tiene ingreso activo, debe quedar persistida como VACIA.
    camas_activas_ids = set(Cama.objects.filter(estado=1).values_list("pk", flat=True))
    camas_desocupadas_ids = camas_activas_ids - camas_con_ingreso_activo
    vacias_creadas = 0
    vacias_actualizadas = 0
    if camas_desocupadas_ids:
        asignaciones_desocupadas = (
            AsignacionCamaPaciente.objects
            .select_related("estado")
            .filter(cama_id__in=camas_desocupadas_ids)
            .order_by("cama_id", "-fecha_inicio", "-id")
        )
        ultima_asignacion_por_cama = {}
        for asig in asignaciones_desocupadas:
            if asig.cama_id not in ultima_asignacion_por_cama:
                ultima_asignacion_por_cama[asig.cama_id] = asig

        camas_para_crear = []
        asignaciones_para_actualizar = []
        for cama_id in camas_desocupadas_ids:
            asig = ultima_asignacion_por_cama.get(cama_id)
            if not asig:
                camas_para_crear.append(cama_id)
                continue
            estado_codigo = getattr(asig.estado, "codigo", None)
            if estado_codigo == "VACIA" and asig.ingreso_id is None:
                continue
            if estado_codigo == "OCUPADA" or asig.ingreso_id is not None or estado_codigo is None:
                asig.estado = estado_vacia
                asig.ingreso = None
                asig.usuario_asignacion = request.user
                asignaciones_para_actualizar.append(asig)

        if camas_para_crear:
            AsignacionCamaPaciente.objects.bulk_create([
                AsignacionCamaPaciente(
                    cama_id=cama_id,
                    estado=estado_vacia,
                    ingreso=None,
                    usuario_asignacion=request.user,
                )
                for cama_id in camas_para_crear
            ])
            vacias_creadas = len(camas_para_crear)

        for asig in asignaciones_para_actualizar:
            asig.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
        vacias_actualizadas = len(asignaciones_para_actualizar)

    return JsonResponse({
        "ok": True,
        "asignaciones_reparadas": asignaciones_reparadas,
        "vacias_creadas": vacias_creadas,
        "vacias_actualizadas": vacias_actualizadas,
        "sincronizados": sincronizados,
        "omitidos": omitidos,
        "errores": errores,
        "errores_detalle": errores_detalle,
        "mensaje": (
            f"Sincronizacion finalizada. {asignaciones_reparadas} reparadas a VACIA, "
            f"{vacias_creadas} vacias creadas, {vacias_actualizadas} vacias actualizadas, "
            f"{sincronizados} sincronizados, {omitidos} omitidos, {errores} errores."
        )
    })

# =============================================================================
# MapeoCamasMapaView
# -----------------------------------------------------------------------------
# Vista de tipo TemplateView que únicamente renderiza el HTML base del mapa.
# No lleva datos de camas en el contexto: la estructura completa se obtiene
# después vía la API mapa_camas_data (llamada desde JavaScript al cargar la página).
# =============================================================================
# [2026-05-07] Vista: Página principal del mapa de camas con sesión de mapeo
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales

# [2026-05-19] El acceso a la vista del mapa es de visualización (HISTORIALES);
# la edición directa se controla aparte con MAPEO_CAMAS_CAMBIOS_*.
class MapeoCamasMapaView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/mapa.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        es_rol_intentos_restringido = _es_rol_intentos_restringido(self.request.user)
        context["titulo"] = "Mapa de Camas"
        context["subtitulo"] = "Asignacion por paciente y estado de cama"
        # [2026-05-26 FEATURE] Mostrar TODOS los mapeos ajenos en progreso
        # (usuario + servicios) en el aviso superior del mapa.
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
        # [2026-05-18] Permiso para flujo de mapeo (iniciar/finalizar/cancelar mapeo).
        context["puede_mapear"] = _puede_gestionar_sesion_mapeo(self.request.user)
        # [2026-05-18] Permiso para cambios manuales directos en el mapa.
        context["puede_hacer_cambios_mapa"] = _tiene_permiso_cambios_mapa(self.request.user)
        context["puede_ver_historiales"] = _tiene_permiso_historiales(self.request.user)
        # [2026-05-25] Control de UI: acciones de sincronización masiva visibles solo para superusuario.
        context["es_superusuario"] = bool(getattr(self.request.user, "is_superuser", False))
        context["es_rol_intentos_restringido"] = es_rol_intentos_restringido
        # Compatibilidad con template/JS existente.
        # es_editor controla MAPA_SOLO_LECTURA en frontend; debe responder al permiso de cambios,
        # no al permiso de iniciar/finalizar mapeo.
        context["es_editor"] = context["puede_hacer_cambios_mapa"]
        return context


# [2026-05-07] Vista: Página de historiales con permiso restringido por rol/unidad
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales
class MapeoCamasHistorialView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Historiales de Camas"
        context["subtitulo"] = "Consulta de historial, movimientos y mapeos"
        return context


# [2026-05-07] Vista: Página de detalle de historiales con permiso restringido
# [2026-05-11] Permisos manejados localmente en mapeo_camas para no afectar mixins globales
class MapeoCamasHistorialDetalleView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales_detalle.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Detalle de Historial"
        context["subtitulo"] = "Cards de detalle por registro"
        return context


@login_required
@require_GET
def debug_permisos_mapa(request):
    """Diagnostico en vivo de permisos para la vista principal del mapa."""
    usuario = request.user
    perfiles = list(
        PerfilUnidad.objects.filter(usuario=usuario)
        .select_related("servicio_unidad")
        .values(
            "rol",
            "alcance",
            "servicio_unidad__nombre_corto_unidad",
            "servicio_unidad__nombre_unidad",
        )
    )

    match_global_vista = PerfilUnidad.objects.filter(
        usuario=usuario,
        rol__in=MAPEO_CAMAS_HISTORIALES_ROLES,
        alcance=AlcanceUsuario.GLOBAL,
    ).exists()

    match_unidad_vista = PerfilUnidad.objects.filter(
        usuario=usuario,
        rol__in=MAPEO_CAMAS_HISTORIALES_ROLES,
        alcance=AlcanceUsuario.UNIDAD,
        servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_HISTORIALES_UNIDADES,
    ).exists()

    return JsonResponse(
        {
            "ok": True,
            "usuario": {
                "id": usuario.id,
                "username": usuario.username,
                "is_authenticated": usuario.is_authenticated,
                "is_active": usuario.is_active,
                "is_superuser": usuario.is_superuser,
            },
            "requerido_vista_mapa": {
                "roles": MAPEO_CAMAS_HISTORIALES_ROLES,
                "unidades": MAPEO_CAMAS_HISTORIALES_UNIDADES,
            },
            "requerido_flujo_mapeo": {
                "roles": MAPEO_CAMAS_MAPEAR_ROLES,
                "unidades": MAPEO_CAMAS_MAPEAR_UNIDADES,
            },
            "requerido_cambios_mapa": {
                "roles": MAPEO_CAMAS_CAMBIOS_ROLES,
                "unidades": MAPEO_CAMAS_CAMBIOS_UNIDADES,
            },
            "perfiles": perfiles,
            "evaluacion": {
                "puede_ver_mapa": _tiene_permiso_historiales(usuario),
                "puede_mapear": _tiene_permiso_mapear(usuario),
                "puede_gestionar_sesion_mapeo": _puede_gestionar_sesion_mapeo(usuario),
                "puede_hacer_cambios_mapa": _tiene_permiso_cambios_mapa(usuario),
                "es_rol_intentos_restringido": _es_rol_intentos_restringido(usuario),
                "mixin_vista_global": match_global_vista,
                "mixin_vista_unidad": match_unidad_vista,
                "mixin_vista_resultado": bool(usuario.is_superuser or match_global_vista or match_unidad_vista),
            },
        }
    )


# --- Helpers privados --------------------------------------------------------

# [2026-05-07] Helper para obtener nombre completo de paciente
def _nombre_paciente(paciente):
    """Construye el nombre completo del paciente concatenando los cuatro campos.
    Retorna 'Sin nombre' si todos están vacíos."""
    partes = [
        getattr(paciente, "primer_nombre", ""),
        getattr(paciente, "segundo_nombre", ""),
        getattr(paciente, "primer_apellido", ""),
        getattr(paciente, "segundo_apellido", ""),
    ]
    nombre = " ".join([p for p in partes if p]).strip()
    return nombre or "Sin nombre"


# [2026-05-07] Helper para obtener nombre completo de usuario
def _nombre_usuario(usuario):
    """Retorna nombre visible del usuario; usa username como fallback."""
    if not usuario:
        return ""
    nombre = ""
    if hasattr(usuario, "get_full_name"):
        nombre = (usuario.get_full_name() or "").strip()
    return nombre or getattr(usuario, "username", "") or ""


# [2026-05-07] Helper para convertir datetime a ISO local
def _hora_local_iso(dt):
    """Convierte datetime a ISO local para consumo del frontend."""
    if not dt:
        return ""
    return timezone.localtime(dt).isoformat()


# [2026-05-07] Helper para serializar datos de paciente en historiales
def _paciente_payload(paciente, ingreso_id=None):
    """Serializa los datos mínimos del paciente para el JSON del mapa.
    Retorna None si no hay paciente (cama vacía)."""
    if not paciente:
        return None
    ingreso_serializado = ingreso_id if ingreso_id is not None else getattr(paciente, "ingreso_activo_id", None)
    return {
        "id": paciente.id,
        "nombre": _nombre_paciente(paciente),
        "dni": getattr(paciente, "dni", None) or "",
        "ingreso_id": ingreso_serializado,
    }


def _resolver_ingreso_operativo(*, ingreso_id=None):
    """
    [2026-05-26 REFACTOR FINAL] Requiere ingreso_id explícitamente; no hay fallback a paciente.
    Levanta error HTTP 400 si falta ingreso_id, ya que es dato operativo obligatorio.
    """
    if not ingreso_id:
        raise ValueError(
            "El ingreso_id es obligatorio para operaciones en mapeo_camas. "
            "Paciente_id ya no es válido como pivote operativo."
        )
    return (
        Ingreso.objects.filter(pk=ingreso_id)
        .select_related("paciente")
        .first()
    )


def _observacion_codigo(observacion):
    """Retorna el texto visible de una observacion catalogada."""
    if not observacion:
        return ""
    return getattr(observacion, "codigo", "") or str(observacion)


def _normalizar_observacion_sesion(observacion):
    """[2026-05-26 AUDIT] Normaliza observación libre y retorna None cuando viene vacía."""
    texto = (observacion or "").strip()
    return texto or None


def _obtener_observacion_desde_request(request):
    """[2026-05-26 FIX] Extrae observación desde JSON o POST para flujos mixtos."""
    observacion = request.POST.get("observacion")
    if observacion is not None:
        return observacion

    try:
        payload = json.loads((request.body or b"").decode("utf-8") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    return payload.get("observacion")


# [2026-05-07] Helper para verificar si usuario es superadmin
def _es_superadmin(usuario):
    """Indica si el usuario es superadmin, lo que exime del límite de cambios."""
    return bool(usuario and usuario.is_superuser)


# [2026-05-19] Helpers de permisos para mantener una sola fuente de verdad.
def _tiene_permiso_historiales(usuario):
    """Permite acceso de solo visualización al mapa e historiales."""
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_HISTORIALES_ROLES,
        MAPEO_CAMAS_HISTORIALES_UNIDADES,
    )


def _tiene_permiso_cambios_mapa(usuario):
    """Permite cambios manuales de estado/movimiento en camas."""
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_CAMBIOS_ROLES,
        MAPEO_CAMAS_CAMBIOS_UNIDADES,
    )


def _tiene_permiso_mapear(usuario):
    """Permite iniciar/finalizar/cancelar sesiones de mapeo."""
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_MAPEAR_ROLES,
        MAPEO_CAMAS_MAPEAR_UNIDADES,
    )


def _puede_gestionar_sesion_mapeo(usuario):
    """Permite administrar sesión de mapeo si tiene permiso y no cae en rol restringido."""
    return _tiene_permiso_mapear(usuario) and (not _es_rol_intentos_restringido(usuario))


# [2026-05-07] Helper para calcular inicio de ventana de límite de movimientos
def _inicio_ventana_limite_sala():
    """Calcula el datetime de inicio de la ventana temporal para el conteo de cambios."""
    return timezone.now() - timedelta(hours=VENTANA_LIMITE_CAMBIOS_SALA_HORAS)


def _filtro_observaciones_movimiento_limite():
    """Filtro común para contar movimientos que consumen límite por sala.
    Los movimientos de superadmin quedan fuera porque usan otra observación."""
    return Q(observacion__codigo__in=[
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
        OBSERVACION_CAMBIO_TRASLADO_MAPEO,
    ])


# [2026-05-07] Helper para contar movimientos manuales recientes por sala
def _contar_cambios_manual_por_sala(sala_id):
    """Cuenta cuántos movimientos de paciente se han registrado en la sala
    dentro de la ventana temporal activa. Se usa para aplicar el límite
    MAX_CAMBIOS_CAMA a usuarios con permiso limitado por intentos."""
    if not sala_id:
        return 0

    return (
        HistorialEstadoCama.objects.annotate(
            # [2026-05-22] Usar siempre cama.sala; el cubículo es solo ubicación física.
            sala_real_id=F("cama__sala_id")
        )
        .filter(
            sala_real_id=sala_id,
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .filter(_filtro_observaciones_movimiento_limite())
        .exclude(estado_anterior=F("estado_nuevo"))
        .count()
    )


def _sala_real_id_desde_cama(cama):
    # [2026-05-22] Regla de negocio: la sala/servicio de la cama es siempre cama.sala.
    # El cubículo solo determina ubicación física, no propiedad operativa.
    """Retorna la sala a la que pertenece la cama (siempre cama.sala)."""
    if not cama:
        return None
    return getattr(cama, "sala_id", None)


# [2026-05-18] Helper para decidir si aplica límite de intentos al usuario
def _aplica_limite_intentos(usuario):
    """Retorna True cuando al usuario se le debe aplicar el límite de cambios por sala."""
    # [2026-05-19] Regla clave:
    # - Superadmin nunca entra al rol limitado, aunque cumpla validaciones de perfiles.
    # - El límite solo aplica a usuarios definidos en MAPEO_CAMAS_INTENTOS_CAMBIO_*.
    if not usuario or getattr(usuario, "is_superuser", False):
        return False
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
        MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    )


def _max_cambios_para_usuario(usuario):
    """Retorna el máximo de cambios permitido para el usuario o None si no aplica límite."""
    return MAX_CAMBIOS_CAMA if _aplica_limite_intentos(usuario) else None


def _es_rol_intentos_restringido(usuario):
    # [2026-05-19] Alias semántico para agrupar todas las restricciones funcionales
    # del rol MAPEO_CAMAS_INTENTOS_CAMBIO_ROLES en un único punto de lectura.
    """Identifica al rol que solo puede mover pacientes y manejar pre-altas/altas."""
    return _aplica_limite_intentos(usuario)


def _validar_limite_intentos_salas(usuario, sala_ids):
    """Valida el límite operativo por sala para usuarios con permiso limitado."""
    if not _aplica_limite_intentos(usuario):
        return None

    salas_validas = [sala_id for sala_id in set(sala_ids or []) if sala_id]
    for sala_id in salas_validas:
        cambios_realizados = _contar_cambios_manual_por_sala(sala_id)
        if cambios_realizados >= MAX_CAMBIOS_CAMA:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        f"La sala ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                        f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                    ),
                    "cambios_realizados": cambios_realizados,
                    "max_cambios": MAX_CAMBIOS_CAMA,
                },
                status=400,
            )

    return None


# [2026-05-07] Helper para obtener sesión de mapeo activa del usuario
def _obtener_sesion_mapeo_activa(usuario):
    """Retorna la sesion EN_PROGRESO activa mas reciente del usuario."""
    return (
        MapeoSesionCama.objects.filter(
            usuario=usuario,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )


# [2026-05-07] Helper para obtener IDs de servicios en sesión de mapeo
def _obtener_servicios_ids_sesion(sesion):
    """Retorna los ids de servicio incluidos en la sesion de mapeo."""
    if not sesion:
        return []
    return list(
        sesion.servicios_incluidos.order_by("servicio_id").values_list("servicio_id", flat=True)
    )


# [2026-05-07] Helper para registrar detalle de mapeo (auditoría)
def _registrar_detalle_mapeo(
    *,
    usuario,
    cama,
    asignacion,
    tipo_accion,
    hubo_cambio,
    observacion="",
    fue_validada=True,
    sesion_mapeo=None,
):
    """Guarda el detalle por cama en tiempo real dentro de la sesion activa."""
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    if not sesion:
        return None

    # [2026-05-04 AUDIT] Bug Fix: Convertir string de tipo_accion a objeto FK EstadoMapeo.
    # tipo_accion puede ser un string (codigo) o un objeto EstadoMapeo.
    # codigo es unique en la tabla, por lo que no se necesita filtrar por categoria.
    if isinstance(tipo_accion, str):
        tipo_accion = EstadoMapeo.objects.get(codigo=tipo_accion)

    observacion_catalogada = get_observacion_mapeo(observacion)

    # [2026-05-21] Si la misma cama vuelve a pasar por la misma sesion,
    # se conserva un solo registro y se actualiza su ultimo estado.
    detalle, _ = DetalleMapeoCama.objects.update_or_create(
        sesion_mapeo=sesion,
        cama=cama,
        defaults={
            "fue_validada": fue_validada,
            "hubo_cambio": hubo_cambio,
            "estado_actual": asignacion.estado if asignacion else None,
            "ingreso_actual": asignacion.ingreso if asignacion else None,
            "tipo_accion": tipo_accion,
            "usuario": usuario,
            "observacion": observacion_catalogada,
            "fecha_hora": timezone.now(),
        },
    )
    return detalle


def _registrar_historial_mapeo(
    *,
    cama,
    estado_anterior,
    estado_nuevo,
    ingreso,
    usuario,
    observacion,
    sesion_mapeo=None,
):
    """Registra historial de cama; en mapeo activo actualiza el último registro de la sesión."""
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    observacion_catalogada = get_observacion_mapeo(observacion)

    if not sesion:
        return HistorialEstadoCama.objects.create(
            cama=cama,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            ingreso=ingreso,
            usuario=usuario,
            observacion=observacion_catalogada,
        )

    # [2026-05-21] Durante la sesión de mapeo se conserva un solo historial por cama.
    historial = (
        HistorialEstadoCama.objects.filter(
            cama=cama,
            usuario=usuario,
            fecha_hora__gte=sesion.fecha_inicio,
        )
        .order_by("-fecha_hora", "-id")
        .first()
    )

    if historial:
        historial.estado_anterior = estado_anterior
        historial.estado_nuevo = estado_nuevo
        historial.ingreso = ingreso
        historial.observacion = observacion_catalogada
        historial.fecha_hora = timezone.now()
        historial.save(
            update_fields=[
                "estado_anterior",
                "estado_nuevo",
                "ingreso",
                "observacion",
                "fecha_hora",
            ]
        )
        return historial

    return HistorialEstadoCama.objects.create(
        cama=cama,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        ingreso=ingreso,
        usuario=usuario,
        observacion=observacion_catalogada,
    )


# [2026-05-21] Helper de consistencia entre mapeo de camas e ingreso activo.
def _sincronizar_cama_en_ingreso_activo(*, ingreso_id=None, cama_id=None):
    """Alinea la cama del ingreso operativo con el estado resultante del mapeo."""
    ingreso_activo = _resolver_ingreso_operativo(ingreso_id=ingreso_id)
    if not ingreso_activo:
        return None

    if ingreso_activo.cama_id == cama_id:
        return ingreso_activo

    # [2026-05-21] Regla de consistencia: cada cambio de cama en mapeo
    # debe reflejarse en el ingreso activo del paciente.
    ingreso_activo.cama_id = cama_id
    ingreso_activo.save(update_fields=["cama"])
    return ingreso_activo


# [2026-05-07] Helper para obtener IDs de camas mapeadas en sesión
def _camas_mapeadas_sesion(sesion):
    """Retorna ids de camas ya mapeadas en la sesion."""
    if not sesion:
        return []
    return list(
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values_list("cama__numero_cama", flat=True)
        .distinct()
    )


def _meta_ultima_actualizacion(historial):
    """Serializa metadatos de la ultima actualizacion de una cama."""
    if not historial:
        return {
            "ultima_actualizacion": "",
            "usuario_ultima_actualizacion": "",
        }
    return {
        "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
        "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
    }


def _parse_fecha_filtro(fecha_texto, fin_del_dia=False):
    """Convierte fecha YYYY-MM-DD a datetime aware en zona local."""
    if not fecha_texto:
        return None
    try:
        fecha = datetime.strptime(fecha_texto, "%Y-%m-%d")
    except ValueError:
        return None
    if fin_del_dia:
        fecha = fecha.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        fecha = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
    return timezone.make_aware(fecha, timezone.get_current_timezone())


def _nombre_cama(cama):
    if not cama:
        return ""
    return str(getattr(cama, "numero_cama", "") or "")


def _ubicacion_desde_cama(cama):
    if not cama:
        return ""
    sala = getattr(cama, "sala", None)
    servicio = getattr(sala, "servicio", None)
    cubiculo = getattr(cama, "cubiculo", None)
    servicio_nombre = getattr(servicio, "nombre_servicio", "") or ""
    sala_nombre = getattr(sala, "nombre_sala", "") or ""
    cubiculo_nombre = getattr(cubiculo, "nombre_cubiculo", "") or "SIN_CUBICULO"
    return f"{servicio_nombre} / {sala_nombre} / {cubiculo_nombre}"


# [2026-05-07] API: Obtener catálogo de camas para filtros de historiales
@login_required
@require_GET
def historiales_camas_filtro(request):
    """Retorna catálogo de camas para el select de filtros."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("numero_cama")
    )
    data = []
    for cama in camas:
        data.append(
            {
                "id": str(cama.numero_cama),
                "numero_cama": str(cama.numero_cama),
                "ubicacion": _ubicacion_desde_cama(cama),
            }
        )
    return JsonResponse({"ok": True, "results": data})


# [2026-05-07] API: Obtener datos de registros en historiales filtrados
@login_required
@require_GET
def historiales_data(request):
    """Lista registros según tipo: mapeo, historial o movimiento."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    tipo = (request.GET.get("tipo") or "mapeo").strip().lower()
    cama_id = (request.GET.get("cama_id") or "").strip()
    fecha_inicio = _parse_fecha_filtro(request.GET.get("fecha_inicio"), fin_del_dia=False)
    fecha_fin = _parse_fecha_filtro(request.GET.get("fecha_fin"), fin_del_dia=True)

    if tipo not in {"mapeo", "historial", "movimiento"}:
        return JsonResponse({"ok": False, "error": "Tipo de historial no valido."}, status=400)

    if tipo == "mapeo":
        sesiones = MapeoSesionCama.objects.select_related("usuario").prefetch_related(
            Prefetch(
                "servicios_incluidos",
                queryset=MapeoSesionServicio.objects.select_related("servicio").order_by("servicio__nombre_servicio"),
                to_attr="servicios_prefetch",
            )
        ).order_by("-fecha_inicio")
        if fecha_inicio:
            sesiones = sesiones.filter(fecha_inicio__gte=fecha_inicio)
        if fecha_fin:
            sesiones = sesiones.filter(fecha_inicio__lte=fecha_fin)

        sesiones = sesiones.annotate(
            total_detalles=Count("detalles", distinct=True),
            total_camas=Count("detalles__cama", distinct=True),
            total_cambios=Count("detalles", filter=Q(detalles__hubo_cambio=True), distinct=True),
        )[:200]

        results = []
        for sesion in sesiones:
            nombres_servicios = [
                ss.servicio.nombre_servicio
                for ss in getattr(sesion, "servicios_prefetch", [])
                if ss.servicio_id
            ]
            results.append(
                {
                    "id": sesion.id,
                    "referencia": f"Sesion {sesion.id}",
                    "tipo": "MAPEO",
                    "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
                    "fecha_principal": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_inicio": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_fin": _hora_local_iso(sesion.fecha_fin),
                    "usuario": _nombre_usuario(sesion.usuario),
                    "detalle_1": f"Camas procesadas: {sesion.total_camas}",
                    "detalle_2": f"Cambios detectados: {sesion.total_cambios}",
                    "detalle_3": f"Registros detalle: {sesion.total_detalles}",
                    "servicios": nombres_servicios,
                }
            )
        return JsonResponse({"ok": True, "results": results})

    if tipo == "historial":
        historial_qs = HistorialEstadoCama.objects.select_related(
            "cama__sala__servicio", "cama__cubiculo", "ingreso__paciente", "usuario"
        )
        if fecha_inicio:
            historial_qs = historial_qs.filter(fecha_hora__gte=fecha_inicio)
        if fecha_fin:
            historial_qs = historial_qs.filter(fecha_hora__lte=fecha_fin)
        if cama_id:
            historial_qs = historial_qs.filter(cama_id=cama_id)

        # Optimización: obtener solo el último evento por cama en DB,
        # evitando recorrer y ordenar en Python todo el historial filtrado.
        latest_id_por_cama = (
            historial_qs.filter(cama_id=OuterRef("cama_id"))
            .order_by("-fecha_hora", "-id")
            .values("id")[:1]
        )

        eventos_por_cama = {
            str(item["cama_id"]): item["total"]
            for item in historial_qs.values("cama_id").annotate(total=Count("id"))
        }

        ultimos_eventos = (
            historial_qs.filter(id=Subquery(latest_id_por_cama))
            .order_by("-fecha_hora", "-id")[:300]
        )

        results = []
        for item in ultimos_eventos:
            total_eventos = eventos_por_cama.get(str(item.cama_id), 0)
            paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
            results.append(
                {
                    "id": item.cama_id,
                    "referencia": f"Cama {_nombre_cama(item.cama)}",
                    "tipo": "HISTORIAL",
                    "estado": item.estado_nuevo.codigo if hasattr(item.estado_nuevo, 'codigo') else str(item.estado_nuevo),
                    "fecha_principal": _hora_local_iso(item.fecha_hora),
                    "fecha_inicio": _hora_local_iso(item.fecha_hora),
                    "fecha_fin": "",
                    "usuario": _nombre_usuario(item.usuario),
                    "detalle_1": f"Cama: {_nombre_cama(item.cama)}",
                    "detalle_2": f"Ultimo cambio: {(getattr(item.estado_anterior, 'codigo', item.estado_anterior) or 'SIN_ESTADO')} -> {getattr(item.estado_nuevo, 'codigo', item.estado_nuevo)}",
                    "detalle_3": f"Eventos: {total_eventos} | " + (
                        f"Paciente: {paciente['nombre']}" if paciente else "Paciente: Sin paciente"
                    ),
                }
            )
        return JsonResponse({"ok": True, "results": results})

    # [2026-05-05 FEATURE] Agrupa movimientos por cama para mostrar una fila por cama.
    # id = cama.pk → al abrir detalle se muestran todos los movimientos de esa cama.
    movimientos = (
        MovimientoCama.objects.select_related(
            "cama_origen__sala__servicio",
            "cama_origen__cubiculo",
            "cama_destino__sala__servicio",
            "cama_destino__cubiculo",
            "ingreso__paciente",
            "usuario",
        )
        .order_by("-fecha_hora")
    )
    if fecha_inicio:
        movimientos = movimientos.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha_hora__lte=fecha_fin)
    if cama_id:
        movimientos = movimientos.filter(Q(cama_origen_id=cama_id) | Q(cama_destino_id=cama_id))

    camas_map = {}
    for mov in movimientos[:500]:
        for cama in [mov.cama_origen, mov.cama_destino]:
            key = str(cama.pk)
            if key not in camas_map:
                camas_map[key] = {"cama": cama, "ultimo": mov, "total": 0}
            camas_map[key]["total"] += 1

    camas_ordenadas = sorted(
        camas_map.values(),
        key=lambda x: x["ultimo"].fecha_hora,
        reverse=True,
    )[:300]

    results = []
    for registro in camas_ordenadas:
        cama = registro["cama"]
        ultimo = registro["ultimo"]
        total = registro["total"]
        paciente = _paciente_payload(ultimo.ingreso.paciente if ultimo.ingreso_id else None, ingreso_id=ultimo.ingreso_id)
        results.append(
            {
                "id": cama.pk,
                "referencia": f"Cama {_nombre_cama(cama)}",
                "tipo": "MOVIMIENTO",
                "estado": f"{total} movimiento(s)",
                "fecha_principal": _hora_local_iso(ultimo.fecha_hora),
                "fecha_inicio": _hora_local_iso(ultimo.fecha_hora),
                "fecha_fin": "",
                "usuario": _nombre_usuario(ultimo.usuario),
                "detalle_1": f"Cama: {_nombre_cama(cama)}",
                "detalle_2": f"Total movimientos: {total}",
                "detalle_3": f"Ultimo paciente: {paciente['nombre']}" if paciente else "Sin paciente",
            }
        )
    return JsonResponse({"ok": True, "results": results})


# [2026-05-07] API: Obtener cards de detalle seg\u00fan tipo y registro
@login_required
@require_GET
def historiales_cards_data(request):
    """Devuelve cards de detalle según tipo seleccionado y registro."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    tipo = (request.GET.get("tipo") or "").strip().lower()
    registro_id = (request.GET.get("id") or "").strip()

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or DETALLE_PAGE_SIZE_DEFAULT)
    except (TypeError, ValueError):
        page_size = DETALLE_PAGE_SIZE_DEFAULT
    page_size = max(1, min(page_size, DETALLE_PAGE_SIZE_MAX))

    if not registro_id:
        return JsonResponse({"ok": False, "error": "Debe indicar id."}, status=400)

    if tipo == "mapeo":
        sesion = MapeoSesionCama.objects.filter(pk=registro_id).first()
        if not sesion:
            return JsonResponse({"ok": False, "error": "Sesion no encontrada."}, status=404)

        # [2026-05-04 AUDIT] Bug Fix: Añadir select_related() para estado_actual y tipo_accion
        # para evitar serialización de objetos FK. Asegurar acceso a .codigo para serializar.
        # [2026-05-18] Orden ascendente para procesar cronológicamente y calcular transiciones
        detalles = (
            DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
            .select_related("cama__sala__servicio", "cama__cubiculo__sala__servicio", "ingreso_actual__paciente", "usuario", "estado_actual", "tipo_accion")
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "fecha_hora")
        )
        
        # [2026-05-18] Convertir a lista, procesar con cache de transiciones, luego reordenar
        detalles_list = list(detalles)
        # Cache de último estado visto por cama (en orden cronológico)
        ultimo_estado_por_cama = {}
        # Diccionario que mapea (cama_id, fecha_hora) -> tipo_accion_display para renderizar
        tipo_accion_display_map = {}
        
        for item in detalles_list:
            estado_actual_codigo = item.estado_actual.codigo if item.estado_actual else ""
            estado_anterior_codigo = ultimo_estado_por_cama.get(item.cama_id, None)
            
            # [2026-05-18] Determinar cómo mostrar la transición
            if estado_anterior_codigo is None:
                # Es el primer cambio de esta cama en la sesión
                tipo_accion_display = "Confirmación"
            else:
                # Hay un estado anterior, mostrar transición
                tipo_accion_display = f"{estado_anterior_codigo} \u2192 {estado_actual_codigo}"
            
            tipo_accion_display_map[(item.cama_id, item.fecha_hora.isoformat())] = tipo_accion_display
            # Actualizar cache con el estado actual
            ultimo_estado_por_cama[item.cama_id] = estado_actual_codigo
        
        # [2026-05-18] Re-ordenar detalles por fecha descendente para renderizar (más reciente primero)
        detalles_list_ordenados = sorted(detalles_list, key=lambda x: x.fecha_hora, reverse=True)
        
        cards = []
        servicios_map = {}
        # [2026-05-07] Deduplicar por cama dentro de cada cubículo/sala:
        # la consulta ordena por "-fecha_hora" por cama, así que el primer registro
        # por numero_cama es el más reciente. Se omiten los duplicados posteriores.
        camas_vistas_estructura = set()
        
        for item in detalles_list_ordenados:
            paciente = _paciente_payload(item.ingreso_actual.paciente if item.ingreso_actual_id else None, ingreso_id=item.ingreso_actual_id)
            cama_numero = _nombre_cama(item.cama)
            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            # [2026-05-07] Usar la sala del cubículo cuando existe, porque la FK sala
            # de la cama puede apuntar a una sala diferente (dato inconsistente en BD).
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre,
                    "cubiculos": {},
                    "camas_directas": [],
                }

            # [2026-05-18] Obtener tipo_accion_display desde el mapa precalculado
            tipo_accion_display = tipo_accion_display_map.get((item.cama_id, item.fecha_hora.isoformat()), "Confirmación")

            # [2026-05-04 AUDIT] Access .codigo for serializable values (EstadoMapeo objects).
            cama_item = {
                "numero_cama": cama_numero,
                "estado": item.estado_actual.codigo if item.estado_actual else "",
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": tipo_accion_display,
                "hubo_cambio": bool(item.hubo_cambio),
                "fue_validada": bool(item.fue_validada),
                "observacion": _observacion_codigo(item.observacion),
            }

            # [2026-05-07] Solo agregar a la estructura si la cama no fue vista antes.
            clave_cama = (servicio_nombre, sala_nombre, cubiculo_nombre, cama_numero)
            if clave_cama not in camas_vistas_estructura:
                camas_vistas_estructura.add(clave_cama)
                if cubiculo_nombre == "SIN_CUBICULO":
                    servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
                else:
                    cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                    if cubiculo_nombre not in cubiculos_map:
                        cubiculos_map[cubiculo_nombre] = {
                            "nombre": cubiculo_nombre,
                            "camas": [],
                        }
                    cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

            cards.append(
                {
                    "titulo": f"Cama {item.cama_id}",
                    "subtitulo": tipo_accion_display,
                    "estado": item.estado_actual.codigo if item.estado_actual else "",
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(item.cama)}",
                    "detalle_2": f"Validada: {'SI' if item.fue_validada else 'NO'}",
                    "detalle_3": f"Hubo cambio: {'SI' if item.hubo_cambio else 'NO'}",
                    "observacion": _observacion_codigo(item.observacion),
                }
            )

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                cubiculos_data = list(sala_data["cubiculos"].values())
                salas_data.append(
                    {
                        "nombre": sala_data["nombre"],
                        "cubiculos": cubiculos_data,
                        "camas_directas": sala_data["camas_directas"],
                    }
                )
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        # [2026-05-08] Servicios incluidos en la sesión (para nota en detalle)
        servicios_sesion = [
            ss.servicio.nombre_servicio
            for ss in MapeoSesionServicio.objects.select_related("servicio")
            .filter(sesion_mapeo=sesion)
            .order_by("servicio__nombre_servicio")
        ]

        return JsonResponse(
            {
                "ok": True,
                "cards": cards,
                "estructura": estructura,
                "servicios_sesion": servicios_sesion,
                "sesion_observacion": sesion.observacion_texto if sesion.observacion_texto else None,
                "paginacion": {
                    "page": 1,
                    "page_size": page_size,
                    "total_items": len(cards),
                    "total_pages": 1,
                },
            }
        )

    if tipo == "historial":
        # [2026-05-05 FEATURE] Construye estructura servicio>sala>cubiculo igual que mapeo.
        # Cada evento del historial se convierte en un cama_item de la estructura.
        timeline_qs = (
            HistorialEstadoCama.objects.select_related(
                "cama__sala__servicio", "cama__cubiculo__sala__servicio",
                "estado_anterior", "estado_nuevo", "ingreso__paciente", "usuario",
            )
            .filter(cama_id=registro_id)
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "-fecha_hora")
        )
        total_items = timeline_qs.count()
        if total_items == 0:
            return JsonResponse({"ok": False, "error": "Historial no encontrado para esta cama."}, status=404)

        total_pages = max(1, (total_items + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        inicio = (page - 1) * page_size
        timeline_page = timeline_qs[inicio:inicio + page_size]

        servicios_map = {}
        for item in timeline_page:
            paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
            estado_nuevo_codigo = item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo)
            estado_anterior_codigo = (
                item.estado_anterior.codigo if hasattr(item.estado_anterior, "codigo") else str(item.estado_anterior)
            ) if item.estado_anterior else "SIN_ESTADO"

            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            # [2026-05-07] Usar sala del cubículo cuando existe para evitar grupos duplicados.
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                }

            cama_item = {
                "numero_cama": _nombre_cama(item.cama),
                "estado": estado_nuevo_codigo,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": f"{estado_anterior_codigo} \u2192 {estado_nuevo_codigo}",
                "observacion": _observacion_codigo(item.observacion),
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                salas_data.append({
                    "nombre": sala_data["nombre"],
                    "cubiculos": list(sala_data["cubiculos"].values()),
                    "camas_directas": sala_data["camas_directas"],
                })
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        return JsonResponse(
            {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }
        )

    if tipo == "movimiento":
        # [2026-05-05 FEATURE] Recibe cama_id, muestra todos sus movimientos en estructura mapeo.
        # Cada movimiento = un cama_item con rol SALIDA/ENTRADA y la cama contraparte.
        movimientos_qs = (
            MovimientoCama.objects.select_related(
                "cama_origen__sala__servicio", "cama_origen__cubiculo__sala__servicio",
                "cama_destino__sala__servicio", "cama_destino__cubiculo__sala__servicio",
                "ingreso__paciente", "usuario",
            )
            .filter(Q(cama_origen_id=registro_id) | Q(cama_destino_id=registro_id))
            .order_by("-fecha_hora")
        )
        total_items = movimientos_qs.count()
        if total_items == 0:
            return JsonResponse({"ok": False, "error": "No se encontraron movimientos para esta cama."}, status=404)

        total_pages = max(1, (total_items + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        inicio = (page - 1) * page_size
        movimientos_page = movimientos_qs[inicio:inicio + page_size]

        # Determinar la cama de referencia usando el primer movimiento
        primer_mov = movimientos_qs.first()
        cama_ref = (
            primer_mov.cama_origen
            if str(primer_mov.cama_origen_id) == str(registro_id)
            else primer_mov.cama_destino
        )

        cubiculo_obj_ref = getattr(cama_ref, "cubiculo", None)
        # [2026-05-07] Usar sala del cubículo cuando existe para evitar grupos duplicados.
        sala_real_ref = (cubiculo_obj_ref.sala if cubiculo_obj_ref else None) or getattr(cama_ref, "sala", None)
        servicio_nombre = getattr(getattr(sala_real_ref, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
        sala_nombre = getattr(sala_real_ref, "nombre_sala", "") or "SIN_SALA"
        cubiculo_nombre = (f"#{cubiculo_obj_ref.numero} {cubiculo_obj_ref.nombre_cubiculo}") if cubiculo_obj_ref else "SIN_CUBICULO"

        servicios_map = {
            servicio_nombre: {
                "nombre": servicio_nombre,
                "salas": {
                    sala_nombre: {
                        "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                    }
                },
            }
        }

        for mov in movimientos_page:
            paciente = _paciente_payload(mov.ingreso.paciente if mov.ingreso_id else None, ingreso_id=mov.ingreso_id)
            tipo_mov = mov.tipo_movimiento.codigo if hasattr(mov.tipo_movimiento, "codigo") else str(mov.tipo_movimiento)
            es_origen = str(mov.cama_origen_id) == str(registro_id)
            otra_cama = mov.cama_destino if es_origen else mov.cama_origen
            rol = f"SALIDA \u2192 Cama {_nombre_cama(otra_cama)}" if es_origen else f"ENTRADA \u2190 Cama {_nombre_cama(otra_cama)}"

            cama_item = {
                "numero_cama": _nombre_cama(cama_ref),
                "estado": tipo_mov,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(mov.usuario),
                "fecha": _hora_local_iso(mov.fecha_hora),
                "tipo_accion": rol,
                "observacion": _observacion_codigo(mov.observacion),
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        salas_data = []
        for sala_data in servicios_map[servicio_nombre]["salas"].values():
            salas_data.append({
                "nombre": sala_data["nombre"],
                "cubiculos": list(sala_data["cubiculos"].values()),
                "camas_directas": sala_data["camas_directas"],
            })
        estructura = [{"nombre": servicio_nombre, "salas": salas_data}]

        return JsonResponse(
            {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }
        )

    return JsonResponse({"ok": False, "error": "Tipo no soportado."}, status=400)


# [2026-05-07] API: Iniciar nueva sesi\u00f3n de mapeo de camas
@login_required
@require_POST
def iniciar_mapeo(request):
    """Inicia una sesion de mapeo para el usuario actual."""
    if not _tiene_permiso_mapear(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    # [2026-05-19] El rol de intentos no puede iniciar sesiones de mapeo.
    # Solo puede operar sobre cambios permitidos cuando el mapa está disponible.
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
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    servicio_ids = payload.get("servicio_ids") or []
    if not isinstance(servicio_ids, list):
        return JsonResponse({"ok": False, "error": "Debe indicar una lista valida de servicios."}, status=400)

    # [2026-05-07] El mapeo deja de ser global: la sesion ahora se inicia con servicios explicitamente seleccionados.
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

    # [2026-05-26 AUDIT] Bloquea sesiones solapadas: un servicio no puede mapearse
    # simultáneamente por dos usuarios diferentes.
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


# [2026-05-07] API: Obtener estado actual de sesión de mapeo activa
@login_required
@require_GET
def estado_mapeo(request):
    """Devuelve la sesion de mapeo activa y camas ya procesadas para restaurar UI."""
    if not _tiene_permiso_historiales(request.user):
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


# [2026-05-07] API: Terminar sesión de mapeo activa
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
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

    # [2026-05-07] El alcance de cierre se calcula solo sobre los servicios ligados a la sesion activa.
    # [2026-05-22] La pertenencia de la cama al servicio se determina siempre por cama.sala;
    # el cubículo es solo su ubicación física, puede estar en otra sala.
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
        # [2026-05-21] Retornar listado de camas faltantes para mostrarlo en modal frontend.
        camas_faltantes = []
        faltantes_qs = (
            total_camas_qs.exclude(pk__in=camas_mapeadas_ids)
            .select_related("sala__servicio", "cubiculo__sala__servicio")
            .order_by("numero_cama")
        )
        for cama in faltantes_qs:
            cubiculo_obj = getattr(cama, "cubiculo", None)
            # [2026-05-22] Sala/servicio siempre desde cama.sala; cubiculo solo es ubicación física.
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
            "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo finalizado correctamente.",
        }
    )


# [2026-05-07] API: Cancelar sesión de mapeo activa
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
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
            "estado": sesion.estado.codigo if hasattr(sesion.estado, 'codigo') else str(sesion.estado),
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo cancelado correctamente.",
        }
    )


# =============================================================================
# mapa_camas_data
# -----------------------------------------------------------------------------
# API GET que construye y retorna en JSON la estructura completa del mapa:
#   Servicio → Sala → Cubículo → Cama  (con estado visual y datos del paciente)
#                   → Camas directas  (camas sin cubículo asignado)
#
# La función no renderiza HTML: prepara exclusivamente un payload JSON para que
# el frontend pinte dinámicamente la estructura del mapa.
#
# Idea general del algoritmo:
# 1. Obtener la última asignación registrada por cama.
# 2. Calcular cuántos movimientos recientes tiene cada sala.
# 3. Cargar la jerarquía Servicio -> Sala -> Cubículo -> Cama usando prefetch.
# 4. Transformar esa jerarquía en listas/diccionarios serializables a JSON.
#
# La última asignación de cada cama determina su estado visual actual.
# También incluye el conteo de cambios recientes por sala para aplicar
# el límite de movimientos en el frontend.
# =============================================================================
# [2026-05-07] API: Obtener estructura completa de camas agrupadas por servicio/sala/cub\u00edculo
@login_required
def mapa_camas_data(request):
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    servicios_ids_sesion = _obtener_servicios_ids_sesion(sesion_activa)

    # [2026-05-26 FEATURE] Exponer en el payload si un servicio está siendo mapeado
    # por otro usuario para bloquear selección directamente en el modal de inicio.
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

    # 1. Resolver solo la ultima asignacion por cama en BD.
    #    Evita iterar todo el historico en Python cuando la tabla crece.
    ultima_asignacion_id = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=OuterRef("cama_id"))
        .order_by("-fecha_inicio", "-id")
        .values("id")[:1]
    )
    asignacion_por_cama = {
        asig.cama_id: asig
        for asig in (
            AsignacionCamaPaciente.objects
            .select_related("ingreso", "estado")
            .filter(id=Subquery(ultima_asignacion_id))
        )
    }

    # 1.b. Resolver ultima actualizacion por cama con el mismo enfoque.
    ultima_historial_id = (
        HistorialEstadoCama.objects
        .filter(cama_id=OuterRef("cama_id"))
        .order_by("-fecha_hora", "-id")
        .values("id")[:1]
    )
    historial_por_cama = {
        historial.cama_id: historial
        for historial in (
            HistorialEstadoCama.objects
            .select_related("usuario")
            .filter(id=Subquery(ultima_historial_id))
        )
    }

    # 2. Calcular el número de movimientos manuales recientes por sala.
    #
    #    Este conteo se toma del historial y queda agrupado por cama__sala_id.
    #    El resultado final se transforma en otro diccionario:
    #        { sala_id: total_cambios }
    #
    #    Se usa después para dos cosas:
    #    - mostrar en cada cama cuántos cambios lleva la sala
    #    - permitir que el frontend informe el límite operativo disponible
    cambios_por_sala = {
        item["sala_real_id"]: item["total"]
        for item in HistorialEstadoCama.objects.filter(
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .filter(_filtro_observaciones_movimiento_limite())
        # [2026-05-22] La pertenencia operativa de la cama se toma desde su sala,
        # aunque el cubículo apunte a otra sala por inconsistencia histórica.
        .annotate(sala_real_id=F("cama__sala_id"))
        .exclude(estado_anterior=F("estado_nuevo"))
        .values("sala_real_id")
        .annotate(total=Count("id"))
    }
    max_cambios_usuario = _max_cambios_para_usuario(request.user)

    # 3. Construcción eficiente de la jerarquía física del hospital.
    #
    #    Se separan dos tipos de camas:
    #    - camas_directas_qs: camas colgadas directamente de una sala.
    #    - camas_cubiculo_qs: camas que pertenecen a un cubículo.
    #
    #    Luego se encadenan prefetch_related para traer toda la estructura en
    #    memoria con el menor número posible de consultas:
    #    Servicio -> Salas -> Cubículos -> Camas
    #                      -> Camas directas
    #
    #    Esto evita el problema N+1 cuando más abajo se recorre cada servicio,
    #    cada sala y cada cubículo para construir el JSON final.
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
        # [2026-05-07] Durante un mapeo activo, el mapa se restringe a los servicios elegidos al iniciar la sesion.
        servicios = servicios.filter(id__in=servicios_ids_sesion)
    servicios = servicios.prefetch_related(
        Prefetch("salas_servicio", queryset=salas_qs)
    ).order_by("nombre_servicio")

    # 4. Transformar la jerarquía ORM en una estructura serializable a JSON.
    #
    #    Formato de salida esperado:
    #    {
    #        "servicios": [
    #            {
    #                "id": ...,
    #                "nombre": ...,
    #                "salas": [
    #                    {
    #                        "id": ...,
    #                        "cubiculos": [...],
    #                        "camas_directas": [...]
    #                    }
    #                ]
    #            }
    #        ]
    #    }
    #
    #    Cada cama expone:
    #    - numero_cama
    #    - estado_visual
    #    - asignacion_estado
    #    - paciente
    #    - cambios_realizados
    #    - max_cambios
    #
    #    Esto le evita al frontend tener que inferir relaciones o recalcular
    #    estados: el backend entrega el árbol listo para pintar.
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

            # [2026-05-22] Cubiculos cruzados: si una cama pertenece a esta sala,
            # pero su cubiculo apunta a otra sala, se conserva dentro del cubiculo
            # correspondiente para no perder la ubicacion fisica en el mapa.
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
# -----------------------------------------------------------------------------
# API GET de autocompletado. Busca pacientes con ingreso activo para
# operaciones del mapa/mapeo.
#
# Regla de negocio:
# - Solo mostrar pacientes con ingreso activo.
# Acepta el parámetro ?q= para filtrar por nombre o DNI.
# Retorna un máximo de 20 resultados.
# =============================================================================
# [2026-05-07] API: Buscar pacientes disponibles para asignar camas
@login_required
@require_GET
def buscar_pacientes_mapa(request):
    termino = (request.GET.get("q") or "").strip()
    tipo_busqueda = (request.GET.get("tipo") or "dni").strip().lower()

    # [2026-05-21] Optimizacion de buscadores mapa/mapeo:
    # limitar la base a pacientes con ingreso activo para reducir ruido y costo.
    ingreso_activo = Exists(
        Ingreso.objects.filter(
            paciente_id=OuterRef("pk"),
            estado=1,
            fecha_egreso__isnull=True,
        )
    )
    ingreso_activo_id = Subquery(
        Ingreso.objects.filter(
            paciente_id=OuterRef("pk"),
            estado=1,
            fecha_egreso__isnull=True,
        )
        .order_by("-fecha_ingreso", "-id")
        .values("id")[:1]
    )
    pacientes_qs = (
        Paciente.objects.filter(estado__in=["A", "P"])
        .annotate(ingreso_activo_id=ingreso_activo_id)
        .filter(ingreso_activo)
    )

    if termino:
        if tipo_busqueda == "dni":
            pacientes_qs = pacientes_qs.filter(dni__icontains=termino)
        elif tipo_busqueda == "nombre":
            pacientes_qs = pacientes_qs.filter(
                Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )
        else:
            pacientes_qs = pacientes_qs.filter(
                Q(dni__icontains=termino)
                | Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )

    pacientes = pacientes_qs.order_by("primer_nombre", "primer_apellido")[:20]
    resultados = [_paciente_payload(p, ingreso_id=getattr(p, "ingreso_activo_id", None)) for p in pacientes]
    return JsonResponse({"results": resultados})


# =============================================================================
# camas_disponibles_mapa
# -----------------------------------------------------------------------------
# API GET que retorna todas las camas en estado VACIA disponibles para
# recibir un traslado de paciente.
# Acepta el parámetro ?excluir= para omitir la cama origen del traslado
# y no ofrecerla como opción de destino.
# =============================================================================
# [2026-05-07] API: Obtener camas disponibles para traslado de pacientes
@login_required
@require_GET
def camas_disponibles_mapa(request):
    excluir_cama = request.GET.get("excluir") or None
    servicio_restringido_id = None

    # [2026-05-26 FEATURE] Para rol de intentos, los traslados solo se permiten
    # dentro del mismo servicio de la cama origen.
    if _es_rol_intentos_restringido(request.user) and excluir_cama:
        try:
            cama_origen = Cama.objects.select_related("sala__servicio").get(numero_cama=excluir_cama)
            servicio_restringido_id = getattr(cama_origen.sala, "servicio_id", None)
        except Cama.DoesNotExist:
            servicio_restringido_id = None

    # Obtener el estado actual de cada cama tomando solo la asignación más reciente.
    asignaciones = AsignacionCamaPaciente.objects.order_by("cama_id", "-fecha_inicio", "-id")
    asignacion_por_cama = {}
    for asig in asignaciones:
        if asig.cama_id not in asignacion_por_cama:
            asignacion_por_cama[asig.cama_id] = asig

    todas_camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("sala__servicio__nombre_servicio", "sala__nombre_sala", "numero_cama")
    )

    resultados = []
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    for cama in todas_camas:
        # Omitir la cama de origen para que no aparezca como destino disponible.
        if excluir_cama and str(cama.numero_cama) == str(excluir_cama):
            continue
        # [2026-05-04 AUDIT] Bug Fix: Usar cama.pk (PK real) como clave, no numero_cama.
        # Esto arregla el problema donde camas disponibles no se mostraban correctamente.
        asig = asignacion_por_cama.get(cama.pk)
        estado = asig.estado if asig else estado_vacia
        if getattr(estado, "codigo", estado) == "VACIA":
            if servicio_restringido_id and getattr(cama.sala, "servicio_id", None) != servicio_restringido_id:
                continue
            resultados.append({
                "numero_cama": cama.numero_cama,
                "sala": cama.sala.nombre_sala,
                "servicio": cama.sala.servicio.nombre_servicio,
                "cubiculo": cama.cubiculo.nombre_cubiculo if cama.cubiculo else None,
            })

    return JsonResponse({"results": resultados})


# =============================================================================
# mover_paciente_cama
# -----------------------------------------------------------------------------
# API POST que ejecuta un traslado atómico de paciente entre camas.
# Flujo dentro de transaction.atomic():
#   1. Libera la cama origen (OCUPADA → VACIA, paciente = None).
#   2. Ocupa la cama destino (VACIA → OCUPADA, asigna el mismo paciente).
#   3. Registra un HistorialEstadoCama por cada cama afectada.
#   4. Crea un MovimientoCama con origen, destino y paciente.
# Para usuarios no superadmin verifica el límite de cambios por sala
# en la ventana temporal activa antes de ejecutar el movimiento.
# =============================================================================
# [2026-05-07] API: Realizar traslado de paciente entre camas
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def mover_paciente_cama(request):
    cama_origen_id = request.POST.get("cama_origen_id")
    cama_destino_id = request.POST.get("cama_destino_id")

    if not cama_origen_id or not cama_destino_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama origen y la cama destino."}, status=400)

    if str(cama_origen_id) == str(cama_destino_id):
        return JsonResponse({"ok": False, "error": "La cama destino debe ser diferente a la cama origen."}, status=400)

    try:
        cama_origen = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_origen_id)
        cama_destino = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_destino_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Una de las camas indicadas no existe."}, status=404)

    # [2026-05-26 FEATURE] Rol de intentos: no puede mover pacientes entre servicios distintos.
    if _es_rol_intentos_restringido(request.user):
        servicio_origen_id = getattr(cama_origen.sala, "servicio_id", None)
        servicio_destino_id = getattr(cama_destino.sala, "servicio_id", None)
        if servicio_origen_id and servicio_destino_id and servicio_origen_id != servicio_destino_id:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Este rol solo puede mover pacientes entre camas del mismo servicio.",
                },
                status=403,
            )

    sala_origen_id = _sala_real_id_desde_cama(cama_origen)
    sala_destino_id = _sala_real_id_desde_cama(cama_destino)

    limite_error = _validar_limite_intentos_salas(request.user, [sala_origen_id, sala_destino_id])
    if limite_error:
        return limite_error

    asig_origen = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=cama_origen_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )
    asig_destino = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=cama_destino_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")

    if not asig_origen or asig_origen.estado is None or asig_origen.estado.codigo not in {"OCUPADA", "PRE_ALTA"}:
        return JsonResponse({"ok": False, "error": "La cama origen no tiene paciente asignado (debe estar OCUPADA o PRE_ALTA)."}, status=400)

    ingreso_operativo = asig_origen.ingreso
    if not ingreso_operativo:
        # [2026-05-26 REFACTOR FINAL] Sin ingreso, no puede haber asignación válida en cama origen.
        return JsonResponse(
            {"ok": False, "error": "La cama origen no tiene un ingreso activo válido. Datos incompletos."},
            status=400,
        )

    if asig_destino and (asig_destino.estado is not None and asig_destino.estado.codigo != "VACIA"):
        return JsonResponse({"ok": False, "error": "La cama destino no esta disponible (no esta vacia)."}, status=400)

    estado_anterior_origen = asig_origen.estado
    estado_anterior_destino = asig_destino.estado if asig_destino else estado_vacia

    # Superadmin: el registro queda, pero con una observación distinta
    # para que _contar_cambios_manual_por_sala no lo cuente.
    es_superadmin = _es_superadmin(request.user)
    obs_origen = (
        get_observacion_mapeo(OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN)
        if es_superadmin
        else get_observacion_mapeo(OBSERVACION_MOVIMIENTO_PACIENTE_MAPA)
    )
    obs_destino = (
        get_observacion_mapeo(OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN)
        if es_superadmin
        else (
            get_observacion_mapeo(OBSERVACION_MOVIMIENTO_PACIENTE_MAPA)
            if sala_destino_id != sala_origen_id
            else get_observacion_mapeo(OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE)
        )
    )
    sesion_mapeo_activa = _obtener_sesion_mapeo_activa(request.user)

    with transaction.atomic():
        # 1. Liberar cama origen (OCUPADA -> VACIA)
        asig_origen.estado = estado_vacia
        asig_origen.save()

        # 2. Ocupar cama destino (VACIA -> OCUPADA con el mismo ingreso)
        if not asig_destino:
            asig_destino = AsignacionCamaPaciente(
                cama=cama_destino,
                estado=estado_ocupada,
                ingreso=ingreso_operativo,
                usuario_asignacion=request.user,
            )
        else:
            asig_destino.estado = estado_ocupada
            asig_destino.ingreso = ingreso_operativo
            asig_destino.usuario_asignacion = request.user
        asig_destino.save()

        # [2026-05-21] Reflejar traslado en ingreso activo del paciente.
        _sincronizar_cama_en_ingreso_activo(
            ingreso_id=ingreso_operativo.id,
            cama_id=cama_destino.pk,
        )

        # 3. Registrar historial para ambas camas
        historial_origen = _registrar_historial_mapeo(
            cama=cama_origen,
            estado_anterior=estado_anterior_origen,
            estado_nuevo=estado_vacia,
            ingreso=None,
            usuario=request.user,
            observacion=obs_origen,
            sesion_mapeo=sesion_mapeo_activa,
        )
        historial_destino = _registrar_historial_mapeo(
            cama=cama_destino,
            estado_anterior=estado_anterior_destino,
            estado_nuevo=estado_ocupada,
            ingreso=ingreso_operativo,
            usuario=request.user,
            observacion=obs_destino,
            sesion_mapeo=sesion_mapeo_activa,
        )

        MovimientoCama.objects.create(
            tipo_movimiento="TRASLADO",
            cama_origen_id=cama_origen_id,
            cama_destino_id=cama_destino_id,
            ingreso=ingreso_operativo,
            usuario=request.user,
            observacion=get_observacion_mapeo("Movimiento desde mapa de camas"),
        )

        # Registro en tiempo real por cama dentro de sesion de mapeo activa.
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_origen,
            asignacion=asig_origen,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion=get_observacion_mapeo("Traslado de paciente desde mapa (cama origen)."),
        )
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_destino,
            asignacion=asig_destino,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion=get_observacion_mapeo("Traslado de paciente desde mapa (cama destino)."),
        )

    cambios_origen_post = _contar_cambios_manual_por_sala(sala_origen_id)
    cambios_destino_post = _contar_cambios_manual_por_sala(sala_destino_id)
    max_cambios_usuario = _max_cambios_para_usuario(request.user)

    return JsonResponse({
        "ok": True,
        "mensaje": f"Paciente movido a la cama {cama_destino_id} correctamente.",
        "cama_origen": {
            "numero_cama": int(cama_origen_id),
            "estado_visual": estado_vacia.codigo,
            "paciente": None,
            "cambios_realizados": cambios_origen_post,
            "max_cambios": max_cambios_usuario,
            "ultima_actualizacion": _hora_local_iso(historial_origen.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_origen.usuario),
        },
        "cama_destino": {
            "numero_cama": int(cama_destino_id),
            "estado_visual": estado_ocupada.codigo,
            "paciente": _paciente_payload(ingreso_operativo.paciente, ingreso_id=ingreso_operativo.id),
            "cambios_realizados": cambios_destino_post,
            "max_cambios": max_cambios_usuario,
            "ultima_actualizacion": _hora_local_iso(historial_destino.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_destino.usuario),
        },
    })


# ===========================================================================
# actualizar_cama_mapa
# ---------------------------------------------------------------------------
# API POST para cambio manual de estado de una cama individual desde el mapa.
# Permite al usuario seleccionar cualquier estado válido y, si el estado
# es OCUPADA, también debe indicar el paciente a asignar.
# Si no existe asignación previa para la cama, la crea en estado VACIA
# antes de aplicar el cambio solicitado.
# Registra el cambio en HistorialEstadoCama con observación de cambio manual.
# ===========================================================================
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def actualizar_cama_mapa(request):
    if not _tiene_permiso_cambios_mapa(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    cama_id = request.POST.get("cama_id")
    estado_codigo = (request.POST.get("estado") or "").strip()
    ingreso_id = request.POST.get("ingreso_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama."}, status=400)

    # Validar que el estado existe y pertenece a la categoría ESTADO_CAMA
    try:
        estado_nuevo_obj = EstadoMapeo.objects.get(codigo=estado_codigo, categoria="ESTADO_CAMA")
    except EstadoMapeo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Estado de cama no válido."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    # Obtener la asignación actual (la más reciente)
    asignacion = (
        AsignacionCamaPaciente.objects.select_related("ingreso", "estado")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    # Si no existe asignación previa, crear una en estado VACIA
    if not asignacion:
        estado_vacia = EstadoMapeo.objects.get(codigo="VACIA", categoria="ESTADO_CAMA")
        asignacion = AsignacionCamaPaciente.objects.create(
            cama=cama,
            usuario_asignacion=request.user,
            estado=estado_vacia,
            ingreso=None,
        )

    ingreso_nuevo = None
    
    if estado_codigo == "OCUPADA":
        # [2026-05-26 REFACTOR FINAL] OCUPADA requiere ingreso_id explícitamente; no hay fallback a paciente.
        if not ingreso_id:
            return JsonResponse(
                {"ok": False, "error": "Para asignar una cama OCUPADA debe indicar el ingreso."},
                status=400,
            )
        ingreso_nuevo = _resolver_ingreso_operativo(ingreso_id=ingreso_id)
        if not ingreso_nuevo:
            return JsonResponse({"ok": False, "error": "El ingreso seleccionado no existe."}, status=404)

    # [2026-05-19] Restricción de edición directa para rol de intentos:
    # solo PRE_ALTA o VACIA desde el modal de cama.
    if _es_rol_intentos_restringido(request.user):
        if estado_codigo not in {"PRE_ALTA", "VACIA"}:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Este rol solo puede hacer pre-altas o pasar la cama a vacia desde edicion directa.",
                },
                status=403,
            )

    # Si el paciente ya tiene otra cama (OCUPADA o PRE_ALTA), detectar para liberar
    asig_previa_paciente = None
    if ingreso_nuevo and estado_codigo == "OCUPADA":
        asig_previa_paciente = (
            AsignacionCamaPaciente.objects
            .select_related("estado", "cama")
            .filter(
                ingreso=ingreso_nuevo,
                estado__codigo__in=["OCUPADA", "PRE_ALTA"],
                estado__categoria="ESTADO_CAMA",
            )
            .exclude(cama_id=cama_id)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    # [2026-05-19] El rol de intentos no puede reasignar pacientes desde edición directa.
    # Debe usar la operación de movimiento entre camas.
    if _es_rol_intentos_restringido(request.user) and asig_previa_paciente:
        return JsonResponse(
            {
                "ok": False,
                "error": "Este rol no puede reasignar pacientes desde la edicion directa. Debe usar movimiento de cama.",
            },
            status=403,
        )

    # Validar que OCUPADA requiere ingreso
    if estado_codigo == "OCUPADA" and not ingreso_nuevo:
        return JsonResponse(
            {
                "ok": False,
                "error": "Para estado OCUPADA debe seleccionar un ingreso activo válido.",
            },
            status=400,
        )

    estado_anterior = asignacion.estado
    ingreso_anterior = asignacion.ingreso
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_alta = get_estado_mapeo("ALTA", "ESTADO_CAMA")

    # [2026-05-27 AUDIT] Una cama VACIA no puede convertirse en PRE_ALTA.
    if estado_anterior and estado_anterior.codigo == "VACIA" and estado_codigo == "PRE_ALTA":
        return JsonResponse(
            {
                "ok": False,
                "error": "Una cama vacia no puede pasar a pre-alta. Debe iniciarse como ocupada o permanecer vacia.",
            },
            status=400,
        )

    # Si la cama estaba en PRE_ALTA y se reasigna a OCUPADA con otro paciente,
    # se registra primero el cierre histórico de alta y la liberación lógica.
    requiere_cierre_prealta = (
        estado_anterior
        and estado_anterior.codigo == "PRE_ALTA"
        and estado_codigo == "OCUPADA"
        and ingreso_anterior
        and (not ingreso_nuevo or ingreso_anterior.id != ingreso_nuevo.id)
    )

    # Si la cama pasa a VACIA desde un estado con paciente, se registra alta.
    requiere_registro_alta_a_vacia = (
        estado_codigo == "VACIA"
        and ingreso_anterior is not None
        and estado_anterior is not None
        and estado_anterior.codigo in {"OCUPADA", "PRE_ALTA", "ALTA"}
    )

    # Lógica de estados especiales
    if estado_codigo == "VACIA":
        ingreso_nuevo = None
    elif estado_codigo in {"PRE_ALTA", "ALTA"} and ingreso_nuevo is None:
        # PRE_ALTA y ALTA deben conservar el paciente actual
        # hasta que la cama pase a VACIA.
        ingreso_nuevo = ingreso_anterior

    # Verificar si hay cambio real
    hubo_cambio = (
        estado_anterior.id != estado_nuevo_obj.id
        or (ingreso_anterior.id if ingreso_anterior else None) != (ingreso_nuevo.id if ingreso_nuevo else None)
    )

    cambios_realizados = _contar_cambios_manual_por_sala(_sala_real_id_desde_cama(cama))
    max_cambios_usuario = _max_cambios_para_usuario(request.user)

    if not hubo_cambio:
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama,
            asignacion=asignacion,
            tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
            hubo_cambio=False,
            observacion=get_observacion_mapeo("Confirmacion sin cambios desde mapa."),
        )
        return JsonResponse(
            {
                "ok": True,
                "mensaje": "No se detectaron cambios para guardar.",
                "cama": {
                    "numero_cama": int(cama_id),
                    "estado_visual": asignacion.estado.codigo,
                    "paciente": _paciente_payload(asignacion.ingreso.paciente if asignacion.ingreso_id else None, ingreso_id=asignacion.ingreso_id),
                    "cambios_realizados": cambios_realizados,
                    "max_cambios": max_cambios_usuario,
                },
            }
        )

    sesion_mapeo_activa = _obtener_sesion_mapeo_activa(request.user)

    try:
        with transaction.atomic():
            estado_historial_anterior = estado_anterior

            if requiere_cierre_prealta:
                _registrar_historial_mapeo(
                    cama=cama,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_alta,
                    ingreso=ingreso_anterior,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Alta historica por reasignacion desde PRE_ALTA"),
                    sesion_mapeo=sesion_mapeo_activa,
                )
                estado_historial_anterior = estado_vacia

            if requiere_registro_alta_a_vacia:
                _registrar_historial_mapeo(
                    cama=cama,
                    estado_anterior=estado_anterior,
                    estado_nuevo=estado_alta,
                    ingreso=ingreso_anterior,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Alta historica por cambio manual a VACIA"),
                    sesion_mapeo=sesion_mapeo_activa,
                )
                estado_historial_anterior = estado_alta

            # Si el paciente ya tenía otra cama asignada, liberarla (cambio de cama)
            if asig_previa_paciente:
                estado_anterior_previa = asig_previa_paciente.estado
                asig_previa_paciente.estado = estado_vacia
                asig_previa_paciente.save()

                _registrar_historial_mapeo(
                    cama=asig_previa_paciente.cama,
                    estado_anterior=estado_anterior_previa,
                    estado_nuevo=estado_vacia,
                    ingreso=None,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Cambio de cama: paciente trasladado a otra cama"),
                    sesion_mapeo=sesion_mapeo_activa,
                )

                MovimientoCama.objects.create(
                    tipo_movimiento="TRASLADO",
                    cama_origen=asig_previa_paciente.cama,
                    cama_destino=cama,
                    ingreso=ingreso_nuevo,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Cambio de cama desde mapa"),
                )

            # Aplicar cambios finales de la asignacion.
            asignacion.estado = estado_nuevo_obj
            asignacion.ingreso = ingreso_nuevo
            asignacion.usuario_asignacion = request.user
            asignacion.save()

            # [2026-05-22] Regla de negocio: al liberar cama en mapa por cambio de paciente,
            # el ingreso del paciente anterior conserva su última cama registrada.

            cama_ingreso_nueva = cama.pk if ingreso_nuevo else None
            if ingreso_nuevo:
                # [2026-05-21] Vincular cama final al ingreso activo del paciente actual.
                _sincronizar_cama_en_ingreso_activo(
                    ingreso_id=ingreso_nuevo.id,
                    cama_id=cama_ingreso_nueva,
                )

            # Registrar historial final del cambio visible en cama.
            historial = _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_historial_anterior,
                estado_nuevo=estado_nuevo_obj,
                ingreso=asignacion.ingreso,
                usuario=request.user,
                observacion=get_observacion_mapeo(OBSERVACION_CAMBIO_MANUAL_MAPA),
                sesion_mapeo=sesion_mapeo_activa,
            )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    # Registrar detalle del mapeo
    _registrar_detalle_mapeo(
        usuario=request.user,
        cama=cama,
        asignacion=asignacion,
        tipo_accion=(
            DetalleMapeoCama.TipoAccion.ALTA
            if estado_codigo == "ALTA" or requiere_registro_alta_a_vacia
            else DetalleMapeoCama.TipoAccion.CAMBIO
        ),
        hubo_cambio=True,
        observacion=get_observacion_mapeo("Actualización de cama desde mapa."),
    )

    cambios_realizados = _contar_cambios_manual_por_sala(_sala_real_id_desde_cama(cama))
    return JsonResponse(
        {
            "ok": True,
            "mensaje": "Cambio de cama actualizado correctamente.",
            "cama": {
                "numero_cama": int(cama_id),
                "estado_visual": asignacion.estado.codigo,
                "paciente": _paciente_payload(asignacion.ingreso.paciente if asignacion.ingreso_id else None, ingreso_id=asignacion.ingreso_id),
                "cambios_realizados": cambios_realizados,
                "max_cambios": max_cambios_usuario,
                "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
                "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
            },
        }
    )


# [2026-05-07] API: Procesar acción de mapeo en cama (confirmar, alta, traslado, etc.)
# [2026-05-08] Requiere rol de editor (admin/digitador de ADMI)
@login_required
@require_POST
def procesar_cama_mapeo(request):
    """
    Ciclo principal de mapeo por cama:
    evaluar -> decidir -> ejecutar -> registrar.
    """
    if not _tiene_permiso_cambios_mapa(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    cama_id = request.POST.get("cama_id")
    accion = (request.POST.get("accion") or "").strip().upper()
    observacion = (request.POST.get("observacion") or "").strip()
    ingreso_observado_id = request.POST.get("ingreso_observado_id") or None
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar cama_id."}, status=400)

    acciones_validas = {
        "CONFIRMAR",
        "CONFIRMAR_ALTA",
        "CANCELAR_PREALTA",
        "CAMBIO_TRASLADO",
        "ASIGNACION",
        "ALTA_FORZADA",
    }
    if accion not in acciones_validas:
        return JsonResponse({"ok": False, "error": "Accion de mapeo no valida."}, status=400)

    # [2026-05-19] Whitelist de acciones permitidas para rol de intentos
    # dentro del flujo de mapeo por cama.
    if _es_rol_intentos_restringido(request.user):
        acciones_permitidas_rol = {"CONFIRMAR", "CAMBIO_TRASLADO", "CONFIRMAR_ALTA", "ALTA_FORZADA"}
        if accion not in acciones_permitidas_rol:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Este rol solo puede confirmar, mover pacientes o liberar camas en el flujo de mapeo.",
                },
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
    # [2026-05-22] La cama pertenece al servicio de su sala (cama.sala), no al del cubículo.
    # Un cubículo puede estar físicamente en otra sala sin cambiar la propiedad de la cama.
    sala_real = cama.sala
    if servicios_ids_sesion and sala_real.servicio_id not in servicios_ids_sesion:
        # [2026-05-07] La cama debe pertenecer a uno de los servicios seleccionados en la sesion.
        return JsonResponse(
            {"ok": False, "error": "La cama seleccionada no pertenece a los servicios de esta sesion de mapeo."},
            status=403,
        )

    asig_actual = (
        AsignacionCamaPaciente.objects.select_related("ingreso")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    ingreso_observado = None
    
    if ingreso_observado_id:
        # [2026-05-26 REFACTOR FINAL] Requiere ingreso_id explícitamente para acción.
        ingreso_observado = _resolver_ingreso_operativo(ingreso_id=ingreso_observado_id)
        if not ingreso_observado:
            return JsonResponse({"ok": False, "error": "Ingreso observado no existe."}, status=404)

    # Obtener instancias de estados
    estado_vacia = get_estado_mapeo("VACIA", "ESTADO_CAMA")
    estado_ocupada = get_estado_mapeo("OCUPADA", "ESTADO_CAMA")
    estado_alta = get_estado_mapeo("ALTA", "ESTADO_CAMA")
    
    # [2026-05-04 AUDIT] Bug Fix: estado_sistema es EstadoMapeo object.
    # Se serializa como .codigo en JsonResponse. No retornar el objeto directamente.
    estado_sistema = asig_actual.estado if asig_actual else estado_vacia

    with transaction.atomic():
        # Caso 1: todo correcto (sin cambios en sistema)
        if accion == "CONFIRMAR":
            # Auditoria de mapeo: aunque no haya cambios, se registra la validacion.
            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_sistema,
                estado_nuevo=estado_sistema,
                ingreso=asig_actual.ingreso if asig_actual else None,
                usuario=request.user,
                observacion=get_observacion_mapeo("Confirmacion de mapeo sin cambios"),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                hubo_cambio=False,
                observacion=get_observacion_mapeo(observacion or "Confirmacion de estado sin cambios."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cama confirmada sin cambios.", "estado_sistema": estado_sistema.codigo})

        # Caso 2A: sistema en ALTA (prealta) y paciente ya egreso.
        if accion == "CONFIRMAR_ALTA":
            if not asig_actual:
                return JsonResponse({"ok": False, "error": "No hay asignacion activa para confirmar alta."}, status=400)

            estado_anterior = asig_actual.estado
            asig_actual.estado = estado_vacia
            asig_actual.ingreso = None
            asig_actual.save()

            # [2026-05-22] Regla de negocio: confirmar alta no limpia cama en ingreso;
            # el ingreso debe conservar la última cama histórica.

            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_vacia,
                ingreso=None,
                usuario=request.user,
                observacion=get_observacion_mapeo("Confirmacion de alta desde mapeo"),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(observacion or "Confirmar alta (egreso)."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta confirmada. Cama liberada."})

        # Caso 2B: cancelar prealta (ALTA -> OCUPADA con mismo paciente)
        if accion == "CANCELAR_PREALTA":
            if not asig_actual or not asig_actual.ingreso_id:
                return JsonResponse({"ok": False, "error": "No existe ingreso actual para cancelar prealta."}, status=400)

            estado_anterior = asig_actual.estado
            asig_actual.estado = estado_ocupada
            asig_actual.save()

            # [2026-05-21] Cancelar prealta restablece cama en ingreso activo.
            _sincronizar_cama_en_ingreso_activo(
                ingreso_id=asig_actual.ingreso_id,
                cama_id=cama.pk,
            )

            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_ocupada,
                ingreso=asig_actual.ingreso,
                usuario=request.user,
                observacion=get_observacion_mapeo("Cancelar prealta desde mapeo"),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CORRECCION,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(observacion or "Cancelar prealta, paciente permanece."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Prealta cancelada. Cama en OCUPADA."})

        # Caso 3: paciente diferente (cambio/traslado)
        if accion == "CAMBIO_TRASLADO":
            if not ingreso_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar ingreso_observado_id para cambio/traslado."},
                    status=400,
                )

            # [2026-05-26 FEATURE] Rol de intentos: el cambio/traslado solo puede
            # involucrar ingresos cuyo último servicio registrado coincida con la cama actual.
            if _es_rol_intentos_restringido(request.user):
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
                            {
                                "ok": False,
                                "error": "Este rol solo puede realizar cambios de cama dentro del mismo servicio.",
                            },
                            status=403,
                        )

            limite_error = _validar_limite_intentos_salas(request.user, [sala_real.id])
            if limite_error:
                return limite_error

            if asig_actual and asig_actual.ingreso_id == ingreso_observado.id:
                # Auditoria de mapeo: se registra validacion aunque paciente y estado coincidan.
                _registrar_historial_mapeo(
                    cama=cama,
                    estado_anterior=estado_sistema,
                    estado_nuevo=estado_sistema,
                    ingreso=asig_actual.ingreso,
                    usuario=request.user,
                    observacion=get_observacion_mapeo("Confirmacion de mapeo sin cambios (paciente coincide)"),
                    sesion_mapeo=sesion,
                )

                _registrar_detalle_mapeo(
                    usuario=request.user,
                    cama=cama,
                    asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                    hubo_cambio=False,
                    observacion=get_observacion_mapeo(observacion or "Paciente coincide con sistema."),
                    sesion_mapeo=sesion,
                )
                return JsonResponse({"ok": True, "mensaje": "Sin cambios: paciente ya coincide con sistema."})

            estado_anterior = asig_actual.estado if asig_actual else estado_vacia
            if asig_actual and asig_actual.ingreso_id:
                asig_actual.estado = estado_vacia
                asig_actual.ingreso = None
                asig_actual.save()

            nueva_asig = AsignacionCamaPaciente.objects.create(
                cama=cama,
                ingreso=ingreso_observado,
                estado=estado_ocupada,
                usuario_asignacion=request.user,
            )

            # [2026-05-22] Regla de negocio: el paciente previo conserva su última cama
            # en ingreso, por lo que no se limpia la referencia al liberar en mapa.
            _sincronizar_cama_en_ingreso_activo(
                ingreso_id=ingreso_observado.id,
                cama_id=cama.pk,
            )

            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_ocupada,
                ingreso=ingreso_observado,
                usuario=request.user,
                observacion=get_observacion_mapeo(OBSERVACION_CAMBIO_TRASLADO_MAPEO),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=nueva_asig,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(observacion or "Cambio/traslado de paciente."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cambio/traslado aplicado correctamente."})

        # Caso 4: sistema libre, pero hay paciente real.
        if accion == "ASIGNACION":
            if not ingreso_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar ingreso_observado_id para asignacion."},
                    status=400,
                )

            if asig_actual and asig_actual.estado == estado_ocupada:
                return JsonResponse(
                    {"ok": False, "error": "La cama ya figura ocupada en sistema. Use CAMBIO_TRASLADO."},
                    status=400,
                )

            if asig_actual:
                asig_actual.estado = estado_ocupada
                asig_actual.ingreso = ingreso_observado
                asig_actual.usuario_asignacion = request.user
                asig_actual.save()
                asignacion_obj = asig_actual
            else:
                asignacion_obj = AsignacionCamaPaciente.objects.create(
                    cama=cama,
                    ingreso=ingreso_observado,
                    estado=estado_ocupada,
                    usuario_asignacion=request.user,
                )

            # [2026-05-21] Asignacion detectada en mapeo: persistir cama en ingreso activo.
            _sincronizar_cama_en_ingreso_activo(
                ingreso_id=ingreso_observado.id,
                cama_id=cama.pk,
            )

            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_vacia,
                estado_nuevo=estado_ocupada,
                ingreso=ingreso_observado,
                usuario=request.user,
                observacion=get_observacion_mapeo("Asignacion detectada durante mapeo"),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asignacion_obj,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(observacion or "Sistema libre, paciente presente (asignacion)."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Asignacion aplicada correctamente."})

        # Caso 5: sistema ocupado, pero cama vacia en la realidad.
        if accion == "ALTA_FORZADA":
            if not asig_actual or asig_actual.estado != estado_ocupada:
                return JsonResponse(
                    {"ok": False, "error": "No existe ocupacion activa para forzar alta."},
                    status=400,
                )

            asig_actual.estado = estado_vacia
            asig_actual.ingreso = None
            asig_actual.save()

            # [2026-05-22] Regla de negocio: en alta forzada la cama del ingreso
            # activo no se modifica; el ingreso debe conservar su cama histórica.

            _registrar_historial_mapeo(
                cama=cama,
                estado_anterior=estado_ocupada,
                estado_nuevo=estado_vacia,
                ingreso=None,
                usuario=request.user,
                observacion=get_observacion_mapeo("Alta forzada desde mapeo"),
                sesion_mapeo=sesion,
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=get_observacion_mapeo(observacion or "Sistema ocupado, cama vacia (alta forzada)."),
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta forzada aplicada. Cama liberada."})

    return JsonResponse({"ok": False, "error": "No se pudo procesar la accion solicitada."}, status=400)
