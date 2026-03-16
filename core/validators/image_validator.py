from django.core.exceptions import ValidationError
from core.constants.media_constants import (
    TIPOS_IMAGEN_PERMITIDOS,
    MAX_TAMANO_IMAGEN_MB
)


def validar_imagen_basica(archivo):
    if archivo.content_type not in TIPOS_IMAGEN_PERMITIDOS:
        raise ValidationError("Formato de imagen no permitido")

    if archivo.size > MAX_TAMANO_IMAGEN_MB * 1024 * 1024:
        raise ValidationError(
            f"La imagen supera los {MAX_TAMANO_IMAGEN_MB}MB permitidos"
        )
