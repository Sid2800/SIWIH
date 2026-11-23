"""Pruebas de s_exp: los limites de las listas y el aviso por WebSocket.

El modulo no tenia ninguna, y las dos cosas que se cubren aqui son
precisamente las que fallaron sin que nada lo delatara: una lista sin tope
que crecia hasta llenar la memoria del navegador, y un aviso en tiempo real
que, si se equivoca de destinatario, enseña a un usuario el movimiento de las
solicitudes de otro.
"""

import asyncio

from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from s_exp.consumers import CambiosConsumer, grupo_de_seccion, grupo_de_usuario
from s_exp.signals import SECCIONES_PERSONALES, SECCIONES_POR_ACCION


class LimitesDeLaListaTests(TestCase):
    """Mis Solicitudes devolvia todo lo del usuario desde siempre."""

    @classmethod
    def setUpTestData(cls):
        # Superusuario mas ficha en RRHH: el permiso del modulo exige las dos
        # cosas, porque comprueba el rol y ademas que la persona exista como
        # empleado. Sin la ficha, el endpoint responde 403 y la prueba no
        # llegaria a ejercitar nada de lo que quiere comprobar.
        cls.usuario = User.objects.create_superuser(
            username="zz_listas", password="clave-de-prueba"
        )

        # La cadena completa que exige el modulo: empleado, su relacion
        # laboral y la unidad donde trabaja. El permiso no se conforma con la
        # ficha: comprueba los tres eslabones, porque la unidad es la que
        # decide a nombre de quien se piden los expedientes.
        from rrhh.models import Empleado, PersonalNoClinico
        from servicio.models import Unidad

        unidad = Unidad.objects.create(
            nombre_unidad="UNIDAD DE PRUEBA",
            tipo=1,
            estado=1,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )

        empleado = Empleado.objects.create(
            dni="0000000000001",
            primer_nombre="PRUEBA",
            primer_apellido="LISTAS",
            estado=1,
            usuario=cls.usuario,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )

        PersonalNoClinico.objects.create(
            empleado=empleado,
            tipo=1,
            servicio_unidad=unidad,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def _pedir(self, **params):
        return self.client.get(reverse("s_exp_mis_solicitudes_api"), params)

    def test_responde_con_la_forma_esperada(self):
        """La respuesta tiene que decir cuanto hay, no solo lo que manda.

        Sin el total, una lista recortada a diez es indistinguible de un
        usuario que solo tiene diez solicitudes, y el limite se convierte en
        datos perdidos a ojos de quien mira.
        """
        respuesta = self._pedir()

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()

        for clave in ("data", "total", "desde", "limite", "hay_mas"):
            self.assertIn(clave, datos, f"falta «{clave}» en la respuesta")

    def test_el_limite_tiene_techo(self):
        """Un parametro en la URL no puede pedir diez mil filas."""
        respuesta = self._pedir(limite=99999)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["limite"], 100)

    def test_los_parametros_basura_caen_en_los_valores_por_defecto(self):
        """Antes que reventar con un 500, la lista se comporta."""
        respuesta = self._pedir(limite="abc", desde="-5")

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["limite"], 10)
        self.assertEqual(datos["desde"], 0)


class RepartoDeAvisosTests(TestCase):
    """Que cada aviso vaya a quien le toca, y a nadie mas."""

    def test_las_acciones_personales_estan_marcadas(self):
        """mis_solicitudes es de cada quien, no de todo el mundo.

        Si esta seccion dejara de estar en SECCIONES_PERSONALES, sus avisos
        saldrian al grupo general y cualquier usuario conectado sabria cuando
        se mueve una solicitud ajena.
        """
        self.assertIn("mis_solicitudes", SECCIONES_PERSONALES)

    def test_toda_accion_mapeada_apunta_a_una_seccion_conocida(self):
        """Una seccion mal escrita deja el aviso sin destinatario y en silencio."""
        conocidas = {
            "solicitudes", "prestamos", "devoluciones", "mis_solicitudes", "global",
        }

        for accion, secciones in SECCIONES_POR_ACCION.items():
            for seccion in secciones:
                self.assertIn(
                    seccion, conocidas,
                    f"«{accion}» apunta a la sección desconocida «{seccion}»",
                )

    def test_los_grupos_de_usuario_no_se_pisan(self):
        self.assertNotEqual(grupo_de_usuario(1), grupo_de_usuario(2))

    def test_un_grupo_de_usuario_no_choca_con_uno_de_seccion(self):
        """Si chocaran, un aviso personal llegaria a toda una seccion."""
        personales = {grupo_de_usuario(i) for i in range(1, 50)}
        secciones = {
            grupo_de_seccion(s)
            for s in ("solicitudes", "prestamos", "devoluciones", "global")
        }

        self.assertFalse(personales & secciones)


class ConexionDelSocketTests(TestCase):
    """Quien no tiene sesion no abre el socket."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="zz_socket", password="clave-de-prueba"
        )

    def _conectar(self, user):
        async def intentar():
            com = WebsocketCommunicator(
                CambiosConsumer.as_asgi(), "/ws/s_exp/cambios/"
            )
            com.scope["user"] = user
            resultado = await com.connect()
            await com.disconnect()
            return resultado

        return asyncio.new_event_loop().run_until_complete(intentar())

    def test_un_anonimo_no_entra(self):
        """Un socket anonimo dejaria saber cuando se mueve el archivo."""
        conectado, codigo = self._conectar(AnonymousUser())

        self.assertFalse(conectado)
        self.assertEqual(codigo, 4401)

    def test_un_usuario_autenticado_entra(self):
        conectado, _ = self._conectar(self.usuario)

        self.assertTrue(conectado)


class ParidadConElPollingTests(TestCase):
    """El socket tiene que avisar lo mismo que avisaba el polling.

    El polling se apaga en cuanto el socket conecta. Cualquier aviso que el
    socket no dé es una pantalla que se queda quieta sin que nadie lo note.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="zz_paridad", password="clave-de-prueba"
        )

    def test_accion_sin_seccion_propia_va_a_global(self):
        """Antes, 'global' se movia con cualquier apunte de la bitacora."""
        from s_exp.signals import secciones_de

        self.assertEqual(secciones_de("REVISION_ENTREGA"), ("global",))
        self.assertEqual(secciones_de("UNA_ACCION_FUTURA"), ("global",))
        self.assertEqual(secciones_de("SOLICITUD_CREADA"), ("solicitudes",))

    def test_global_va_al_grupo_de_administradores(self):
        """El ritmo de trabajo del archivo no es asunto de cualquier usuario."""
        from unittest import mock

        from s_exp import signals

        enviados = []

        class CapaFalsa:
            async def group_send(self, grupo, evento):
                enviados.append((grupo, evento))

        with mock.patch("channels.layers.get_channel_layer", return_value=CapaFalsa()):
            signals._emitir("global", "ts", "REVISION_ENTREGA", actor_id=7)

        self.assertEqual(len(enviados), 1)
        grupo, evento = enviados[0]
        self.assertEqual(grupo, grupo_de_seccion("admin_global"))
        self.assertEqual(evento["actor_id"], 7)

    def _recibe(self, grupo, evento):
        """Conecta al usuario, manda un evento al grupo y dice si le llego."""
        from channels.layers import get_channel_layer

        async def probar():
            com = WebsocketCommunicator(CambiosConsumer.as_asgi(), "/ws/s_exp/cambios/")
            com.scope["user"] = self.usuario
            await com.connect()
            await com.receive_json_from()  # {'tipo': 'conectado'}
            await get_channel_layer().group_send(grupo, dict(evento, type="cambio"))
            nada = await com.receive_nothing(timeout=0.2)
            await com.disconnect()
            return not nada

        return asyncio.new_event_loop().run_until_complete(probar())

    def test_usuario_normal_no_entra_a_admin_global(self):
        llego = self._recibe(
            grupo_de_seccion("admin_global"),
            {"seccion": "global", "ts": "t", "accion": "REVISION_ENTREGA", "actor_id": None},
        )
        self.assertFalse(llego)

    def test_el_actor_no_recibe_su_propio_aviso_global(self):
        """El polling excluia los apuntes propios en 'global' y 'prestamos'."""
        llego = self._recibe(
            grupo_de_usuario(self.usuario.id),
            {"seccion": "global", "ts": "t", "accion": "X", "actor_id": self.usuario.id},
        )
        self.assertFalse(llego)

    def test_el_actor_si_recibe_lo_de_mis_solicitudes(self):
        """mis_solicitudes no excluia al propio usuario en el polling."""
        llego = self._recibe(
            grupo_de_usuario(self.usuario.id),
            {"seccion": "mis_solicitudes", "ts": "t", "accion": "X", "actor_id": self.usuario.id},
        )
        self.assertTrue(llego)

    def test_recuperacion_avisa_a_cada_dueno(self):
        """Una recuperacion toca solicitudes de varias personas a la vez."""
        from unittest import mock

        from s_exp import signals

        with mock.patch.object(signals, "_emitir") as emitir:
            with self.captureOnCommitCallbacks(execute=True):
                signals.avisar_usuarios([3, 4, 3], "EXPEDIENTES_RECUPERADOS")

        destinatarios = sorted(c.kwargs["usuario_id"] for c in emitir.call_args_list)
        self.assertEqual(destinatarios, [3, 4])
        for c in emitir.call_args_list:
            self.assertEqual(c.args[0], "mis_solicitudes")


# ---------------------------------------------------------------------------
# Datos de prueba para Devoluciones y Reportes
# ---------------------------------------------------------------------------

class DatosDePrestamoMixin:
    """Crea admin con su ficha de RRHH y préstamos con expedientes.

    El permiso de administración exige la cadena completa de RRHH, igual que
    en LimitesDeLaListaTests; sin ella las vistas responden 403.
    """

    @classmethod
    def crear_admin(cls, username):
        from rrhh.models import Empleado, PersonalNoClinico
        from servicio.models import Unidad

        admin = User.objects.create_superuser(username=username, password="clave-de-prueba")
        unidad = Unidad.objects.create(
            nombre_unidad="UNIDAD " + username, tipo=1, estado=1,
            creado_por=admin, modificado_por=admin,
        )
        empleado = Empleado.objects.create(
            dni=str(abs(hash(username)))[:13].rjust(13, "0"),
            primer_nombre="PRUEBA", primer_apellido="ADMIN", estado=1,
            usuario=admin, creado_por=admin, modificado_por=admin,
        )
        PersonalNoClinico.objects.create(
            empleado=empleado, tipo=1, servicio_unidad=unidad,
            creado_por=admin, modificado_por=admin,
        )
        cls.unidad = unidad
        return admin

    _numero = 0

    @classmethod
    def crear_prestamo(cls, admin, estado_sol, estado_prestamo, n_detalles=2,
                       devueltos=0, minutos_limite=60, usuario=None):
        from datetime import timedelta

        from django.utils import timezone

        from expediente.models import Expediente
        from s_exp.models import (
            EstadoExpedienteFisico, EstadoPrestamo, EstadoSolicitud,
            ExpedientePrestamo, MotivoSolicitud, Prestamo,
            SolicitudExpedienteDetalle, SolicitudPrestamo,
        )

        solicitud = SolicitudPrestamo.objects.create(
            usuario=usuario or admin,
            estado_flujo_id=EstadoSolicitud.id_de(estado_sol),
            motivo=MotivoSolicitud.objects.first(),
            servicio_unidad=cls.unidad,
        )
        for i in range(n_detalles):
            DatosDePrestamoMixin._numero += 1
            exp = Expediente.objects.create(
                numero=900000 + DatosDePrestamoMixin._numero,
                creado_por=admin, modificado_por=admin,
            )
            ep = ExpedientePrestamo.objects.create(
                expediente=exp,
                estado_id=EstadoExpedienteFisico.id_de('EXP_PRESTADO'),
            )
            SolicitudExpedienteDetalle.objects.create(
                solicitud=solicitud, expediente_prestamo=ep,
                aprobado=True, devuelto=i < devueltos,
            )
        prestamo = Prestamo.objects.create(
            solicitud=solicitud, admin_aprobador=admin,
            estado_id=EstadoPrestamo.id_de(estado_prestamo),
            fecha_limite=timezone.now() + timedelta(minutes=minutos_limite),
        )
        return prestamo


class DevolucionesTests(DatosDePrestamoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = cls.crear_admin("zz_devol")

    def setUp(self):
        self.client.force_login(self.admin)

    def _crear(self, n):
        return [
            self.crear_prestamo(self.admin, 'SOL_EN_DEVOLUCION', 'Entregado')
            for _ in range(n)
        ]

    def _pedir(self):
        return self.client.get(reverse("s_exp_prestamos_devolucion_api"))

    def test_devoluciones_consultas_constantes(self):
        """Antes eran unas tres consultas por préstamo."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._crear(3)
        self._pedir()  # calienta cachés de catálogos
        with CaptureQueriesContext(connection) as con3:
            self.assertEqual(self._pedir().status_code, 200)
        self._crear(3)
        with CaptureQueriesContext(connection) as con6:
            self.assertEqual(self._pedir().status_code, 200)

        self.assertEqual(len(con3), len(con6))

    def test_devoluciones_forma_y_total(self):
        self._crear(3)
        datos = self._pedir().json()

        self.assertEqual(datos["total"], 3)
        self.assertEqual(datos["mostrando"], 3)
        fila = datos["data"][0]
        self.assertEqual(set(fila), {
            "id", "solicitud_id", "usuario", "usuario_nombre", "unidad", "estado",
            "detalles_expedientes", "cant_expedientes", "cant_devueltos",
            "fecha_limite", "esta_vencido",
        })
        self.assertEqual(fila["cant_expedientes"], 2)
        self.assertEqual(fila["cant_devueltos"], 0)
        self.assertEqual(len(fila["detalles_expedientes"]), 2)

    def test_procesar_devolucion_es_atomico(self):
        """Un fallo a mitad no puede dejar expedientes devueltos sin cerrar."""
        import json
        from unittest import mock

        from s_exp.models import Devolucion

        prestamo = self._crear(1)[0]
        detalle = prestamo.solicitud.detalles.first()

        with mock.patch.object(Devolucion.objects, "create", side_effect=RuntimeError("boom")):
            r = self.client.post(
                reverse("s_exp_procesar_devolucion_api"),
                data=json.dumps({"prestamo_id": prestamo.id, "detalles_recibidos": [detalle.id]}),
                content_type="application/json",
            )

        self.assertEqual(r.status_code, 500)
        detalle.refresh_from_db()
        self.assertFalse(detalle.devuelto)

    def test_procesar_devolucion_completa_cierra_el_prestamo(self):
        """El camino normal sigue igual dentro de la transacción."""
        import json

        from s_exp.models import EstadoPrestamo, EstadoSolicitud

        prestamo = self._crear(1)[0]
        ids = list(prestamo.solicitud.detalles.values_list("id", flat=True))
        r = self.client.post(
            reverse("s_exp_procesar_devolucion_api"),
            data=json.dumps({"prestamo_id": prestamo.id, "detalles_recibidos": ids}),
            content_type="application/json",
        )

        self.assertEqual(r.status_code, 200)
        prestamo.refresh_from_db()
        prestamo.solicitud.refresh_from_db()
        self.assertEqual(EstadoPrestamo.codigo_de(prestamo.estado_id), "Cerrado")
        self.assertEqual(EstadoSolicitud.codigo_de(prestamo.solicitud.estado_flujo_id), "SOL_FINALIZADA")
        self.assertEqual(prestamo.devoluciones.count(), 1)


class ReportesTests(DatosDePrestamoMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = cls.crear_admin("zz_reportes")

    def setUp(self):
        self.client.force_login(self.admin)

    def _pedir(self):
        return self.client.get(reverse("s_exp_reportes_data_api"))

    def test_inconsistencias_no_suma_acumulados(self):
        """Cada auditoría guarda el total acumulado, no lo de esa tanda.

        3 aprobados; primera auditoría recibe 1 (cantidad_recibida=1), la
        segunda otro más (cantidad_recibida=2). Sumar daba 3 devueltos y
        "0 faltantes" cuando en realidad falta uno.
        """
        from s_exp.models import Devolucion, EstadoDevolucion

        p = self.crear_prestamo(self.admin, 'SOL_INCOMPLETA', 'DevolucionParcial',
                                n_detalles=3, devueltos=2)
        for recibida in (1, 2):
            Devolucion.objects.create(
                prestamo=p, cantidad_esperada=3, cantidad_recibida=recibida,
                estado_id=EstadoDevolucion.id_de('Incompleta'),
            )

        fila = self._pedir().json()["inconsistencias"][0]

        self.assertEqual(fila["total_expedientes"], 3)
        self.assertEqual(fila["devueltos"], 2)
        self.assertEqual(fila["faltantes"], 1)

    def test_reportes_consultas_constantes(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def crear(n):
            for _ in range(n):
                self.crear_prestamo(self.admin, 'SOL_RECHAZADA', 'Cerrado', n_detalles=1)
                self.crear_prestamo(self.admin, 'SOL_INCOMPLETA', 'DevolucionParcial', devueltos=1)
                self.crear_prestamo(self.admin, 'SOL_EN_PRESTAMO', 'Entregado', minutos_limite=-30)

        crear(2)
        self._pedir()
        with CaptureQueriesContext(connection) as c2:
            self.assertEqual(self._pedir().status_code, 200)
        crear(3)
        with CaptureQueriesContext(connection) as c5:
            datos = self._pedir().json()

        self.assertEqual(len(c2), len(c5))
        self.assertEqual(datos["rechazos_total"], 5)
        self.assertEqual(datos["morosidad_total"], 5)
        self.assertEqual(datos["inconsistencias_total"], 5)


class ProximoChequeoDeAlertasTests(DatosDePrestamoMixin, TestCase):
    """Los avisos de 10 / 5 minutos salen del reloj, no de una acción.

    Con polling aparecían de rebote con cualquier movimiento del sistema;
    con el socket, el navegador necesita saber cuándo volver a mirar.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = cls.crear_admin("zz_alertas")

    def setUp(self):
        self.client.force_login(self.admin)

    def _proximo(self):
        return self.client.get(reverse("s_exp_alertas_api")).json()["proximo_chequeo_seg"]

    def test_sin_prestamos_no_hay_chequeo(self):
        self.assertIsNone(self._proximo())

    def test_entregado_espera_al_umbral_de_diez_minutos(self):
        self.crear_prestamo(self.admin, 'SOL_EN_PRESTAMO', 'Entregado', minutos_limite=30)
        self.assertAlmostEqual(self._proximo(), 20 * 60, delta=5)

    def test_dentro_de_los_diez_minutos_espera_al_de_cinco(self):
        self.crear_prestamo(self.admin, 'SOL_EN_PRESTAMO', 'Entregado', minutos_limite=8)
        self.assertAlmostEqual(self._proximo(), 3 * 60, delta=5)

    def test_vencido_repite_cada_cinco_minutos(self):
        self.crear_prestamo(self.admin, 'SOL_EN_PRESTAMO', 'Vencido', minutos_limite=-30)
        self.assertAlmostEqual(self._proximo(), 300, delta=2)
