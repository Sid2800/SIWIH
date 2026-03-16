from usuario.models import PerfilUnidad


def verificar_permisos(user, roles=None, unidades=None):
    """
    Verifica si un usuario tiene permisos en base a roles y/o unidades.
    
    - Si es superusuario: siempre True
    - roles puede ser lista, tupla o set
    - unidades puede ser lista, tupla o set
    - Si ambos son None → False (no hay criterios)
    """

    if user.is_superuser:
        return True

    filtros = {"usuario": user}

    if roles:
        filtros["rol__in"] = roles

    if unidades:
        filtros["unidad__nombre_unidad__in"] = unidades

    print(filtros)

    if len(filtros) == 1:  # solo tiene {"usuario": user}
        # No tiene sentido verificar sin roles ni unidades
        return False

    return PerfilUnidad.objects.filter(**filtros).exists()


def verificar_permisos_usuario(user, required_roles, required_unidades):
    return verificar_permisos(user, roles=required_roles, unidades=required_unidades)


def verificar_permisos_dispensacion(user, required_roles, required_unidades):
    return verificar_permisos(user, roles=required_roles, unidades=required_unidades)
