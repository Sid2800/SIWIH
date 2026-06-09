# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Helpers de permisos del flujo de mapeo de camas.

Centraliza la verificación de roles/unidades y la lógica del límite de
intentos por sala que aplica a roles restringidos.
"""

from datetime import timedelta

from django.db.models import F, Q
from django.http import JsonResponse
from django.utils import timezone

from core.constants.permisos import (
    MAPEO_CAMAS_CAMBIOS_ROLES,
    MAPEO_CAMAS_CAMBIOS_UNIDADES,
    MAPEO_CAMAS_DASHBOARD_ROLES,
    MAPEO_CAMAS_DASHBOARD_UNIDADES,
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
    MAPEO_CAMAS_INTENTOS_CAMBIO_ROLES as MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
    MAPEO_CAMAS_INTENTOS_CAMBIO_UNIDADES as MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    MAPEO_CAMAS_MAPEAR_ROLES,
    MAPEO_CAMAS_MAPEAR_UNIDADES,
)
from usuario.permisos import verificar_permisos_usuario

from mapeo_camas.models import HistorialEstadoCama

from ._constants import (
    MAX_CAMBIOS_CAMA,
    OBSERVACION_CAMBIO_TRASLADO_MAPEO,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
    VENTANA_LIMITE_CAMBIOS_SALA_HORAS,
)
from ._sesion import _obtener_sesion_mapeo_activa


__all__ = [
    "_tiene_permiso_historiales",
    "_tiene_permiso_cambios_mapa",
    "_tiene_permiso_mapear",
    "_tiene_permiso_dashboard",
    "_puede_editar_cama_en_mapa",
    "_puede_gestionar_sesion_mapeo",
    "_inicio_ventana_limite_sala",
    "_filtro_observaciones_movimiento_limite",
    "_contar_cambios_manual_por_sala",
    "_sala_real_id_desde_cama",
    "_aplica_limite_intentos",
    "_max_cambios_para_usuario",
    "_es_rol_intentos_restringido",
    "_validar_limite_intentos_salas",
]


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


# [2026-05-28] MC-PERM-007: helper específico del dashboard, separado de historiales
# para evitar acoplamiento de permisos entre auditoría y monitoreo operativo.
def _tiene_permiso_dashboard(usuario):
    """Permite acceso al dashboard operativo de KPIs/gráficas en tiempo real."""
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_DASHBOARD_ROLES,
        MAPEO_CAMAS_DASHBOARD_UNIDADES,
    )


# [2026-05-28] FIX: los endpoints de edición de cama desde el mapa (actualizar_cama_mapa,
# mover_paciente_cama) son compartidos por dos flujos:
#   1) Edición MANUAL fuera de mapeo → requiere MAPEO_CAMAS_CAMBIOS_*.
#   2) Edición DENTRO de una sesión activa de mapeo → requiere MAPEO_CAMAS_MAPEAR_*
#      y que el usuario tenga sesión EN_PROGRESO.
def _puede_editar_cama_en_mapa(usuario):
    if _tiene_permiso_cambios_mapa(usuario):
        return True
    if _tiene_permiso_mapear(usuario) and _obtener_sesion_mapeo_activa(usuario) is not None:
        return True
    return False


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
    """Retorna la sala a la que pertenece la cama (siempre cama.sala)."""
    if not cama:
        return None
    return getattr(cama, "sala_id", None)


# [2026-05-18] Helper para decidir si aplica límite de intentos al usuario
def _aplica_limite_intentos(usuario):
    if not usuario or getattr(usuario, "is_superuser", False):
        return False
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
        MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    )


def _max_cambios_para_usuario(usuario):
    return MAX_CAMBIOS_CAMA if _aplica_limite_intentos(usuario) else None


def _es_rol_intentos_restringido(usuario):
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
