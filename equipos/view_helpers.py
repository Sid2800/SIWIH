# Ayudantes usados por mas de un modulo de vistas: registro central de
# errores con su decorador, y las consultas de asignacion, baja e
# imagenes que necesitan varios temas a la vez.


import logging
from functools import wraps

from django.http import Http404

from core.services.server_image.media_service import MediaService
from .forms import TIPOS_IMAGEN_DISPOSITIVO
from .models import BajaDispositivo, OrdenTrabajoBajaDispositivo
from .view_constants import ICONOS_TIPO_IMAGEN

logger = logging.getLogger("siwi")
LOG_EXTRA = {"app": "equipos"}


def _registrar_error_vista(mensaje, request, **contexto):
    # Los logs del modulo registran solo errores tecnicos. No guardan exitos ni
    # valores del formulario para evitar ruido y datos sensibles innecesarios.
    usuario = getattr(getattr(request, "user", None), "username", "") or "anonimo"
    detalles = {
        "usuario": usuario,
        "metodo": getattr(request, "method", ""),
        "ruta": getattr(request, "path", ""),
        **contexto,
    }
    contexto_log = " ".join(
        f"{clave}={valor}"
        for clave, valor in detalles.items()
        if valor not in (None, "")
    )
    logger.exception("%s | %s", mensaje, contexto_log, extra=LOG_EXTRA)


def registrar_errores_vista(mensaje):
    def decorador(vista):
        @wraps(vista)
        def wrapper(request, *args, **kwargs):
            try:
                return vista(request, *args, **kwargs)
            except Http404:
                raise
            except Exception:
                _registrar_error_vista(mensaje, request, **kwargs)
                raise

        return wrapper

    return decorador


def _obtener_asignacion_actual(dispositivo):
    # La asignacion activa es la que no tiene fecha_fin.
    return dispositivo.asignaciones.filter(
        fecha_fin__isnull=True
    ).select_related(
        "area_clinica__servicio",
        "unidad_no_clinica",
        "responsable",
    ).first()
def _obtener_baja_dispositivo(dispositivo):
    # Evita repetir try/except cada vez que necesitamos saber si el equipo
    # ya tiene baja administrativa.
    try:
        return dispositivo.baja
    except BajaDispositivo.DoesNotExist:
        return None


def _obtener_orden_trabajo_baja(dispositivo):
    try:
        return dispositivo.orden_trabajo_baja
    except OrdenTrabajoBajaDispositivo.DoesNotExist:
        return None


def _obtener_contexto_imagenes_dispositivo(dispositivo_id):
    # Ordena la respuesta remota según las seis categorías acordadas. La base
    # principal conserva solo el id del equipo; no duplica rutas de archivos.
    imagenes, media_server_offline = (
        MediaService.obtener_imagenes_dispositivo(dispositivo_id)
    )
    imagenes_por_tipo = {
        imagen.get("tipo_imagen"): imagen
        for imagen in imagenes
        if imagen.get("tipo_imagen")
    }
    imagenes_slots = [
        {
            "tipo": tipo,
            "etiqueta": etiqueta,
            "icono": ICONOS_TIPO_IMAGEN[tipo],
            "imagen": imagenes_por_tipo.get(tipo),
        }
        for tipo, etiqueta in TIPOS_IMAGEN_DISPOSITIVO
    ]
    tipos_ocupados = {
        slot["tipo"] for slot in imagenes_slots if slot["imagen"]
    }

    return {
        "imagen_general": imagenes_por_tipo.get("GENERAL"),
        "imagenes_slots": imagenes_slots,
        "cantidad_imagenes": len(tipos_ocupados),
        "tipos_imagen_ocupados": tipos_ocupados,
        "tipos_imagen_disponibles": (
            not media_server_offline
            and len(tipos_ocupados) < len(TIPOS_IMAGEN_DISPOSITIVO)
        ),
        "media_server_offline": media_server_offline,
    }
