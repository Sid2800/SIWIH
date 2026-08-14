import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core.constants.permisos import (
    SG_TRANSPORTE_AUTORIZACION_UNIDADES,
    SG_TRANSPORTE_EJECUCION_UNIDADES,
    SG_TRANSPORTE_RESUMEN_UNIDADES,
    SG_TRANSPORTE_SOLICITUD_UNIDADES,
    SG_TRANSPORTE_VIAJE_UNIDADES,
)
from usuario.models import PerfilUnidad

from .views import (
    api_estado_modulo,
    puede_autorizacion_modulo,
    puede_ejecucion_modulo,
    puede_resumen_modulo,
    puede_solicitud_modulo,
    puede_ver_modulo,
    puede_viaje_modulo,
)


class SGTransporteHospitalarioPermisosTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _usuario(self, superuser=False):
        return SimpleNamespace(is_superuser=superuser, pk=1, id=1)

    def test_puede_ver_modulo_por_superusuario(self):
        usuario = self._usuario(superuser=True)

        self.assertTrue(puede_ver_modulo(usuario))

    @patch("sg_transporte_hospitalario.views.UsuarioService.es_admin_global", return_value=True)
    def test_admin_global_tiene_acceso_total(self, mocked_admin_global):
        usuario = self._usuario()

        self.assertTrue(puede_solicitud_modulo(usuario))
        self.assertTrue(puede_autorizacion_modulo(usuario))
        self.assertTrue(puede_viaje_modulo(usuario))
        self.assertTrue(puede_ejecucion_modulo(usuario))
        self.assertTrue(puede_resumen_modulo(usuario))
        mocked_admin_global.assert_called()

    @patch("sg_transporte_hospitalario.views.UsuarioService.es_directivo", return_value=True)
    def test_directivo_global_solo_tiene_resumen(self, mocked_directivo_global):
        usuario = self._usuario()

        with patch.object(PerfilUnidad.objects, "filter") as mocked_filter:
            mocked_filter.return_value.exists.return_value = False

            self.assertFalse(puede_solicitud_modulo(usuario))
            self.assertFalse(puede_autorizacion_modulo(usuario))
            self.assertFalse(puede_viaje_modulo(usuario))
            self.assertFalse(puede_ejecucion_modulo(usuario))
            self.assertTrue(puede_resumen_modulo(usuario))
            mocked_filter.assert_called()

        mocked_directivo_global.assert_called()

    def test_puede_solicitud_modulo_usa_roles_y_unidades(self):
        usuario = self._usuario()

        with patch.object(PerfilUnidad.objects, "filter") as mocked_filter:
            mocked_filter.return_value.exists.return_value = True

            self.assertTrue(puede_solicitud_modulo(usuario))
            mocked_filter.assert_called_once_with(
                usuario_id=usuario.id,
                rol__in=["admin", "digitador"],
                servicio_unidad__nombre_corto_unidad__in=SG_TRANSPORTE_SOLICITUD_UNIDADES,
            )

    def test_puede_autorizacion_modulo_usa_roles_y_unidades(self):
        usuario = self._usuario()

        with patch.object(PerfilUnidad.objects, "filter") as mocked_filter:
            mocked_filter.return_value.exists.return_value = True

            self.assertTrue(puede_autorizacion_modulo(usuario))
            mocked_filter.assert_called_once_with(
                usuario_id=usuario.id,
                rol__in=["admin", "digitador"],
                servicio_unidad__nombre_corto_unidad__in=SG_TRANSPORTE_AUTORIZACION_UNIDADES,
            )

    def test_puede_viaje_modulo_usa_roles_y_unidades(self):
        usuario = self._usuario()

        with patch.object(PerfilUnidad.objects, "filter") as mocked_filter:
            mocked_filter.return_value.exists.return_value = True

            self.assertTrue(puede_viaje_modulo(usuario))
            mocked_filter.assert_called_once_with(
                usuario_id=usuario.id,
                rol__in=["admin", "digitador"],
                servicio_unidad__nombre_corto_unidad__in=SG_TRANSPORTE_VIAJE_UNIDADES,
            )

    def test_puede_ejecucion_modulo_usa_roles_y_unidades(self):
        usuario = self._usuario()

        with patch.object(PerfilUnidad.objects, "filter") as mocked_filter:
            mocked_filter.return_value.exists.return_value = True

            self.assertTrue(puede_ejecucion_modulo(usuario))
            mocked_filter.assert_called_once_with(
                usuario_id=usuario.id,
                rol__in=["admin", "digitador"],
                servicio_unidad__nombre_corto_unidad__in=SG_TRANSPORTE_EJECUCION_UNIDADES,
            )

    def test_puede_resumen_modulo_usa_roles_y_unidades(self):
        usuario = self._usuario()

        with patch("sg_transporte_hospitalario.views.PerfilUnidad") as mocked_model:
            mocked_model.objects.filter.return_value.exists.return_value = True

            self.assertTrue(puede_resumen_modulo(usuario))
            mocked_model.objects.filter.assert_called_once_with(
                usuario_id=usuario.id,
                rol__in=["admin", "digitador", "directivo", "visitante"],
                servicio_unidad__nombre_corto_unidad__in=SG_TRANSPORTE_RESUMEN_UNIDADES,
            )

    @patch("sg_transporte_hospitalario.views.puede_solicitud_modulo", return_value=False)
    @patch("sg_transporte_hospitalario.views.puede_autorizacion_modulo", return_value=False)
    @patch("sg_transporte_hospitalario.views.puede_viaje_modulo", return_value=False)
    @patch("sg_transporte_hospitalario.views.puede_ejecucion_modulo", return_value=False)
    @patch("sg_transporte_hospitalario.views.puede_resumen_modulo", return_value=False)
    def test_puede_ver_modulo_rechaza_si_no_hay_etapas_habilitadas(
        self,
        mocked_resumen,
        mocked_ejecucion,
        mocked_viaje,
        mocked_autorizacion,
        mocked_solicitud,
    ):
        usuario = self._usuario()

        self.assertFalse(puede_ver_modulo(usuario))
        mocked_solicitud.assert_called_once_with(usuario)
        mocked_autorizacion.assert_called_once_with(usuario)
        mocked_viaje.assert_called_once_with(usuario)
        mocked_ejecucion.assert_called_once_with(usuario)
        mocked_resumen.assert_called_once_with(usuario)

    def test_api_estado_modulo_rechaza_usuario_sin_acceso(self):
        request = self.factory.get("/sg-transporte-hospitalario/api/estado/")
        request.user = self._usuario()

        with patch("sg_transporte_hospitalario.views.puede_ver_modulo", return_value=False):
            response = api_estado_modulo(request)

        self.assertEqual(response.status_code, 403)

    def test_api_estado_modulo_devuelve_permisos_granulares(self):
        request = self.factory.get("/sg-transporte-hospitalario/api/estado/")
        request.user = self._usuario()

        with patch("sg_transporte_hospitalario.views.puede_ver_modulo", return_value=True), patch(
            "sg_transporte_hospitalario.views.puede_solicitud_modulo", return_value=True
        ), patch(
            "sg_transporte_hospitalario.views.puede_autorizacion_modulo", return_value=False
        ), patch(
            "sg_transporte_hospitalario.views.puede_viaje_modulo", return_value=True
        ), patch(
            "sg_transporte_hospitalario.views.puede_ejecucion_modulo", return_value=False
        ), patch(
            "sg_transporte_hospitalario.views.puede_resumen_modulo", return_value=True
        ):
            response = api_estado_modulo(request)

        payload = json.loads(response.content.decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["lectura"])
        self.assertTrue(payload["solicitud"])
        self.assertFalse(payload["autorizacion"])
        self.assertTrue(payload["viaje"])
        self.assertFalse(payload["ejecucion"])
        self.assertTrue(payload["resumen"])