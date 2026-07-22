from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from .views import api_estado_modulo, puede_gestionar_modulo, puede_ver_modulo


class SGTransporteHospitalarioPermisosTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_puede_ver_modulo_por_superusuario(self):
        usuario = SimpleNamespace(is_superuser=True)

        self.assertTrue(puede_ver_modulo(usuario))

    def test_puede_gestionar_modulo_solo_admin_global_o_superusuario(self):
        usuario = SimpleNamespace(is_superuser=False)

        with patch("sg_transporte_hospitalario.views.UsuarioService.es_admin_global", return_value=False):
            self.assertFalse(puede_gestionar_modulo(usuario))

    def test_api_estado_modulo_rechaza_usuario_sin_acceso(self):
        request = self.factory.get("/sg-transporte-hospitalario/api/estado/")
        request.user = SimpleNamespace(is_superuser=False)

        with patch("sg_transporte_hospitalario.views.puede_ver_modulo", return_value=False):
            response = api_estado_modulo(request)

        self.assertEqual(response.status_code, 403)