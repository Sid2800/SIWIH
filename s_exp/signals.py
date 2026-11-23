"""De un apunte en la bitacora a un aviso en pantalla.

El modulo ya registraba cada accion en LogHistorico, y el polling que habia
antes no hacia otra cosa que preguntar "cual es el apunte mas reciente". Asi
que la bitacora ya era la fuente de la verdad; lo unico que faltaba era que
avisara en lugar de esperar a que le preguntaran.

Se engancha por señal y no dentro de _registrar_log a proposito. Son doce
llamadas repartidas por cinco archivos de vistas, y cualquier codigo futuro
que cree un LogHistorico por su cuenta -una importacion, un comando de
gestion, el admin- tendria que acordarse de avisar tambien. Por señal no hay
nada que recordar.

El aviso sale despues de que la transaccion confirme. Si saliera dentro, el
navegador podria pedir los datos nuevos antes de que existan para el resto
del mundo, y lo que veria es el estado anterior: un refresco que no refresca
nada y que ademas solo falla de vez en cuando, que es la peor clase de fallo.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import log_error

# Que secciones de pantalla le importan a cada accion. Es el mismo reparto
# que hacia changes_check_api; se mantiene para que las pantallas no tengan
# que cambiar de criterio al pasar de polling a socket.
#
# Una accion puede tocar varias secciones: entregar un prestamo le interesa a
# monitoreo y tambien a quien lo pidio.
SECCIONES_POR_ACCION = {
    'SOLICITUD_CREADA': ('solicitudes',),
    'SOLICITUD_DEVOLUCION_INICIADA': ('devoluciones',),
    'PRESTAMO_ENTREGADO': ('prestamos', 'mis_solicitudes'),
    'DEVOLUCION_PROCESADA': ('prestamos', 'mis_solicitudes'),
    'SOLICITUD_APROBADA': ('mis_solicitudes',),
    'SOLICITUD_RECHAZADA': ('mis_solicitudes',),
    'SOLICITUD_LISTA': ('mis_solicitudes',),
}

# Las secciones que son de cada usuario y no de todo el mundo. Un aviso de
# estas va solo al grupo de su dueño.
SECCIONES_PERSONALES = ('mis_solicitudes',)

# 'global' era, en el polling, "cualquier apunte de la bitacora que no sea
# mio". Dashboard, Reportes y las alertas emergentes se movian con eso. Las
# acciones que no tienen pantalla propia se mandan como 'global', pero solo a
# los administradores: es el ritmo de trabajo del archivo.
GRUPO_GLOBAL = 'admin_global'


def secciones_de(codigo):
    """Secciones a las que hay que avisar por una accion de la bitacora.

    Una accion sin seccion propia -o una que se agregue en el futuro- cae en
    'global'. Antes se descartaba, y como el polling se apaga al conectar el
    socket, el Dashboard y Reportes se quedaban quietos sin que nada lo dijera.
    """
    return SECCIONES_POR_ACCION.get(codigo) or ('global',)


def _emitir(seccion, ts, accion, usuario_id=None, actor_id=None):
    """Manda un aviso al grupo que corresponda."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from s_exp.consumers import grupo_de_seccion, grupo_de_usuario

    capa = get_channel_layer()

    if capa is None:
        return

    if seccion in SECCIONES_PERSONALES:
        if not usuario_id:
            return
        grupo = grupo_de_usuario(usuario_id)
    elif seccion == 'global':
        grupo = grupo_de_seccion(GRUPO_GLOBAL)
    else:
        grupo = grupo_de_seccion(seccion)

    async_to_sync(capa.group_send)(grupo, {
        # 'type' es lo que Channels usa para elegir el metodo del consumer.
        'type': 'cambio',
        'seccion': seccion,
        'ts': ts,
        'accion': accion,
        # Quien hizo la accion. Lo usa el consumer para no avisarle de lo
        # suyo, como hacia el polling; no se reenvia al navegador.
        'actor_id': actor_id,
    })


@receiver(post_save, sender='s_exp.LogHistorico')
def avisar_cambio(sender, instance, created, **kwargs):
    """Convierte un apunte nuevo de la bitacora en avisos por WebSocket."""
    if not created:
        return

    try:
        from s_exp.models import TipoAccionLog

        codigo = TipoAccionLog.codigo_de(instance.accion_id)
        secciones = secciones_de(codigo)
        actor_id = instance.usuario_id

        ts = instance.timestamp.isoformat() if instance.timestamp else ''

        # Para las secciones personales hace falta saber de quien es la
        # solicitud, que no es necesariamente quien hizo la accion: a una
        # solicitud la aprueba un administrador y el aviso va al solicitante.
        dueno_id = _dueno_de(instance)

        def enviar():
            for seccion in secciones:
                _emitir(seccion, ts, codigo, usuario_id=dueno_id, actor_id=actor_id)

        transaction.on_commit(enviar)

    except Exception as e:
        # Un fallo avisando no puede tumbar la operacion que lo provoco. Si
        # el socket falla, la pantalla se entera al recargar; si la
        # excepcion subiera, se perderia la aprobacion del prestamo entera.
        log_error(f"Error emitiendo aviso de cambio s_exp: {e}", app=LogApp.S_EXP)


def avisar_usuarios(usuario_ids, accion):
    """Aviso personal a varias personas, despues de confirmar la transaccion.

    Para acciones cuyo apunte en la bitacora no basta para saber a quien le
    toca: una recuperacion de urgencia de Admision afecta solicitudes de
    varios usuarios, pero el log solo apunta a una de ellas.
    """
    from django.utils import timezone

    destinatarios = sorted({u for u in usuario_ids if u})
    ts = timezone.now().isoformat()

    def enviar():
        for uid in destinatarios:
            try:
                _emitir('mis_solicitudes', ts, accion, usuario_id=uid)
            except Exception as e:
                log_error(f"Error avisando a usuario {uid}: {e}", app=LogApp.S_EXP)

    transaction.on_commit(enviar)


def _dueno_de(log):
    """Quien debe recibir los avisos personales de este apunte.

    El log apunta al objeto afectado por tipo y id. Cuando es una solicitud,
    su dueño es quien la creo. Si no se puede resolver, se devuelve None y el
    aviso personal simplemente no se manda: es preferible a mandarselo a
    quien no le toca.
    """
    try:
        from s_exp.models import SolicitudPrestamo, TipoObjetoLog

        if not log.objeto_id or not log.objeto_tipo_id:
            return None

        tipo = TipoObjetoLog.codigo_de(log.objeto_tipo_id)

        if tipo != 'SolicitudPrestamo':
            return None

        return (
            SolicitudPrestamo.objects
            .filter(pk=log.objeto_id)
            .values_list('usuario_id', flat=True)
            .first()
        )
    except Exception:
        return None
