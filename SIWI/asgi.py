"""Punto de entrada ASGI de SIWIH, servido con Daphne.

Daphne sustituye a Gunicorn. Gunicorn habla WSGI, un protocolo donde cada
peticion ocupa un proceso o hilo de principio a fin y donde no existen las
conexiones persistentes; ASGI admite ademas websockets y vistas asincronas.

Que cambia en la practica:

  - Las vistas sincronas de siempre siguen funcionando igual. Django las
    ejecuta en un hilo del pool, asi que no hace falta reescribir nada para
    migrar el servidor.

  - Las vistas declaradas "async def" no ocupan un hilo mientras esperan. Eso
    importa en las que solo esperan red: el proxy de fotos de equipos pasa el
    99% del tiempo aguardando a SIWIH Images, y una ficha con seis fotos son
    seis esperas simultaneas. Ver core/views.py::media_equipo_proxy.

  - Los websockets ya estan conectados (avisos en tiempo real de s_exp, ver
    s_exp/routing.py). Aqui se enchufan las rutas de cualquier modulo que
    los necesite (mapa de camas, estado del servidor de imagenes...).

El orden importa. get_asgi_application() tiene que construirse ANTES de
importar nada que toque modelos -los consumers lo hacen-, porque esa llamada
es la que deja Django cargado. Importar routing antes revienta con
AppRegistryNotReady, y el error no dice que el problema sea el orden.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')

# Se resuelve al importar para que Daphne falle al arrancar si algo esta mal
# configurado, en vez de responder 500 en la primera peticion. Django va
# primero: Lo que venga despues ya puede importar modelos.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from s_exp.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    # HTTP sigue igual que siempre: las mismas vistas, los mismos middlewares.
    'http': django_asgi_app,

    # AllowedHostsOriginValidator rechaza los sockets que vengan de un origen
    # que no este en ALLOWED_HOSTS. Sin el, cualquier pagina de internet
    # podria abrir un socket contra el hospital usando la sesion del
    # navegador de quien la visite.
    #
    # AuthMiddlewareStack es lo que pone request.user -aqui scope['user']- a
    # partir de la cookie de sesion. Sin el, el consumer no sabria quien se
    # esta conectando y tendria que dejar entrar a cualquiera.
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
