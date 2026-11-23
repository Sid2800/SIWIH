"""
ASGI config for SIWI project.

Expone la aplicacion ASGI. A diferencia de wsgi.py, esta atiende dos
protocolos: las peticiones HTTP de siempre y las conexiones WebSocket.

El orden importa. get_asgi_application() tiene que construirse ANTES de
importar nada que toque modelos -los consumers lo hacen-, porque esa llamada
es la que deja Django cargado. Importar routing antes revienta con
AppRegistryNotReady, y el error no dice que el problema sea el orden.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')

# Django primero. Lo que venga despues ya puede importar modelos.
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
