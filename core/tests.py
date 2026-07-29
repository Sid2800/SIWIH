import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from core.services.server_image.media_service import MediaService
from core.services.server_image.request_service import RequestService


@override_settings(IMAGE_SERVER_URL="http://imagenes.test")
class RequestServiceEquiposTests(SimpleTestCase):
    def crear_webp(self):
        return SimpleUploadedFile(
            "equipo.webp",
            b"contenido-webp",
            content_type="image/webp",
        )

    @patch(
        "core.services.server_image.request_service.requests.post"
    )
    @patch(
        "core.services.server_image.request_service.traer_server_token",
        return_value="jwt-prueba",
    )
    def test_subir_imagen_dispositivo_envia_webp_y_jwt(
        self,
        mock_token,
        mock_post,
    ):
        respuesta = Mock(status_code=201, text="")
        respuesta.json.return_value = {
            "imagen": {"uuid": "uuid-prueba", "dispositivo_id": 19}
        }
        mock_post.return_value = respuesta
        archivo = self.crear_webp()

        resultado = RequestService.subir_imagen_dispositivo({
            "dispositivo_id": 19,
            "archivo": archivo,
            "tipo_imagen": "GENERAL",
            "usuario_id": 3,
            "usuario_nombre": "Tecnico Prueba",
        })

        self.assertTrue(resultado["ok"])
        mock_token.assert_called_once_with()
        mock_post.assert_called_once()
        url, = mock_post.call_args.args
        opciones = mock_post.call_args.kwargs
        self.assertEqual(url, "http://imagenes.test/api_images/equipos/subir/")
        self.assertEqual(
            opciones["headers"]["Authorization"],
            "Bearer jwt-prueba",
        )
        self.assertEqual(opciones["data"]["dispositivo_id"], 19)
        self.assertEqual(opciones["data"]["tipo_imagen"], "GENERAL")
        self.assertEqual(
            json.loads(opciones["data"]["usuario_snapshot"])["id"],
            3,
        )
        self.assertEqual(opciones["files"]["archivo"][2], "image/webp")

    @patch(
        "core.services.server_image.request_service.requests.post"
    )
    def test_subir_imagen_dispositivo_rechaza_archivo_no_webp(
        self,
        mock_post,
    ):
        archivo = SimpleUploadedFile(
            "equipo.jpg",
            b"contenido-jpg",
            content_type="image/jpeg",
        )

        with self.assertRaisesMessage(ValueError, "solo acepta archivos WebP"):
            RequestService.subir_imagen_dispositivo({
                "dispositivo_id": 19,
                "archivo": archivo,
                "tipo_imagen": "GENERAL",
            })

        mock_post.assert_not_called()

    @patch(
        "core.services.server_image.request_service.requests.get"
    )
    @patch(
        "core.services.server_image.request_service.traer_server_token",
        return_value="jwt-prueba",
    )
    def test_consultar_imagenes_dispositivo_usa_ruta_del_equipo(
        self,
        mock_token,
        mock_get,
    ):
        respuesta = Mock(status_code=200, text="")
        respuesta.json.return_value = {
            "dispositivo_id": 19,
            "cantidad": 0,
            "imagenes": [],
        }
        mock_get.return_value = respuesta

        resultado = RequestService.consultar_imagenes_dispositivo(19)

        self.assertTrue(resultado["ok"])
        mock_token.assert_called_once_with()
        mock_get.assert_called_once_with(
            "http://imagenes.test/api_images/equipos/19/imagenes/",
            headers={"Authorization": "Bearer jwt-prueba"},
            timeout=10,
        )

    @patch(
        "core.services.server_image.request_service.requests.get"
    )
    @patch(
        "core.services.server_image.request_service.traer_server_token",
        return_value="jwt-prueba",
    )
    def test_obtener_archivo_media_equipo_descarga_con_jwt(
        self,
        mock_token,
        mock_get,
    ):
        respuesta = Mock(
            status_code=200,
            content=b"imagen-webp",
            headers={
                "Content-Type": "image/webp",
                "ETag": '"equipo-19"',
            },
        )
        mock_get.return_value = respuesta

        resultado = RequestService.obtener_archivo_media_equipo(
            "EQUIPOS/2026/07/equipo 19.webp"
        )

        self.assertEqual(resultado["contenido"], b"imagen-webp")
        self.assertEqual(resultado["content_type"], "image/webp")
        self.assertEqual(resultado["etag"], '"equipo-19"')
        mock_token.assert_called_once_with()
        mock_get.assert_called_once_with(
            "http://imagenes.test/media/EQUIPOS/2026/07/equipo%2019.webp",
            headers={"Authorization": "Bearer jwt-prueba"},
            timeout=10,
        )

    def test_obtener_archivo_media_equipo_rechaza_recorrido_directorios(self):
        with self.assertRaisesMessage(
            ValueError,
            "Ruta de imagen de equipo no valida",
        ):
            RequestService.obtener_archivo_media_equipo(
                "EQUIPOS/../USUARIOS/avatar.webp"
            )

    @patch(
        "core.services.server_image.request_service.requests.post"
    )
    @patch(
        "core.services.server_image.request_service.traer_server_token",
        return_value="jwt-prueba",
    )
    def test_subir_ficha_baja_envia_webp_y_jwt(
        self,
        mock_token,
        mock_post,
    ):
        respuesta = Mock(status_code=201, text="")
        respuesta.json.return_value = {
            "ficha": {"uuid": "uuid-ficha", "dispositivo_id": 19}
        }
        mock_post.return_value = respuesta
        archivo = self.crear_webp()

        resultado = RequestService.subir_ficha_baja_dispositivo({
            "dispositivo_id": 19,
            "archivo": archivo,
            "usuario_id": 3,
            "usuario_nombre": "Tecnico Prueba",
        })

        self.assertTrue(resultado["ok"])
        mock_token.assert_called_once_with()
        url, = mock_post.call_args.args
        opciones = mock_post.call_args.kwargs
        self.assertEqual(
            url,
            "http://imagenes.test/api_images/equipos/bajas/subir/",
        )
        self.assertEqual(
            opciones["headers"]["Authorization"],
            "Bearer jwt-prueba",
        )
        self.assertEqual(opciones["data"]["dispositivo_id"], 19)
        self.assertEqual(opciones["files"]["archivo"][2], "image/webp")

    @patch(
        "core.services.server_image.request_service.requests.get"
    )
    @patch(
        "core.services.server_image.request_service.traer_server_token",
        return_value="jwt-prueba",
    )
    def test_consultar_ficha_baja_usa_ruta_del_equipo(
        self,
        mock_token,
        mock_get,
    ):
        respuesta = Mock(status_code=200, text="")
        respuesta.json.return_value = {
            "dispositivo_id": 19,
            "ficha": None,
        }
        mock_get.return_value = respuesta

        resultado = RequestService.consultar_ficha_baja_dispositivo(19)

        self.assertTrue(resultado["ok"])
        mock_token.assert_called_once_with()
        mock_get.assert_called_once_with(
            "http://imagenes.test/api_images/equipos/19/baja/ficha/",
            headers={"Authorization": "Bearer jwt-prueba"},
            timeout=10,
        )


@override_settings(IMAGE_SERVER_URL="http://imagenes.test")
class MediaServiceEquiposTests(SimpleTestCase):
    @patch.object(RequestService, "subir_imagen_dispositivo")
    def test_subir_imagen_dispositivo_devuelve_imagen(
        self,
        mock_subir,
    ):
        mock_subir.return_value = {
            "ok": True,
            "data": {
                "imagen": {"uuid": "uuid-prueba", "dispositivo_id": 19}
            },
        }
        usuario = SimpleNamespace(
            id=3,
            first_name="Tecnico",
            last_name="Prueba",
        )
        archivo = SimpleUploadedFile(
            "equipo.webp",
            b"contenido-webp",
            content_type="image/webp",
        )

        resultado = MediaService.subir_imagen_dispositivo(
            19,
            archivo,
            "GENERAL",
            usuario,
        )

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["imagen"]["dispositivo_id"], 19)

    @patch.object(RequestService, "consultar_imagenes_dispositivo")
    def test_obtener_imagenes_dispositivo_construye_urls_del_siwih_actual(
        self,
        mock_consultar,
    ):
        mock_consultar.return_value = {
            "ok": True,
            "data": {
                "imagenes": [{
                    "url": "/media/EQUIPOS/equipo.webp",
                    "miniatura": "/media/EQUIPOS/thumb_equipo.webp",
                }]
            },
        }

        imagenes, servidor_inactivo = (
            MediaService.obtener_imagenes_dispositivo(19)
        )

        self.assertFalse(servidor_inactivo)
        self.assertEqual(
            imagenes[0]["url"],
            "/media/equipos/equipo.webp",
        )
        self.assertEqual(
            imagenes[0]["miniatura"],
            "/media/equipos/thumb_equipo.webp",
        )

    @patch.object(RequestService, "subir_ficha_baja_dispositivo")
    def test_subir_ficha_baja_devuelve_constancia(
        self,
        mock_subir,
    ):
        mock_subir.return_value = {
            "ok": True,
            "data": {
                "ficha": {"uuid": "uuid-ficha", "dispositivo_id": 19}
            },
        }
        usuario = SimpleNamespace(
            id=3,
            first_name="Tecnico",
            last_name="Prueba",
        )
        archivo = SimpleUploadedFile(
            "ficha.webp",
            b"contenido-webp",
            content_type="image/webp",
        )

        resultado = MediaService.subir_ficha_baja_dispositivo(
            19,
            archivo,
            usuario,
        )

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["ficha"]["dispositivo_id"], 19)

    @patch.object(RequestService, "consultar_ficha_baja_dispositivo")
    def test_obtener_ficha_baja_construye_urls_del_siwih_actual(
        self,
        mock_consultar,
    ):
        mock_consultar.return_value = {
            "ok": True,
            "data": {
                "ficha": {
                    "url": "/media/EQUIPOS/BAJAS/ficha.webp",
                    "miniatura": "/media/EQUIPOS/BAJAS/thumb_ficha.webp",
                }
            },
        }

        ficha, servidor_inactivo = (
            MediaService.obtener_ficha_baja_dispositivo(19)
        )

        self.assertFalse(servidor_inactivo)
        self.assertEqual(
            ficha["url"],
            "/media/equipos/BAJAS/ficha.webp",
        )
        self.assertEqual(
            ficha["miniatura"],
            "/media/equipos/BAJAS/thumb_ficha.webp",
        )
