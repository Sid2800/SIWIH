"""Rutas de WebSocket de s_exp.

Van aparte de urls.py porque no son lo mismo: urls.py lo recorre el router
HTTP de Django y esto lo recorre el router de WebSocket de Channels. Mezclar
los dos archivos haria creer que una ruta de aqui responde a una peticion
normal del navegador, y no es asi.
"""

from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/s_exp/cambios/', consumers.CambiosConsumer.as_asgi()),
]
