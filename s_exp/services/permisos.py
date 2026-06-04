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
import logging

from usuario.models import PerfilUnidad

logger = logging.getLogger("s_exp")


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
            logger.warning(f"Usuario {user.username} (id={user.id}) no existe en rrhh_empleado")
            return False

        # Personal NO clínico con servicio_unidad asignado
        if PersonalNoClinico.objects.filter(
            empleado_id=empleado.id, servicio_unidad_id__isnull=False
        ).exists():
            logger.info(f"Usuario {user.username}: Validado - PersonalNoClinico con servicio_unidad")
            return True

        # Personal de salud con servicio_unidad asignado
        if PersonalSalud.objects.filter(
            empleado_id=empleado.id, servicio_unidad_id__isnull=False
        ).exists():
            logger.info(f"Usuario {user.username}: Validado - PersonalSalud con servicio_unidad")
            return True

        logger.warning(
            f"Usuario {user.username}: Empleado registrado pero sin "
            f"PersonalNoClinico/PersonalSalud o sin servicio_unidad asignado"
        )
        return False

    except Exception as e:
        logger.error(f"Error al validar RRHH para usuario {user.username}: {e}", exc_info=True)
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
            logger.warning(f"Usuario {user.username} (id={user.id}) no tiene registro en rrhh_empleado")
            return None, False

        # PersonalNoClinico
        pnc = PersonalNoClinico.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()
        if pnc:
            if pnc.servicio_unidad_id:
                logger.info(f"Usuario {user.username}: ServicioUnidad {pnc.servicio_unidad_id} desde PersonalNoClinico")
                return pnc.servicio_unidad, True
            logger.warning(f"Usuario {user.username}: PersonalNoClinico sin servicio_unidad asignado")
            return None, True  # registrado en RRHH pero sin unidad

        # PersonalSalud (alternativo)
        ps = PersonalSalud.objects.filter(
            empleado_id=empleado.id
        ).select_related('servicio_unidad').first()
        if ps:
            if ps.servicio_unidad_id:
                logger.info(f"Usuario {user.username}: ServicioUnidad {ps.servicio_unidad_id} desde PersonalSalud")
                return ps.servicio_unidad, True
            logger.warning(f"Usuario {user.username}: PersonalSalud sin servicio_unidad asignado")
            return None, True

        logger.warning(f"Usuario {user.username}: Empleado registrado pero sin PersonalNoClinico ni PersonalSalud")
        return None, True

    except Exception as e:
        logger.error(f"Error al verificar RRHH para usuario {user.username}: {e}", exc_info=True)
        return None, False
