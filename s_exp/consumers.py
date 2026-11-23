"""WebSocket de s_exp: el servidor avisa, el navegador ya no pregunta.

Hasta ahora cada pantalla abierta preguntaba al servidor cada cinco segundos
si habia cambiado algo. La respuesta era "no" casi siempre, pero el viaje se
hacia igual: doce peticiones por minuto y por pestaña, todo el dia, para
enterarse de algo que ocurre un par de veces por hora.

Aqui se da la vuelta. El navegador abre una conexion y espera; cuando algo
cambia de verdad, el servidor lo empuja. Cero trafico mientras no pasa nada,
y el aviso llega en el momento en lugar de hasta cinco segundos despues.

Lo que viaja por el socket es deliberadamente minimo: la seccion que cambio y
cuando. Ningun dato de solicitudes, pacientes ni expedientes. La pantalla usa
el aviso para decidir si recarga, y los datos los pide por las mismas APIs de
siempre, que son las que ya aplican permisos. Asi el socket no se convierte
en una segunda puerta a los datos por la que haya que volver a comprobarlo
todo.
"""

import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer

# Secciones que el frontend sabe escuchar. Son las mismas que devuelve
# changes_check_api, para que el cambio de polling a socket no obligue a
# tocar la logica de las pantallas.
SECCIONES = ('solicitudes', 'prestamos', 'devoluciones', 'mis_solicitudes', 'global')

# Prefijo de los grupos del channel layer. Los nombres de grupo son globales
# al proyecto, asi que conviene que digan de quien son.
PREFIJO_GRUPO = 's_exp'

# Secciones en las que el polling excluia los apuntes del propio usuario
# (exclude(usuario=user) en changes_check_api). Sin esto, el admin que
# entrega un prestamo recibiria el aviso de su propia entrega.
SECCIONES_SIN_AUTOAVISO = ('prestamos', 'global')


def grupo_de_seccion(seccion):
    """Nombre del grupo que recibe los avisos de una seccion."""
    return f'{PREFIJO_GRUPO}_{seccion}'


def grupo_de_usuario(user_id):
    """Grupo propio de un usuario, para lo que solo le incumbe a el.

    "Mis solicitudes" es de cada quien: que a Esmeralda le aprueben una
    solicitud no es noticia para Marileth. Mandarlo a todos obligaria al
    navegador a filtrar, y para entonces el dato ya viajo.
    """
    return f'{PREFIJO_GRUPO}_usuario_{user_id}'


class CambiosConsumer(AsyncJsonWebsocketConsumer):
    """Mantiene abierta la conexion de una pantalla y le pasa los avisos."""

    async def connect(self):
        user = self.scope.get('user')

        # Sin sesion no hay socket. Un WebSocket anonimo seria una via para
        # saber cuando se mueve el modulo sin estar autorizado a verlo.
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_id = user.id
        self.grupos = [grupo_de_usuario(user.id)]

        # Las secciones de administracion solo se escuchan si se pueden ver.
        # Si no, cualquier usuario sabria el ritmo de trabajo del archivo:
        # cuantas solicitudes entran y a que hora, que es informacion del
        # servicio aunque no incluya ningun dato de paciente.
        if await self._puede_ver_administracion(user):
            self.grupos += [
                grupo_de_seccion('solicitudes'),
                grupo_de_seccion('prestamos'),
                grupo_de_seccion('devoluciones'),
                grupo_de_seccion('admin_global'),
            ]

        self.grupos.append(grupo_de_seccion('global'))

        for grupo in self.grupos:
            await self.channel_layer.group_add(grupo, self.channel_name)

        await self.accept()

        # Se avisa de que la conexion quedo lista para que el cliente pueda
        # apagar el polling de respaldo. Mientras no llegue esto, el
        # navegador sigue preguntando: es preferible trafico de mas que una
        # pantalla congelada sin que nadie lo note.
        await self.send_json({'tipo': 'conectado'})

    async def disconnect(self, code):
        for grupo in getattr(self, 'grupos', []):
            await self.channel_layer.group_discard(grupo, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """El cliente casi no habla; solo manda latidos.

        No se acepta ninguna orden por el socket a proposito. Todo lo que
        modifica datos sigue entrando por las vistas HTTP, que ya tienen sus
        comprobaciones de permiso y su registro en la bitacora.
        """
        if isinstance(content, dict) and content.get('tipo') == 'ping':
            await self.send_json({'tipo': 'pong'})

    # -- Mensajes que llegan desde el channel layer -------------------------

    async def cambio(self, evento):
        """Reenvia al navegador un aviso de cambio.

        El nombre del metodo tiene que coincidir con el 'type' que usa quien
        emite -'cambio'-, porque asi es como Channels enruta los mensajes de
        grupo a un metodo del consumer.
        """
        seccion = evento.get('seccion')
        actor = evento.get('actor_id')

        if actor and actor == getattr(self, 'user_id', None) and seccion in SECCIONES_SIN_AUTOAVISO:
            return

        await self.send_json({
            'tipo': 'cambio',
            'seccion': evento.get('seccion'),
            'ts': evento.get('ts'),
            'accion': evento.get('accion', ''),
        })

    # -- Apoyo --------------------------------------------------------------

    async def _puede_ver_administracion(self, user):
        """Si este usuario puede ver las pantallas de administracion del modulo.

        La comprobacion toca la base de datos -perfiles y unidades-, asi que
        va envuelta para no bloquear el bucle de eventos.
        """
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def comprobar():
            from s_exp.views.comunes import _es_exp_admin

            return bool(_es_exp_admin(user))

        try:
            return await comprobar()
        except Exception:
            # Ante la duda, no se escucha. Una pantalla que no recibe avisos
            # se refresca sola al recargar; una que recibe de mas filtra
            # informacion.
            return False
