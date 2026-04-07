import time
import requests
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.constants.image_server_enpoints import OBTENER_TOKEN

from django.conf import settings

# Token en memoria 
_IMAGE_TOKEN = None
_IMAGE_TOKEN_EXPIRES_AT = 0

class ImageServerAuthError(Exception):
    """Error de autenticación contra el servidor de imágenes"""
    pass


def _request_new_token():
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
            timeout=5,
        )
    except requests.RequestException as exc:
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


def traer_server_token():
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
    token = _request_new_token()

    log_warning(
        "Se generó nuevo token para servidor de imágenes",
        app=LogApp.TOKEN
    )

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