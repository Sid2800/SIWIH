# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Helpers compartidos por las vistas de mapeo_camas."""

from datetime import datetime
from functools import lru_cache

from django.db.models import OuterRef, Subquery
from django.http import JsonResponse
from django.utils import timezone

from core.services.mapeo_camas_service import MapeoCamasService
from core.services.usuario_service import UsuarioService
from core.utils.utilidades_fechas import hora_local_iso
from core.utils.utilidades_request import parse_json_request
from core.utils.utilidades_textos import (
    construir_nombre_dinamico,
    formatear_nombre_completo,
)
from ingreso.models import Ingreso
from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama

# 2026-06-09: compatibilidad temporal con imports existentes en core/services.
# Mantiene alineación porque delega al helper general de core.utils.utilidades_fechas.
_hora_local_iso = hora_local_iso


# Helper global para obtener instancias de EstadoMapeo
# 2026-05-29: delega en MapeoCamasService.get_estado_mapeo (core) manteniendo el lru_cache
# local para evitar consultas repetidas en bucles calientes.
@lru_cache(maxsize=64)
def get_estado_mapeo(codigo, categoria):
    return MapeoCamasService.get_estado_mapeo(codigo, categoria)


# 2026-05-29: delega en core.utils.utilidades_textos.formatear_nombre_completo
def _nombre_paciente(paciente):
    """Nombre completo del paciente; 'Sin nombre' si todos los campos están vacíos."""
    nombre = formatear_nombre_completo(
        getattr(paciente, "primer_nombre", ""),
        getattr(paciente, "segundo_nombre", ""),
        getattr(paciente, "primer_apellido", ""),
        getattr(paciente, "segundo_apellido", ""),
    )
    return nombre or "Sin nombre"


# 2026-05-29: delega en core.utils.utilidades_textos.construir_nombre_dinamico
def _nombre_usuario(usuario):
    """Nombre visible del usuario; usa username como fallback."""
    if not usuario:
        return ""
    return construir_nombre_dinamico(usuario, ["first_name", "last_name"]) or getattr(usuario, "username", "") or ""


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

    # 2026-05-29: reutiliza core.utils.utilidades_request.parse_json_request
    try:
        payload = parse_json_request(request)
    except ValueError:
        payload = {}
    return payload.get("observacion")


# 2026-06-01: reutiliza helper global existente en UsuarioService; evita mantener utilidades_usuario.py.
def _es_superadmin(usuario):
    return bool(usuario and UsuarioService.es_global_roles(usuario))


def _meta_ultima_actualizacion(historial):
    """Serializa metadatos de la ultima actualizacion de una cama."""
    if not historial:
        return {
            "ultima_actualizacion": "",
            "usuario_ultima_actualizacion": "",
        }
    # 2026-06-09: usa helper general de core para formato de fecha local.
    return {
        "ultima_actualizacion": hora_local_iso(historial.fecha_hora),
        "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
    }


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


def _dashboard_response(data, meta=None):
    """Envoltura estándar de respuesta para endpoints del dashboard."""
    # 2026-06-09: unificado en _helpers.py para mantener un único módulo de helpers.
    payload = {
        "ok": True,
        "ts": hora_local_iso(timezone.now()),
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return JsonResponse(payload)


def _dashboard_error(msg, status=500):
    """Respuesta de error uniforme para el dashboard."""
    return JsonResponse(
        {"ok": False, "error": str(msg), "ts": hora_local_iso(timezone.now())},
        status=status,
    )


def _dashboard_parse_range(request):
    """Parsea ?desde=ISO&hasta=ISO y devuelve (desde, hasta) aware."""
    tz = timezone.get_current_timezone()
    ahora = timezone.localtime(timezone.now())

    def _parse(s):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, tz)
        return dt

    desde = _parse(request.GET.get("desde"))
    hasta = _parse(request.GET.get("hasta"))

    if desde is None:
        desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    if hasta is None:
        hasta = ahora
    if hasta < desde:
        desde, hasta = hasta, desde
    return desde, hasta


def _dashboard_granularidad(desde, hasta):
    """hora si span <= 2 días, día si <= 60 días, mes si >."""
    span = hasta - desde
    if span.total_seconds() <= 2 * 86400:
        return "hora"
    if span.days <= 60:
        return "dia"
    return "mes"


def _snapshot_estado_camas(hasta):
    """{codigo_estado: cantidad} usando solo fuentes del módulo mapeo_camas."""
    estado_por_cama = _snapshot_estado_por_cama(hasta)
    conteo = {}
    for cod in estado_por_cama.values():
        cod = cod or "VACIA"
        conteo[cod] = conteo.get(cod, 0) + 1
    return conteo


def _snapshot_estado_por_cama(hasta):
    """{cama_id: codigo_estado} en el momento hasta usando tablas de mapeo_camas."""
    ultima_asig_id = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=OuterRef("cama_id"), fecha_inicio__lte=hasta)
        .order_by("-fecha_inicio", "-id")
        .values("id")[:1]
    )

    estado_por_cama = {
        r["cama_id"]: (r["estado_nuevo__codigo"] or "VACIA")
        for r in HistorialEstadoCama.objects
        .filter(id=Subquery(
            HistorialEstadoCama.objects
            .filter(cama_id=OuterRef("cama_id"), fecha_hora__lte=hasta)
            .order_by("-fecha_hora", "-id")
            .values("id")[:1]
        ))
        .values("cama_id", "estado_nuevo__codigo")
    }

    for row in (
        AsignacionCamaPaciente.objects
        .filter(id=Subquery(ultima_asig_id))
        .values("cama_id", "estado__codigo")
    ):
        estado_por_cama[row["cama_id"]] = row["estado__codigo"] or "VACIA"

    return estado_por_cama


def _rango_meta(desde, hasta):
    """Meta serializable del rango aplicado."""
    return {
        "desde": hora_local_iso(desde),
        "hasta": hora_local_iso(hasta),
        "granularidad": _dashboard_granularidad(desde, hasta),
    }
