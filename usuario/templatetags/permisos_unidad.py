from django import template
from usuario.models import PerfilUnidad

register = template.Library()

@register.filter
def tiene_rol(user, valores):
    """
    Recibe un valor o una lista de valores separados por coma.
    Cada valor debe tener formato "ROL:UNIDAD".
    Devuelve True si el usuario tiene alguno de ellos.
    
    Ejemplos:
        "auditor:DIRECTIVOS"
        "ADMIN:Admision,digitador:Admision,auditor:DIRECTIVOS"
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Aseguramos que sea lista
    if isinstance(valores, str):
        valores = valores.split(',')

    for valor in valores:
        try:
            rol, unidad = valor.split(':', 1)
            if PerfilUnidad.objects.filter(usuario=user, rol=rol, unidad__nombre_unidad=unidad).exists():
                return True
        except ValueError:
            continue

    return False
    


@register.filter
def tiene_unidad(user, unidades_str):
    """
    Uso:
        user|tiene_unidad:"imagenologia"
        user|tiene_unidad:"imagenologia:Referencia:DIRECTIVOS"
    Evalúa si el usuario pertenece a cualquiera de esas unidades.
    """

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Separar unidades por ':'
    unidades = unidades_str.split(':')

    for unidad in unidades:
        unidad = unidad.strip()
        if not unidad:
            continue

        if PerfilUnidad.objects.filter(
            usuario=user,
            unidad__nombre_unidad=unidad
        ).exists():
            return True

    return False


@register.filter
def en_grupo(user, grupos_str):
    """
    Verifica si el usuario pertenece a alguno de los grupos indicados.
    Uso:
        user|en_grupo:"Solicitantes"
        user|en_grupo:"Solicitantes:Exp_Administradores"
    Superusuarios y staff siempre retornan True.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    grupos = [g.strip() for g in grupos_str.split(':') if g.strip()]
    return user.groups.filter(name__in=grupos).exists()


@register.filter
def tiene_rol_global(user, roles_str):
    """
    Verifica si el usuario tiene alguno de los roles indicados en CUALQUIER unidad.
    Uso:
        user|tiene_rol_global:"exp_solicitante"
        user|tiene_rol_global:"exp_solicitante:admin"
    Superusuarios y staff siempre retornan True.
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    roles = [r.strip() for r in roles_str.split(':') if r.strip()]
    return PerfilUnidad.objects.filter(usuario=user, rol__in=roles).exists()