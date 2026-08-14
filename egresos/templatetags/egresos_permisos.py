"""Filtro de plantilla para gatear el acceso al módulo de Egresos."""
from django import template

register = template.Library()


@register.filter
def puede_egresos(user):
    """
    True si el usuario puede acceder a Egresos (Estadística o staff).
    Delega en el servicio, única fuente de la verdad de esta regla.

    Uso:  {% load egresos_permisos %}  {% if request.user|puede_egresos %}
    """
    from egresos.services.permisos import puede_acceder_egresos
    try:
        return puede_acceder_egresos(user)
    except Exception:
        return False
