"""
Servicio de bitácora/auditoría (módulo s_exp).
=============================================================================

Registra eventos en LogHistorico. La acción es relacional (FK a TipoAccionLog);
si llega un código de acción nuevo, se crea al vuelo para que el log nunca
falle por un código no registrado previamente.
"""
import logging

logger = logging.getLogger("s_exp")


def registrar_log(usuario, accion, descripcion, objeto_tipo=None, objeto_id=None):
    """
    Registra un evento en la bitácora (LogHistorico).

    Args:
        usuario: instancia de User que realiza la acción.
        accion: CÓDIGO de la acción (ej. 'SOLICITUD_CREADA'). Es el PK del
                catálogo TipoAccionLog; se asigna como accion_id.
        descripcion: texto explicativo del evento.
        objeto_tipo: nombre del modelo afectado (opcional).
        objeto_id: ID del registro afectado (opcional).
    """
    from s_exp.models import LogHistorico, TipoAccionLog

    # Garantizar que el tipo de acción exista en el catálogo (evita FK error).
    # La PK del catálogo es un id ENTERO, así que usamos la instancia obtenida.
    tipo, _ = TipoAccionLog.objects.get_or_create(codigo=accion, defaults={'nombre': accion})

    LogHistorico.objects.create(
        accion=tipo,        # FK al catálogo TipoAccionLog (PK = id entero)
        usuario=usuario,
        detalle=descripcion,
        objeto_tipo=objeto_tipo,
        objeto_id=objeto_id,
    )
