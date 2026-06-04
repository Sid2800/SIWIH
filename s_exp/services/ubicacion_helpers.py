"""
Helpers de ubicación de expedientes (módulo s_exp).
=============================================================================

Resuelve y actualiza la ubicación física de un expediente durante el flujo
de préstamo/devolución. Convive con el sistema legacy (expediente.localizacion
texto) mientras dura la transición al catálogo relacional expediente_ubicacion.

Prioridad de lectura: catálogo nuevo (FK) → legacy (texto) → fallback.
"""
import logging

from .permisos import get_servicio_unidad_from_rrhh

logger = logging.getLogger("s_exp")


def resolver_ubicacion_expediente(expediente, info_exp=None):
    """
    Resuelve la ubicación ACTUAL del expediente (texto legible).

    Prioridad (obtención híbrida durante la transición):
      1. NUEVO: ExpedientePrestamo.ubicacion (FK a ExpedienteUbicacion).
      2. LEGACY: expediente.localizacion.descripcion_localizacion
         (lo que usa el módulo expediente para atenciones/ingresos).
      3. LEGACY: info_exp.ubicacion_fisica (texto libre antiguo).
      4. "ADMISION" como último fallback (ARCHIVO quedó deprecado en s_exp).

    Args:
        expediente: instancia de Expediente.
        info_exp: instancia opcional de ExpedientePrestamo.

    Returns:
        str: descripción de la ubicación actual.
    """
    # 1) Nuevo catálogo (FK relacional) — solo si el expediente está prestado/movido
    try:
        if info_exp and getattr(info_exp, 'ubicacion_id', None):
            desc = info_exp.ubicacion.descripcion
            if desc:
                return desc
    except Exception:
        pass

    # 2) Legacy: localizacion del expediente (atenciones/ingresos)
    try:
        if expediente.localizacion and expediente.localizacion.descripcion_localizacion:
            return expediente.localizacion.descripcion_localizacion
    except Exception:
        pass

    # 3) Legacy: texto libre antiguo
    if info_exp and getattr(info_exp, 'ubicacion_fisica', None):
        return info_exp.ubicacion_fisica

    return "ADMISION"


def set_localizacion_por_solicitud(expediente, solicitud, usuario_admin):
    """
    Actualiza expediente.localizacion (LEGACY) al ENTREGAR un préstamo.

    La nueva ubicación es la unidad del SOLICITANTE, obtenida desde
    SolicitudPrestamo.servicio_unidad (capturada vía RRHH al crear la
    solicitud) o, en su defecto, resuelta desde la cadena RRHH del usuario.

    Mantiene sincronizado el campo legacy mientras dura la transición; la
    fuente principal es ExpedientePrestamo.ubicacion (FK al catálogo).

    Returns:
        str: descripción (mayúsculas) de la nueva ubicación asignada.
    """
    from expediente.models import Localizacion

    nombre_ubicacion = None

    # 1. De SolicitudPrestamo.servicio_unidad
    try:
        if solicitud.servicio_unidad and solicitud.servicio_unidad.nombre_unidad:
            nombre_ubicacion = solicitud.servicio_unidad.nombre_unidad
    except Exception:
        pass

    # 2. Fallback: cadena RRHH del solicitante
    if not nombre_ubicacion:
        try:
            servicio_unidad, _ok = get_servicio_unidad_from_rrhh(solicitud.usuario)
            if servicio_unidad and servicio_unidad.nombre_unidad:
                nombre_ubicacion = servicio_unidad.nombre_unidad
        except Exception:
            pass

    # 3. Fallback final
    if not nombre_ubicacion:
        if solicitud.servicio_unidad_id and solicitud.servicio_unidad:
            nombre_ubicacion = (solicitud.servicio_unidad.nombre_unidad or '').strip()
        if not nombre_ubicacion:
            nombre_ubicacion = 'PRESTADO'

    nombre_ubicacion = nombre_ubicacion.upper()

    try:
        loc_obj, _ = Localizacion.objects.get_or_create(
            descripcion_localizacion=nombre_ubicacion,
            defaults={'estado': True}
        )
        expediente.localizacion = loc_obj
        expediente.modificado_por = usuario_admin
        expediente.save(update_fields=['localizacion', 'modificado_por', 'fecha_modificado'])
        return nombre_ubicacion
    except Exception as e:
        logger.warning(f"No se pudo actualizar localizacion del expediente #{expediente.numero}: {e}")
        return nombre_ubicacion


def set_localizacion_admision(expediente, usuario_admin):
    """
    Devuelve expediente.localizacion (LEGACY) a 'ADMISION' tras una DEVOLUCIÓN.

    El módulo s_exp ya NO usa 'ARCHIVO': los expedientes devueltos regresan a
    ADMISION. Mantiene sincronizado el campo legacy mientras dura la transición;
    la fuente principal es ExpedientePrestamo.ubicacion (FK al catálogo).

    Returns:
        str: "ADMISION".
    """
    from expediente.models import Localizacion

    try:
        loc_obj = Localizacion.objects.filter(
            descripcion_localizacion__iexact='ADMISION'
        ).first()
        if not loc_obj:
            loc_obj, _ = Localizacion.objects.get_or_create(
                descripcion_localizacion='ADMISION',
                defaults={'estado': True}
            )
        expediente.localizacion = loc_obj
        expediente.modificado_por = usuario_admin
        expediente.save(update_fields=['localizacion', 'modificado_por', 'fecha_modificado'])
    except Exception as e:
        logger.warning(f"No se pudo regresar a ADMISION el expediente #{expediente.numero}: {e}")

    return 'ADMISION'
