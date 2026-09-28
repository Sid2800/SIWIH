import time
import requests
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import log_warning, log_error
from core.constants.image_server_enpoints import OBTENER_TOKEN

from django.conf import settings

# Token en memoria 
_IMAGE_TOKEN = None
_IMAGE_TOKEN_EXPIRES_AT = 0

class ImageServerAuthError(Exception):
    """Error de autenticación contra el servidor de imágenes"""
    pass


def _request_new_token(timeout):
    """
    Solicita un nuevo token  al servidor de imágenes.
    """
    try:
        response = requests.post(
            f"{settings.IMAGE_SERVER_URL}{OBTENER_TOKEN}",
            json={
                "username": settings.IMAGE_SERVER_USER,
                "password": settings.IMAGE_SERVER_PASSWORD,
            },
            timeout=(0.1,timeout)
        )
    except requests.RequestException as exc:

        log_error(
            f"No se pudo conectar al servidor de imágenes: {exc}",
            app=LogApp.TOKEN
        )

        raise ImageServerAuthError(
            f"No se pudo conectar al servidor de imágenes: {exc}"
        )

    if response.status_code != 200:
        raise ImageServerAuthError(
            f"Error al solicitar token de imágenes "
            f"(status {response.status_code}): {response.text}"
        )

    try:
        data = response.json()
    except ValueError:
        raise ImageServerAuthError(
            "Respuesta inválida del servidor de imágenes (no es JSON)"
        )

    if "access" not in data:

        raise ImageServerAuthError(
            "Respuesta inválida del servidor de imágenes (no viene access token)"
        )

    return data["access"]


def traer_server_token(timeout=5):
    """
    Retorna un token JWT válido para el servidor de imágenes.
    Si existe uno en memoria y no ha expirado, lo reutiliza.
    """
    global _IMAGE_TOKEN, _IMAGE_TOKEN_EXPIRES_AT

    now = time.time()

    # Reutilizar token si sigue vigente
    if _IMAGE_TOKEN and now < _IMAGE_TOKEN_EXPIRES_AT:
        return _IMAGE_TOKEN

    # Pedir uno nuevo
    token = _request_new_token(timeout=timeout)

    # log_warning(
    #     "Se generó nuevo token para servidor de imágenes",
    #     app=LogApp.TOKEN
    # )

    _IMAGE_TOKEN = token

    # Tiempo de vida conservador (ej: 4 minutos)
    _IMAGE_TOKEN_EXPIRES_AT = now + (4 * 60)

    return _IMAGE_TOKEN


def invalidate_image_server_token():
    """
    Invalida el token actual (por ejemplo, tras recibir un 401).
    """
    global _IMAGE_TOKEN, _IMAGE_TOKEN_EXPIRES_AT
    _IMAGE_TOKEN = None
    _IMAGE_TOKEN_EXPIRES_AT = 0


async def traer_server_token_async(timeout=5):
    """Version asincrona, para las vistas que no deben ocupar un hilo.

    Comparte el token en memoria con la version sincrona: es el mismo servidor
    y el mismo usuario, asi que pedir dos tokens en paralelo solo gastaria
    peticiones. Cuando ya hay uno vigente no toca la red y devuelve al
    instante, que es el caso habitual.

    No hay candado alrededor de la escritura: dos peticiones simultaneas con
    el token vencido pediran uno cada una y la ultima gana. Ambos son validos,
    asi que el peor caso es una peticion de mas, mucho mas barato que
    serializar todas las subidas detras de un lock.
    """
    global _IMAGE_TOKEN, _IMAGE_TOKEN_EXPIRES_AT

    ahora = time.time()

    if _IMAGE_TOKEN and ahora < _IMAGE_TOKEN_EXPIRES_AT:
        return _IMAGE_TOKEN

    # Import local: httpx solo hace falta en la ruta asincrona, y asi el
    # arranque del proyecto no depende de el.
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as cliente:
            respuesta = await cliente.post(
                f"{settings.IMAGE_SERVER_URL}{OBTENER_TOKEN}",
                json={
                    "username": settings.IMAGE_SERVER_USER,
                    "password": settings.IMAGE_SERVER_PASSWORD,
                },
            )
    except httpx.RequestError as exc:
        log_error(
            f"No se pudo conectar al servidor de imágenes: {exc}",
            app=LogApp.TOKEN,
        )
        raise ImageServerAuthError(
            f"No se pudo conectar al servidor de imágenes: {exc}"
        )

    if respuesta.status_code != 200:
        raise ImageServerAuthError(
            f"Error al solicitar token de imágenes "
            f"(status {respuesta.status_code})"
        )

    try:
        datos = respuesta.json()
    except ValueError:
        raise ImageServerAuthError(
            "Respuesta invalida del servidor de imágenes (no es JSON)"
        )

    if "access" not in datos:
        raise ImageServerAuthError(
            "Respuesta invalida del servidor de imágenes (no viene access token)"
        )

    _IMAGE_TOKEN = datos["access"]
    # Mismo margen conservador que la version sincrona: Images los emite por
    # diez minutos y aqui se renuevan a los cuatro.
    _IMAGE_TOKEN_EXPIRES_AT = ahora + (4 * 60)

    return _IMAGE_TOKEN