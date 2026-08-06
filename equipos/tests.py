from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from io import BytesIO
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.constants.choices_constants import (
    AlcanceUsuario,
    EstadoRegistro,
    RolUsuario,
    TipoUnidad,
)
from expediente.models import ExpedienteUbicacion
from rrhh.models import Empleado
from servicio.models import Area_atencion, Servicio, Unidad
from usuario.models import PerfilUnidad

from .models import (
    AreaGestora,
    AsignacionDispositivo,
    BajaDispositivo,
    ColorDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    DIAS_AVISO_GARANTIA,
    EstadoDispositivo,
    EstadoGarantiaDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    OrdenTrabajoBajaDispositivo,
    PausaGarantia,
    TipoDispositivo,
    TipoTecnologiaDispositivo,
)
from .forms import CostoLempirasField, DispositivoCreateForm
from .services.garantia_service import (
    calcular_estado_garantia,
    puede_pausarse,
)
from .permisos import (
    puede_administrar_catalogos_equipos,
    puede_dar_baja_equipos,
    puede_editar_equipos,
    puede_visualizar_equipos,
)
from .signals import CODIGO_UNIDAD as CODIGO_UNIDAD_EQUIPOS
from .signals import asegurar_unidad_equipos
from .services.ficha_baja_pdf_service import FichaBajaPdfService
from .services.ficha_activo_fijo_pdf_service import FichaActivoFijoPdfService


def unidad_equipos():
    """Devuelve la unidad EQ, creandola si la migracion no alcanzo a hacerlo.

    En pruebas la base arranca vacia y la migracion 0026 se salta la creacion
    cuando no hay ningun usuario todavia. Aqui la garantizamos.
    """
    responsable = get_user_model().objects.order_by("pk").first()
    unidad, _ = Unidad.objects.get_or_create(
        nombre_corto_unidad="EQ",
        defaults={
            "nombre_unidad": "Equipos",
            "tipo": TipoUnidad.APOYO,
            "estado": EstadoRegistro.ACTIVO,
            "creado_por": responsable,
            "modificado_por": responsable,
        },
    )
    return unidad


def dar_acceso_equipos(usuario, rol=RolUsuario.DIGITADOR):
    """Asigna al usuario un PerfilUnidad en EQ con alcance de unidad."""
    return PerfilUnidad.objects.create(
        usuario=usuario,
        servicio_unidad=unidad_equipos(),
        alcance=AlcanceUsuario.UNIDAD,
        rol=rol,
    )


def dar_acceso_global(usuario, rol=RolUsuario.ADMIN):
    """Asigna un perfil institucional: entra a EQ sin pertenecer a la unidad."""
    return PerfilUnidad.objects.create(
        usuario=usuario,
        servicio_unidad=None,
        alcance=AlcanceUsuario.GLOBAL,
        rol=rol,
    )


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
        # Estas pruebas verifican el comportamiento del modulo, no el control de
        # acceso: los usuarios necesitan permiso para llegar a las vistas.
        dar_acceso_equipos(cls.usuario)
        dar_acceso_equipos(cls.usuario_secundario)
        cls.tipo = TipoDispositivo.objects.create(nombre="MONITOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="MINDRAY")
        # Un modelo ya no existe suelto: cuelga siempre de su marca.
        cls.modelo = ModeloDispositivo.objects.create(
            marca=cls.marca, nombre="BENE VIEW"
        )
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
            # Por defecto se registra con un solo color: el secundario es la
            # excepcion, no la norma.
            "color_secundario": "",
            "numero_serie": "SERIE-PRUEBA",
            "inventario_bienes_nacionales": "",
            "inventario_numero_ficha": "",
            "estado": EstadoDispositivo.OPERATIVO,
            "criticidad": CriticidadDispositivo.MEDIA,
            "frecuencia_mantenimiento_meses": "",
            "fecha_instalacion": "",
            "fecha_fin_garantia": "",
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
            'catalogo_marcas_equipos',
        ]

        for nombre_ruta in nombres_rutas:
            with self.subTest(nombre_ruta=nombre_ruta):
                respuesta = self.client.get(reverse(nombre_ruta))

                self.assertEqual(respuesta.status_code, 200)

    def test_el_menu_enlaza_al_catalogo_de_marcas(self):
        # Sin enlace la pantalla existe pero nadie la encuentra.
        respuesta = self.client.get(reverse('inicio_equipos'))

        self.assertContains(respuesta, reverse('catalogo_marcas_equipos'))
        self.assertContains(respuesta, 'Marcas y modelos')

    # --- Color secundario -------------------------------------------------

    def test_registro_con_un_solo_color_deja_el_secundario_vacio(self):
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(numero_serie="SOLO-UN-COLOR"),
        )
        equipo = Dispositivo.objects.filter(numero_serie="SOLO-UN-COLOR").first()

        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNotNone(equipo)
        self.assertIsNone(equipo.color_secundario_id)

    def test_registro_admite_dos_colores_distintos(self):
        segundo = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]

        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="DOS-COLORES", color_secundario=segundo.id
            ),
        )
        equipo = Dispositivo.objects.filter(numero_serie="DOS-COLORES").first()

        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNotNone(equipo)
        self.assertEqual(equipo.color_id, self.color.id)
        self.assertEqual(equipo.color_secundario_id, segundo.id)

    def test_registro_rechaza_dos_colores_iguales(self):
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="COLOR-REPETIDO", color_secundario=self.color.id
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "El color secundario debe ser diferente del color principal",
        )
        self.assertFalse(
            Dispositivo.objects.filter(numero_serie="COLOR-REPETIDO").exists()
        )

    def test_edicion_agrega_cambia_y_quita_el_color_secundario(self):
        azul = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]
        verde = ColorDispositivo.objects.get_or_create(nombre="VERDE")[0]
        url = reverse("editar_dispositivo_equipos", args=[self.dispositivo.id])
        datos = self._datos_formulario_dispositivo(
            numero_serie=self.dispositivo.numero_serie
        )
        datos.pop("foto_general", None)

        # Agregar
        self.client.post(url, {**datos, "color_secundario": azul.id})
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.color_secundario_id, azul.id)

        # Cambiar
        self.client.post(url, {**datos, "color_secundario": verde.id})
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.color_secundario_id, verde.id)

        # Quitar
        self.client.post(url, {**datos, "color_secundario": ""})
        self.dispositivo.refresh_from_db()
        self.assertIsNone(self.dispositivo.color_secundario_id)

    def test_los_colores_inactivos_no_se_ofrecen_en_ninguno_de_los_dos(self):
        retirado = ColorDispositivo.objects.create(
            nombre="COLOR RETIRADO", activo=False
        )

        form = DispositivoCreateForm()

        self.assertNotIn(retirado, form.fields["color"].queryset)
        self.assertNotIn(retirado, form.fields["color_secundario"].queryset)

    def test_la_edicion_conserva_el_color_secundario_inactivo_del_equipo(self):
        # Si el color se desactiva despues, abrir el equipo no puede obligar a
        # cambiarlo para poder guardar.
        azul = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]
        self.dispositivo.color_secundario = azul
        self.dispositivo.save()
        azul.activo = False
        azul.save()

        form = DispositivoCreateForm(instance=self.dispositivo)

        self.assertIn(azul, form.fields["color_secundario"].queryset)

    def test_el_selector_secundario_ofrece_la_opcion_vacia_con_su_texto(self):
        respuesta = self.client.get(reverse("registrar_dispositivo_equipos"))

        self.assertContains(respuesta, "Sin color secundario")
        self.assertContains(respuesta, "color_secundario_dispositivo")

    def test_el_detalle_muestra_los_dos_colores(self):
        azul = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]
        self.dispositivo.color_secundario = azul
        self.dispositivo.save()

        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.id])
        )

        self.assertContains(respuesta, "Color principal")
        self.assertContains(respuesta, "Color secundario")
        self.assertContains(respuesta, "AZUL")

    def test_el_detalle_sin_color_secundario_dice_no_indicado(self):
        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.id])
        )

        self.assertContains(respuesta, "Color secundario")
        self.assertContains(respuesta, "No indicado")

    def test_un_equipo_previo_a_la_migracion_conserva_sus_datos(self):
        # La migracion es un AddField con null=True: los equipos que ya
        # existian no se tocan y quedan sin color secundario.
        self.dispositivo.refresh_from_db()

        self.assertIsNone(self.dispositivo.color_secundario_id)
        self.assertEqual(self.dispositivo.color_id, self.color.id)

    def test_un_color_usado_como_secundario_no_se_puede_borrar(self):
        azul = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]
        self.dispositivo.color_secundario = azul
        self.dispositivo.save()

        with self.assertRaises(ProtectedError):
            azul.delete()

    def test_un_tipo_con_equipos_no_se_puede_borrar(self):
        # El catalogo solo ofrece desactivar, pero la proteccion real vive en
        # el modelo: aunque se intente por otra via, no se pierde el historico.
        with self.assertRaises(ProtectedError):
            self.dispositivo.tipo.delete()

    def test_los_tipos_inactivos_no_se_ofrecen_al_registrar(self):
        retirado = TipoDispositivo.objects.create(
            nombre="TIPO RETIRADO", activo=False
        )

        form = DispositivoCreateForm()

        self.assertNotIn(retirado, form.fields["tipo"].queryset)

    def test_la_edicion_conserva_el_tipo_inactivo_del_equipo(self):
        # Si el tipo se desactiva despues de registrar, abrir el equipo no
        # puede obligar a cambiarlo para poder guardar.
        tipo = self.dispositivo.tipo
        tipo.activo = False
        tipo.save()

        form = DispositivoCreateForm(instance=self.dispositivo)

        self.assertIn(tipo, form.fields["tipo"].queryset)

    def test_el_tipo_se_busca_por_ajax(self):
        respuesta = self.client.get(reverse("registrar_dispositivo_equipos"))

        self.assertContains(respuesta, "data-url-tipos")
        self.assertContains(respuesta, reverse("buscar_tipos_equipos"))

    def test_ficha_se_muestra_arriba_con_su_etiqueta_corta(self):
        respuesta = self.client.get(reverse("registrar_dispositivo_equipos"))
        html = respuesta.content.decode()

        self.assertIn('<label for="inventario_numero_ficha">Ficha</label>', html)
        self.assertNotIn("Inventario número de ficha", html)
        self.assertIn('placeholder="Ej. F/212300"', html)
        # Debe quedar fuera del bloque plegable de datos opcionales.
        self.assertLess(
            html.index("inventario_numero_ficha"),
            html.index("equipos-registro__opcionales"),
        )

    def test_inventario_de_bienes_nacionales_solo_dice_opcional(self):
        respuesta = self.client.get(reverse("registrar_dispositivo_equipos"))
        html = respuesta.content.decode()

        self.assertIn("Inventario de bienes nacionales", html)
        self.assertNotIn("Ej. F/212300 (opcional)", html)

    def test_url_equipos_es_canonica(self):
        self.assertEqual(reverse("inicio_equipos"), "/equipos/")
        self.assertEqual(
            reverse(
                "detalle_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            f"/equipos/dispositivos/{self.dispositivo.id}/",
        )

    def test_inicio_muestra_inventario_y_catalogos_sin_opciones_inexistentes(self):
        # El menu tiene dos secciones: lo que se opera a diario y lo que se
        # configura. Sigue sin anunciar funciones que aun no existen.
        respuesta = self.client.get(reverse("inicio_equipos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Registrar equipo")
        self.assertContains(respuesta, "Listado de equipos")
        self.assertContains(respuesta, "Buscar equipo")
        self.assertContains(respuesta, "Marcas y modelos")
        self.assertEqual(
            respuesta.content.decode().count(
                '<section class="equipos-submenu">'
            ),
            2,
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

    def test_registro_guarda_la_garantia_como_fecha_del_contrato(self):
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-GARANTIA-FECHA",
                fecha_fin_garantia="2028-03-15",
            ),
        )

        dispositivo = Dispositivo.objects.get(numero_serie="SERIE-GARANTIA-FECHA")
        self.assertRedirects(
            respuesta,
            reverse("detalle_dispositivo_equipos", args=[dispositivo.id]),
        )
        self.assertEqual(dispositivo.fecha_fin_garantia, date(2028, 3, 15))

        detalle = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[dispositivo.id])
        )
        self.assertContains(detalle, "15/03/2028")

    def test_registro_admite_equipo_sin_garantia(self):
        # Sin garantia se expresa dejando la fecha vacia, no con una opcion.
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-SIN-GARANTIA",
                fecha_fin_garantia="",
            ),
        )

        dispositivo = Dispositivo.objects.get(numero_serie="SERIE-SIN-GARANTIA")
        self.assertRedirects(
            respuesta,
            reverse("detalle_dispositivo_equipos", args=[dispositivo.id]),
        )
        self.assertIsNone(dispositivo.fecha_fin_garantia)

    def test_registro_admite_garantia_ya_vencida(self):
        # Hace falta para cargar inventario antiguo: el equipo existe y su
        # garantia caduco, y eso tambien es un hecho que hay que poder anotar.
        self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-GARANTIA-VIEJA",
                fecha_fin_garantia="2020-01-01",
            ),
        )

        dispositivo = Dispositivo.objects.get(numero_serie="SERIE-GARANTIA-VIEJA")
        self.assertEqual(dispositivo.fecha_fin_garantia, date(2020, 1, 1))

    def test_registro_rechaza_una_fecha_de_garantia_invalida(self):
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                numero_serie="SERIE-GARANTIA-INVALIDA",
                fecha_fin_garantia="no-es-una-fecha",
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors.get("fecha_fin_garantia"))
        self.assertFalse(
            Dispositivo.objects.filter(
                numero_serie="SERIE-GARANTIA-INVALIDA"
            ).exists()
        )

    def test_usuario_autenticado_puede_abrir_edicion(self):
        respuesta = self.client.get(
            reverse('editar_dispositivo_equipos', args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Editar equipo")
        self.assertNotContains(respuesta, "Trámite de baja")
        self.assertContains(respuesta, self.dispositivo.codigo)

    def test_tramite_de_baja_permite_ampliar_la_foto_del_equipo(self):
        # La baja es irreversible: hay que poder mirar bien la foto antes de
        # confirmar que es el equipo correcto.
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
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="ampliar_foto_equipo"')
        self.assertContains(respuesta, "equipos-baja__equipo-imagen--ampliable")
        self.assertContains(respuesta, "http://imagenes.test/media/general.webp")

    def test_tramite_sin_foto_no_ofrece_ampliar(self):
        # Sin foto se muestra un icono, que no abre nada: no debe insinuar
        # que se puede pulsar.
        self.obtener_imagenes_mock.return_value = ([], False)

        respuesta = self.client.get(
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.id])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="ampliar_foto_equipo"')

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
                "fecha_fin_garantia": "2028-01-15",
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
        self.assertContains(respuesta, "Equipo seleccionado")

    def test_tramite_baja_muestra_la_imagen_general_del_equipo(self):
        self.obtener_imagenes_mock.return_value = (
            [
                {
                    "tipo_imagen": "GENERAL",
                    "url": "http://imagenes.test/equipo-general.webp",
                }
            ],
            False,
        )

        respuesta = self.client.get(
            reverse(
                "tramite_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "http://imagenes.test/equipo-general.webp",
        )
        self.assertContains(
            respuesta,
            f"Foto general del equipo {self.dispositivo.codigo}",
        )
        self.assertContains(respuesta, "Empleado asignado")
        self.assertContains(respuesta, self.responsable_original.nombre_completo)
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
        with patch(
            "equipos.services.ficha_baja_pdf_service."
            "ReportePdfBaseService.dibujar_pie_pagina_carta"
        ) as dibujar_pie_pagina:
            respuesta = self.client.post(
                reverse(
                    'ficha_baja_dispositivo_equipos',
                    args=[self.dispositivo.id],
                ),
                {
                    "fecha_baja": date.today().isoformat(),
                    "habitacion_estancia": "Observación 2",
                    "motivo": "Daño irreversible para previsualizar.",
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("inline;", respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"%PDF"))
        self.assertFalse(
            dibujar_pie_pagina.call_args.kwargs["mostrar_paginacion"]
        )
        self.assertEqual(dibujar_pie_pagina.call_args.args[5], "")
        self.assertEqual(
            dibujar_pie_pagina.call_args.kwargs["etiqueta_usuario"],
            "GENERADO POR: ",
        )
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

    def test_detalle_ofrece_ficha_de_activo_fijo(self):
        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.id])
        )
        url_ficha = reverse(
            "ficha_activo_fijo_equipos",
            args=[self.dispositivo.id],
        )

        self.assertContains(respuesta, url_ficha)
        self.assertContains(respuesta, "Ficha de activo fijo")

    def test_ficha_activo_fijo_genera_pdf_sin_modificar_el_equipo(self):
        fecha_modificado = self.dispositivo.fecha_modificado

        with patch(
            "equipos.services.ficha_activo_fijo_pdf_service."
            "ReportePdfBaseService.dibujar_pie_pagina_carta"
        ) as dibujar_pie_pagina:
            respuesta = self.client.get(
                reverse(
                    "ficha_activo_fijo_equipos",
                    args=[self.dispositivo.id],
                )
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn("inline;", respuesta["Content-Disposition"])
        self.assertIn(self.dispositivo.codigo, respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"%PDF"))
        self.assertFalse(
            dibujar_pie_pagina.call_args.kwargs["mostrar_paginacion"]
        )
        self.assertEqual(
            dibujar_pie_pagina.call_args.kwargs["etiqueta_usuario"],
            "GENERADO POR: ",
        )
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.fecha_modificado, fecha_modificado)

    def test_ficha_activo_fijo_mapea_datos_y_deja_campos_manuales_vacios(self):
        azul = ColorDispositivo.objects.get_or_create(nombre="AZUL")[0]
        Dispositivo.objects.filter(pk=self.dispositivo.pk).update(
            color_secundario=azul,
            numero_serie="SERIE-ACTIVO-001",
            inventario_bienes_nacionales="BN-100",
            inventario_numero_ficha="F/212300",
            costo_adquisicion=Decimal("12500.50"),
        )
        self.dispositivo.refresh_from_db()

        datos = FichaActivoFijoPdfService.construir_datos(
            self.dispositivo,
            self.asignacion_original,
        )

        self.assertEqual(datos["numero_inventario"], "BN-100")
        self.assertEqual(datos["inventario_bn"], "F/212300")
        self.assertIn("MONITOR", datos["descripcion"])
        self.assertEqual(datos["marca"], "MINDRAY")
        self.assertEqual(datos["modelo"], "BENE VIEW")
        self.assertEqual(datos["color"], "BLANCO / AZUL")
        self.assertEqual(datos["numero_serie"], "SERIE-ACTIVO-001")
        self.assertEqual(datos["precio"], "L 12,500.50")
        self.assertEqual(datos["departamento"], str(self.area_clinica))
        self.assertEqual(
            datos["fecha_entrega"],
            timezone.localtime(self.dispositivo.fecha_creado).strftime(
                "%d/%m/%Y"
            ),
        )

        campos_manuales = (
            "potencia",
            "principal_componente",
            "inactivo",
            "en_reparacion",
            "fecha_baja",
            "numero_factura",
            "tipo_garantia",
            "activo_sustituido",
            "orden_compra",
            "comprobante",
            "familia",
            "subfamilia",
            "codigo_local",
            "centro_costo",
            "sala_ambiente",
            "jefe_departamento",
            "proveedor",
            "proveedor_mantenimiento",
            "contrato_mantenimiento",
            "fecha_inicio_contrato",
            "fecha_fin_contrato",
            "tipo_contrato",
        )
        self.assertTrue(all(datos[campo] == "" for campo in campos_manuales))

    def test_la_ficha_rellena_la_garantia_con_el_vencimiento_real(self):
        # Estas dos casillas estaban vacias hasta que la garantia paso a ser
        # una fecha. Se imprime el vencimiento ya ajustado con las pausas,
        # que es hasta cuando se le puede reclamar al proveedor.
        self.dispositivo.fecha_fin_garantia = date(2028, 3, 15)
        self.dispositivo.save(update_fields=["fecha_fin_garantia"])
        # El equipo debe llevar tiempo registrado para admitir una pausa que
        # empezo hace tres semanas.
        registrar_equipo_el(self.dispositivo, date(2026, 1, 1))
        PausaGarantia.objects.create(
            dispositivo=self.dispositivo,
            fecha_salida=timezone.localdate() - timedelta(days=20),
            fecha_retorno=timezone.localdate() - timedelta(days=5),
            registrado_por=self.usuario,
        )

        datos = FichaActivoFijoPdfService.construir_datos(self.dispositivo, None)

        self.assertEqual(datos["fecha_fin_garantia"], "30/03/2028")
        self.assertIn("mes", datos["duracion_garantia"])

    def test_la_ficha_marca_la_garantia_como_indefinida_si_no_hay(self):
        self.dispositivo.fecha_fin_garantia = None
        self.dispositivo.save(update_fields=["fecha_fin_garantia"])

        datos = FichaActivoFijoPdfService.construir_datos(self.dispositivo, None)

        self.assertEqual(datos["fecha_fin_garantia"], "INDEFINIDO")
        self.assertEqual(datos["duracion_garantia"], "INDEFINIDO")

    def test_otro_usuario_reutiliza_la_orden_del_mismo_equipo(self):
        url_ficha = reverse(
            "ficha_baja_dispositivo_equipos",
            args=[self.dispositivo.id],
        )
        datos_ficha = {
            "fecha_baja": date.today().isoformat(),
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
                "habitacion_estancia": "",
                "motivo": "",
            },
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(
            BajaDispositivo.objects.filter(dispositivo=self.dispositivo).exists()
        )

    def test_ficha_baja_pdf_rechaza_equipo_sin_asignacion_activa(self):
        self.asignacion_original.fecha_fin = timezone.now()
        self.asignacion_original.save(update_fields=["fecha_fin"])

        respuesta = self.client.post(
            reverse(
                "ficha_baja_dispositivo_equipos",
                args=[self.dispositivo.id],
            ),
            {
                "fecha_baja": date.today().isoformat(),
                "habitacion_estancia": "",
                "motivo": "Equipo retirado de uso.",
            },
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(
            respuesta,
            "El equipo no tiene una asignación activa",
            status_code=400,
        )
        self.assertFalse(
            OrdenTrabajoBajaDispositivo.objects.filter(
                dispositivo=self.dispositivo
            ).exists()
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
        fecha_esperada = timezone.localdate()
        respuesta = self.client.post(
            reverse(
                'tramite_baja_dispositivo_equipos',
                args=[self.dispositivo.id],
            ),
            {
                # Aunque un cliente intente enviar otra fecha, el formulario
                # no la acepta y el servidor usa la fecha de confirmacion.
                "fecha_baja": "2000-01-01",
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
        self.assertEqual(baja.fecha_baja, fecha_esperada)
        self.assertEqual(baja.motivo, "Equipo retirado de uso por daño irreversible.")
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

        self.assertContains(respuesta, self.responsable_original.nombre_completo)
        self.assertContains(respuesta, "Sala 2")
        self.assertContains(respuesta, orden.numero_orden)
        self.assertContains(respuesta, "Ver ficha firmada")
        # La constancia se abre en el visor compartido, pero conserva el href
        # para que siga funcionando si el visor no carga.
        self.assertContains(respuesta, 'id="abrir_ficha_firmada"')
        self.assertContains(respuesta, "http://imagenes.test/media/ficha.webp")
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

    def test_listado_incluye_boton_buscar_vinculado_a_los_filtros(self):
        respuesta = self.client.get(reverse("listado_dispositivos_equipos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "equipos-listado__boton-buscar")
        self.assertContains(respuesta, 'form="equipos-listado-filtros"', count=2)

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
        self.assertNotContains(
            respuesta,
            "Los resultados de la consulta se muestran debajo.",
        )


    # --- Pareja marca-modelo: se valida en el servidor, no solo en el
    #     navegador, porque un POST directo se salta el filtro del Select2.

    def test_registro_rechaza_un_modelo_de_otra_marca(self):
        otra_marca = MarcaDispositivo.objects.create(nombre="PHILIPS")
        modelo_ajeno = ModeloDispositivo.objects.create(
            marca=otra_marca, nombre="INTELLIVUE MX450"
        )

        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                marca=self.marca.id,
                modelo=modelo_ajeno.id,
                numero_serie="SERIE-COMBINACION",
            ),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(
            Dispositivo.objects.filter(numero_serie="SERIE-COMBINACION").exists()
        )

    def test_edicion_rechaza_un_modelo_de_otra_marca(self):
        otra_marca = MarcaDispositivo.objects.create(nombre="DRAGER")
        modelo_ajeno = ModeloDispositivo.objects.create(
            marca=otra_marca, nombre="EVITA V300"
        )
        datos = self._datos_formulario_dispositivo(
            marca=self.marca.id,
            modelo=modelo_ajeno.id,
        )
        datos.pop("foto_general")

        respuesta = self.client.post(
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.id]),
            datos,
        )

        self.dispositivo.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.dispositivo.modelo, self.modelo)

    def test_cambiar_de_marca_descarta_el_modelo_incompatible(self):
        # Al enviar otra marca, el modelo anterior deja de estar entre las
        # opciones validas: el formulario no lo conserva.
        otra_marca = MarcaDispositivo.objects.create(nombre="GE HEALTHCARE")
        form = DispositivoCreateForm(
            data=self._datos_formulario_dispositivo(
                marca=otra_marca.id,
                modelo=self.modelo.id,
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("modelo", form.errors)
        self.assertNotIn(
            self.modelo, form.fields["modelo"].queryset
        )

    def test_equipo_sin_modelo_se_muestra_como_indefinido(self):
        self.dispositivo.modelo = None
        self.dispositivo.save()

        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.id])
        )

        self.assertIsNone(self.dispositivo.modelo_id)
        self.assertEqual(self.dispositivo.modelo_nombre, "INDEFINIDO")
        self.assertContains(respuesta, "INDEFINIDO")

    def test_registro_acepta_dejar_el_modelo_vacio(self):
        respuesta = self.client.post(
            reverse("registrar_dispositivo_equipos"),
            self._datos_formulario_dispositivo(
                modelo="",
                numero_serie="SERIE-SIN-MODELO",
            ),
        )

        equipo = Dispositivo.objects.filter(
            numero_serie="SERIE-SIN-MODELO"
        ).first()

        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNotNone(equipo)
        self.assertIsNone(equipo.modelo_id)
        self.assertEqual(equipo.modelo_nombre, "INDEFINIDO")


class CatalogoMarcaModeloTests(TestCase):
    """Relacion marca-modelo, endpoints de autocompletado y vista de catalogo."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="catalogo", password="clave-catalogo"
        )
        dar_acceso_equipos(cls.usuario)
        cls.philips = MarcaDispositivo.objects.create(nombre="PHILIPS")
        cls.mindray = MarcaDispositivo.objects.create(nombre="MINDRAY")

    def setUp(self):
        self.client.force_login(self.usuario)

    # --- Modelo de datos -------------------------------------------------

    def test_una_marca_admite_varios_modelos(self):
        ModeloDispositivo.objects.create(marca=self.philips, nombre="MX450")
        ModeloDispositivo.objects.create(marca=self.philips, nombre="MX500")

        self.assertEqual(self.philips.modelos.count(), 2)

    def test_no_permite_repetir_modelo_en_la_misma_marca(self):
        ModeloDispositivo.objects.create(marca=self.philips, nombre="MX450")

        with self.assertRaises(ValidationError):
            ModeloDispositivo.objects.create(marca=self.philips, nombre="MX450")

    def test_permite_el_mismo_nombre_en_marcas_distintas(self):
        uno = ModeloDispositivo.objects.create(marca=self.philips, nombre="SERIE 100")
        otro = ModeloDispositivo.objects.create(marca=self.mindray, nombre="SERIE 100")

        self.assertNotEqual(uno.pk, otro.pk)
        self.assertEqual(uno.nombre, otro.nombre)

    def test_normaliza_el_nombre_a_mayusculas(self):
        modelo = ModeloDispositivo.objects.create(
            marca=self.philips, nombre="  intellivue mx550  "
        )

        self.assertEqual(modelo.nombre, "INTELLIVUE MX550")

    # --- Endpoints de autocompletado -------------------------------------

    def test_endpoint_de_modelos_solo_devuelve_los_de_la_marca_pedida(self):
        ModeloDispositivo.objects.create(marca=self.philips, nombre="MX450")
        ModeloDispositivo.objects.create(marca=self.mindray, nombre="BENEVISION")

        respuesta = self.client.get(
            reverse("buscar_modelos_equipos"), {"marca_id": self.philips.pk}
        )
        textos = [r["text"] for r in respuesta.json()["results"]]

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(textos, ["MX450"])

    def test_endpoint_de_modelos_exige_marca(self):
        respuesta = self.client.get(reverse("buscar_modelos_equipos"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["results"], [])

    def test_endpoint_de_modelos_omite_los_inactivos(self):
        ModeloDispositivo.objects.create(marca=self.philips, nombre="VIGENTE")
        ModeloDispositivo.objects.create(
            marca=self.philips, nombre="RETIRADO", activo=False
        )

        respuesta = self.client.get(
            reverse("buscar_modelos_equipos"), {"marca_id": self.philips.pk}
        )
        textos = [r["text"] for r in respuesta.json()["results"]]

        self.assertEqual(textos, ["VIGENTE"])

    def test_endpoint_de_marcas_omite_las_inactivas(self):
        MarcaDispositivo.objects.create(nombre="DESCONTINUADA", activo=False)

        respuesta = self.client.get(reverse("buscar_marcas_equipos"))
        textos = [r["text"] for r in respuesta.json()["results"]]

        self.assertIn("PHILIPS", textos)
        self.assertNotIn("DESCONTINUADA", textos)

    def test_endpoint_de_marcas_informa_si_hay_mas_paginas(self):
        for indice in range(25):
            MarcaDispositivo.objects.create(nombre=f"MARCA {indice:03d}")

        respuesta = self.client.get(reverse("buscar_marcas_equipos"))
        cuerpo = respuesta.json()

        self.assertEqual(len(cuerpo["results"]), 20)
        self.assertTrue(cuerpo["pagination"]["more"])

    # --- Vista de catalogo -----------------------------------------------

    def test_catalogo_crea_una_marca(self):
        respuesta = self.client.post(
            reverse("agregar_marca_equipos"), {"nombre": "ge healthcare"}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            MarcaDispositivo.objects.filter(nombre="GE HEALTHCARE").exists()
        )

    def test_catalogo_rechaza_una_marca_duplicada(self):
        self.client.post(reverse("agregar_marca_equipos"), {"nombre": "philips"})

        self.assertEqual(
            MarcaDispositivo.objects.filter(nombre="PHILIPS").count(), 1
        )

    def test_catalogo_crea_un_modelo_dentro_de_la_marca(self):
        self.client.post(
            reverse("agregar_modelo_equipos", args=[self.philips.pk]),
            {"nombre": "intellivue mx700"},
        )

        modelo = ModeloDispositivo.objects.get(nombre="INTELLIVUE MX700")
        self.assertEqual(modelo.marca, self.philips)

    def test_catalogo_muestra_solo_los_modelos_de_la_marca_elegida(self):
        ModeloDispositivo.objects.create(marca=self.philips, nombre="MX450")
        ModeloDispositivo.objects.create(marca=self.mindray, nombre="BENEVISION")

        respuesta = self.client.get(
            reverse("catalogo_marcas_equipos"), {"marca": self.philips.pk}
        )

        self.assertContains(respuesta, "MX450")
        self.assertNotContains(respuesta, "BENEVISION")

    def test_catalogo_desactiva_y_reactiva_sin_borrar(self):
        modelo = ModeloDispositivo.objects.create(
            marca=self.philips, nombre="MX450"
        )
        url = reverse("cambiar_estado_modelo_equipos", args=[modelo.pk])

        self.client.post(url)
        modelo.refresh_from_db()
        self.assertFalse(modelo.activo)

        self.client.post(url)
        modelo.refresh_from_db()
        self.assertTrue(modelo.activo)
        self.assertTrue(ModeloDispositivo.objects.filter(pk=modelo.pk).exists())


class CostoEnLempirasTests(TestCase):
    """El importe se escribe y se muestra como se usa en Honduras: L 1,234.56"""

    databases = {"default"}

    def _limpiar(self, texto):
        return CostoLempirasField(
            required=False, max_digits=12, decimal_places=2
        ).clean(texto)

    def test_acepta_el_punto_decimal_hondureno(self):
        self.assertEqual(self._limpiar("1234.56"), Decimal("1234.56"))

    def test_acepta_la_coma_decimal_de_quien_viene_del_teclado_espanol(self):
        # Antes esto devolvia "Introduzca un numero" y parecia que el campo no
        # admitia decimales.
        self.assertEqual(self._limpiar("1234,56"), Decimal("1234.56"))

    def test_acepta_el_formato_completo_con_separador_de_miles(self):
        self.assertEqual(self._limpiar("1,234.56"), Decimal("1234.56"))

    def test_acepta_tambien_el_formato_espanol_completo(self):
        self.assertEqual(self._limpiar("1.234,56"), Decimal("1234.56"))

    def test_un_separador_con_tres_digitos_detras_es_de_miles(self):
        # "1,500" son mil quinientos lempiras, no uno con cinco.
        self.assertEqual(self._limpiar("1,500"), Decimal("1500"))
        self.assertEqual(self._limpiar("1.500"), Decimal("1500"))

    def test_acepta_varios_grupos_de_miles(self):
        self.assertEqual(self._limpiar("1,234,567.89"), Decimal("1234567.89"))

    def test_ignora_el_simbolo_de_moneda_y_los_espacios(self):
        self.assertEqual(self._limpiar("L 1,234.56"), Decimal("1234.56"))
        self.assertEqual(self._limpiar("L. 1,234.56"), Decimal("1234.56"))

    def test_un_entero_sin_separadores_no_cambia(self):
        self.assertEqual(self._limpiar("1234"), Decimal("1234"))

    def test_vacio_sigue_siendo_opcional(self):
        self.assertIsNone(self._limpiar(""))

    def test_el_detalle_muestra_el_formato_hondureno(self):
        # La propiedad evita que Django localice a la española (1234,56) y
        # deje la pantalla contradiciendo al formulario.
        equipo = Dispositivo(costo_adquisicion=Decimal("1234.56"))

        self.assertEqual(equipo.costo_formateado, "1,234.56")

    def test_sin_costo_la_propiedad_no_revienta(self):
        self.assertEqual(Dispositivo(costo_adquisicion=None).costo_formateado, "")

    def test_el_formulario_no_usa_input_numerico(self):
        # <input type="number"> depende del idioma del navegador y llega a
        # rechazar el punto decimal segun el equipo.
        html = str(DispositivoCreateForm()["costo_adquisicion"])

        self.assertNotIn('type="number"', html)
        self.assertIn('inputmode="decimal"', html)


class CatalogoTipoEquipoTests(TestCase):
    """Autocompletado de tipos y su gestion desde la vista de catalogo."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="catalogo-tipos", password="clave-tipos"
        )
        dar_acceso_equipos(cls.usuario)
        cls.monitor = TipoDispositivo.objects.create(nombre="MONITOR")
        cls.bomba = TipoDispositivo.objects.create(nombre="BOMBA DE INFUSION")

    def setUp(self):
        self.client.force_login(self.usuario)

    # --- Endpoint de autocompletado --------------------------------------

    def test_endpoint_de_tipos_filtra_por_texto(self):
        respuesta = self.client.get(
            reverse("buscar_tipos_equipos"), {"q": "bomba"}
        )
        nombres = [item["text"] for item in respuesta.json()["results"]]

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("BOMBA DE INFUSION", nombres)
        self.assertNotIn("MONITOR", nombres)

    def test_endpoint_de_tipos_sin_texto_devuelve_el_catalogo(self):
        # Permite abrir el selector y elegir con el raton sin escribir nada.
        respuesta = self.client.get(reverse("buscar_tipos_equipos"))
        nombres = [item["text"] for item in respuesta.json()["results"]]

        self.assertIn("MONITOR", nombres)
        self.assertIn("BOMBA DE INFUSION", nombres)

    def test_endpoint_de_tipos_omite_los_inactivos(self):
        self.bomba.activo = False
        self.bomba.save()

        respuesta = self.client.get(reverse("buscar_tipos_equipos"))
        nombres = [item["text"] for item in respuesta.json()["results"]]

        self.assertNotIn("BOMBA DE INFUSION", nombres)

    def test_endpoint_de_tipos_exige_sesion(self):
        self.client.logout()

        respuesta = self.client.get(reverse("buscar_tipos_equipos"))

        self.assertEqual(respuesta.status_code, 302)

    # --- Vista de catalogo -----------------------------------------------

    def test_catalogo_crea_un_tipo_normalizado(self):
        respuesta = self.client.post(
            reverse("agregar_tipo_equipos"), {"nombre": "desfibrilador"}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            TipoDispositivo.objects.filter(nombre="DESFIBRILADOR").exists()
        )

    def test_catalogo_rechaza_duplicado_por_mayusculas_y_espacios(self):
        self.client.post(
            reverse("agregar_tipo_equipos"), {"nombre": "  monitor  "}
        )

        self.assertEqual(
            TipoDispositivo.objects.filter(nombre="MONITOR").count(), 1
        )

    def test_catalogo_renombra_un_tipo(self):
        self.client.post(
            reverse("editar_tipo_equipos", args=[self.monitor.pk]),
            {"nombre": "monitor de signos vitales"},
        )
        self.monitor.refresh_from_db()

        self.assertEqual(self.monitor.nombre, "MONITOR DE SIGNOS VITALES")

    def test_renombrar_no_puede_chocar_con_otro_tipo(self):
        self.client.post(
            reverse("editar_tipo_equipos", args=[self.monitor.pk]),
            {"nombre": "bomba de infusion"},
        )
        self.monitor.refresh_from_db()

        self.assertEqual(self.monitor.nombre, "MONITOR")

    def test_catalogo_desactiva_y_reactiva_el_tipo_sin_borrarlo(self):
        url = reverse("cambiar_estado_tipo_equipos", args=[self.monitor.pk])

        self.client.post(url)
        self.monitor.refresh_from_db()
        self.assertFalse(self.monitor.activo)

        self.client.post(url)
        self.monitor.refresh_from_db()
        self.assertTrue(self.monitor.activo)
        self.assertTrue(
            TipoDispositivo.objects.filter(pk=self.monitor.pk).exists()
        )

    def test_catalogo_lista_los_tipos_y_su_formulario(self):
        respuesta = self.client.get(reverse("catalogo_marcas_equipos"))

        self.assertContains(respuesta, "Tipos de equipo")
        self.assertContains(respuesta, "MONITOR")
        self.assertContains(respuesta, reverse("agregar_tipo_equipos"))

    def test_catalogo_abre_el_modo_edicion_del_tipo_elegido(self):
        respuesta = self.client.get(
            reverse("catalogo_marcas_equipos"), {"tipo": self.monitor.pk}
        )

        self.assertContains(
            respuesta,
            reverse("editar_tipo_equipos", args=[self.monitor.pk]),
        )


class PermisosEquiposTests(TestCase):
    """Control de acceso del modulo: quien entra, quien no y a que."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        # Un usuario sin ningun PerfilUnidad: el caso del resto del hospital.
        cls.sin_permiso = Usuario.objects.create_user(
            username="enfermeria", password="clave-enfermeria"
        )
        cls.tecnico = Usuario.objects.create_user(
            username="tecnico-eq", password="clave-tecnico"
        )
        cls.admin_equipos = Usuario.objects.create_user(
            username="admin-eq", password="clave-admin"
        )
        cls.directivo = Usuario.objects.create_user(
            username="directivo-eq", password="clave-directivo"
        )
        # Rol correcto pero en otra unidad: no debe alcanzar Equipos.
        cls.digitador_otra_unidad = Usuario.objects.create_user(
            username="digitador-emergencia", password="clave-otra"
        )
        # is_staff abre el admin de Django; aqui no debe conceder nada.
        cls.staff = Usuario.objects.create_user(
            username="staff-sin-perfil", password="clave-staff", is_staff=True
        )
        cls.superusuario = Usuario.objects.create_superuser(
            username="root-eq", password="clave-root"
        )

        dar_acceso_equipos(cls.tecnico, RolUsuario.DIGITADOR)
        dar_acceso_equipos(cls.admin_equipos, RolUsuario.ADMIN)
        dar_acceso_equipos(cls.directivo, RolUsuario.DIRECTIVO)

        otra_unidad = Unidad.objects.create(
            nombre_unidad="Emergencia",
            nombre_corto_unidad="EMER",
            tipo=TipoUnidad.APOYO,
            estado=EstadoRegistro.ACTIVO,
            creado_por=cls.sin_permiso,
            modificado_por=cls.sin_permiso,
        )
        PerfilUnidad.objects.create(
            usuario=cls.digitador_otra_unidad,
            servicio_unidad=otra_unidad,
            alcance=AlcanceUsuario.UNIDAD,
            rol=RolUsuario.DIGITADOR,
        )

        cls.tipo = TipoDispositivo.objects.create(nombre="DESFIBRILADOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="ZOLL")
        cls.modelo = ModeloDispositivo.objects.create(
            marca=cls.marca, nombre="R SERIES"
        )
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")
        cls.dispositivo = Dispositivo.objects.create(
            tipo=cls.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=cls.marca,
            modelo=cls.modelo,
            area_gestora=cls.area_gestora,
            color=cls.color,
            numero_serie="SERIE-PERMISOS",
            estado=EstadoDispositivo.OPERATIVO,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=cls.tecnico,
            modificado_por=cls.tecnico,
        )

    # --- URLs agrupadas por capacidad ------------------------------------

    def urls_visualizacion(self):
        # El detalle no esta aqui a proposito: es la unica vista del modulo
        # abierta a cualquier usuario autenticado, porque es el destino de los
        # QR pegados a los equipos. Ver test_el_detalle_es_la_excepcion_del_qr
        # y la clase DetalleReducidoTests.
        return [
            reverse("inicio_equipos"),
            reverse("listado_dispositivos_equipos"),
            reverse("buscar_dispositivo_equipos"),
            reverse("qr_dispositivo_equipos", args=[self.dispositivo.pk]),
        ]

    def urls_edicion(self):
        return [
            reverse("registrar_dispositivo_equipos"),
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk]),
        ]

    def urls_catalogo(self):
        return [
            reverse("catalogo_marcas_equipos"),
            reverse("agregar_marca_equipos"),
            reverse("agregar_tipo_equipos"),
            reverse("agregar_modelo_equipos", args=[self.marca.pk]),
            reverse("editar_tipo_equipos", args=[self.tipo.pk]),
            reverse("cambiar_estado_marca_equipos", args=[self.marca.pk]),
            reverse("cambiar_estado_modelo_equipos", args=[self.modelo.pk]),
            reverse("cambiar_estado_tipo_equipos", args=[self.tipo.pk]),
        ]

    def urls_baja(self):
        return [
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk]),
            reverse("ficha_baja_dispositivo_equipos", args=[self.dispositivo.pk]),
        ]

    def urls_json(self):
        return [
            reverse("buscar_tipos_equipos"),
            reverse("buscar_marcas_equipos"),
            reverse("buscar_modelos_equipos"),
            reverse("buscar_empleados_equipos"),
        ]

    def assertRedirigeAAccesoDenegado(self, url, usuario):
        self.client.force_login(usuario)
        respuesta = self.client.get(url)
        self.assertRedirects(
            respuesta,
            reverse("acceso_denegado"),
            msg_prefix=f"{usuario.username} no deberia entrar a {url}",
        )

    def assertEntra(self, url, usuario):
        self.client.force_login(usuario)
        respuesta = self.client.get(url)
        self.assertNotEqual(
            respuesta.status_code,
            403,
            msg=f"{usuario.username} deberia entrar a {url}",
        )
        if respuesta.status_code in (301, 302):
            self.assertNotIn(
                reverse("acceso_denegado"),
                respuesta["Location"],
                msg=f"{usuario.username} deberia entrar a {url}",
            )

    # --- Usuario sin ningun perfil ---------------------------------------

    def test_usuario_sin_perfil_no_entra_a_ninguna_vista_html(self):
        urls = (
            self.urls_visualizacion()
            + self.urls_edicion()
            + self.urls_catalogo()
            + self.urls_baja()
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.sin_permiso)

    def test_usuario_sin_perfil_recibe_403_en_endpoints_json(self):
        self.client.force_login(self.sin_permiso)
        for url in self.urls_json():
            with self.subTest(url=url):
                respuesta = self.client.get(url, {"term": "a"})
                self.assertEqual(respuesta.status_code, 403)
                self.assertEqual(respuesta["Content-Type"], "application/json")

    def test_el_detalle_es_la_excepcion_del_qr(self):
        # Los codigos QR van pegados a los aparatos y los escanea cualquiera.
        # Por eso el detalle si abre sin permiso de Equipos, pero mostrando
        # una version reducida: el contenido lo cubre DetalleReducidoTests.
        url = reverse("detalle_dispositivo_equipos", args=[self.dispositivo.pk])

        for usuario in (self.sin_permiso, self.staff, self.digitador_otra_unidad):
            with self.subTest(usuario=usuario.username):
                self.assertEntra(url, usuario)

    def test_anonimo_es_enviado_al_login(self):
        respuesta = self.client.get(reverse("listado_dispositivos_equipos"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(reverse("acceso_denegado"), respuesta["Location"])

    # --- is_staff no es autorizacion --------------------------------------

    def test_is_staff_no_concede_acceso_a_equipos(self):
        for url in self.urls_visualizacion() + self.urls_edicion():
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.staff)

    def test_superusuario_entra_a_todo(self):
        urls = (
            self.urls_visualizacion()
            + self.urls_edicion()
            + [reverse("catalogo_marcas_equipos")]
            + [reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk])]
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEntra(url, self.superusuario)

    # --- El rol correcto en la unidad equivocada ---------------------------

    def test_digitador_de_otra_unidad_no_entra_a_equipos(self):
        for url in self.urls_visualizacion() + self.urls_edicion():
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.digitador_otra_unidad)

    def test_alcance_global_entra_sin_pertenecer_a_la_unidad(self):
        institucional = get_user_model().objects.create_user(
            username="admin-institucional", password="clave-inst"
        )
        dar_acceso_global(institucional, RolUsuario.ADMIN)
        for url in self.urls_visualizacion() + self.urls_edicion():
            with self.subTest(url=url):
                self.assertEntra(url, institucional)

    # --- Tecnico (digitador en EQ): el caso de uso principal ---------------

    def test_tecnico_entra_a_visualizacion_edicion_catalogo_y_baja(self):
        urls = (
            self.urls_visualizacion()
            + self.urls_edicion()
            + [reverse("catalogo_marcas_equipos")]
            + [reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk])]
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEntra(url, self.tecnico)

    def test_tecnico_usa_los_endpoints_de_autocompletado(self):
        self.client.force_login(self.tecnico)
        # buscar-modelos exige la marca; sin ella responde 400 por su propia
        # validacion, que no tiene nada que ver con los permisos.
        parametros = {
            reverse("buscar_modelos_equipos"): {"marca_id": self.marca.pk},
        }
        for url in self.urls_json():
            with self.subTest(url=url):
                respuesta = self.client.get(url, parametros.get(url, {}))
                self.assertEqual(respuesta.status_code, 200)

    def test_admin_de_equipos_entra_a_todo(self):
        urls = (
            self.urls_visualizacion()
            + self.urls_edicion()
            + [reverse("catalogo_marcas_equipos")]
            + [reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk])]
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEntra(url, self.admin_equipos)

    # --- Directivo: consulta, no toca -------------------------------------

    def test_directivo_consulta_el_inventario(self):
        for url in self.urls_visualizacion():
            with self.subTest(url=url):
                self.assertEntra(url, self.directivo)

    def test_directivo_no_edita_equipos(self):
        for url in self.urls_edicion():
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.directivo)

    def test_directivo_no_administra_catalogos(self):
        for url in self.urls_catalogo():
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.directivo)

    def test_directivo_no_tramita_bajas(self):
        for url in self.urls_baja():
            with self.subTest(url=url):
                self.assertRedirigeAAccesoDenegado(url, self.directivo)

    def test_directivo_no_usa_el_autocompletado_de_los_formularios(self):
        # Los Select2 de tipo, marca, modelo y responsable solo viven en el
        # formulario de equipos. Quien no puede editar no los necesita, y
        # dejarlos abiertos filtraria el catalogo y la nomina de empleados.
        self.client.force_login(self.directivo)
        for url in self.urls_json():
            with self.subTest(url=url):
                respuesta = self.client.get(url, {"term": ""})
                self.assertEqual(respuesta.status_code, 403)

    # --- POST tambien va protegido, no solo el GET -------------------------

    def test_post_de_edicion_sin_permiso_no_modifica_nada(self):
        self.client.force_login(self.directivo)
        respuesta = self.client.post(
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk]),
            {"numero_serie": "SERIE-ALTERADA"},
        )
        self.assertRedirects(respuesta, reverse("acceso_denegado"))
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.numero_serie, "SERIE-PERMISOS")

    def test_post_de_catalogo_sin_permiso_no_crea_marcas(self):
        self.client.force_login(self.directivo)
        respuesta = self.client.post(
            reverse("agregar_marca_equipos"), {"nombre": "MARCA INTRUSA"}
        )
        self.assertRedirects(respuesta, reverse("acceso_denegado"))
        self.assertFalse(
            MarcaDispositivo.objects.filter(nombre="MARCA INTRUSA").exists()
        )

    # --- Helpers de permisos ----------------------------------------------

    def test_helpers_reflejan_la_matriz_de_permisos(self):
        casos = [
            (self.sin_permiso, False, False, False, False),
            (self.staff, False, False, False, False),
            (self.digitador_otra_unidad, False, False, False, False),
            (self.directivo, True, False, False, False),
            (self.tecnico, True, True, True, True),
            (self.admin_equipos, True, True, True, True),
            (self.superusuario, True, True, True, True),
        ]
        for usuario, ver, editar, catalogo, baja in casos:
            with self.subTest(usuario=usuario.username):
                self.assertIs(puede_visualizar_equipos(usuario), ver)
                self.assertIs(puede_editar_equipos(usuario), editar)
                self.assertIs(puede_administrar_catalogos_equipos(usuario), catalogo)
                self.assertIs(puede_dar_baja_equipos(usuario), baja)

    def test_helpers_rechazan_al_anonimo(self):
        anonimo = AnonymousUser()
        self.assertFalse(puede_visualizar_equipos(anonimo))
        self.assertFalse(puede_editar_equipos(anonimo))
        self.assertFalse(puede_administrar_catalogos_equipos(anonimo))
        self.assertFalse(puede_dar_baja_equipos(anonimo))

    # --- Plantillas: lo que no se puede hacer, no se ofrece -----------------

    def test_menu_general_oculta_equipos_a_quien_no_lo_usa(self):
        enlace = reverse("inicio_equipos")
        self.client.force_login(self.sin_permiso)
        self.assertNotContains(self.client.get(reverse("home")), f'href="{enlace}"')
        self.client.force_login(self.tecnico)
        self.assertContains(self.client.get(reverse("home")), f'href="{enlace}"')

    def test_inicio_de_equipos_oculta_registrar_y_catalogos_al_directivo(self):
        self.client.force_login(self.directivo)
        respuesta = self.client.get(reverse("inicio_equipos"))
        self.assertNotContains(respuesta, reverse("registrar_dispositivo_equipos"))
        self.assertNotContains(respuesta, reverse("catalogo_marcas_equipos"))
        self.assertContains(respuesta, reverse("listado_dispositivos_equipos"))

    def test_inicio_de_equipos_muestra_todo_al_tecnico(self):
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("inicio_equipos"))
        self.assertContains(respuesta, reverse("registrar_dispositivo_equipos"))
        self.assertContains(respuesta, reverse("catalogo_marcas_equipos"))

    def test_listado_oculta_acciones_de_edicion_y_baja_al_directivo(self):
        self.client.force_login(self.directivo)
        respuesta = self.client.get(reverse("listado_dispositivos_equipos"))
        self.assertNotContains(
            respuesta,
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        self.assertNotContains(
            respuesta,
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        # El doble clic no se desarma: lleva al detalle, que es lo que este
        # usuario si puede ver. Una fila muerta se siente como un fallo.
        detalle = reverse("detalle_dispositivo_equipos", args=[self.dispositivo.pk])
        self.assertContains(respuesta, f'data-edit-url="{detalle}"')

    def test_listado_muestra_acciones_de_edicion_y_baja_al_tecnico(self):
        self.client.force_login(self.tecnico)
        respuesta = self.client.get(reverse("listado_dispositivos_equipos"))
        self.assertContains(
            respuesta,
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        self.assertContains(
            respuesta,
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        editar = reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk])
        self.assertContains(respuesta, f'data-edit-url="{editar}"')


class UnidadEquiposTests(TestCase):
    """La red de seguridad que garantiza la unidad EQ tras cada migrate."""

    databases = {"default"}

    def setUp(self):
        # Cada caso parte de una base sin la unidad, que es el estado en el
        # que queda una instalacion limpia. Hay que retirar antes la ubicacion
        # que expediente le crea por signal: la referencia con PROTECT y sin
        # quitarla la unidad no se puede borrar.
        ExpedienteUbicacion.objects.filter(
            unidad_no_clinica__nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS
        ).delete()
        Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).delete()

    def ejecutar_receptor(self, etiqueta_app="equipos"):
        asegurar_unidad_equipos(
            sender=None,
            app_config=django_apps.get_app_config(etiqueta_app),
        )

    def existe_eq(self):
        return Unidad.objects.filter(
            nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS
        ).exists()

    def test_crea_la_unidad_cuando_ya_hay_usuarios(self):
        get_user_model().objects.create_user(username="primero", password="clave")

        self.ejecutar_receptor()

        self.assertTrue(self.existe_eq())
        unidad = Unidad.objects.get(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS)
        self.assertEqual(unidad.nombre_unidad, "EQUIPOS")
        self.assertEqual(unidad.estado, EstadoRegistro.ACTIVO)
        self.assertIsNotNone(unidad.creado_por)

    def test_no_crea_nada_ni_falla_cuando_no_hay_usuarios(self):
        # Reproduce la instalacion limpia: migrate corre antes que
        # createsuperuser. El receptor no debe reventar, solo abstenerse.
        # Se simula el vacio en lugar de borrar usuarios porque media base
        # los referencia con PROTECT.
        Usuario = get_user_model()
        with patch.object(
            Usuario._default_manager.__class__,
            "get_queryset",
            return_value=Usuario.objects.none(),
        ):
            self.ejecutar_receptor()

        self.assertFalse(self.existe_eq())

    def test_ignora_el_aviso_de_las_demas_apps(self):
        # post_migrate se emite una vez por aplicacion instalada.
        get_user_model().objects.create_user(username="primero", password="clave")

        self.ejecutar_receptor(etiqueta_app="servicio")

        self.assertFalse(self.existe_eq())

    def test_es_idempotente_y_no_duplica_la_unidad(self):
        get_user_model().objects.create_user(username="primero", password="clave")

        self.ejecutar_receptor()
        self.ejecutar_receptor()

        self.assertEqual(
            Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).count(), 1
        )

    def test_no_pisa_una_unidad_existente(self):
        usuario = get_user_model().objects.create_user(
            username="primero", password="clave"
        )
        Unidad.objects.create(
            nombre_unidad="EQUIPOS BIOMEDICOS",
            nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS,
            tipo=TipoUnidad.APOYO,
            estado=EstadoRegistro.ACTIVO,
            creado_por=usuario,
            modificado_por=usuario,
        )

        self.ejecutar_receptor()

        unidad = Unidad.objects.get(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS)
        self.assertEqual(unidad.nombre_unidad, "EQUIPOS BIOMEDICOS")


class ReversaMigracionUnidadTests(TestCase):
    """La marcha atras de 0026 nunca debe interrumpir un rollback.

    Es el escenario acordado: probar la rama y poder volver al commit
    anterior. Si la reversa revienta, el rollback queda a medias.
    """

    databases = {"default"}

    def cargar_funciones(self):
        modulo = import_module("equipos.migrations.0026_unidad_equipos")
        return modulo.crear_unidad_equipos, modulo.quitar_unidad_equipos

    def estado_real(self):
        # La migracion recibe modelos historicos; aqui basta el registro real
        # porque el esquema no cambia entre 0025 y 0026.
        return django_apps

    def test_la_reversa_borra_la_unidad_si_nadie_la_usa(self):
        crear, quitar = self.cargar_funciones()
        usuario = get_user_model().objects.create_user(
            username="responsable-reversa", password="clave"
        )
        Unidad.objects.get_or_create(
            nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS,
            defaults={
                "nombre_unidad": "EQUIPOS",
                "tipo": TipoUnidad.APOYO,
                "estado": EstadoRegistro.ACTIVO,
                "creado_por": usuario,
                "modificado_por": usuario,
            },
        )
        # El signal de expediente crea la ubicacion protegida; se retira para
        # dejar la unidad realmente libre.
        ExpedienteUbicacion.objects.filter(
            unidad_no_clinica__nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS
        ).delete()

        quitar(self.estado_real(), None)

        self.assertFalse(
            Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).exists()
        )

    def test_la_reversa_no_revienta_con_la_ubicacion_protegida(self):
        # Es el estado normal tras un migrate: la unidad existe y expediente
        # ya le creo su ExpedienteUbicacion con FK PROTECT.
        _, quitar = self.cargar_funciones()
        usuario = get_user_model().objects.create_user(
            username="responsable-protegida", password="clave"
        )
        Unidad.objects.get_or_create(
            nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS,
            defaults={
                "nombre_unidad": "EQUIPOS",
                "tipo": TipoUnidad.APOYO,
                "estado": EstadoRegistro.ACTIVO,
                "creado_por": usuario,
                "modificado_por": usuario,
            },
        )
        self.assertTrue(
            ExpedienteUbicacion.objects.filter(
                unidad_no_clinica__nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS
            ).exists(),
            "expediente deberia haber creado la ubicacion por signal",
        )

        # No debe lanzar ProtectedError.
        quitar(self.estado_real(), None)

        # La unidad se conserva, que es lo correcto: borrarla seria meterse
        # con datos de otro modulo.
        self.assertTrue(
            Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).exists()
        )

    def test_la_reversa_conserva_la_unidad_si_hay_tecnicos_asignados(self):
        _, quitar = self.cargar_funciones()
        usuario = get_user_model().objects.create_user(
            username="tecnico-reversa", password="clave"
        )
        unidad, _ = Unidad.objects.get_or_create(
            nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS,
            defaults={
                "nombre_unidad": "EQUIPOS",
                "tipo": TipoUnidad.APOYO,
                "estado": EstadoRegistro.ACTIVO,
                "creado_por": usuario,
                "modificado_por": usuario,
            },
        )
        PerfilUnidad.objects.create(
            usuario=usuario,
            servicio_unidad=unidad,
            alcance=AlcanceUsuario.UNIDAD,
            rol=RolUsuario.DIGITADOR,
        )

        quitar(self.estado_real(), None)

        self.assertTrue(
            Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).exists()
        )

    def test_la_reversa_no_falla_si_la_unidad_no_existe(self):
        _, quitar = self.cargar_funciones()
        ExpedienteUbicacion.objects.filter(
            unidad_no_clinica__nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS
        ).delete()
        Unidad.objects.filter(nombre_corto_unidad=CODIGO_UNIDAD_EQUIPOS).delete()

        quitar(self.estado_real(), None)  # no debe lanzar nada


class DetalleReducidoTests(TestCase):
    """La cara reducida del detalle: lo que ve quien no pertenece a Equipos.

    Es la URL que llevan los codigos QR pegados a los aparatos, asi que la
    abre cualquiera del hospital. Lo importante es que no se escape nada
    administrativo por ahi.
    """

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.enfermera = Usuario.objects.create_user(
            username="enfermera-reducido", password="clave-enfermera"
        )
        cls.tecnico = Usuario.objects.create_user(
            username="tecnico-reducido", password="clave-tecnico"
        )
        dar_acceso_equipos(cls.tecnico, RolUsuario.DIGITADOR)

        cls.tipo = TipoDispositivo.objects.create(nombre="VENTILADOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="DRAGER")
        cls.modelo = ModeloDispositivo.objects.create(
            marca=cls.marca, nombre="EVITA 4"
        )
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")
        cls.dispositivo = Dispositivo.objects.create(
            tipo=cls.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=cls.marca,
            modelo=cls.modelo,
            area_gestora=cls.area_gestora,
            color=cls.color,
            numero_serie="SERIE-REDUCIDO",
            inventario_bienes_nacionales="BN-987654",
            inventario_numero_ficha="FICHA-4321",
            costo_adquisicion=Decimal("125000"),
            estado=EstadoDispositivo.OPERATIVO,
            criticidad=CriticidadDispositivo.ALTA,
            creado_por=cls.tecnico,
            modificado_por=cls.tecnico,
        )

    def setUp(self):
        # El detalle consulta el servidor de imagenes; aqui no debe depender
        # de que este encendido.
        patch(
            "equipos.views.MediaService.obtener_imagenes_dispositivo",
            return_value=([], False),
        ).start()
        patch(
            "equipos.views.MediaService.obtener_ficha_baja_dispositivo",
            return_value=(None, False),
        ).start()
        self.addCleanup(patch.stopall)

    def url_detalle(self):
        return reverse("detalle_dispositivo_equipos", args=[self.dispositivo.pk])

    # --- Acceso -----------------------------------------------------------

    def test_usuario_sin_permiso_de_equipos_abre_el_detalle(self):
        # Antes recibia acceso denegado; ahora es la URL del QR.
        self.client.force_login(self.enfermera)

        respuesta = self.client.get(self.url_detalle())

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(
            respuesta, "equipos/detalle_dispositivo_reducido_equipos.html"
        )

    def test_el_anonimo_sigue_yendo_al_login(self):
        respuesta = self.client.get(self.url_detalle())

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn(reverse("acceso_denegado"), respuesta["Location"])

    def test_el_tecnico_sigue_viendo_la_ficha_completa(self):
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(self.url_detalle())

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(
            respuesta, "equipos/detalle_dispositivo_equipos.html"
        )

    # --- Que se muestra ---------------------------------------------------

    def test_la_version_reducida_muestra_lo_necesario_para_identificar(self):
        self.client.force_login(self.enfermera)

        respuesta = self.client.get(self.url_detalle())

        self.assertContains(respuesta, self.dispositivo.codigo)
        self.assertContains(respuesta, "VENTILADOR")
        self.assertContains(respuesta, "DRAGER")
        self.assertContains(respuesta, "EVITA 4")
        self.assertContains(respuesta, "SERIE-REDUCIDO")

    # --- Que NO se muestra ------------------------------------------------

    def test_la_version_reducida_no_filtra_datos_administrativos(self):
        self.client.force_login(self.enfermera)

        respuesta = self.client.get(self.url_detalle())

        # Costo de adquisicion en cualquiera de sus formas.
        self.assertNotContains(respuesta, "125000")
        self.assertNotContains(respuesta, "125,000")
        self.assertNotContains(respuesta, "Costo")
        # Inventario de bienes nacionales y numero de ficha.
        self.assertNotContains(respuesta, "BN-987654")
        self.assertNotContains(respuesta, "FICHA-4321")

    def test_la_version_reducida_no_ofrece_acciones_del_modulo(self):
        self.client.force_login(self.enfermera)

        respuesta = self.client.get(self.url_detalle())

        self.assertNotContains(
            respuesta,
            reverse("editar_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        self.assertNotContains(
            respuesta,
            reverse("tramite_baja_dispositivo_equipos", args=[self.dispositivo.pk]),
        )
        self.assertNotContains(respuesta, reverse("listado_dispositivos_equipos"))
        self.assertNotContains(
            respuesta, reverse("ficha_activo_fijo_equipos", args=[self.dispositivo.pk])
        )

    def test_el_contexto_reducido_no_arrastra_la_baja_ni_la_ficha_firmada(self):
        # Aunque la plantilla no los pinte, tampoco deben viajar en el
        # contexto: de ahi es de donde se filtran las cosas sin querer.
        self.client.force_login(self.enfermera)

        respuesta = self.client.get(self.url_detalle())

        for clave in (
            "baja_dispositivo",
            "orden_trabajo_baja",
            "ficha_baja_firmada",
            "imagenes_slots",
        ):
            self.assertNotIn(clave, respuesta.context, msg=f"sobra {clave}")

    def test_el_resto_del_modulo_sigue_cerrado_para_quien_no_es_de_equipos(self):
        # Abrir el detalle no debe abrir nada mas.
        self.client.force_login(self.enfermera)

        for nombre in (
            "listado_dispositivos_equipos",
            "buscar_dispositivo_equipos",
            "inicio_equipos",
        ):
            with self.subTest(url=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertRedirects(respuesta, reverse("acceso_denegado"))

        for nombre in ("qr_dispositivo_equipos", "ficha_activo_fijo_equipos"):
            with self.subTest(url=nombre):
                respuesta = self.client.get(
                    reverse(nombre, args=[self.dispositivo.pk])
                )
                self.assertRedirects(respuesta, reverse("acceso_denegado"))


def registrar_equipo_el(equipo, cuando):
    """Retrasa la fecha de registro de un equipo.

    fecha_creado es auto_now_add, asi que en pruebas todo equipo nace hoy y no
    admitiria pausas anteriores. Con update() se salta el automatismo y se
    puede simular un equipo que lleva tiempo en el hospital.
    """
    marca = timezone.make_aware(datetime.combine(cuando, datetime.min.time()))
    Dispositivo.objects.filter(pk=equipo.pk).update(fecha_creado=marca)
    equipo.refresh_from_db()
    return equipo


class GarantiaCalculoTests(TestCase):
    """El calculo del vencimiento, que es donde se juega la credibilidad."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="tecnico-garantia", password="clave"
        )
        cls.tipo = TipoDispositivo.objects.create(nombre="VENTILADOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="DRAGER")
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")

    def crear_equipo(self, fin_garantia=None, estado=EstadoDispositivo.OPERATIVO,
                     serie=None):
        equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=self.marca,
            area_gestora=self.area_gestora,
            color=self.color,
            numero_serie=serie or f"SG-{Dispositivo.objects.count() + 1:04d}",
            fecha_fin_garantia=fin_garantia,
            estado=estado,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        # El equipo lleva en el hospital desde principios de 2026, para
        # que admita pausas con fechas anteriores a hoy.
        return registrar_equipo_el(equipo, date(2026, 1, 1))

    def pausar(self, equipo, salida, retorno=None):
        return PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=salida,
            fecha_retorno=retorno,
            motivo="Enviado a reparación",
            registrado_por=self.usuario,
        )

    # --- Sin pausas -------------------------------------------------------

    def test_sin_fecha_es_sin_garantia(self):
        equipo = self.crear_equipo(fin_garantia=None)

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.SIN_GARANTIA)
        self.assertIsNone(estado.fin_real)
        self.assertIsNone(estado.dias_restantes)
        self.assertFalse(estado.tiene_garantia)

    def test_vigente_cuando_falta_mucho(self):
        equipo = self.crear_equipo(fin_garantia=date(2027, 8, 6))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.VIGENTE)
        self.assertEqual(estado.dias_restantes, 365)
        self.assertTrue(estado.esta_vigente)

    def test_vencida_cuando_ya_paso(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 8, 1))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.VENCIDA)
        self.assertEqual(estado.dias_restantes, -5)
        self.assertFalse(estado.esta_vigente)

    # --- El umbral de 30 dias --------------------------------------------

    def test_a_31_dias_todavia_es_vigente(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 9, 6))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_restantes, 31)
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.VIGENTE)

    def test_a_30_dias_exactos_ya_es_por_vencer(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 9, 5))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_restantes, 30)
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.POR_VENCER)

    def test_el_ultimo_dia_sigue_cubierto(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 8, 6))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_restantes, 0)
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.POR_VENCER)
        self.assertTrue(estado.esta_vigente)

    # --- Con pausas -------------------------------------------------------

    def test_una_pausa_cerrada_corre_el_vencimiento(self):
        equipo = self.crear_equipo(fin_garantia=date(2028, 3, 15))
        self.pausar(equipo, date(2026, 6, 10), date(2026, 7, 25))  # 45 dias

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_pausados, 45)
        self.assertEqual(estado.fin_contrato, date(2028, 3, 15))
        self.assertEqual(estado.fin_real, date(2028, 4, 29))

    def test_varias_pausas_se_acumulan(self):
        equipo = self.crear_equipo(fin_garantia=date(2028, 1, 1))
        self.pausar(equipo, date(2026, 3, 1), date(2026, 3, 11))   # 10
        self.pausar(equipo, date(2026, 5, 1), date(2026, 5, 21))   # 20

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_pausados, 30)
        self.assertEqual(estado.fin_real, date(2028, 1, 31))

    def test_la_pausa_abierta_no_suma_todavia(self):
        # Es la decision de disenio: los dias se suman al retorno, no dia a
        # dia, porque hasta que no vuelve no se sabe cuanto estuvo fuera.
        equipo = self.crear_equipo(fin_garantia=date(2028, 3, 15))
        self.pausar(equipo, date(2026, 7, 1), retorno=None)

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_pausados, 0)
        self.assertEqual(estado.fin_real, date(2028, 3, 15))
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.PAUSADA)
        self.assertIsNotNone(estado.pausa_abierta)

    def test_al_cerrar_la_pausa_se_suman_los_dias(self):
        equipo = self.crear_equipo(fin_garantia=date(2028, 3, 15))
        pausa = self.pausar(equipo, date(2026, 7, 1), retorno=None)

        pausa.fecha_retorno = date(2026, 7, 21)
        pausa.save()

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_pausados, 20)
        self.assertEqual(estado.fin_real, date(2028, 4, 4))
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.VIGENTE)

    def test_pausa_de_cero_dias_no_altera_nada(self):
        # Es el remedio de una pausa registrada por error y corregida el mismo
        # dia: sale gratis del propio modelo.
        equipo = self.crear_equipo(fin_garantia=date(2028, 3, 15))
        self.pausar(equipo, date(2026, 7, 1), date(2026, 7, 1))

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.dias_pausados, 0)
        self.assertEqual(estado.fin_real, date(2028, 3, 15))

    def test_una_pausa_puede_rescatar_una_garantia_recien_vencida(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 8, 1))
        self.pausar(equipo, date(2026, 5, 1), date(2026, 5, 31))  # 30 dias

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.fin_real, date(2026, 8, 31))
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.POR_VENCER)

    def test_un_equipo_fuera_se_muestra_pausado_aunque_la_fecha_pasara(self):
        equipo = self.crear_equipo(fin_garantia=date(2026, 1, 1))
        self.pausar(equipo, date(2026, 7, 1), retorno=None)

        estado = calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))

        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.PAUSADA)

    # --- El dato del contrato nunca se toca -------------------------------

    def test_las_pausas_no_modifican_la_fecha_guardada(self):
        equipo = self.crear_equipo(fin_garantia=date(2028, 3, 15))
        self.pausar(equipo, date(2026, 6, 10), date(2026, 7, 25))

        calcular_estado_garantia(equipo, hoy=date(2026, 8, 6))
        equipo.refresh_from_db()

        self.assertEqual(equipo.fecha_fin_garantia, date(2028, 3, 15))


class PausaGarantiaModeloTests(TestCase):
    """Las reglas que protege la propia base de datos."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="tecnico-pausas", password="clave"
        )
        cls.tipo = TipoDispositivo.objects.create(nombre="DESFIBRILADOR")
        cls.marca = MarcaDispositivo.objects.create(nombre="ZOLL")
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")

    def crear_equipo(self, estado=EstadoDispositivo.OPERATIVO, fin=None):
        equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=self.marca,
            area_gestora=self.area_gestora,
            color=self.color,
            numero_serie=f"PZ-{Dispositivo.objects.count() + 1:04d}",
            fecha_fin_garantia=fin or date(2028, 1, 1),
            estado=estado,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        # El equipo lleva en el hospital desde principios de 2026, para
        # que admita pausas con fechas anteriores a hoy.
        return registrar_equipo_el(equipo, date(2026, 1, 1))

    def test_no_admite_dos_pausas_abiertas(self):
        equipo = self.crear_equipo()
        PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )

        with self.assertRaises(ValidationError):
            PausaGarantia.objects.create(
                dispositivo=equipo,
                fecha_salida=timezone.localdate(),
                registrado_por=self.usuario,
            )

    def test_la_base_impide_dos_pausas_abiertas_sin_pasar_por_python(self):
        # Se salta full_clean() a proposito: si la unicidad viviera solo en la
        # validacion, un doble clic o dos peticiones a la vez la esquivarian.
        # MySQL ignora los UniqueConstraint con condicion, de ahi la columna
        # equipo_con_pausa_abierta.
        equipo = self.crear_equipo()
        PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )

        intrusa = PausaGarantia(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )
        intrusa.equipo_con_pausa_abierta = equipo.pk

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                super(PausaGarantia, intrusa).save(force_insert=True)

    def test_al_cerrar_la_pausa_se_libera_la_columna_de_unicidad(self):
        equipo = self.crear_equipo()
        pausa = PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate() - timedelta(days=3),
            registrado_por=self.usuario,
        )
        self.assertEqual(pausa.equipo_con_pausa_abierta, equipo.pk)

        pausa.fecha_retorno = timezone.localdate()
        pausa.save()
        pausa.refresh_from_db()

        self.assertIsNone(pausa.equipo_con_pausa_abierta)

    def test_si_admite_una_nueva_tras_cerrar_la_anterior(self):
        equipo = self.crear_equipo()
        primera = PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate() - timedelta(days=10),
            registrado_por=self.usuario,
        )
        primera.fecha_retorno = timezone.localdate() - timedelta(days=5)
        primera.save()

        segunda = PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )

        self.assertTrue(segunda.esta_abierta)
        self.assertEqual(equipo.pausas_garantia.count(), 2)

    def test_el_retorno_no_puede_preceder_a_la_salida(self):
        equipo = self.crear_equipo()

        with self.assertRaises(ValidationError):
            PausaGarantia.objects.create(
                dispositivo=equipo,
                fecha_salida=date(2026, 7, 20),
                fecha_retorno=date(2026, 7, 10),
                registrado_por=self.usuario,
            )

    def test_la_salida_no_puede_preceder_al_registro_del_equipo(self):
        equipo = self.crear_equipo()

        with self.assertRaises(ValidationError):
            PausaGarantia.objects.create(
                dispositivo=equipo,
                fecha_salida=date(2020, 1, 1),
                registrado_por=self.usuario,
            )

    def test_admite_salidas_retroactivas(self):
        # El tecnico registra la salida dias despues; es la norma, no la
        # excepcion.
        equipo = self.crear_equipo()

        pausa = PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )

        self.assertTrue(pausa.esta_abierta)


class PuedePausarseTests(TestCase):
    """Cuando tiene sentido ofrecer el boton de salida."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="tecnico-puede", password="clave"
        )
        cls.tipo = TipoDispositivo.objects.create(nombre="INCUBADORA")
        cls.marca = MarcaDispositivo.objects.create(nombre="GE")
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")

    def crear_equipo(self, fin, estado=EstadoDispositivo.OPERATIVO):
        equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=self.marca,
            area_gestora=self.area_gestora,
            color=self.color,
            numero_serie=f"PP-{Dispositivo.objects.count() + 1:04d}",
            fecha_fin_garantia=fin,
            estado=estado,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        # El equipo lleva en el hospital desde principios de 2026, para
        # que admita pausas con fechas anteriores a hoy.
        return registrar_equipo_el(equipo, date(2026, 1, 1))

    def test_equipo_operativo_con_garantia_vigente_si_puede(self):
        equipo = self.crear_equipo(fin=date(2028, 1, 1))

        permitido, motivo = puede_pausarse(equipo, hoy=date(2026, 8, 6))

        self.assertTrue(permitido)
        self.assertEqual(motivo, "")

    def test_equipo_sin_garantia_no_puede(self):
        equipo = self.crear_equipo(fin=None)

        permitido, motivo = puede_pausarse(equipo, hoy=date(2026, 8, 6))

        self.assertFalse(permitido)
        self.assertIn("no tiene garantía", motivo)

    def test_equipo_con_garantia_vencida_no_puede(self):
        equipo = self.crear_equipo(fin=date(2026, 1, 1))

        permitido, motivo = puede_pausarse(equipo, hoy=date(2026, 8, 6))

        self.assertFalse(permitido)
        self.assertIn("venció", motivo)

    def test_equipo_dado_de_baja_no_puede(self):
        equipo = self.crear_equipo(
            fin=date(2028, 1, 1), estado=EstadoDispositivo.DADO_DE_BAJA
        )

        permitido, motivo = puede_pausarse(equipo, hoy=date(2026, 8, 6))

        self.assertFalse(permitido)
        self.assertIn("dado de baja", motivo)

    def test_equipo_ya_pausado_no_puede_otra_vez(self):
        equipo = self.crear_equipo(fin=date(2028, 1, 1))
        PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=timezone.localdate(),
            registrado_por=self.usuario,
        )

        permitido, motivo = puede_pausarse(equipo, hoy=date(2026, 8, 6))

        self.assertFalse(permitido)
        self.assertIn("pausa abierta", motivo)


class VistasGarantiaTests(TestCase):
    """Panel de garantias y registro de salidas y retornos."""

    databases = {"default"}

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.tecnico = Usuario.objects.create_user(
            username="tecnico-vistas-g", password="clave"
        )
        cls.directora = Usuario.objects.create_user(
            username="directora-vistas-g", password="clave"
        )
        cls.ajeno = Usuario.objects.create_user(
            username="ajeno-vistas-g", password="clave"
        )
        dar_acceso_equipos(cls.tecnico, RolUsuario.DIGITADOR)
        dar_acceso_global(cls.directora, RolUsuario.DIRECTIVO)

        cls.tipo = TipoDispositivo.objects.create(nombre="AUTOCLAVE")
        cls.marca = MarcaDispositivo.objects.create(nombre="TUTTNAUER")
        cls.area_gestora, _ = AreaGestora.objects.get_or_create(nombre="BIOMEDICA")
        cls.color, _ = ColorDispositivo.objects.get_or_create(nombre="BLANCO")

    def crear_equipo(self, fin, serie, estado=EstadoDispositivo.OPERATIVO):
        equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
            marca=self.marca,
            area_gestora=self.area_gestora,
            color=self.color,
            numero_serie=serie,
            fecha_fin_garantia=fin,
            estado=estado,
            criticidad=CriticidadDispositivo.MEDIA,
            creado_por=self.tecnico,
            modificado_por=self.tecnico,
        )
        return registrar_equipo_el(equipo, date(2026, 1, 1))

    def setUp(self):
        patch(
            "equipos.views.MediaService.obtener_imagenes_dispositivo",
            return_value=([], False),
        ).start()
        patch(
            "equipos.views.MediaService.obtener_ficha_baja_dispositivo",
            return_value=(None, False),
        ).start()
        self.addCleanup(patch.stopall)

    # --- Permisos del panel ------------------------------------------------

    def test_el_tecnico_entra_al_panel(self):
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(reverse("panel_garantias_equipos"))

        self.assertEqual(respuesta.status_code, 200)

    def test_la_directora_entra_al_panel_aunque_no_pueda_editar(self):
        # Es justo a quien le interesa saber que se pierde este mes.
        self.client.force_login(self.directora)

        respuesta = self.client.get(reverse("panel_garantias_equipos"))

        self.assertEqual(respuesta.status_code, 200)

    def test_quien_no_es_de_equipos_no_entra_al_panel(self):
        self.client.force_login(self.ajeno)

        respuesta = self.client.get(reverse("panel_garantias_equipos"))

        self.assertRedirects(respuesta, reverse("acceso_denegado"))

    # --- Que muestra el panel ---------------------------------------------

    def test_por_defecto_solo_muestra_lo_accionable(self):
        proximo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=10), serie="VG-PROXIMO"
        )
        tranquilo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=400), serie="VG-TRANQUILO"
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(reverse("panel_garantias_equipos"))

        self.assertContains(respuesta, proximo.codigo)
        self.assertNotContains(respuesta, tranquilo.codigo)

    def test_el_filtro_muestra_los_de_ese_estado(self):
        tranquilo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=400), serie="VG-VIGENTE"
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(
            reverse("panel_garantias_equipos"),
            {"estado": EstadoGarantiaDispositivo.VIGENTE},
        )

        self.assertContains(respuesta, tranquilo.codigo)

    def test_el_panel_ignora_los_equipos_dados_de_baja(self):
        baja = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=10),
            serie="VG-BAJA",
            estado=EstadoDispositivo.DADO_DE_BAJA,
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(reverse("panel_garantias_equipos"))

        self.assertNotContains(respuesta, baja.codigo)

    # --- Registrar salida --------------------------------------------------

    def test_el_tecnico_registra_una_salida(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-SALIDA"
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.post(
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
            {
                "fecha_salida": timezone.localdate().isoformat(),
                "motivo": "Enviado al proveedor, orden 4471.",
            },
        )

        self.assertRedirects(
            respuesta,
            reverse("detalle_dispositivo_equipos", args=[equipo.pk]),
        )
        pausa = equipo.pausas_garantia.get()
        self.assertTrue(pausa.esta_abierta)
        self.assertEqual(pausa.registrado_por, self.tecnico)
        self.assertIn("4471", pausa.motivo)

    def test_la_directora_no_puede_registrar_salidas(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-SALIDA-DIR"
        )
        self.client.force_login(self.directora)

        respuesta = self.client.post(
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
            {"fecha_salida": timezone.localdate().isoformat(), "motivo": ""},
        )

        self.assertRedirects(respuesta, reverse("acceso_denegado"))
        self.assertEqual(equipo.pausas_garantia.count(), 0)

    def test_no_admite_una_salida_futura(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-FUTURA"
        )
        self.client.force_login(self.tecnico)

        self.client.post(
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
            {
                "fecha_salida": (
                    timezone.localdate() + timedelta(days=5)
                ).isoformat(),
                "motivo": "",
            },
        )

        self.assertEqual(equipo.pausas_garantia.count(), 0)

    def test_no_admite_salida_en_equipo_sin_garantia(self):
        equipo = self.crear_equipo(fin=None, serie="VG-SIN-GARANTIA")
        self.client.force_login(self.tecnico)

        self.client.post(
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
            {"fecha_salida": timezone.localdate().isoformat(), "motivo": ""},
        )

        self.assertEqual(equipo.pausas_garantia.count(), 0)

    # --- Registrar retorno -------------------------------------------------

    def test_el_retorno_suma_los_dias_al_vencimiento(self):
        fin = timezone.localdate() + timedelta(days=200)
        equipo = self.crear_equipo(fin=fin, serie="VG-RETORNO")
        salida = timezone.localdate() - timedelta(days=12)
        PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=salida,
            registrado_por=self.tecnico,
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.post(
            reverse("registrar_retorno_garantia_equipos", args=[equipo.pk]),
            {
                "fecha_retorno": timezone.localdate().isoformat(),
                "motivo": "Cambio de sensor.",
            },
        )

        self.assertRedirects(
            respuesta,
            reverse("detalle_dispositivo_equipos", args=[equipo.pk]),
        )
        estado = calcular_estado_garantia(equipo)
        self.assertEqual(estado.dias_pausados, 12)
        self.assertEqual(estado.fin_real, fin + timedelta(days=12))
        # El dato del contrato no se toca.
        equipo.refresh_from_db()
        self.assertEqual(equipo.fecha_fin_garantia, fin)

    def test_no_admite_retorno_anterior_a_la_salida(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-RET-MALO"
        )
        salida = timezone.localdate() - timedelta(days=3)
        PausaGarantia.objects.create(
            dispositivo=equipo,
            fecha_salida=salida,
            registrado_por=self.tecnico,
        )
        self.client.force_login(self.tecnico)

        self.client.post(
            reverse("registrar_retorno_garantia_equipos", args=[equipo.pk]),
            {
                "fecha_retorno": (salida - timedelta(days=1)).isoformat(),
                "motivo": "",
            },
        )

        pausa = equipo.pausas_garantia.get()
        self.assertTrue(pausa.esta_abierta)

    def test_no_hay_retorno_sin_salida_pendiente(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-SIN-SALIDA"
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.post(
            reverse("registrar_retorno_garantia_equipos", args=[equipo.pk]),
            {"fecha_retorno": timezone.localdate().isoformat(), "motivo": ""},
        )

        self.assertRedirects(
            respuesta,
            reverse("detalle_dispositivo_equipos", args=[equipo.pk]),
        )
        self.assertEqual(equipo.pausas_garantia.count(), 0)

    # --- La tarjeta del detalle -------------------------------------------

    def test_el_detalle_ofrece_el_boton_de_salida_al_tecnico(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-CARD-TEC"
        )
        self.client.force_login(self.tecnico)

        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[equipo.pk])
        )

        self.assertContains(
            respuesta,
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
        )

    def test_la_directora_ve_la_garantia_pero_sin_botones(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-CARD-DIR"
        )
        self.client.force_login(self.directora)

        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[equipo.pk])
        )

        self.assertContains(respuesta, "Garantía")
        self.assertNotContains(
            respuesta,
            reverse("registrar_salida_garantia_equipos", args=[equipo.pk]),
        )

    def test_la_vista_reducida_no_menciona_la_garantia(self):
        equipo = self.crear_equipo(
            fin=timezone.localdate() + timedelta(days=200), serie="VG-REDUCIDA"
        )
        self.client.force_login(self.ajeno)

        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[equipo.pk])
        )

        self.assertTemplateUsed(
            respuesta, "equipos/detalle_dispositivo_reducido_equipos.html"
        )
        self.assertNotContains(respuesta, "Garantía")
