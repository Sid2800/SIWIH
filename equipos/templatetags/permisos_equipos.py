"""Filtros para ocultar en pantalla lo que el usuario no puede ejecutar.

Delegan en equipos/permisos.py, las mismas funciones que usan las vistas. No
se reimplementa la regla aqui: cuando la logica vive en dos sitios, uno de
los dos se queda atras y aparece el boton que lleva a un 403.

Ocultar es solo presentacion. Quien protege de verdad es el decorador de la
vista, porque una URL escrita a mano no pasa por la plantilla.
"""

from django import template

from equipos.permisos import (
    puede_administrar_catalogos_equipos,
    puede_dar_baja_equipos,
    puede_editar_equipos,
    puede_visualizar_equipos,
)

register = template.Library()


@register.filter
def puede_ver_equipos(user):
    return puede_visualizar_equipos(user)


@register.filter
def puede_editar_equipo(user):
    return puede_editar_equipos(user)


@register.filter
def puede_administrar_catalogo_equipos(user):
    return puede_administrar_catalogos_equipos(user)


@register.filter
def puede_dar_baja_equipo(user):
    return puede_dar_baja_equipos(user)
