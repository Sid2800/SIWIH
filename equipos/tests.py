"""Pruebas de las reglas que el modulo no puede permitirse equivocar.

Se cubren las que tienen una respuesta exacta y verificable: el calculo del
vencimiento de garantia, la clasificacion por categoria incluyendo hibridos, y
que la ubicacion fisica se reutilice en lugar de duplicarse. Lo demas (colores
multiples, permisos, pantallas) ya lo sostienen las restricciones de base y
los decoradores.
"""

import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from expediente.models import ExpedienteUbicacion
from servicio.models import Unidad

from .forms import (
    ColoresOrdenadosField,
    MarcaEnTipoForm,
    TipoCatalogoForm,
)
from .models import (
    AreaGestora,
    AsignacionDispositivo,
    CategoriaEquipo,
    ColorDispositivo,
    Dispositivo,
    MarcaDispositivo,
    ModalidadProcedencia,
    ModeloDispositivo,
    Procedencia,
    TipoDispositivo,
    TipoProcedencia,
    TipoTecnologiaDispositivo,
    UbicacionFisica,
)


class GarantiaCalculadaTests(TestCase):
    """El vencimiento se cuenta en meses de calendario, no en dias."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("tecnico", password="x")
        cls.categoria = CategoriaEquipo.objects.get(nombre="MEDICO")
        cls.tipo = TipoDispositivo.objects.create(
            nombre="MONITOR",
            categoria=cls.categoria,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
        )
        cls.area = AreaGestora.objects.get(nombre="BIOMEDICA")
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )

    def _crear_equipo(self, **extra):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            area_gestora=self.area,
            modalidad_procedencia=ModalidadProcedencia.COMPRA,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
            **extra,
        )

    def test_duracion_en_meses_define_el_vencimiento(self):
        # Un anio desde el 1 de marzo cubre hasta la vispera: el 1 de marzo
        # siguiente ya esta fuera de garantia.
        equipo = self._crear_equipo(
            fecha_inicio_garantia=datetime.date(2024, 3, 1),
            garantia_meses=12,
        )

        self.assertEqual(
            equipo.fecha_fin_garantia,
            datetime.date(2025, 2, 28),
        )

    def test_vencimiento_respeta_el_ultimo_dia_del_mes(self):
        # 31 de enero mas un mes no puede caer en un 31 de febrero.
        equipo = self._crear_equipo(
            fecha_inicio_garantia=datetime.date(2024, 1, 31),
            garantia_meses=1,
        )

        self.assertEqual(
            equipo.fecha_fin_garantia,
            datetime.date(2024, 2, 28),
        )

    def test_se_acepta_una_garantia_ya_vencida(self):
        # Se registran equipos viejos: que la garantia haya vencido es un dato
        # del expediente, no un error de captura.
        equipo = self._crear_equipo(
            fecha_inicio_garantia=datetime.date(2019, 6, 1),
            garantia_meses=24,
        )

        self.assertEqual(
            equipo.fecha_fin_garantia,
            datetime.date(2021, 5, 31),
        )

    def test_fecha_suelta_del_contrato_se_conserva(self):
        # Sin duracion pactada manda la fecha que escribio el usuario.
        equipo = self._crear_equipo(
            fecha_fin_garantia=datetime.date(2030, 7, 15),
        )

        self.assertEqual(
            equipo.fecha_fin_garantia,
            datetime.date(2030, 7, 15),
        )

    def test_duracion_sin_inicio_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._crear_equipo(garantia_meses=12)

        self.assertIn("fecha_inicio_garantia", error.exception.message_dict)

    def test_vencimiento_anterior_al_inicio_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._crear_equipo(
                fecha_inicio_garantia=datetime.date(2025, 1, 1),
                fecha_fin_garantia=datetime.date(2024, 1, 1),
            )

        self.assertIn("fecha_fin_garantia", error.exception.message_dict)


class CategoriaEquipoTests(TestCase):
    """La categoria vive en el tipo y admite equipos hibridos."""

    @classmethod
    def setUpTestData(cls):
        cls.medico = CategoriaEquipo.objects.get(nombre="MEDICO")
        cls.informatica = CategoriaEquipo.objects.get(nombre="INFORMATICA")

    def test_el_tipo_expone_principal_y_secundarias(self):
        tipo = TipoDispositivo.objects.create(
            nombre="ECOGRAFO CON ESTACION",
            categoria=self.medico,
        )
        tipo.categorias_secundarias.add(self.informatica)

        self.assertEqual(
            [categoria.nombre for categoria in tipo.categorias],
            ["MEDICO", "INFORMATICA"],
        )

    def test_el_formulario_rechaza_repetir_la_principal(self):
        formulario = TipoCatalogoForm(data={
            "nombre": "COMPUTADORA",
            "categoria": self.informatica.pk,
            "categorias_secundarias": [self.informatica.pk],
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn("categorias_secundarias", formulario.errors)

    def test_el_nombre_se_normaliza_a_mayusculas(self):
        tipo = TipoDispositivo.objects.create(
            nombre="  camilla de traslado ",
            categoria=self.medico,
        )

        self.assertEqual(tipo.nombre, "CAMILLA DE TRASLADO")


class UbicacionAsignacionTests(TestCase):
    """Una sola FK de ubicacion y una zona fisica que no se duplica."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("tecnico", password="x")
        cls.categoria = CategoriaEquipo.objects.get(nombre="MEDICO")
        cls.tipo = TipoDispositivo.objects.create(
            nombre="MONITOR",
            categoria=cls.categoria,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
        )
        cls.area = AreaGestora.objects.get(nombre="BIOMEDICA")
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )
        cls.unidad = Unidad.objects.create(
            nombre_unidad="BODEGA CENTRAL",
            nombre_corto_unidad="BOD",
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.ubicacion = ExpedienteUbicacion.objects.create(
            unidad_no_clinica=cls.unidad,
            tipo=ExpedienteUbicacion.TIPO_NO_CLINICA,
        )

    def test_la_ubicacion_dice_si_es_clinica(self):
        equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            area_gestora=self.area,
            modalidad_procedencia=ModalidadProcedencia.COMPRA,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )
        asignacion = AsignacionDispositivo(
            dispositivo=equipo,
            ubicacion=self.ubicacion,
            responsable=None,
        )

        self.assertFalse(asignacion.es_clinica)

    def test_la_zona_fisica_se_normaliza_y_se_reutiliza(self):
        primera = UbicacionFisica.objects.create(nombre=" sala 3 - cama 12 ")

        self.assertEqual(primera.nombre, "SALA 3 - CAMA 12")

        # El nombre es unico: escribirla de otra forma no crea una segunda.
        with self.assertRaises(ValidationError):
            UbicacionFisica.objects.create(nombre="Sala 3 - Cama 12")


class ColoresEquipoTests(TestCase):
    """Lista ordenada: el primero es el principal y los demas lo acompanan."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("tecnico", password="x")
        cls.tipo = TipoDispositivo.objects.create(
            nombre="CAMILLA",
            categoria=CategoriaEquipo.objects.get(nombre="MOBILIARIO CLINICO"),
            tipo_tecnologia=TipoTecnologiaDispositivo.NO_ELECTRONICO,
        )
        cls.procedencia = Procedencia.objects.create(
            nombre="DONANTE",
            tipo=TipoProcedencia.PERSONA,
        )

    def _crear_equipo(self):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            area_gestora=AreaGestora.objects.get(nombre="ANALOGICA"),
            modalidad_procedencia=ModalidadProcedencia.DONACION,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )

    def test_se_conserva_el_orden_en_que_se_agregaron(self):
        equipo = self._crear_equipo()
        # El catalogo de colores ya viene sembrado por la migracion 0014.
        por_nombre = {
            color.nombre: color
            for color in ColorDispositivo.objects.filter(
                nombre__in=["BLANCO", "GRIS", "AZUL"]
            )
        }

        # Se agregan en un orden distinto al alfabetico a proposito: lo que
        # manda es el orden en que los eligio el usuario.
        equipo.definir_colores([
            por_nombre["GRIS"],
            por_nombre["AZUL"],
            por_nombre["BLANCO"],
        ])

        self.assertEqual(
            [color.nombre for color in equipo.colores_ordenados],
            ["GRIS", "AZUL", "BLANCO"],
        )
        self.assertEqual(equipo.color_principal.nombre, "GRIS")

    def test_redefinir_los_colores_reemplaza_la_lista(self):
        equipo = self._crear_equipo()
        colores = list(ColorDispositivo.objects.exclude(nombre="INDEFINIDO")[:3])

        equipo.definir_colores(colores)
        equipo.definir_colores([colores[2]])

        self.assertEqual(equipo.colores.count(), 1)
        self.assertEqual(equipo.color_principal, colores[2])

    def test_sin_colores_no_hay_principal(self):
        equipo = self._crear_equipo()

        self.assertIsNone(equipo.color_principal)
        self.assertEqual(equipo.colores_ordenados, [])


class ColoresOrdenadosFieldTests(TestCase):
    """El campo recibe los identificadores en el orden del navegador."""

    def test_conserva_el_orden_recibido_y_descarta_repetidos(self):
        campo = ColoresOrdenadosField(required=False)
        colores = list(ColorDispositivo.objects.exclude(nombre="INDEFINIDO")[:3])
        primero, segundo, tercero = colores

        entrada = f"{tercero.pk},{primero.pk},{tercero.pk},{segundo.pk}"

        self.assertEqual(
            campo.clean(entrada),
            [tercero, primero, segundo],
        )

    def test_vacio_devuelve_lista_vacia(self):
        campo = ColoresOrdenadosField(required=False)

        self.assertEqual(campo.clean(""), [])

    def test_rechaza_un_color_inexistente(self):
        campo = ColoresOrdenadosField(required=False)

        with self.assertRaises(ValidationError):
            campo.clean("999999")


class CascadaTipoMarcaModeloTests(TestCase):
    """El catalogo es una cadena: tipo -> marcas del tipo -> modelos.

    Es la regla que sostiene los tres desplegables del formulario, asi que
    tambien se comprueba desde el modelo: si se pudiera saltar por codigo, un
    POST manipulado podria dejar un equipo con un modelo de otro aparato.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("tecnico", password="x")
        cls.impresora = TipoDispositivo.objects.create(
            nombre="IMPRESORA",
            categoria=CategoriaEquipo.objects.get(nombre="INFORMATICA"),
        )
        cls.camilla = TipoDispositivo.objects.create(
            nombre="CAMILLA",
            categoria=CategoriaEquipo.objects.get(nombre="MOBILIARIO CLINICO"),
            tipo_tecnologia=TipoTecnologiaDispositivo.NO_ELECTRONICO,
        )
        cls.epson = MarcaDispositivo.objects.create(nombre="EPSON")
        cls.impresora.marcas.add(cls.epson)
        cls.modelo = ModeloDispositivo.objects.create(
            tipo=cls.impresora,
            marca=cls.epson,
            nombre="L3250",
        )
        cls.area = AreaGestora.objects.get(nombre="INFORMATICA")
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )

    def _equipo(self, **extra):
        return Dispositivo(
            tipo=self.impresora,
            area_gestora=self.area,
            modalidad_procedencia=ModalidadProcedencia.COMPRA,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
            **extra,
        )

    def test_la_tecnologia_la_trae_el_tipo(self):
        equipo = self._equipo()

        self.assertEqual(
            equipo.tipo_tecnologia,
            TipoTecnologiaDispositivo.ELECTRONICO,
        )
        self.assertEqual(equipo.get_tipo_tecnologia_display(), "Electrónico")

    def test_un_modelo_exige_que_la_marca_este_en_el_tipo(self):
        # Epson no esta declarada en camillas, asi que no puede tener modelos
        # de camilla aunque la marca exista.
        with self.assertRaises(ValidationError) as error:
            ModeloDispositivo.objects.create(
                tipo=self.camilla,
                marca=self.epson,
                nombre="CUALQUIERA",
            )

        self.assertIn("marca", error.exception.message_dict)

    def test_el_mismo_nombre_vale_en_tipos_distintos(self):
        self.camilla.marcas.add(self.epson)

        gemelo = ModeloDispositivo.objects.create(
            tipo=self.camilla,
            marca=self.epson,
            nombre="L3250",
        )

        self.assertNotEqual(gemelo.pk, self.modelo.pk)

    def test_un_equipo_rechaza_marca_ajena_al_tipo(self):
        otra = MarcaDispositivo.objects.create(nombre="MINDRAY")

        with self.assertRaises(ValidationError) as error:
            self._equipo(marca=otra).save()

        self.assertIn("marca", error.exception.message_dict)

    def test_un_equipo_rechaza_modelo_de_otro_tipo(self):
        self.camilla.marcas.add(self.epson)
        modelo_camilla = ModeloDispositivo.objects.create(
            tipo=self.camilla,
            marca=self.epson,
            nombre="RODABLE",
        )

        equipo = self._equipo(marca=self.epson, modelo=modelo_camilla)

        with self.assertRaises(ValidationError) as error:
            equipo.save()

        self.assertIn("modelo", error.exception.message_dict)

    def test_la_combinacion_correcta_se_guarda(self):
        equipo = self._equipo(marca=self.epson, modelo=self.modelo)
        equipo.save()

        self.assertEqual(equipo.modelo.nombre, "L3250")


class MarcaEnTipoFormTests(TestCase):
    """Un solo campo para crear la marca o reutilizar la que ya existe."""

    @classmethod
    def setUpTestData(cls):
        cls.impresora = TipoDispositivo.objects.create(
            nombre="IMPRESORA",
            categoria=CategoriaEquipo.objects.get(nombre="INFORMATICA"),
        )
        cls.escaner = TipoDispositivo.objects.create(
            nombre="ESCANER",
            categoria=CategoriaEquipo.objects.get(nombre="INFORMATICA"),
        )

    def test_crea_la_marca_si_no_existia(self):
        formulario = MarcaEnTipoForm(
            data={"nombre": "brother"},
            tipo=self.impresora,
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        marca, creada = formulario.guardar()

        self.assertTrue(creada)
        self.assertEqual(marca.nombre, "BROTHER")
        self.assertIn(marca, self.impresora.marcas.all())

    def test_reutiliza_la_marca_de_otro_tipo(self):
        existente = MarcaDispositivo.objects.create(nombre="EPSON")
        self.impresora.marcas.add(existente)

        formulario = MarcaEnTipoForm(
            data={"nombre": "Epson"},
            tipo=self.escaner,
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        marca, creada = formulario.guardar()

        self.assertFalse(creada)
        self.assertEqual(marca.pk, existente.pk)
        # El catalogo trae un INDEFINIDO sembrado de antes: lo que importa
        # es que no se haya creado una segunda Epson.
        self.assertEqual(
            MarcaDispositivo.objects.filter(nombre="EPSON").count(),
            1,
        )

    def test_rechaza_repetirla_en_el_mismo_tipo(self):
        marca = MarcaDispositivo.objects.create(nombre="EPSON")
        self.impresora.marcas.add(marca)

        formulario = MarcaEnTipoForm(
            data={"nombre": "EPSON"},
            tipo=self.impresora,
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("nombre", formulario.errors)
