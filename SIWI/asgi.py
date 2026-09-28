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

  - Los websockets quedan disponibles para lo que venga (avisos en vivo del
    mapa de camas, estado del servidor de imagenes). Requieren agregar
    channels y su routing; este archivo es el sitio donde se enchufan.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')

# Se resuelve al importar para que Daphne falle al arrancar si algo esta mal
# configurado, en vez de responder 500 en la primera peticion.
application = get_asgi_application()
