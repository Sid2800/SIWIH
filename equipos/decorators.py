"""Decoradores que aplican los permisos del modulo a cada vista.

No deciden nada por su cuenta: preguntan a equipos/permisos.py. Su unico
trabajo es traducir un "no" a la respuesta que corresponde segun quien
pregunta, que no es la misma para una pantalla que para un endpoint.
"""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from .permisos import (
    puede_administrar_catalogos_equipos,
    puede_dar_baja_equipos,
    puede_editar_equipos,
    puede_usar_formularios_equipos,
    puede_visualizar_equipos,
)


def _exigir(comprueba, como_json=False):
    """Construye un decorador a partir de una funcion de permiso.

    como_json distingue el destinatario: una pantalla lleva a la persona a
    acceso_denegado, mientras que un endpoint tiene que responder 403. Un 200
    con lista vacia seria indistinguible de "no hay datos", y el JavaScript
    de la pagina lo tomaria por bueno.
    """

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if comprueba(request.user):
                return vista(request, *args, **kwargs)

            if como_json:
                return JsonResponse(
                    {"error": "No tiene permiso para esta acción."},
                    status=403,
                )

            return redirect("acceso_denegado")

        return envoltura

    return decorador


exige_ver_equipos = _exigir(puede_visualizar_equipos)
exige_editar_equipos = _exigir(puede_editar_equipos)
exige_catalogo_equipos = _exigir(puede_administrar_catalogos_equipos)
exige_baja_equipos = _exigir(puede_dar_baja_equipos)

# Los buscadores de los formularios responden a fetch, no a una navegacion.
exige_formularios_equipos_json = _exigir(puede_usar_formularios_equipos, como_json=True)
