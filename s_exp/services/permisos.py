"""
Servicio de permisos y resolución de unidad del usuario (módulo s_exp).
=============================================================================

Centraliza la verificación de acceso al módulo de Solicitud de Expedientes y
la resolución de la unidad de servicio del usuario vía la cadena RRHH.

Cadena RRHH (fuente de verdad para "quién puede acceder y desde qué unidad"):
    auth_user
      → rrhh_empleado (usuario_id)
        → rrhh_personalnoclinico  O  rrhh_personalsalud (empleado_id)
          → servicio_unidad_id

Estas funciones se importan desde las vistas. Tener la lógica aquí evita
duplicarla y mantiene las vistas delgadas.
"""

from usuario.models import PerfilUnidad

from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


def es_usuario_valido_rrhh(user):
    """
    Verifica que el usuario esté COMPLETAMENTE registrado en la cadena RRHH.
    Es el requisito previo para CUALQUIER acceso al módulo s_exp.

    Valida:
      1. Existe en rrhh_empleado (usuario_id = user.id)
      2. Existe en rrhh_personalnoclinico O rrhh_personalsalud (empleado_id)
      3. Tiene servicio_unidad_id asignado en uno de los dos

    Returns:
        bool: True si está completamente registrado, False en caso contrario.
    """
    from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud

    try:
        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if not empleado:
            log_warning(f"Usuario {user.username} (id={user.id}) no existe en rrhh_empleado", app=LogApp.S_EXP)
            return False

        # Personal NO clínico con servicio_unidad asignado
        if PersonalNoClinico.objects.filter(
            empleado_id=empleado.id, servicio_unidad_id__isnull=False
        ).exists():
            log_info(f"Usuario {user.username}: Validado - PersonalNoClinico con servicio_unidad", app=LogApp.S_EXP)
            return True

        # Personal de salud con servicio_unidad asignado
        if PersonalSalud.objects.filter(
            empleado_id=empleado.id, servicio_unidad_id__isnull=False
        ).exists():
            log_info(f"Usuario {user.username}: Validado - PersonalSalud con servicio_unidad", app=LogApp.S_EXP)
            return True

        log_warning(f"Usuario {user.username}: Empleado registrado pero sin PersonalNoClinico/PersonalSalud o sin servicio_unidad asignado", app=LogApp.S_EXP)
        return False

    except Exception as e:
        log_error(f"Error al validar RRHH para usuario {user.username}: {e}", app=LogApp.S_EXP)
        return False


def es_exp_admin(user):
    """
    True si el usuario tiene permisos ADMINISTRATIVOS sobre el módulo.
    Requisitos:
      - Estar registrado en RRHH (es_usuario_valido_rrhh)
      - Ser superuser/staff, estar en grupo 'administradores',
        o tener rol admin/digitador/directivo en PerfilUnidad.
    """
    if not es_usuario_valido_rrhh(user):
        return False

    if user.is_superuser or user.is_staff:
        return True
    if user.groups.filter(name='administradores').exists():
        return True
    return PerfilUnidad.objects.filter(
        usuario=user,
        rol__in=['admin', 'digitador', 'directivo']
    ).exists()


def puede_recuperar_expedientes(user):
    """
    True si el usuario puede RECUPERAR expedientes de urgencia (forzar su
    devolución inmediata a Admisión, saltándose el flujo normal).

    Es un permiso distinto de es_exp_admin: aquella incluye a digitadores y
    directivos de CUALQUIER unidad, y esta acción solo corresponde a Admisión
    (son quienes reciben físicamente el expediente).

    Se permite a:
      - superuser / staff
      - usuarios "globales" con alguno de S_EXP_RECUPERACION_ROLES (misma regla
        que el filtro tiene_rol: un usuario global no se ata a una unidad)
      - rol de S_EXP_RECUPERACION_ROLES (admin/digitador) en una unidad de
        S_EXP_RECUPERACION_UNIDADES (ADMI)

    Se incluye 'digitador' porque el personal real de Admisión tiene ese rol;
    con solo 'admin' el permiso dejaría fuera a quienes deben usarlo.

    El código de unidad ('ADMI') se compara contra
    servicio_unidad.nombre_corto_unidad, igual que el filtro tiene_rol (la tabla
    de unidades no tiene campo 'codigo').
    """
    from core.constants.permisos import (
        S_EXP_ADMIN_ROLES, S_EXP_RECUPERACION_ROLES, S_EXP_RECUPERACION_UNIDADES,
    )
    from core.services.usuario_service import UsuarioService

    if not user or not user.is_authenticated:
        return False
    # Staff/superuser siempre: administran el sistema completo.
    if user.is_superuser or user.is_staff:
        return True
    if not es_usuario_valido_rrhh(user):
        return False

    qs = PerfilUnidad.objects.filter(usuario=user, rol__in=S_EXP_RECUPERACION_ROLES)

    # Un usuario "global" no se ata a una unidad (misma idea que el filtro
    # tiene_rol). Aquí ese salto se limita al rol ADMIN a propósito: un
    # 'digitador' global de otra área (p. ej. Calidad) NO es personal de
    # Admisión y no debe poder forzar la devolución de un expediente.
    try:
        if UsuarioService.es_global(user) and qs.filter(rol__in=S_EXP_ADMIN_ROLES).exists():
            return True
    except Exception:
        pass

    return qs.filter(
        servicio_unidad__nombre_corto_unidad__in=S_EXP_RECUPERACION_UNIDADES
    ).exists()


def es_exp_solicitante(user):
    """
    True si el usuario puede SOLICITAR expedientes.
    Requisitos:
      - Estar registrado en RRHH
      - Ser admin del módulo, o tener rol 'exp_solicitante' en PerfilUnidad.
    """
    if not es_usuario_valido_rrhh(user):
        return False
    if es_exp_admin(user):
        return True
    return PerfilUnidad.objects.filter(usuario=user, rol='exp_solicitante').exists()


def get_unidad_usuario(user):
    """
    Devuelve el NOMBRE de la unidad del usuario con cascada de resolución:
      1. PerfilUnidad (sistema de roles del módulo s_exp)
      2. Cadena RRHH (Empleado → PersonalNoClinico/PersonalSalud → servicio_unidad)

    Cubre solicitantes (suelen tener PerfilUnidad) y admins/digitadores
    (suelen estar solo en RRHH). Devuelve '' si no se encuentra.
    """
    # 1) PerfilUnidad
    perfil = PerfilUnidad.objects.filter(usuario=user).select_related('servicio_unidad').first()
    if perfil and perfil.servicio_unidad:
        return perfil.servicio_unidad.nombre_unidad

    # 2) Cadena RRHH (reutiliza el resolver del servicio de datos)
    try:
        from s_exp.services.datos_solicitud import UbicacionUsuario
        unidad = UbicacionUsuario.resolver(user)
        if unidad:
            return unidad.nombre_unidad
    except Exception:
        pass

    return ''


def get_servicio_unidad_from_rrhh(user):
    """
    Obtiene la Unidad de Servicio (instancia) del usuario vía la cadena RRHH,
    verificando explícitamente cada paso.

    Returns:
        tuple (servicio_unidad_obj, es_valido):
          - servicio_unidad_obj: instancia de servicio.Unidad, o None.
          - es_valido: True si el usuario está registrado en RRHH, False si no.
    """
    from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud

    try:
        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if not empleado:
            log_warning(f"Usuario {user.username} (id={user.id}) no tiene registro en rrhh_empleado", app=LogApp.S_EXP)
            return None, False

        # PersonalNoClinico
        pnc = PersonalNoClinico.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()
        if pnc:
            if pnc.servicio_unidad_id:
                log_info(f"Usuario {user.username}: ServicioUnidad {pnc.servicio_unidad_id} desde PersonalNoClinico", app=LogApp.S_EXP)
                return pnc.servicio_unidad, True
            log_warning(f"Usuario {user.username}: PersonalNoClinico sin servicio_unidad asignado", app=LogApp.S_EXP)
            return None, True  # registrado en RRHH pero sin unidad

        # PersonalSalud (alternativo)
        ps = PersonalSalud.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()
        if ps:
            if ps.servicio_unidad_id:
                log_info(f"Usuario {user.username}: ServicioUnidad {ps.servicio_unidad_id} desde PersonalSalud", app=LogApp.S_EXP)
                return ps.servicio_unidad, True
            log_warning(f"Usuario {user.username}: PersonalSalud sin servicio_unidad asignado", app=LogApp.S_EXP)
            return None, True

        log_warning(f"Usuario {user.username}: Empleado registrado pero sin PersonalNoClinico ni PersonalSalud", app=LogApp.S_EXP)
        return None, True

    except Exception as e:
        log_error(f"Error al verificar RRHH para usuario {user.username}: {e}", app=LogApp.S_EXP)
        return None, False
