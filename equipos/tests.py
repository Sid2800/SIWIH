from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.constants.choices_constants import EstadoRegistro, TipoUnidad
from rrhh.models import Empleado
from servicio.models import Area_atencion, Servicio, Unidad

from .models import (
    AreaGestora,
    AsignacionDispositivo,
    BajaDispositivo,
    ColorDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    EstadoDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    OrdenTrabajoBajaDispositivo,
    TipoDispositivo,
    TipoTecnologiaDispositivo,
)
from .services.ficha_baja_pdf_service import FichaBajaPdfService


class EquiposViewsTests(TestCase):
    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        # Datos base compartidos por todas las pruebas: usuario, catalogos,
        # ubicaciones, responsable y un equipo con asignacion activa.
        cls.usuario = get_user_model().objects.create_user(
            username='usuario_equipos',
            password='clave-prueba'
        )
        cls.usuario_secundario = get_user_model().objects.create_user(
            username="usuario_equipos_2",
            password="clave-prueba-2",
        )
        cls.tipo = TipoDispositivo.objects.create(nombre="MONITOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="MINDRAY")
        cls.modelo = ModeloDispositivo.objects.create(nombre="BENE VIEW")
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")
        cls.servicio = Servicio.objects.create(
            nombre_servicio="Emergencia",
            nombre_corto="EMER",
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.area_clinica = Area_atencion.objects.create(
            servicio=cls.servicio,
            nombre_area_atencion="Observación",
            nombre_corto_area_atencion="OBS",
            estado=EstadoRegistro.ACTIVO,
        )
        cls.unidad_no_clinica = Unidad.objects.create(
            nombre_unidad="Biomédica",
            nombre_corto_unidad="BIOM",
            tipo=TipoUnidad.ADMINISTRATIVA,
            estado=EstadoRegistro.ACTIVO,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.responsable_original = Empleado.objects.create(
            dni="0801199000001",
            primer_nombre="Ana",
            primer_apellido="Lopez",
            estado=EstadoRegistro.ACTIVO,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.responsable_nuevo = Empleado.objects.create(
            dni="0801199000002",
            primer_nombre="Luis",
            primer_apellido="Martinez",
            estado=EstadoRegistro.ACTIVO,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.dispositivo = Dispositivo.objects.create(
            tipo=cls.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=cls.marca,
            modelo=cls.modelo,
            area_gestora=cls.area_gestora,
            color=cls.color,
            numero_serie="SERIE-ORIGINAL",
            estado=EstadoDispositivo.OPERATIVO,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.asignacion_original = AsignacionDispositivo.objects.create(
            dispositivo=cls.dispositivo,
            area_clinica=cls.area_clinica,
            responsable=cls.responsable_original,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        # Las pruebas del modulo no dependen de que el servidor externo este
        # encendido; cada caso controla explicitamente su respuesta.
        self.subir_imagen_mock = patch(
            "equipos.views.MediaService.subir_imagen_dispositivo",
            return_value={
                "ok": True,
                "imagen": {"uuid": "uuid-imagen-prueba"},
            },
        ).start()
        self.obtener_imagenes_mock = patch(
            "equipos.views.MediaService.obtener_imagenes_dispositivo",
            return_value=([], False),
        ).start()
        self.subir_ficha_baja_mock = patch(
            "equipos.views.MediaService.subir_ficha_baja_dispositivo",
            return_value={
                "ok": True,
                "ficha": {
                    "uuid": "11111111-1111-4111-8111-111111111111",
                },
            },
        ).start()
        self.obtener_ficha_baja_mock = patch(
            "equipos.views.MediaService.obtener_ficha_baja_dispositivo",
            return_value=(None, False),
        ).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def _foto_general_webp():
        contenido = BytesIO()
        Image.new("RGB", (20, 20), "white").save(contenido, "WEBP")
        return SimpleUploadedFile(
            "equipo.webp",
            contenido.getvalue(),
            content_type="image/webp",
        )

    def _reservar_orden_trabajo(self, usuario=None):
        orden, _ = OrdenTrabajoBajaDispositivo.objects.get_or_create(
            dispositivo=self.dispositivo,
            defaults={"creado_por": usuario or self.usuario},
        )
        return orden

    def _datos_formulario_dispositivo(self, **sobrescribir):
        # Payload reutilizable para POST de registro/edicion.
        datos = {
            "tipo": self.tipo.id,
            "tipo_tecnologia": TipoTecnologiaDispositivo.ELECTRONICO,
            "marca": self.marca.id,
            "modelo": self.modelo.id,
            "area_gestora": self.area_gestora.id,
            "color": self.color.id,
            "numero_serie": "SERIE-PRUEBA",
            "inventario_bienes_nacionales": "",
            "inventario_numero_ficha": "",
            "estado": EstadoDispositivo.OPERATIVO,
            "criticidad": CriticidadDispositivo.MEDIA,
            "frecuencia_mantenimiento_meses": "",
            "fecha_instalacion": "",
            "fin_garantia": "",
            "costo_adquisicion": "",
            "observaciones": "",
            "tipo_area": "clinica",
            "area_clinica": self.area_clinica.id,
            "unidad_no_clinica": "",
            "responsable": self.responsable_original.id,
            "foto_general": self._foto_general_webp(),
        }
        datos.update(sobrescribir)
        return datos

    def test_usuario_autenticado_puede_abrir_pantallas_del_modulo(self):
        # Prueba de humo: las pantallas principales deben responder 200.
        nombres_rutas = [
            'inicio_equipos',
            'registrar_dispositivo_equipos',
            'listado_dispositivos_equipos',
            'buscar_dispositivo_equipos',
        ]

        for nombre_ruta in nombres_rutas:
            with self.subTest(nombre_ruta=nombre_ruta):
                respuesta = self.client.get(reverse(nombre_ruta))

                self.assertEqual(respuesta.status_code, 200)

    def test_url_equipos_es_canonica(self):
        self.assertEqual(reverse("inicio_equipos"), "/equipos/")
        self.assertEqual(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            f"/equipos/dispositivos/{self.dispositivo.id}/",
        )

    def test_inicio_solo_muestra_opciones_del_inventario(self):
        respuesta = self.client.get(reverse("inicio_equipos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Registrar equipo")
        self.assertContains(respuesta, "Listado de equipos")
        self.assertContains(respuesta, "Buscar equipo")
        self.assertEqual(
            respuesta.content.decode().count(
                '<section class="equipos-submenu">'
            ),
            1,
        )
        self.assertNotContains(respuesta, "Registrar mantenimiento")
        self.assertNotContains(respuesta, "Reporte de inventario")

    def test_vistas_de_imagenes_cargan_herramientas_multimedia(self):
        # Estos helpers crean el modal de recorte y el visor compartido. Si una
        # plantilla reemplaza extra_js, los botones de imagen quedan inactivos.
        rutas = [
            reverse("registrar_dispositivo_equipos"),
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            reverse(
                "tramite_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
        ]

        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)

                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(
                    respuesta,
                    "core/vendor/cropper/cropper.min.js",
                )
                self.assertContains(
                    respuesta,
                    "core/scripts/media/editorImageHelper.js",
                )
                self.assertContains(
                    respuesta,
                    "core/scripts/media/visorImageHelper.js",
                )

    def test_busqueda_empleados_solo_consulta_dni_y_nombre(self):
        url = reverse("buscar_empleados_equipos")

        respuesta_dni = self.client.get(
            url,
            {"q": self.responsable_original.dni},
        )
        respuesta_nombre = self.client.get(url, {"q": "Ana Lopez"})

        self.assertEqual(respuesta_dni.status_code, 200)
        self.assertEqual(respuesta_nombre.status_code, 200)
        self.assertEqual(
            respuesta_dni.json()["results"][0],
            {
                "id": self.responsable_original.id,
                "text": (
                    f"{self.responsable_original.dni} - "
                    f"{self.responsable_original.nombre_completo}"
                ),
            },
        )
        self.assertIn(
            self.responsable_original.id,
            [
                resultado["id"]
                for resultado in respuesta_nombre.json()["results"]
            ],
        )

        empleado_solo_por_id = Empleado.objects.create(
            dni="9999999999999",
            primer_nombre="Zoe",
            primer_apellido="Prueba",
            estado=EstadoRegistro.ACTIVO,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        respuesta_id = self.client.get(url, {"q": str(empleado_solo_por_id.id)})

        self.assertNotIn(
            empleado_solo_por_id.id,
            [
                resultado["id"]
                for resultado in respuesta_id.json()["results"]
            ],
        )

    def test_detalle_inexistente_responde_404(self):
        respuesta = self.client.get(
            reverse('detalle_dispositivo_equipos', args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_detalle_muestra_foto_general_del_equipo(self):
        url_imagen = "http://imagenes.test/media/EQUIPOS/general.webp"
        self.obtener_imagenes_mock.return_value = (
            [
                {
                    "tipo_imagen": "GENERAL",
                    "url": url_imagen,
                    "miniatura": "http://imagenes.test/media/EQUIPOS/thumb.webp",
                }
            ],
            False,
        )

        respuesta = self.client.get(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'src="{url_imagen}"')
        self.assertContains(
            respuesta,
            f'alt="Foto general del equipo {self.dispositivo.codigo}"',
        )
        self.assertContains(respuesta, "1 de 6")
        self.obtener_imagenes_mock.assert_called_once_with(self.dispositivo.id)

    @patch(
        "core.views.RequestService.obtener_archivo_media_equipo",
        return_value={
            "contenido": b"foto-equipo",
            "content_type": "image/webp",
            "etag": '"foto-general"',
        },
    )
    def test_proxy_media_equipo_sirve_imagen_con_sesion(
        self,
        mock_obtener_archivo,
    ):
        respuesta = self.client.get(
            reverse(
                "media_equipo_proxy",
                kwargs={"ruta_archivo": "2026/07/general.webp"},
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content, b"foto-equipo")
        self.assertEqual(respuesta["Content-Type"], "image/webp")
        self.assertEqual(respuesta["ETag"], '"foto-general"')
        self.assertEqual(respuesta["Cache-Control"], "private, max-age=300")
        mock_obtener_archivo.assert_called_once_with(
            "EQUIPOS/2026/07/general.webp"
        )

    def test_proxy_media_equipo_exige_inicio_de_sesion(self):
        self.client.logout()
        url = reverse(
            "media_equipo_proxy",
            kwargs={"ruta_archivo": "2026/07/general.webp"},
        )

        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta["Location"].startswith("/login/?next="))

    def test_detalle_sin_imagen_muestra_marcador(self):
        respuesta = self.client.get(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Sin fotografía")

    def test_detalle_abre_si_servidor_de_imagenes_no_responde(self):
        self.obtener_imagenes_mock.return_value = ([], True)

        respuesta = self.client.get(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Fotografía no disponible")
        self.assertNotContains(respuesta, "Sin fotografía")

    def test_detalle_muestra_galeria_y_categorias_pendientes(self):
        self.obtener_imagenes_mock.return_value = (
            [
                {
                    "tipo_imagen": "GENERAL",
                    "url": "http://imagenes.test/media/general.webp",
                    "miniatura": "http://imagenes.test/media/thumb-general.webp",
                },
                {
                    "tipo_imagen": "INVENTARIO",
                    "url": "http://imagenes.test/media/inventario.webp",
                    "miniatura": "http://imagenes.test/media/thumb-inventario.webp",
                },
            ],
            False,
        )

        respuesta = self.client.get(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Fotografías del equipo")
        self.assertContains(respuesta, "2 de 6")
        self.assertContains(
            respuesta,
            'data-imagen-url="http://imagenes.test/media/inventario.webp"',
        )
        self.assertContains(respuesta, "Placa o serie")
        self.assertContains(respuesta, "Sin fotografía")

    def test_registro_crea_dispositivo_y_asignacion_inicial(self):
        # Registrar equipo debe crear Dispositivo y AsignacionDispositivo activa.
        respuesta = self.client.post(
            reverse('registrar_dispositivo_equipos'),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-REGISTRO",
                inventario_bienes_nacionales="BN-REG-001",
                inventario_numero_ficha="FICHA-REG-001",
                observaciones="Equipo creado desde prueba.",
            ),
        )
        dispositivo = Dispositivo.objects.get(numero_serie="SERIE-REGISTRO")
        asignacion = dispositivo.asignaciones.get(fecha_fin__isnull=True)

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[dispositivo.id]),
        )
        self.assertEqual(dispositivo.creado_por, self.usuario)
        self.assertEqual(dispositivo.modificado_por, self.usuario)
        self.assertEqual(dispositivo.inventario_bienes_nacionales, "BN-REG-001")
        self.assertEqual(dispositivo.area_gestora, self.area_gestora)
        self.assertEqual(dispositivo.color, self.color)
        self.assertEqual(asignacion.area_clinica, self.area_clinica)
        self.assertEqual(asignacion.responsable, self.responsable_original)
        self.assertEqual(asignacion.creado_por, self.usuario)
        self.subir_imagen_mock.assert_called_once()
        argumentos = self.subir_imagen_mock.call_args.kwargs
        self.assertEqual(argumentos["dispositivo_id"], dispositivo.id)
        self.assertEqual(argumentos["tipo_imagen"], "GENERAL")
        self.assertEqual(argumentos["usuario"], self.usuario)

    def test_registro_exige_foto_general(self):
        datos = self._datos_formulario_dispositivo(
            numero_serie="SERIE-SIN-FOTO",
        )
        datos.pop("foto_general")

        respuesta = self.client.post(
            reverse('registrar_dispositivo_equipos'),
            datos,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"],
            "foto_general",
            "Debe agregar una foto general del equipo.",
        )
        self.assertFalse(
            Dispositivo.objects.filter(numero_serie="SERIE-SIN-FOTO").exists()
        )
        self.subir_imagen_mock.assert_not_called()

    def test_registro_revierte_datos_si_falla_servidor_imagenes(self):
        self.subir_imagen_mock.return_value = {
            "ok": False,
            "error": "Servidor no disponible",
        }

        respuesta = self.client.post(
            reverse('registrar_dispositivo_equipos'),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-FALLO-IMAGEN",
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"],
            "foto_general",
            "No se pudo guardar la foto. Intente nuevamente.",
        )
        self.assertFalse(
            Dispositivo.objects.filter(
                numero_serie="SERIE-FALLO-IMAGEN"
            ).exists()
        )
        self.assertEqual(
            AsignacionDispositivo.objects.filter(
                dispositivo__numero_serie="SERIE-FALLO-IMAGEN"
            ).count(),
            0,
        )

    def test_area_gestora_no_permite_indefinido(self):
        area = AreaGestora(nombre="INDEFINIDO")

        with self.assertRaisesMessage(Exception, "El area gestora debe ser un area real."):
            area.full_clean()

    def test_formulario_no_muestra_area_gestora_indefinida(self):
        AreaGestora.objects.filter(nombre="INDEFINIDO").update(activo=True)

        respuesta = self.client.get(reverse('registrar_dispositivo_equipos'))
        opciones = list(respuesta.context["form"].fields["area_gestora"].queryset)

        self.assertIn(self.area_gestora, opciones)
        self.assertFalse(any(area.nombre == "INDEFINIDO" for area in opciones))

    def test_registro_exige_area_gestora(self):
        respuesta = self.client.post(
            reverse('registrar_dispositivo_equipos'),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-SIN-AREA-GESTORA",
                area_gestora="",
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(
            respuesta.context["form"],
            "area_gestora",
            "Este campo es obligatorio.",
        )
        self.assertFalse(
            Dispositivo.objects.filter(numero_serie="SERIE-SIN-AREA-GESTORA").exists()
        )

    def test_registro_permite_fecha_instalacion_futura(self):
        fecha_futura = date.today() + timedelta(days=30)
        respuesta = self.client.post(
            reverse('registrar_dispositivo_equipos'),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-FECHA-FUTURA",
                fecha_instalacion=fecha_futura.isoformat(),
            ),
        )

        dispositivo = Dispositivo.objects.get(numero_serie="SERIE-FECHA-FUTURA")

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[dispositivo.id]),
        )
        self.assertEqual(dispositivo.fecha_instalacion, fecha_futura)

    def test_usuario_autenticado_puede_abrir_edicion(self):
        respuesta = self.client.get(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Editar equipo")
        self.assertNotContains(respuesta, "Trámite de baja")
        self.assertContains(respuesta, self.dispositivo.codigo)

    def test_edicion_muestra_fotos_existentes_y_solo_tipos_faltantes(self):
        self.obtener_imagenes_mock.return_value = (
            [
                {
                    "tipo_imagen": "GENERAL",
                    "url": "http://imagenes.test/media/general.webp",
                    "miniatura": "http://imagenes.test/media/thumb-general.webp",
                }
            ],
            False,
        )

        respuesta = self.client.get(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Fotografías del equipo")
        self.assertContains(respuesta, "1 de 6")
        self.assertContains(
            respuesta,
            '<option value="INVENTARIO">Inventario</option>',
            html=True,
        )
        self.assertNotContains(
            respuesta,
            '<option value="GENERAL">General</option>',
            html=True,
        )

    def test_agregar_fotografia_faltante_no_modifica_datos_del_equipo(self):
        self.obtener_imagenes_mock.return_value = (
            [{"tipo_imagen": "GENERAL", "url": "general.webp"}],
            False,
        )
        numero_serie_original = self.dispositivo.numero_serie

        respuesta = self.client.post(
            reverse(
                "agregar_imagen_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "tipo_imagen": "INVENTARIO",
                "archivo": self._foto_general_webp(),
            },
        )

        self.assertRedirects(
            respuesta,
            reverse(
                "editar_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            fetch_redirect_response=False,
        )
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.numero_serie, numero_serie_original)
        self.subir_imagen_mock.assert_called_once()
        argumentos = self.subir_imagen_mock.call_args.kwargs
        self.assertEqual(argumentos["dispositivo_id"], self.dispositivo.id)
        self.assertEqual(argumentos["tipo_imagen"], "INVENTARIO")
        self.assertEqual(argumentos["usuario"], self.usuario)

    def test_agregar_fotografia_rechaza_tipo_ya_registrado(self):
        self.obtener_imagenes_mock.return_value = (
            [{"tipo_imagen": "GENERAL", "url": "general.webp"}],
            False,
        )

        respuesta = self.client.post(
            reverse(
                "agregar_imagen_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "tipo_imagen": "GENERAL",
                "archivo": self._foto_general_webp(),
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.subir_imagen_mock.assert_not_called()

    def test_agregar_fotografia_se_bloquea_si_servidor_no_responde(self):
        self.obtener_imagenes_mock.return_value = ([], True)

        respuesta = self.client.post(
            reverse(
                "agregar_imagen_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "tipo_imagen": "GENERAL",
                "archivo": self._foto_general_webp(),
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.subir_imagen_mock.assert_not_called()

    def test_detalle_no_muestra_acciones_de_edicion_o_baja(self):
        respuesta = self.client.get(
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(
            respuesta,
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id]),
        )
        self.assertNotContains(respuesta, "Trámite de baja")
        self.assertContains(respuesta, "Ver / Imprimir QR")

    def test_edicion_actualiza_dispositivo_y_asignacion(self):
        # Si cambia ubicacion/responsable, la asignacion anterior se cierra
        # y se crea una nueva.
        respuesta = self.client.post(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id]),
            {
                "tipo": self.tipo.id,
                "tipo_tecnologia": TipoTecnologiaDispositivo.NO_ELECTRONICO,
                "marca": self.marca.id,
                "modelo": self.modelo.id,
                "area_gestora": self.area_gestora.id,
                "color": self.color.id,
                "numero_serie": "SERIE-EDITADA",
                "inventario_bienes_nacionales": "F/212300",
                "inventario_numero_ficha": "FICHA-001",
                "estado": EstadoDispositivo.FUERA_DE_SERVICIO,
                "criticidad": CriticidadDispositivo.ALTA,
                "frecuencia_mantenimiento_meses": "",
                "fecha_instalacion": "",
                "fin_garantia": "",
                "costo_adquisicion": "",
                "observaciones": "Equipo actualizado en prueba.",
                "tipo_area": "no_clinica",
                "area_clinica": "",
                "unidad_no_clinica": self.unidad_no_clinica.id,
                "responsable": self.responsable_nuevo.id,
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

        self.dispositivo.refresh_from_db()
        self.asignacion_original.refresh_from_db()
        asignacion_actual = self.dispositivo.asignaciones.get(fecha_fin__isnull=True)

        self.assertEqual(self.dispositivo.numero_serie, "SERIE-EDITADA")
        self.assertEqual(
            self.dispositivo.tipo_tecnologia,
            TipoTecnologiaDispositivo.NO_ELECTRONICO,
        )
        self.assertEqual(self.dispositivo.estado, EstadoDispositivo.FUERA_DE_SERVICIO)
        self.assertIsNotNone(self.asignacion_original.fecha_fin)
        self.assertEqual(asignacion_actual.unidad_no_clinica, self.unidad_no_clinica)
        self.assertEqual(asignacion_actual.responsable, self.responsable_nuevo)

    def test_estado_repuesto_pendiente_se_guarda_y_sigue_activo(self):
        respuesta = self.client.post(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id]),
            self._datos_formulario_dispositivo(
                estado=EstadoDispositivo.REPUESTO_PENDIENTE,
                numero_serie="SERIE-REPUESTO",
            ),
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

        self.dispositivo.refresh_from_db()
        self.assertEqual(
            self.dispositivo.estado,
            EstadoDispositivo.REPUESTO_PENDIENTE,
        )

        respuesta_listado = self.client.get(reverse('listado_dispositivos_equipos'))
        self.assertContains(respuesta_listado, self.dispositivo.codigo)
        self.assertContains(respuesta_listado, "Rep.")
        self.assertContains(respuesta_listado, "Repuesto pendiente")
    def test_edicion_sin_cambio_de_ubicacion_no_duplica_asignacion(self):
        # Editar datos administrativos no debe duplicar historial de asignacion.
        respuesta = self.client.post(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id]),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-ORIGINAL",
                observaciones="Solo se actualizan datos administrativos.",
            ),
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

        self.asignacion_original.refresh_from_db()

        self.assertIsNone(self.asignacion_original.fecha_fin)
        self.assertEqual(
            self.dispositivo.asignaciones.filter(fecha_fin__isnull=True).count(),
            1,
        )
        self.assertEqual(self.dispositivo.asignaciones.count(), 1)

    def test_usuario_autenticado_puede_abrir_baja(self):
        respuesta = self.client.get(
            reverse(
                'tramite_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Trámite de baja")
        self.assertContains(respuesta, self.dispositivo.codigo)
        self.assertContains(respuesta, "Generar ficha PDF")
        self.assertContains(respuesta, "Confirmar baja definitiva")
        self.assertContains(respuesta, "Responsable de la petición")
        self.assertContains(respuesta, 'id="responsable_peticion_baja"')
        self.assertContains(
            respuesta,
            reverse("buscar_empleados_equipos"),
        )
        self.assertContains(respuesta, "Habitación / Estancia")
        self.assertNotContains(
            respuesta,
            "Comentario del responsable de mantenimiento",
        )

    def test_listado_y_busqueda_muestran_tramite_en_hamburguesa(self):
        url_tramite = reverse(
            "tramite_baja_dispositivo_equipos",
            args=[self.dispositivo.id],
        )

        respuesta_listado = self.client.get(
            reverse("listado_dispositivos_equipos")
        )
        respuesta_busqueda = self.client.get(
            reverse("buscar_dispositivo_equipos"),
            {"q": self.dispositivo.codigo},
        )

        self.assertContains(respuesta_listado, url_tramite)
        self.assertContains(respuesta_listado, "Trámite de baja")
        self.assertContains(respuesta_busqueda, url_tramite)

    def test_ficha_baja_pdf_no_registra_baja_ni_cambia_estado(self):
        respuesta = self.client.post(
            reverse(
                'ficha_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "Observación 2",
                "motivo": "Daño irreversible para previsualizar.",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("inline;", respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"%PDF"))
        self.assertFalse(
            BajaDispositivo.objects.filter(dispositivo=self.dispositivo).exists()
        )
        orden = OrdenTrabajoBajaDispositivo.objects.get(
            dispositivo=self.dispositivo
        )
        self.assertEqual(orden.creado_por, self.usuario)
        self.assertEqual(
            orden.numero_orden,
            f"OT-{orden.fecha_creado.year}-{orden.id:05d}",
        )

        self.dispositivo.refresh_from_db()
        self.assertEqual(
            self.dispositivo.estado,
            EstadoDispositivo.OPERATIVO,
        )

    def test_otro_usuario_reutiliza_la_orden_del_mismo_equipo(self):
        url_ficha = reverse(
            "ficha_baja_dispositivo_equipos",
            args=[self.dispositivo.id],
        )
        datos_ficha = {
            "fecha_baja": date.today().isoformat(),
            "responsable_peticion": self.responsable_nuevo.id,
            "habitacion_estancia": "Observación 2",
            "motivo": "Daño irreversible para previsualizar.",
        }

        self.client.post(url_ficha, datos_ficha)
        orden_original = OrdenTrabajoBajaDispositivo.objects.get(
            dispositivo=self.dispositivo
        )
        numero_original = orden_original.numero_orden

        self.client.force_login(self.usuario_secundario)
        respuesta = self.client.post(url_ficha, datos_ficha)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            OrdenTrabajoBajaDispositivo.objects.filter(
                dispositivo=self.dispositivo
            ).count(),
            1,
        )
        orden_original.refresh_from_db()
        self.assertEqual(orden_original.numero_orden, numero_original)
        self.assertEqual(orden_original.creado_por, self.usuario)

    def test_ficha_baja_pdf_rechaza_datos_invalidos(self):
        respuesta = self.client.post(
            reverse(
                'ficha_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "",
                "motivo": "",
            },
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(
            BajaDispositivo.objects.filter(dispositivo=self.dispositivo).exists()
        )

    def test_codigo_inventario_pdf_usa_solo_numero_de_ficha(self):
        Dispositivo.objects.filter(pk=self.dispositivo.pk).update(
            inventario_bienes_nacionales="BN-001",
            inventario_numero_ficha="FICHA-001",
        )
        self.dispositivo.refresh_from_db()

        self.assertEqual(
            FichaBajaPdfService._codigo_inventario(self.dispositivo),
            "FICHA-001",
        )

    @override_settings(EQUIPOS_QR_BASE_URL="http://192.168.0.102:8000")
    def test_qr_usa_url_base_configurada(self):
        # El QR debe usar la base configurada para que funcione desde telefono/red.
        respuesta = self.client.get(
            reverse('qr_dispositivo_equipos', args=[self.dispositivo.id])
        )
        detalle_url = (
            "http://192.168.0.102:8000"
            + reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, detalle_url)

    def test_baja_crea_registro_y_cambia_estado_del_dispositivo(self):
        # Dar de baja crea historial y cambia el estado sin eliminar la ficha.
        orden = self._reservar_orden_trabajo()
        respuesta = self.client.post(
            reverse(
                'tramite_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "Observación 2",
                "motivo": "Equipo retirado de uso por daño irreversible.",
                "ficha_firmada": self._foto_general_webp(),
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

        self.dispositivo.refresh_from_db()
        baja = self.dispositivo.baja

        self.assertEqual(self.dispositivo.estado, EstadoDispositivo.DADO_DE_BAJA)
        self.assertEqual(baja.motivo, "Equipo retirado de uso por daño irreversible.")
        self.assertEqual(
            baja.responsable_peticion,
            self.responsable_nuevo,
        )
        self.assertEqual(baja.habitacion_estancia, "Observación 2")
        self.assertEqual(
            str(baja.ficha_firmada_uuid),
            "11111111-1111-4111-8111-111111111111",
        )
        self.assertEqual(baja.registrado_por, self.usuario)
        self.assertEqual(
            self.dispositivo.orden_trabajo_baja,
            orden,
        )
        self.subir_ficha_baja_mock.assert_called_once()

    def test_baja_exige_generar_primero_la_orden_de_trabajo(self):
        respuesta = self.client.post(
            reverse(
                "tramite_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "",
                "motivo": "Equipo retirado de uso.",
                "ficha_firmada": self._foto_general_webp(),
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Primero debe generar la ficha PDF",
        )
        self.subir_ficha_baja_mock.assert_not_called()
        self.assertFalse(
            BajaDispositivo.objects.filter(
                dispositivo=self.dispositivo
            ).exists()
        )

    def test_baja_exige_ficha_firmada(self):
        respuesta = self.client.post(
            reverse(
                "tramite_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "",
                "motivo": "Equipo retirado de uso.",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Este campo es obligatorio")
        self.subir_ficha_baja_mock.assert_not_called()
        self.assertFalse(
            BajaDispositivo.objects.filter(
                dispositivo=self.dispositivo
            ).exists()
        )
        self.dispositivo.refresh_from_db()
        self.assertEqual(
            self.dispositivo.estado,
            EstadoDispositivo.OPERATIVO,
        )

    def test_fallo_subiendo_ficha_no_da_de_baja_el_equipo(self):
        self._reservar_orden_trabajo()
        self.subir_ficha_baja_mock.return_value = {
            "ok": False,
            "error": "Servidor no disponible",
        }

        respuesta = self.client.post(
            reverse(
                "tramite_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "",
                "motivo": "Equipo retirado de uso.",
                "ficha_firmada": self._foto_general_webp(),
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "El equipo no fue dado de baja",
        )
        self.assertFalse(
            BajaDispositivo.objects.filter(
                dispositivo=self.dispositivo
            ).exists()
        )
        self.dispositivo.refresh_from_db()
        self.assertEqual(
            self.dispositivo.estado,
            EstadoDispositivo.OPERATIVO,
        )

    def test_baja_permite_dispositivo_con_datos_incompletos(self):
        self._reservar_orden_trabajo()
        Dispositivo.objects.filter(pk=self.dispositivo.pk).update(
            tipo_tecnologia=None,
            numero_serie=None,
        )

        respuesta = self.client.post(
            reverse(
                'tramite_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "responsable_peticion": self.responsable_nuevo.id,
                "habitacion_estancia": "",
                "motivo": "Equipo viejo sin todos los datos técnicos.",
                "ficha_firmada": self._foto_general_webp(),
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

        self.dispositivo.refresh_from_db()

        self.assertEqual(self.dispositivo.estado, EstadoDispositivo.DADO_DE_BAJA)
        self.assertIsNone(self.dispositivo.tipo_tecnologia)
        self.assertIsNone(self.dispositivo.numero_serie)
        self.assertTrue(
            BajaDispositivo.objects.filter(dispositivo=self.dispositivo).exists()
        )

    def test_baja_bloquea_edicion_del_dispositivo(self):
        BajaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            fecha_baja=date.today(),
            motivo="Equipo retirado de inventario.",
            registrado_por=self.usuario,
        )
        self.dispositivo.estado = EstadoDispositivo.DADO_DE_BAJA
        self.dispositivo.save(update_fields=["estado"])

        respuesta = self.client.get(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )

    def test_detalle_de_baja_muestra_ficha_firmada(self):
        orden = self._reservar_orden_trabajo()
        BajaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            fecha_baja=date.today(),
            motivo="Equipo retirado de inventario.",
            responsable_peticion=self.responsable_nuevo,
            habitacion_estancia="Sala 2",
            ficha_firmada_uuid=(
                "22222222-2222-4222-8222-222222222222"
            ),
            registrado_por=self.usuario,
        )
        self.dispositivo.estado = EstadoDispositivo.DADO_DE_BAJA
        self.dispositivo.save(update_fields=["estado"])
        self.obtener_ficha_baja_mock.return_value = (
            {
                "uuid": "22222222-2222-4222-8222-222222222222",
                "url": "http://imagenes.test/media/ficha.webp",
            },
            False,
        )

        respuesta = self.client.get(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertContains(respuesta, self.responsable_nuevo.nombre_completo)
        self.assertContains(respuesta, "Sala 2")
        self.assertContains(respuesta, orden.numero_orden)
        self.assertContains(respuesta, "Ver ficha firmada")
        self.assertContains(respuesta, "bi-file-earmark-check-fill")
        self.assertContains(respuesta, "bi-box-arrow-up-right")
        self.assertContains(
            respuesta,
            "http://imagenes.test/media/ficha.webp",
        )
        self.assertNotContains(
            respuesta,
            "No fue posible recuperar la ficha firmada",
        )

    def test_baja_no_se_duplica(self):
        BajaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            fecha_baja=date.today(),
            motivo="Baja registrada previamente.",
            registrado_por=self.usuario,
        )

        respuesta = self.client.post(
            reverse(
                'tramite_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "motivo": "Segundo intento de baja.",
            },
        )

        self.assertRedirects(
            respuesta,
            reverse('detalle_dispositivo_equipos', args=[self.dispositivo.id]),
        )
        self.assertEqual(
            BajaDispositivo.objects.filter(dispositivo=self.dispositivo).count(),
            1,
        )

    def test_listado_oculta_bajas_por_defecto_y_las_muestra_con_filtro(self):
        # Inventario normal muestra equipos activos; bajas aparecen solo al filtrar.
        BajaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            fecha_baja=date.today(),
            motivo="Equipo fuera del inventario activo.",
            registrado_por=self.usuario,
        )
        self.dispositivo.estado = EstadoDispositivo.DADO_DE_BAJA
        self.dispositivo.save(update_fields=["estado"])

        respuesta_default = self.client.get(reverse('listado_dispositivos_equipos'))
        respuesta_filtrada = self.client.get(
            reverse('listado_dispositivos_equipos'),
            {"estado": EstadoDispositivo.DADO_DE_BAJA},
        )

        self.assertNotContains(respuesta_default, self.dispositivo.codigo)
        self.assertContains(respuesta_filtrada, self.dispositivo.codigo)

    def test_buscador_listado_excluye_serie_modelo_y_area_gestora(self):
        url = reverse("listado_dispositivos_equipos")

        for consulta in (
            self.dispositivo.numero_serie,
            self.modelo.nombre,
            self.area_gestora.nombre,
        ):
            with self.subTest(consulta=consulta):
                respuesta = self.client.get(url, {"q": consulta})

                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, self.dispositivo.codigo)

    def test_buscador_listado_mantiene_campos_principales(self):
        url = reverse("listado_dispositivos_equipos")

        for consulta in (
            self.dispositivo.codigo,
            self.tipo.nombre,
            self.marca.nombre,
            self.color.nombre,
        ):
            with self.subTest(consulta=consulta):
                respuesta = self.client.get(url, {"q": consulta})

                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, self.dispositivo.codigo)

    def test_busqueda_equipo_usa_los_mismos_campos_que_el_listado(self):
        url = reverse("buscar_dispositivo_equipos")

        for consulta in (
            self.dispositivo.numero_serie,
            self.modelo.nombre,
            self.area_gestora.nombre,
        ):
            with self.subTest(campo_excluido=consulta):
                respuesta = self.client.get(url, {"q": consulta})

                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, self.dispositivo.codigo)

        for consulta in (
            self.dispositivo.codigo,
            self.tipo.nombre,
            self.marca.nombre,
            self.color.nombre,
        ):
            with self.subTest(campo_permitido=consulta):
                respuesta = self.client.get(url, {"q": consulta})

                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, self.dispositivo.codigo)

    def test_busqueda_conserva_la_consulta(self):
        respuesta = self.client.get(
            reverse('buscar_dispositivo_equipos'),
            {'q': 'Monitor EQ-001'}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['consulta'], 'Monitor EQ-001')
        self.assertContains(respuesta, 'Monitor EQ-001')
