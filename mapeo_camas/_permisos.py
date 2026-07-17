# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Helpers de permisos del flujo de mapeo de camas.

Centraliza la verificación de roles/unidades y la lógica del límite de
intentos por servicio que aplica a roles restringidos.
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
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)
from core.services.usuario_service import UsuarioService
from usuario.permisos import verificar_permisos_usuario

from mapeo_camas.models import HistorialEstadoCama, MapeoSesionCama
from servicio.models import Sala

from core.constants.mapeo_camas_constants import (
    MAX_CAMBIOS_CAMA,
    OBSERVACION_CAMBIO_TRASLADO_MAPEO,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
    OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE,
    VENTANA_LIMITE_CAMBIOS_SALA_HORAS,
)
from ._sesion import _obtener_sesion_mapeo_activa

# [2026-06-12] Flujo interno del módulo:
# 1) Permisos base por capacidad (ver, cambiar, mapear, dashboard).
# 2) Resolución del contexto real de trabajo (sala/servicio).
# 3) Aplicación de límite operativo para perfiles restringidos.
# 4) Respuesta uniforme con JsonResponse cuando se rebasa el límite.

# [2026-05-19] Helpers de permisos para mantener una sola fuente de verdad.
def _tiene_permiso_visualizacion_mapa(usuario):
    """Permite acceso de solo lectura al template y data del mapa."""
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_VISUALIZACION_ROLES,
        MAPEO_CAMAS_VISUALIZACION_UNIDADES,
    )


# [2026-06-22 AUDIT] Historiales y dashboard quedaron definidos como acceso especial:
# solo superusuario o cualquier perfil con alcance GLOBAL, sin permiso extra.
def _tiene_acceso_global_mapeo(usuario):
    return bool(usuario and (usuario.is_superuser or UsuarioService.es_global(usuario)))


def _tiene_acceso_edicion_global_mapeo(usuario):
    """Permite escritura completa solo a superusuario o admin global."""
    return bool(usuario and (usuario.is_superuser or UsuarioService.es_admin_global(usuario)))


def _tiene_permiso_historiales(usuario):
    """Permite acceso de solo visualización al mapa e historiales."""
    return _tiene_acceso_global_mapeo(usuario)


def _tiene_permiso_cambios_mapa(usuario):
    """Permite cambios manuales de estado/movimiento en camas."""
    # [2026-07-17] Solo admin global puede escribir fuera del rol/unidad.
    if _tiene_acceso_edicion_global_mapeo(usuario):
        return True
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_CAMBIOS_ROLES,
        MAPEO_CAMAS_CAMBIOS_UNIDADES,
    )


def _tiene_permiso_mapear(usuario):
    """Permite iniciar/finalizar/cancelar sesiones de mapeo."""
    # [2026-07-17] Solo admin global puede gestionar sesiones de mapeo.
    if _tiene_acceso_edicion_global_mapeo(usuario):
        return True
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_MAPEAR_ROLES,
        MAPEO_CAMAS_MAPEAR_UNIDADES,
    )


# [2026-05-28] MC-PERM-007: helper específico del dashboard, separado de historiales
# para evitar acoplamiento de permisos entre auditoría y monitoreo operativo.
def _tiene_permiso_dashboard(usuario):
    """Permite acceso al dashboard operativo de KPIs/gráficas en tiempo real."""
    return _tiene_acceso_global_mapeo(usuario)


# [2026-05-28] FIX: los endpoints de edición de cama desde el mapa (actualizar_cama_mapa,
# mover_paciente_cama) son compartidos por dos flujos:
#   1) Edición MANUAL fuera de mapeo → requiere MAPEO_CAMAS_CAMBIOS_*.
#   2) Edición DENTRO de una sesión activa de mapeo → requiere MAPEO_CAMAS_MAPEAR_*
#      y que el usuario tenga sesión EN_PROGRESO.
def _puede_editar_cama_en_mapa(usuario):
    """Determina si el usuario puede editar camas desde el mapa.

    Flujo:
    1) Si tiene permiso de cambios manuales, permite edición directa.
    2) Si no, valida permiso de mapeo y sesión activa EN_PROGRESO.
    3) Si ninguna condición se cumple, deniega.
    """
    if _tiene_permiso_cambios_mapa(usuario):
        return True
    if _tiene_permiso_mapear(usuario) and _obtener_sesion_mapeo_activa(usuario) is not None:
        return True
    return False


def _puede_gestionar_sesion_mapeo(usuario):
    """Permite administrar sesión de mapeo a quien tenga permiso MAPEAR_*.

    [2026-06-11] El acceso al flujo de mapeo se rige por MAPEO_CAMAS_MAPEAR_*;
    las restricciones de intentos aplican a movimientos/edición, no al botón de sesión.
    """
    return _tiene_permiso_mapear(usuario)


def _puede_cancelar_mapeo(usuario):
    """Permite cancelar/finalizar sesiones de mapeo de otros usuarios.
    
    [2026-07-17] Acceso para: superusuario o admin global.
    El directivo global queda en modo lectura y no puede cancelar mapeos ajenos.
    """
    if _tiene_acceso_edicion_global_mapeo(usuario):
        return True
    return verificar_permisos_usuario(
        usuario,
        ["admin"],
        MAPEO_CAMAS_MAPEAR_UNIDADES,
    )


def _puede_cancelar_mapeo_banner(usuario):
    """Permite mostrar el botón de cancelar en alerta de mapeos ajenos.

    [2026-07-17] Regla UI: solo superusuario o admin global.
    """
    return _tiene_acceso_edicion_global_mapeo(usuario)


# [2026-05-07] Helper para calcular inicio de ventana de límite de movimientos
def _inicio_ventana_limite_sala():
    """Calcula el datetime de inicio de la ventana temporal para el conteo de cambios."""
    return timezone.now() - timedelta(hours=VENTANA_LIMITE_CAMBIOS_SALA_HORAS)


def _filtro_observaciones_movimiento_limite():
    """Filtro para contar SOLO MOVIMIENTOS que consumen límite por sala.
    
    [2026-07-09] DIAGNÓSTICO BD COMPLETADO:
    - MOV_PAC: Movimiento inter-servicio (diferentes salas) → CUENTA ✓
    - MOV_PAC_DETALLE: Movimiento intra-servicio (misma sala) → NO CUENTA ✗
    - CAMBIO_TRASLADO_MAPEO: Movimiento en sesión mapeo → CUENTA ✓
    - MOV_PAC_SUPERADMIN: Movimiento admin → NO CUENTA ✗
    
    Se excluyen intra-servicio (MOV_PAC_DETALLE) y cambios de estado sin movimiento.
    Datos BD: Servicio 200 tiene 12 MOV_PAC + 6 MOV_PAC_DETALLE.
    Solo los 12 MOV_PAC deberían contar en el límite.
    """
    return Q(observacion__codigo__in=[
        OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,          # MOV_PAC: inter-servicio
        OBSERVACION_CAMBIO_TRASLADO_MAPEO,             # Cambio traslado en mapeo
    ])


# [2026-06-12] Refactor: centralizar conteo por servicio para evitar duplicación.
def _contar_cambios_por_servicio(servicio_id):
    """Cuenta cambios efectivos de cama dentro de la ventana por servicio.

    Considera solo observaciones que consumen límite operativo y descarta
    transiciones sin cambio real de estado.
    """
    if not servicio_id:
        return 0

    return (
        HistorialEstadoCama.objects.annotate(
            # [2026-05-22] Usar siempre cama.sala; el cubículo es solo ubicación física.
            servicio_real_id=F("cama__sala__servicio_id")
        )
        .filter(
            servicio_real_id=servicio_id,
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .filter(_filtro_observaciones_movimiento_limite())
        .exclude(estado_anterior=F("estado_nuevo"))
        .count()
    )


# [2026-06-11] El limite operativo se mide por servicio completo, no por sala.
def _contar_cambios_manual_por_sala(sala_id):
    """Resuelve servicio desde sala y delega el conteo al helper central.

    Nota: el límite es por servicio completo, no por sala individual.
    """
    if not sala_id:
        return 0

    servicio_id = (
        Sala.objects
        .filter(pk=sala_id)
        .values_list("servicio_id", flat=True)
        .first()
    )
    if not servicio_id:
        return 0

    return _contar_cambios_por_servicio(servicio_id)


def _sala_real_id_desde_cama(cama):
    """Retorna la sala a la que pertenece la cama (siempre cama.sala)."""
    if not cama:
        return None
    return getattr(cama, "sala_id", None)


# [2026-05-18] Helper para decidir si aplica límite de intentos al usuario
def _aplica_limite_intentos(usuario):
    """Indica si al usuario le aplica límite de intentos operativos."""
    if not usuario or getattr(usuario, "is_superuser", False):
        return False
    return verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
        MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    )


def _max_cambios_para_usuario(usuario):
    """Devuelve el máximo permitido para UI/API o None si no aplica límite."""
    return MAX_CAMBIOS_CAMA if _aplica_limite_intentos(usuario) else None


def _es_rol_intentos_restringido(usuario):
    """Identifica al rol que solo puede mover pacientes y manejar pre-altas/altas."""
    return _aplica_limite_intentos(usuario)


def _validar_limite_intentos_salas(usuario, sala_ids):
    """Valida el límite operativo por servicio para usuarios con permiso limitado.

    Flujo:
    1) Omite validación para usuarios sin restricción.
    2) Traduce sala_ids a servicio_ids únicos.
    3) Cuenta cambios por servicio en ventana vigente.
    4) Retorna JsonResponse 400 si el límite fue alcanzado; en caso contrario None.
    """
    if not _aplica_limite_intentos(usuario):
        return None

    salas_validas = [sala_id for sala_id in set(sala_ids or []) if sala_id]
    servicio_ids = set(
        Sala.objects.filter(pk__in=salas_validas).values_list("servicio_id", flat=True)
    )

    for servicio_id in servicio_ids:
        cambios_realizados = _contar_cambios_por_servicio(servicio_id)
        if cambios_realizados >= MAX_CAMBIOS_CAMA:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        f"El servicio ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                        f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                    ),
                    "cambios_realizados": cambios_realizados,
                    "max_cambios": MAX_CAMBIOS_CAMA,
                },
                status=400,
            )

    return None


# [2026-07-09] Validación para bloquear cambios mientras hay mapeo en proceso
def _validar_mapeo_no_iniciado(usuario):
    """Valida que NO haya una sesión de mapeo en proceso (EN_PROGRESO).
    
    IMPORTANTE: Esta validación SOLO aplica a usuarios con rol/unidad MAPEO_CAMAS_INTENTOS_CAMBIO
    (digitador en ADMI/SALA). Los demás usuarios pueden hacer cambios libremente.
    
    Retorna JsonResponse 400 si existe una sesión activa y el usuario es restringido; 
    en caso contrario None.
    """
    # [2026-07-09] Validar explícitamente por permisos de intentos de cambio.
    if not usuario or getattr(usuario, "is_superuser", False):
        return None
    if not verificar_permisos_usuario(
        usuario,
        MAPEO_CAMAS_INTENTO_CAMBIO_ROLES,
        MAPEO_CAMAS_INTENTO_CAMBIO_UNIDADES,
    ):
        return None
    
    sesion_activa = MapeoSesionCama.objects.filter(
        estado__codigo="EN_PROGRESO",
        fecha_fin__isnull=True,
    ).exclude(usuario=usuario).order_by("-fecha_inicio").first()
    
    if sesion_activa:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    f"No se pueden realizar cambios mientras hay un mapeo en proceso. "
                    f"Iniciado por {sesion_activa.usuario.get_full_name()} "
                    f"a las {sesion_activa.fecha_inicio:%H:%M}."
                ),
                "sesion_id": sesion_activa.id,
            },
            status=400,
        )
    
    return None
