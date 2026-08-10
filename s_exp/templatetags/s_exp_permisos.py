"""
Filtros de plantilla para los permisos del módulo s_exp.

Existen para que las plantillas usen EXACTAMENTE la misma regla que el backend,
sin reescribirla con `tiene_rol` (que no contempla is_staff y obligaría a
duplicar la lista de roles/unidades en el HTML).
"""
from django import template

register = template.Library()


@register.filter
def puede_recuperar(user):
    """
    True si el usuario puede recuperar expedientes de urgencia (Admisión).

    Delega en s_exp.services.permisos.puede_recuperar_expedientes, que es la
    única fuente de verdad de esta regla (la usan también la vista y las APIs).

    Uso en plantilla:
        {% load s_exp_permisos %}
        {% if request.user|puede_recuperar %} ... {% endif %}
    """
    from s_exp.services.permisos import puede_recuperar_expedientes
    try:
        return puede_recuperar_expedientes(user)
    except Exception:
        return False
