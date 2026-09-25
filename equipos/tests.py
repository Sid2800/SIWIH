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

from .forms import ColoresOrdenadosField, TipoCatalogoForm
from .models import (
    TipoTecnologiaDispositivo,
    AreaGestora,
    AsignacionDispositivo,
    CategoriaEquipo,
    ColorDispositivo,
    Dispositivo,
    ModalidadProcedencia,
    Procedencia,
    TipoDispositivo,
    TipoProcedencia,
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
        )
        cls.area = AreaGestora.objects.get(nombre="BIOMEDICA")
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )

    def _crear_equipo(self, **extra):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
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
            tipo_tecnologia=TipoTecnologiaDispositivo.ELECTRONICO,
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
        )
        cls.procedencia = Procedencia.objects.create(
            nombre="DONANTE",
            tipo=TipoProcedencia.PERSONA,
        )

    def _crear_equipo(self):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            tipo_tecnologia=TipoTecnologiaDispositivo.NO_ELECTRONICO,
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
