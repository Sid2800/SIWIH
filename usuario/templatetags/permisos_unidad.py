from django import template
from usuario.models import PerfilUnidad
from core.services.usuario_service import UsuarioService

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
    gbal = False

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True
    
    if user.es_global:
        gbal = True

    # Aseguramos que sea lista
    if isinstance(valores, str):
        valores = valores.split(',')

    for valor in valores:
        try:
            rol, unidad = valor.split(':', 1)
            if gbal:
                if PerfilUnidad.objects.filter(usuario=user, rol=rol, ).exists():
                    return True
            else:
                if PerfilUnidad.objects.filter(usuario=user, rol=rol, servicio_unidad__nombre_unidad=unidad).exists():
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
    
    if user.es_global:
        return True

    # Separar unidades por ':'
    unidades = unidades_str.split(':')

    for unidad in unidades:
        unidad = unidad.strip()
        if not unidad:
            continue

        if PerfilUnidad.objects.filter(
            usuario=user,
            servicio_unidad__nombre_unidad=unidad
        ).exists():
            return True

    return False