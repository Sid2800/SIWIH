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
