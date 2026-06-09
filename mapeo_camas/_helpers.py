# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Helpers de formateo, parseo y resolución compartidos por las vistas de mapeo_camas."""

from functools import lru_cache

from core.services.mapeo_camas_service import MapeoCamasService
from core.services.usuario_service import UsuarioService
from core.utils.utilidades_fechas import hora_local_iso, parse_fecha_filtro_dia
from core.utils.utilidades_request import parse_json_request
from core.utils.utilidades_textos import (
    construir_nombre_dinamico,
    formatear_nombre_completo,
)
from ingreso.models import Ingreso


__all__ = [
    "get_estado_mapeo",
    "_nombre_paciente",
    "_nombre_usuario",
    "_hora_local_iso",
    "_paciente_payload",
    "_resolver_ingreso_operativo",
    "_observacion_codigo",
    "_normalizar_observacion_sesion",
    "_obtener_observacion_desde_request",
    "_es_superadmin",
    "_meta_ultima_actualizacion",
    "_parse_fecha_filtro",
    "_nombre_cama",
    "_ubicacion_desde_cama",
]


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


# 2026-05-29: alias local del helper global core.utils.utilidades_fechas.hora_local_iso
_hora_local_iso = hora_local_iso


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
    return {
        "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
        "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
    }


# 2026-05-29: alias local del helper global core.utils.utilidades_fechas.parse_fecha_filtro_dia
_parse_fecha_filtro = parse_fecha_filtro_dia


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
