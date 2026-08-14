"""
Permisos del módulo de Egresos.

Sigue EXACTAMENTE el mismo patrón que s_exp (basado en el resto de módulos):
requiere estar registrado en la cadena RRHH y luego valida rol+unidad, con
staff/superuser y el grupo 'administradores' con acceso total. No se crea un
mecanismo nuevo: se reutiliza la validación RRHH de s_exp y las constantes de
core.constants.permisos.

Quién accede:
  - Estadística (unidad 'EST'): llena/gestiona los egresos.
  - staff / superuser / grupo 'administradores': acceso y visualización TOTAL.
"""
from usuario.models import PerfilUnidad
# Reutilizamos la validación de la cadena RRHH ya existente (no se duplica).
from s_exp.services.permisos import es_usuario_valido_rrhh
from core.constants.permisos import EGRESOS_EDITOR_ROLES, EGRESOS_EDITOR_UNIDADES


def es_staff_total(user):
    """
    Acceso TOTAL sin importar unidad: superuser, staff o grupo 'administradores'.
    Es el mismo criterio 'staff' que usan los demás módulos.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='administradores').exists()


def puede_acceder_egresos(user):
    """
    True si el usuario puede usar el módulo de Egresos.

    - staff/superuser/administradores: siempre (visualización y acceso total).
    - Estadística: registrado en RRHH y con rol de EGRESOS_EDITOR_ROLES en una
      unidad de EGRESOS_EDITOR_UNIDADES ('EST').

    El código de unidad ('EST') se compara contra nombre_corto_unidad, igual que
    el filtro tiene_rol y el permiso de recuperación de s_exp.
    """
    if not user or not user.is_authenticated:
        return False
    if es_staff_total(user):
        return True
    if not es_usuario_valido_rrhh(user):
        return False
    return PerfilUnidad.objects.filter(
        usuario=user,
        rol__in=EGRESOS_EDITOR_ROLES,
        servicio_unidad__nombre_corto_unidad__in=EGRESOS_EDITOR_UNIDADES,
    ).exists()
