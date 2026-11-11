"""Pruebas de las reglas que el modulo no puede permitirse equivocar.

Se cubren las que tienen una respuesta exacta y verificable: el calculo del
vencimiento de garantia, la clasificacion por categoria incluyendo hibridos, y
que la ubicacion fisica se reutilice en lugar de duplicarse. Lo demas (colores
multiples, permisos, pantallas) ya lo sostienen las restricciones de base y
los decoradores.
"""

import datetime
import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.constants.choices_constants import EstadoRegistro
from expediente.models import ExpedienteUbicacion
from rrhh.models import Empleado
from servicio.models import Unidad

from .services import actividades_service
from .services.calendario_service import (
    crear_plan,
    mover_visita,
    omitir_visita,
    regenerar_visitas,
    registrar_realizacion,
)
from .services.garantia_service import calcular_estado_garantia
from .forms import (
    ColoresOrdenadosField,
    MarcaEnTipoForm,
    TipoCatalogoForm,
)
from .models import (
    ActividadEnOrdenTrabajo,
    ActividadMantenimiento,
    ActividadTipoDispositivo,
    AreaGestora,
    AsignacionDispositivo,
    CategoriaEquipo,
    ColorDispositivo,
    Dispositivo,
    EstadoGarantiaDispositivo,
    GarantiaDispositivo,
    MarcaDispositivo,
    ModalidadProcedencia,
    EquipoEnOrdenTrabajo,
    EstadoOrdenTrabajo,
    EstadoVisitaPreventiva,
    ModeloDispositivo,
    OrdenTrabajoBajaDispositivo,
    OrdenTrabajoMantenimiento,
    OrigenOrdenTrabajo,
    PlanMantenimiento,
    MotivoCierreGarantia,
    PausaGarantia,
    Procedencia,
    TipoDispositivo,
    TecnologiaEquipo,
    TipoProcedencia,
    UbicacionFisica,
    corresponde_dia_habil,
    normalizar_actividad,
    sumar_meses,
)


def _dispositivo_de_prueba(usuario):
    """Equipo minimo, con lo justo para colgarle asignaciones y ordenes."""
    categoria = CategoriaEquipo.objects.get(nombre="MEDICO")
    tecnologia = TecnologiaEquipo.objects.get(nombre="ELECTRONICO")
    tipo = TipoDispositivo.objects.create(
        nombre="EQUIPO DE PRUEBA %s" % usuario.pk,
        categoria=categoria,
        tecnologia=tecnologia,
    )
    marca = MarcaDispositivo.objects.create(nombre="MARCA DE PRUEBA %s" % usuario.pk)
    tipo.marcas.add(marca)
    modelo = ModeloDispositivo.objects.create(
        nombre="MODELO DE PRUEBA",
        tipo=tipo,
        marca=marca,
    )

    procedencia = Procedencia.objects.create(
        nombre="PROVEEDOR DE PRUEBA %s" % usuario.pk,
        tipo=TipoProcedencia.EMPRESA,
    )

    return Dispositivo.objects.create(
        tipo=tipo,
        marca=marca,
        modelo=modelo,
        area_gestora=AreaGestora.objects.create(
            nombre="AREA DE PRUEBA %s" % usuario.pk
        ),
        modalidad_procedencia=ModalidadProcedencia.COMPRA,
        procedencia=procedencia,
        creado_por=usuario,
        modificado_por=usuario,
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
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        cls.area = AreaGestora.objects.get(nombre="BIOMEDICA")
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )

    def _crear_equipo(self):
        return Dispositivo.objects.create(
            tipo=self.tipo,
            area_gestora=self.area,
            modalidad_procedencia=ModalidadProcedencia.COMPRA,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )

    def _crear_garantia(self, **extra):
        datos = {
            "dispositivo": self._crear_equipo(),
            "registrado_por": self.usuario,
        }
        datos.update(extra)
        return GarantiaDispositivo.objects.create(**datos)

    def test_duracion_en_meses_define_el_vencimiento(self):
        # Un anio desde el 1 de marzo cubre hasta la vispera: el 1 de marzo
        # siguiente ya esta fuera de garantia.
        garantia = self._crear_garantia(
            fecha_inicio=datetime.date(2024, 3, 1),
            meses=12,
        )

        self.assertEqual(garantia.fecha_fin, datetime.date(2025, 2, 28))

    def test_vencimiento_respeta_el_ultimo_dia_del_mes(self):
        # 31 de enero mas un mes no puede caer en un 31 de febrero.
        garantia = self._crear_garantia(
            fecha_inicio=datetime.date(2024, 1, 31),
            meses=1,
        )

        self.assertEqual(garantia.fecha_fin, datetime.date(2024, 2, 28))

    def test_se_acepta_una_garantia_ya_vencida(self):
        # Se registran equipos viejos: que la garantia haya vencido es un dato
        # del expediente, no un error de captura.
        garantia = self._crear_garantia(
            fecha_inicio=datetime.date(2019, 6, 1),
            meses=24,
        )

        self.assertEqual(garantia.fecha_fin, datetime.date(2021, 5, 31))

    def test_fecha_suelta_del_contrato_se_conserva(self):
        # Sin duracion pactada manda la fecha que escribio el usuario.
        garantia = self._crear_garantia(
            fecha_inicio=datetime.date(2030, 1, 1),
            fecha_fin=datetime.date(2030, 7, 15),
        )

        self.assertEqual(garantia.fecha_fin, datetime.date(2030, 7, 15))

    def test_vencimiento_anterior_al_inicio_se_rechaza(self):
        with self.assertRaises(ValidationError) as error:
            self._crear_garantia(
                fecha_inicio=datetime.date(2025, 1, 1),
                fecha_fin=datetime.date(2024, 1, 1),
            )

        self.assertIn("fecha_fin", error.exception.message_dict)

    def test_el_equipo_expone_su_garantia_vigente(self):
        equipo = self._crear_equipo()
        garantia = GarantiaDispositivo.objects.create(
            dispositivo=equipo,
            fecha_inicio=datetime.date(2026, 1, 1),
            meses=12,
            registrado_por=self.usuario,
        )

        self.assertEqual(equipo.garantia_vigente, garantia)

    def test_sin_garantia_el_estado_lo_dice(self):
        estado = calcular_estado_garantia(self._crear_equipo())

        self.assertFalse(estado.tiene_garantia)
        self.assertEqual(
            estado.estado,
            EstadoGarantiaDispositivo.SIN_GARANTIA,
        )


class HistorialGarantiasTests(TestCase):
    """Un equipo puede tener varias garantias: una vigente y las anteriores."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user("tecnico", password="x")
        cls.tipo = TipoDispositivo.objects.create(
            nombre="MONITOR",
            categoria=CategoriaEquipo.objects.get(nombre="MEDICO"),
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        cls.procedencia = Procedencia.objects.create(
            nombre="PROVEEDOR",
            tipo=TipoProcedencia.EMPRESA,
        )

    def setUp(self):
        self.equipo = Dispositivo.objects.create(
            tipo=self.tipo,
            area_gestora=AreaGestora.objects.get(nombre="BIOMEDICA"),
            modalidad_procedencia=ModalidadProcedencia.COMPRA,
            procedencia=self.procedencia,
            creado_por=self.usuario,
            modificado_por=self.usuario,
        )

    def _garantia(self, anio, **extra):
        datos = {
            "dispositivo": self.equipo,
            "fecha_inicio": datetime.date(anio, 1, 1),
            "meses": 12,
            "registrado_por": self.usuario,
        }
        datos.update(extra)
        return GarantiaDispositivo.objects.create(**datos)

    def test_no_se_admiten_dos_vigentes_a_la_vez(self):
        self._garantia(2024)

        with self.assertRaises(ValidationError) as error:
            self._garantia(2025)

        self.assertIn("dispositivo", error.exception.message_dict)

    def test_al_cerrar_una_cabe_la_siguiente(self):
        primera = self._garantia(2024)
        primera.cerrar(MotivoCierreGarantia.RENOVACION)

        segunda = self._garantia(2025)

        self.assertEqual(self.equipo.garantias.count(), 2)
        self.assertEqual(self.equipo.garantia_vigente, segunda)
        self.assertFalse(primera.esta_vigente)

    def test_una_garantia_cerrada_queda_en_el_historial(self):
        garantia = self._garantia(2024)
        garantia.cerrar(
            MotivoCierreGarantia.INCUMPLIMIENTO,
            "El proveedor no atendio el reclamo 123.",
        )

        garantia.refresh_from_db()

        self.assertEqual(garantia.fecha_cierre, timezone.localdate())
        self.assertEqual(
            garantia.etiqueta_cierre,
            "Incumplimiento del proveedor",
        )
        self.assertIsNone(self.equipo.garantia_vigente)

    def test_cerrar_sin_motivo_se_rechaza(self):
        garantia = self._garantia(2024)
        garantia.fecha_cierre = timezone.localdate()

        with self.assertRaises(ValidationError) as error:
            garantia.save()

        self.assertIn("motivo_cierre", error.exception.message_dict)

    def test_las_pausas_pertenecen_a_su_garantia(self):
        primera = self._garantia(2024)
        PausaGarantia.objects.create(
            garantia=primera,
            fecha_salida=datetime.date(2024, 3, 1),
            fecha_retorno=datetime.date(2024, 3, 11),
            motivo="Enviado al proveedor.",
            observaciones_retorno="Cambio de fuente.",
            registrado_por=self.usuario,
        )
        primera.cerrar(MotivoCierreGarantia.RENOVACION)

        segunda = self._garantia(2025)

        # Los diez dias de la primera no alargan la segunda: cada cobertura
        # lleva la cuenta de sus propias paradas.
        self.assertEqual(primera.dias_pausados, 10)
        self.assertEqual(segunda.dias_pausados, 0)
        self.assertEqual(
            primera.fin_real,
            datetime.date(2025, 1, 10),
        )

    def test_una_pausa_alarga_el_vencimiento_de_su_garantia(self):
        garantia = self._garantia(2026)
        PausaGarantia.objects.create(
            garantia=garantia,
            fecha_salida=datetime.date(2026, 2, 1),
            fecha_retorno=datetime.date(2026, 2, 16),
            motivo="Reparacion en garantia.",
            observaciones_retorno="Devuelto funcionando.",
            registrado_por=self.usuario,
        )

        estado = calcular_estado_garantia(
            self.equipo,
            hoy=datetime.date(2026, 6, 1),
        )

        self.assertEqual(estado.dias_pausados, 15)
        self.assertEqual(estado.fin_contrato, datetime.date(2026, 12, 31))
        self.assertEqual(estado.fin_real, datetime.date(2027, 1, 15))

    def test_una_pausa_abierta_no_suma_todavia(self):
        garantia = self._garantia(2026)
        PausaGarantia.objects.create(
            garantia=garantia,
            fecha_salida=datetime.date(2026, 2, 1),
            motivo="Sigue con el proveedor.",
            registrado_por=self.usuario,
        )

        estado = calcular_estado_garantia(
            self.equipo,
            hoy=datetime.date(2026, 6, 1),
        )

        self.assertEqual(estado.dias_pausados, 0)
        self.assertTrue(estado.esta_pausada)
        self.assertEqual(estado.estado, EstadoGarantiaDispositivo.PAUSADA)

    def test_solo_una_pausa_abierta_por_garantia(self):
        garantia = self._garantia(2026)
        PausaGarantia.objects.create(
            garantia=garantia,
            fecha_salida=datetime.date(2026, 2, 1),
            motivo="Primera salida.",
            registrado_por=self.usuario,
        )

        with self.assertRaises(ValidationError) as error:
            PausaGarantia.objects.create(
                garantia=garantia,
                fecha_salida=datetime.date(2026, 3, 1),
                motivo="Segunda salida.",
                registrado_por=self.usuario,
            )

        self.assertIn("garantia", error.exception.message_dict)


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
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        tipo.categorias_secundarias.add(self.informatica)

        self.assertEqual(
            [categoria.nombre for categoria in tipo.categorias],
            ["MEDICO", "INFORMATICA"],
        )

    def test_el_formulario_exige_al_menos_una_categoria(self):
        # La primera de la lista es la principal, y es columna obligatoria.
        formulario = TipoCatalogoForm(data={
            "nombre": "COMPUTADORA",
            "tecnologia": TecnologiaEquipo.objects.get(nombre="ELECTRONICO").pk,
            "categorias": "",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn("categorias", formulario.errors)

    def test_el_nombre_se_normaliza_a_mayusculas(self):
        tipo = TipoDispositivo.objects.create(
            nombre="  camilla de traslado ",
            categoria=self.medico,
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
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
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
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
            tecnologia=TecnologiaEquipo.objects.get(nombre="NO ELECTRONICO"),
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
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        cls.camilla = TipoDispositivo.objects.create(
            nombre="CAMILLA",
            categoria=CategoriaEquipo.objects.get(nombre="MOBILIARIO CLINICO"),
            tecnologia=TecnologiaEquipo.objects.get(nombre="NO ELECTRONICO"),
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

        self.assertEqual(equipo.tecnologia, self.impresora.tecnologia)
        self.assertEqual(equipo.tecnologia.nombre, "ELECTRONICO")

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
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        cls.escaner = TipoDispositivo.objects.create(
            nombre="ESCANER",
            categoria=CategoriaEquipo.objects.get(nombre="INFORMATICA"),
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
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


class FichaDelEquipoAbreTests(TestCase):
    """La ficha tiene que abrir, con y sin garantia.

    No habia ninguna prueba que la pidiera, y asi se quedo un buen rato
    devolviendo error 500: al mover las pausas del equipo a la garantia se
    quito la linea que las buscaba, pero no la que las mandaba a la plantilla.
    Una peticion de verdad lo habria dicho en el acto.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_ficha",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def _abrir(self):
        return self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.pk])
        )

    def test_abre_sin_garantia(self):
        respuesta = self._abrir()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.dispositivo.codigo)

    def test_abre_con_garantia_y_muestra_sus_pausas(self):
        garantia = GarantiaDispositivo.objects.create(
            dispositivo=self.dispositivo,
            fecha_inicio=datetime.date(2026, 1, 1),
            meses=12,
            registrado_por=self.usuario,
        )
        PausaGarantia.objects.create(
            garantia=garantia,
            fecha_salida=datetime.date(2026, 2, 1),
            fecha_retorno=datetime.date(2026, 2, 11),
            motivo="Enviado al proveedor.",
            observaciones_retorno="Regresó reparado.",
            registrado_por=self.usuario,
        )

        respuesta = self._abrir()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Historial de pausas")
        self.assertContains(respuesta, "Enviado al proveedor.")

    def test_muestra_la_frecuencia_y_de_donde_sale(self):
        self.dispositivo.tipo.frecuencia_mantenimiento_meses = 6
        self.dispositivo.tipo.save()

        respuesta = self._abrir()

        self.assertContains(respuesta, "Cada 6 meses")
        self.assertContains(respuesta, "del tipo")


class AsignacionUnicaAbiertaTests(TestCase):
    """Un equipo no puede quedar con dos responsables a la vez.

    La regla estaba en clean(), pero preguntar y despues insertar deja una
    rendija: dos ediciones del mismo equipo a la vez pasan las dos la
    comprobacion. Ahora la impone tambien el motor, con una columna unica que
    vale el id del equipo mientras la asignacion sigue abierta.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_asignacion",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)
        cls.empleado = Empleado.objects.create(
            dni="0801199012345",
            primer_nombre="ANA",
            primer_apellido="LOPEZ",
            estado=EstadoRegistro.ACTIVO,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        unidad = Unidad.objects.create(
            nombre_unidad="TALLER DE PRUEBA",
            nombre_corto_unidad="TAL",
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )
        cls.ubicacion = ExpedienteUbicacion.objects.create(
            unidad_no_clinica=unidad,
            tipo=ExpedienteUbicacion.TIPO_NO_CLINICA,
        )

    def _asignacion(self, **extra):
        datos = {
            "dispositivo": self.dispositivo,
            "ubicacion": self.ubicacion,
            "responsable": self.empleado,
            "creado_por": self.usuario,
            "modificado_por": self.usuario,
        }
        datos.update(extra)
        return AsignacionDispositivo(**datos)

    def test_la_abierta_lleva_el_id_del_equipo_en_el_candado(self):
        abierta = self._asignacion()
        abierta.save()

        self.assertEqual(
            abierta.equipo_con_asignacion_abierta,
            self.dispositivo.pk,
        )

    def test_al_cerrarla_el_candado_se_suelta(self):
        asignacion = self._asignacion()
        asignacion.save()

        asignacion.fecha_fin = timezone.now()
        asignacion.save()

        self.assertIsNone(asignacion.equipo_con_asignacion_abierta)

    def test_el_motor_rechaza_una_segunda_abierta(self):
        """Saltandose clean(), que es justo lo que haria una carrera."""
        self._asignacion().save()
        intrusa = self._asignacion()
        intrusa.equipo_con_asignacion_abierta = self.dispositivo.pk

        with self.assertRaises(IntegrityError):
            # bulk_create no pasa por save() ni por full_clean(), asi que lo
            # unico que puede pararlo es la base.
            AsignacionDispositivo.objects.bulk_create([intrusa])

    def test_cerrada_la_primera_se_puede_abrir_otra(self):
        primera = self._asignacion()
        primera.save()
        primera.fecha_fin = timezone.now()
        primera.save()

        segunda = self._asignacion()
        segunda.save()

        self.assertEqual(
            AsignacionDispositivo.objects.filter(
                dispositivo=self.dispositivo,
                fecha_fin__isnull=True,
            ).count(),
            1,
        )


class FrecuenciaDeMantenimientoTests(TestCase):
    """La frecuencia se declara en el tipo; el equipo solo la excepciona."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_frecuencia",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)

    def test_sin_nada_en_el_equipo_manda_la_del_tipo(self):
        self.dispositivo.tipo.frecuencia_mantenimiento_meses = 6
        self.dispositivo.tipo.save()
        self.dispositivo.frecuencia_mantenimiento_meses = None

        self.assertEqual(self.dispositivo.frecuencia_mantenimiento, 6)
        self.assertFalse(self.dispositivo.frecuencia_es_excepcion)

    def test_la_del_equipo_gana_cuando_la_tiene(self):
        self.dispositivo.tipo.frecuencia_mantenimiento_meses = 6
        self.dispositivo.tipo.save()
        self.dispositivo.frecuencia_mantenimiento_meses = 3

        self.assertEqual(self.dispositivo.frecuencia_mantenimiento, 3)
        self.assertTrue(self.dispositivo.frecuencia_es_excepcion)

    def test_sin_ninguna_de_las_dos_no_hay_frecuencia(self):
        """Ese equipo no entra al calendario de preventivos."""
        self.dispositivo.tipo.frecuencia_mantenimiento_meses = None
        self.dispositivo.tipo.save()
        self.dispositivo.frecuencia_mantenimiento_meses = None

        self.assertIsNone(self.dispositivo.frecuencia_mantenimiento)

    def test_el_tipo_la_guarda_desde_su_formulario(self):
        formulario = TipoCatalogoForm(data={
            "nombre": "AUTOCLAVE DE PRUEBA",
            "tecnologia": TecnologiaEquipo.objects.get(nombre="ELECTRONICO").pk,
            "categorias": str(CategoriaEquipo.objects.get(nombre="MEDICO").pk),
            "frecuencia_mantenimiento_meses": 6,
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.save().frecuencia_mantenimiento_meses, 6)

    def test_el_tipo_puede_no_llevar_mantenimiento_programado(self):
        formulario = TipoCatalogoForm(data={
            "nombre": "MUEBLE DE PRUEBA",
            "tecnologia": TecnologiaEquipo.objects.get(nombre="ELECTRONICO").pk,
            "categorias": str(CategoriaEquipo.objects.get(nombre="MEDICO").pk),
            "frecuencia_mantenimiento_meses": "",
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertIsNone(formulario.save().frecuencia_mantenimiento_meses)


class SeriesDeOrdenDeTrabajoTests(TestCase):
    """Baja y mantenimiento son tramites distintos y no comparten numero."""

    def test_la_orden_de_baja_lleva_su_prefijo(self):
        usuario = User.objects.create_superuser(
            username="zz_orden",
            password="clave-de-prueba",
        )
        orden = OrdenTrabajoBajaDispositivo.objects.create(
            dispositivo=_dispositivo_de_prueba(usuario),
            creado_por=usuario,
        )

        self.assertTrue(
            orden.numero_orden.startswith("OTB-"),
            orden.numero_orden,
        )
        self.assertEqual(OrdenTrabajoBajaDispositivo.PREFIJO, "OTB")


class CategoriasDelTipoTests(TestCase):
    """Todas las categorias del tipo llegan en una sola lista ordenada.

    El navegador las va agregando de una en una y las manda en un campo
    oculto -"3,7"-. La primera es la principal, que en la base es una clave
    propia porque ordena listados y reportes; las demas son secundarias.
    """

    @classmethod
    def setUpTestData(cls):
        cls.medico = CategoriaEquipo.objects.get(nombre="MEDICO")
        cls.informatica = CategoriaEquipo.objects.get(nombre="INFORMATICA")
        cls.electronico = TecnologiaEquipo.objects.get(nombre="ELECTRONICO")

    def _datos(self, categorias, nombre="ECOGRAFO CON ESTACION"):
        return {
            "nombre": nombre,
            "tecnologia": self.electronico.pk,
            "categorias": categorias,
        }

    def test_la_primera_es_la_principal_y_el_resto_secundarias(self):
        formulario = TipoCatalogoForm(data=self._datos(
            "{0},{1}".format(self.medico.pk, self.informatica.pk)
        ))

        self.assertTrue(formulario.is_valid(), formulario.errors)
        tipo = formulario.save()

        self.assertEqual(tipo.categoria, self.medico)
        self.assertEqual(
            list(tipo.categorias_secundarias.values_list("nombre", flat=True)),
            ["INFORMATICA"],
        )

    def test_el_orden_de_la_lista_decide_cual_es_la_principal(self):
        # La misma pareja al reves da la otra principal: el orden es el dato.
        formulario = TipoCatalogoForm(data=self._datos(
            "{0},{1}".format(self.informatica.pk, self.medico.pk)
        ))

        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.save().categoria, self.informatica)

    def test_una_sola_categoria_deja_el_tipo_sin_secundarias(self):
        formulario = TipoCatalogoForm(data=self._datos(
            str(self.medico.pk), nombre="CAMILLA"
        ))

        self.assertTrue(formulario.is_valid(), formulario.errors)
        tipo = formulario.save()

        self.assertEqual(tipo.categoria, self.medico)
        self.assertEqual(tipo.categorias_secundarias.count(), 0)

    def test_una_repetida_no_se_guarda_dos_veces(self):
        formulario = TipoCatalogoForm(data=self._datos(
            "{0},{0}".format(self.medico.pk)
        ))

        self.assertTrue(formulario.is_valid(), formulario.errors)
        tipo = formulario.save()

        self.assertEqual(tipo.categoria, self.medico)
        self.assertEqual(tipo.categorias_secundarias.count(), 0)

    def test_sin_ninguna_no_es_valido(self):
        formulario = TipoCatalogoForm(data=self._datos(""))

        self.assertFalse(formulario.is_valid())
        self.assertIn("categorias", formulario.errors)

    def test_el_campo_oculto_se_dibuja_con_las_ya_guardadas(self):
        """Al editar, el valor tiene que volver en el mismo formato y orden.

        Si el widget pintara la lista de Python tal cual -"[3, 7]"- al
        guardar de nuevo esos corchetes no serian identificadores y el tipo
        perderia sus categorias.
        """
        tipo = TipoDispositivo.objects.create(
            nombre="ECOGRAFO CON ESTACION",
            categoria=self.medico,
            tecnologia=self.electronico,
        )
        tipo.categorias_secundarias.add(self.informatica)

        formulario = TipoCatalogoForm(instance=tipo)

        self.assertEqual(
            [categoria.pk for categoria in formulario.categorias_elegidas],
            [self.medico.pk, self.informatica.pk],
        )
        self.assertIn(
            'value="%s,%s"' % (self.medico.pk, self.informatica.pk),
            str(formulario["categorias"]),
        )

    def test_editar_puede_cambiar_cual_es_la_principal(self):
        tipo = TipoDispositivo.objects.create(
            nombre="ECOGRAFO CON ESTACION",
            categoria=self.medico,
            tecnologia=self.electronico,
        )
        tipo.categorias_secundarias.add(self.informatica)

        formulario = TipoCatalogoForm(
            data=self._datos("{0},{1}".format(self.informatica.pk, self.medico.pk)),
            instance=tipo,
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        tipo = formulario.save()

        self.assertEqual(tipo.categoria, self.informatica)
        self.assertEqual(
            list(tipo.categorias_secundarias.values_list("nombre", flat=True)),
            ["MEDICO"],
        )

    def test_cada_categoria_viaja_con_las_tecnologias_en_que_se_usa(self):
        """Es lo que permite acercar las que corresponden a la tecnologia.

        La relacion no es un dato aparte que alguien deba mantener: sale de
        los tipos ya registrados.
        """
        TipoDispositivo.objects.create(
            nombre="TOMOGRAFO",
            categoria=self.medico,
            tecnologia=self.electronico,
        )

        disponibles = {
            categoria["nombre"]: categoria["tecnologias"]
            for categoria in TipoCatalogoForm().categorias_disponibles
        }

        self.assertEqual(disponibles["MEDICO"], str(self.electronico.pk))


class RenombrarEnElSitioTests(TestCase):
    """Marcas y modelos se renombran sin recargar la pantalla.

    Responden JSON porque el navegador cambia solo la fila. El nombre se
    normaliza igual que en los formularios, asi que "  epson " y "EPSON" son
    el mismo nombre y los duplicados se detectan.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_renombrar",
            password="clave-de-prueba",
        )
        cls.impresora = TipoDispositivo.objects.create(
            nombre="IMPRESORA",
            categoria=CategoriaEquipo.objects.get(nombre="INFORMATICA"),
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )
        cls.epson = MarcaDispositivo.objects.create(nombre="EPSOM")
        cls.hp = MarcaDispositivo.objects.create(nombre="HP")
        cls.impresora.marcas.add(cls.epson, cls.hp)
        cls.modelo = ModeloDispositivo.objects.create(
            nombre="L3250",
            tipo=cls.impresora,
            marca=cls.epson,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def _renombrar_marca(self, marca, nombre):
        return self.client.post(
            reverse("renombrar_marca_equipos", args=[marca.pk]),
            {"nombre": nombre},
        )

    def _renombrar_modelo(self, modelo, nombre):
        return self.client.post(
            reverse("renombrar_modelo_equipos", args=[modelo.pk]),
            {"nombre": nombre},
        )

    def test_corrige_el_nombre_de_la_marca(self):
        respuesta = self._renombrar_marca(self.epson, "  epson ")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], "EPSON")
        self.epson.refresh_from_db()
        self.assertEqual(self.epson.nombre, "EPSON")

    def test_los_modelos_de_la_marca_no_se_tocan(self):
        """Apuntan por identificador, no por texto."""
        self._renombrar_marca(self.epson, "EPSON")

        self.modelo.refresh_from_db()
        self.assertEqual(self.modelo.marca_id, self.epson.pk)
        self.assertEqual(self.modelo.nombre, "L3250")

    def test_rechaza_el_nombre_de_otra_marca(self):
        respuesta = self._renombrar_marca(self.epson, "hp")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("HP", respuesta.json()["error"])
        self.epson.refresh_from_db()
        self.assertEqual(self.epson.nombre, "EPSOM")

    def test_rechaza_dejarlo_vacio(self):
        respuesta = self._renombrar_marca(self.epson, "   ")

        self.assertEqual(respuesta.status_code, 400)
        self.epson.refresh_from_db()
        self.assertEqual(self.epson.nombre, "EPSOM")

    def test_corrige_el_nombre_del_modelo(self):
        respuesta = self._renombrar_modelo(self.modelo, "l3251")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["nombre"], "L3251")

    def test_el_modelo_solo_choca_dentro_de_su_tipo_y_marca(self):
        """La L3250 de otra marca no estorba: el nombre es unico ahi dentro."""
        ModeloDispositivo.objects.create(
            nombre="L3250",
            tipo=self.impresora,
            marca=self.hp,
        )
        otro = ModeloDispositivo.objects.create(
            nombre="L5290",
            tipo=self.impresora,
            marca=self.epson,
        )

        # Contra el de otra marca no hay conflicto...
        self.assertEqual(self._renombrar_modelo(otro, "L3251").status_code, 200)

        # ...pero contra el de la misma marca y tipo, si.
        respuesta = self._renombrar_modelo(otro, "L3250")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("L3250", respuesta.json()["error"])

    def test_sin_permiso_responde_403_y_no_una_pagina(self):
        """El navegador espera JSON: un redirect llegaria como HTML."""
        self.client.logout()
        sin_permiso = User.objects.create_user(
            username="zz_sin_permiso",
            password="clave-de-prueba",
        )
        self.client.force_login(sin_permiso)

        respuesta = self._renombrar_marca(self.epson, "EPSON")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        self.epson.refresh_from_db()
        self.assertEqual(self.epson.nombre, "EPSOM")


class FormularioDelTipoEnLaRespuestaParcialTests(TestCase):
    """El formulario de arriba solo viaja cuando se pidio editar un tipo.

    Es lo que permite filtrar y elegir sin borrarle al usuario lo que lleva
    escrito, y a la vez abrir un tipo para editarlo sin recargar la pantalla.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_form_parcial",
            password="clave-de-prueba",
        )
        cls.tipo = TipoDispositivo.objects.create(
            nombre="CAMILLA DE TRASLADO",
            categoria=CategoriaEquipo.objects.get(nombre="MEDICO"),
            tecnologia=TecnologiaEquipo.objects.get(nombre="ELECTRONICO"),
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def _parcial(self, **parametros):
        parametros["parcial"] = "1"
        respuesta = self.client.get("/equipos/catalogo/marcas/", parametros)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_al_filtrar_no_viaja(self):
        html = self._parcial(q="CAMILLA")

        self.assertNotIn('id="equipos_form_tipo"', html)
        self.assertNotIn('id="nombre_tipo_catalogo"', html)

    def test_al_pedir_editar_si_viaja_y_con_el_tipo_puesto(self):
        html = self._parcial(editar=self.tipo.pk, form="1")

        self.assertIn('id="equipos_form_tipo"', html)
        self.assertIn("Editar tipo", html)
        self.assertIn("CAMILLA DE TRASLADO", html)

    def test_cancelar_la_edicion_devuelve_el_formulario_en_blanco(self):
        html = self._parcial(form="1")

        self.assertIn('id="equipos_form_tipo"', html)
        self.assertIn("Nuevo tipo de equipo", html)

    def test_la_senal_del_formulario_no_se_cuela_en_los_enlaces(self):
        html = self._parcial(editar=self.tipo.pk, form="1", q="CAMILLA")

        self.assertNotIn("form=1&", html.replace("&form=1", ""))
        self.assertNotIn("parcial=1", html)


class CatalogoParcialTests(TestCase):
    """La pantalla pide solo los trozos que cambian.

    Filtrar la lista o elegir un tipo no toca el formulario de alta de
    arriba, y recargar la pagina entera por eso borraba lo que el usuario
    llevaba escrito ahi.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="catalogo_parcial",
            password="clave-de-prueba",
        )
        cls.medico = CategoriaEquipo.objects.get(nombre="MEDICO")
        cls.informatica = CategoriaEquipo.objects.get(nombre="INFORMATICA")
        cls.electronico = TecnologiaEquipo.objects.get(nombre="ELECTRONICO")

        cls.monitor = TipoDispositivo.objects.create(
            nombre="MONITOR DE SIGNOS",
            categoria=cls.medico,
            tecnologia=cls.electronico,
        )
        cls.laptop = TipoDispositivo.objects.create(
            nombre="COMPUTADORA PORTATIL",
            categoria=cls.informatica,
            tecnologia=cls.electronico,
        )
        cls.hp = MarcaDispositivo.objects.create(nombre="HP")
        cls.laptop.marcas.add(cls.hp)

    def setUp(self):
        self.client.force_login(self.usuario)

    def _parcial(self, **parametros):
        parametros["parcial"] = "1"
        respuesta = self.client.get("/equipos/catalogo/marcas/", parametros)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_devuelve_los_trozos_y_no_la_pagina_entera(self):
        html = self._parcial()

        for identificador in (
            "equipos_migas",
            "equipos_tipos_cuerpo",
            "equipos_paso_marcas",
            "equipos_paso_modelos",
        ):
            self.assertIn('id="%s"' % identificador, html)

        # Ni la plantilla base ni el formulario de alta: la base volveria a
        # mandar el menu en cada peticion, y el formulario es justo lo que
        # hay que dejar intacto.
        self.assertNotIn("<html", html)
        self.assertNotIn('id="nombre_tipo_catalogo"', html)

    def test_el_filtro_de_categoria_recorta_la_lista(self):
        html = self._parcial(categoria=self.informatica.pk)

        self.assertIn("COMPUTADORA PORTATIL", html)
        self.assertNotIn("MONITOR DE SIGNOS", html)

    def test_elegir_un_tipo_trae_sus_marcas(self):
        html = self._parcial(tipo=self.laptop.pk)

        self.assertIn("Fabricantes de COMPUTADORA PORTATIL", html)
        self.assertIn("HP", html)

    def test_los_enlaces_no_arrastran_el_parametro_parcial(self):
        """Un enlace del trozo tiene que llevar a la pantalla completa.

        Si conservara parcial=1, pulsarlo sin JavaScript abriria un pedazo de
        HTML suelto, sin menu ni estilos.
        """
        html = self._parcial(q="COMPUTADORA")

        self.assertNotIn("parcial=1", html)
        self.assertNotIn("parcial%3D1", html)


# ===========================================================================
# MANTENIMIENTO
# ===========================================================================


class FechasDelCalendarioTests(TestCase):
    """Las dos funciones de las que depende todo el calendario.

    Van primero y por separado porque son las que, si se equivocan, equivocan
    todas las fechas del sistema sin que ninguna pantalla lo delate.
    """

    def test_el_fin_de_semana_se_pasa_al_lunes(self):
        # 2026-03-07 es sabado y 2026-03-08 domingo.
        self.assertEqual(
            corresponde_dia_habil(datetime.date(2026, 3, 7)),
            datetime.date(2026, 3, 9),
        )
        self.assertEqual(
            corresponde_dia_habil(datetime.date(2026, 3, 8)),
            datetime.date(2026, 3, 9),
        )

    def test_un_dia_habil_no_se_toca(self):
        viernes = datetime.date(2026, 3, 6)
        self.assertEqual(corresponde_dia_habil(viernes), viernes)

    def test_quien_trabaja_fin_de_semana_conserva_su_sabado(self):
        sabado = datetime.date(2026, 3, 7)

        self.assertEqual(
            corresponde_dia_habil(sabado, incluye_fin_de_semana=True),
            sabado,
        )

    def test_se_mueve_hacia_adelante_y_no_hacia_atras(self):
        """Adelantar acortaria el intervalo, que es lo que la frecuencia cuida."""
        sabado = datetime.date(2026, 3, 7)
        resultado = corresponde_dia_habil(sabado)

        self.assertGreater(resultado, sabado)

    def test_los_meses_se_cuentan_en_calendario(self):
        # Seis meses desde el 15 de enero es el 15 de julio, no 180 dias.
        self.assertEqual(
            sumar_meses(datetime.date(2026, 1, 15), 6),
            datetime.date(2026, 7, 15),
        )

    def test_el_31_de_enero_mas_un_mes_no_inventa_un_31_de_febrero(self):
        self.assertEqual(
            sumar_meses(datetime.date(2026, 1, 31), 1),
            datetime.date(2026, 2, 28),
        )

    def test_cruza_el_anio(self):
        self.assertEqual(
            sumar_meses(datetime.date(2026, 11, 10), 6),
            datetime.date(2027, 5, 10),
        )


class CalendarioPreventivoTests(TestCase):
    """La cadena de visitas: como nace, como se mueve y que nunca cambia."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_calendario",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)

    def _plan(self, **extra):
        datos = {
            "dispositivo": self.dispositivo,
            "responsable": self.usuario,
            "frecuencia_meses": 6,
            # Un lunes, para que las fechas calculadas no tropiecen con el
            # fin de semana y la prueba diga lo que quiere decir.
            "fecha_inicio": timezone.localdate() + datetime.timedelta(days=30),
            "trabaja_fines_de_semana": True,
            "creado_por": self.usuario,
        }
        datos.update(extra)

        return crear_plan(**datos)

    def test_el_plan_nace_con_su_calendario_lleno(self):
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))

        # Dos anios de horizonte con frecuencia semestral: la primera mas las
        # que caben hasta el limite.
        self.assertGreaterEqual(len(visitas), 4)
        self.assertEqual(visitas[0].fecha_programada, plan.fecha_inicio)

    def test_las_visitas_van_separadas_por_la_frecuencia(self):
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))

        self.assertEqual(
            visitas[1].fecha_programada,
            sumar_meses(visitas[0].fecha_programada, 6),
        )

    def test_mover_una_visita_arrastra_a_las_siguientes(self):
        """Si marzo se corre dos semanas, septiembre se corre las mismas dos."""
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))
        primera, segunda = visitas[0], visitas[1]

        fecha_segunda_antes = segunda.fecha_programada
        nueva = primera.fecha_programada + datetime.timedelta(days=14)

        mover_visita(primera, nueva)
        segunda.refresh_from_db()

        self.assertEqual(
            segunda.fecha_programada,
            fecha_segunda_antes + datetime.timedelta(days=14),
        )

    def test_mover_marca_la_visita_para_que_el_calculo_no_la_devuelva(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()

        mover_visita(primera, primera.fecha_programada + datetime.timedelta(days=7))
        primera.refresh_from_db()

        self.assertTrue(primera.movida_a_mano)

    def test_una_visita_realizada_no_se_mueve(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()
        registrar_realizacion(primera, timezone.localdate())

        with self.assertRaises(ValueError):
            mover_visita(primera, timezone.localdate() + datetime.timedelta(days=5))

    def test_la_siguiente_se_cuenta_desde_la_fecha_en_que_se_hizo(self):
        """El preventivo de marzo hecho en abril corre el de septiembre a octubre."""
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()

        # Se hizo hoy, un mes antes de lo programado.
        hecha_el = timezone.localdate()
        registrar_realizacion(primera, hecha_el)

        siguiente = plan.proxima_visita

        self.assertEqual(
            siguiente.fecha_programada,
            corresponde_dia_habil(sumar_meses(hecha_el, 6), True),
        )

    def test_lo_realizado_sobrevive_a_la_regeneracion(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()
        hecha_el = timezone.localdate()

        registrar_realizacion(primera, hecha_el)
        regenerar_visitas(plan)
        primera.refresh_from_db()

        self.assertEqual(primera.estado, EstadoVisitaPreventiva.REALIZADA)
        self.assertEqual(primera.fecha_realizada, hecha_el)

    def test_lo_movido_a_mano_sobrevive_a_la_regeneracion(self):
        """Se movio por un motivo que el calculo no conoce: no se le devuelve."""
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))
        segunda = visitas[1]

        nueva = segunda.fecha_programada + datetime.timedelta(days=21)
        mover_visita(segunda, nueva)

        registrar_realizacion(visitas[0], timezone.localdate())
        segunda.refresh_from_db()

        self.assertEqual(segunda.fecha_programada, nueva)
        self.assertTrue(segunda.movida_a_mano)

    def test_mover_una_visita_lejana_no_se_come_las_de_en_medio(self):
        """Lo movido a mano no es ancla del calculo, aunque sea posterior.

        Pasaba: se corria a mano la visita de 2028, se registraba la de 2026 y
        las de 2027 desaparecian del calendario. El calculo arrancaba despues
        de la fecha movida y se saltaba dos anios de preventivos, sin que nada
        lo dijera: el aparato simplemente dejaba de aparecer.
        """
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))
        self.assertGreaterEqual(len(visitas), 4)

        lejana = visitas[3]
        mover_visita(lejana, lejana.fecha_programada + datetime.timedelta(days=20))
        registrar_realizacion(visitas[0], timezone.localdate())

        quedan = plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA
        ).count()

        self.assertGreaterEqual(
            quedan, 3, "la visita movida se comió las intermedias"
        )

    def test_no_se_duplica_la_visita_que_ocupa_el_hueco_de_una_movida(self):
        """Si no, el tecnico tiene dos visitas al mismo aparato a pocos dias."""
        plan = self._plan()
        visitas = list(plan.visitas.order_by("fecha_programada"))
        segunda = visitas[1]

        # Se corre tres dias: sigue siendo la misma visita, no otra.
        mover_visita(segunda, segunda.fecha_programada + datetime.timedelta(days=3))
        registrar_realizacion(visitas[0], timezone.localdate())

        cerca = plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            fecha_programada__gte=segunda.fecha_programada
            - datetime.timedelta(days=20),
            fecha_programada__lte=segunda.fecha_programada
            + datetime.timedelta(days=20),
        ).count()

        self.assertEqual(cerca, 1)

    def test_no_se_puede_registrar_dos_veces_la_misma_visita(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()
        registrar_realizacion(primera, timezone.localdate())

        with self.assertRaises(ValueError):
            registrar_realizacion(primera, timezone.localdate())

    def test_omitir_exige_motivo(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()

        with self.assertRaises(ValueError):
            omitir_visita(primera, "   ")

    def test_omitir_deja_dicho_por_que(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()

        omitir_visita(primera, "La sala estaba cerrada por obra.")
        primera.refresh_from_db()

        self.assertEqual(primera.estado, EstadoVisitaPreventiva.OMITIDA)
        self.assertIn("obra", primera.observaciones)

    def test_desactivar_el_plan_vacia_el_calendario_pero_no_el_historial(self):
        plan = self._plan()
        primera = plan.visitas.order_by("fecha_programada").first()
        registrar_realizacion(primera, timezone.localdate())

        plan.activo = False
        plan.save()
        regenerar_visitas(plan)

        self.assertEqual(
            plan.visitas.filter(estado=EstadoVisitaPreventiva.PROGRAMADA).count(),
            0,
        )
        self.assertEqual(
            plan.visitas.filter(estado=EstadoVisitaPreventiva.REALIZADA).count(),
            1,
        )

    def test_sin_trabajar_fin_de_semana_ninguna_visita_cae_en_sabado(self):
        plan = self._plan(trabaja_fines_de_semana=False)

        for visita in plan.visitas.all():
            self.assertLess(
                visita.fecha_programada.weekday(),
                5,
                "quedó una visita en fin de semana: %s" % visita.fecha_programada,
            )

    def test_una_visita_realizada_necesita_su_fecha(self):
        plan = self._plan()
        visita = plan.visitas.first()
        visita.estado = EstadoVisitaPreventiva.REALIZADA

        with self.assertRaises(ValidationError):
            visita.save()


class CatalogoDeActividadesTests(TestCase):
    """El catalogo que se llena con el uso, no con una importacion."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_actividades",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)
        cls.tipo = cls.dispositivo.tipo

    def test_la_misma_linea_escrita_distinto_es_una_sola(self):
        """Sin esto el catalogo se llena de variantes y la sugerencia no sirve."""
        primera = actividades_service.registrar_actividad("Limpieza general")
        segunda = actividades_service.registrar_actividad("limpieza general.")
        tercera = actividades_service.registrar_actividad("  LIMPIEZA GENERAL  ")

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(primera.pk, tercera.pk)
        self.assertEqual(ActividadMantenimiento.objects.count(), 1)

    def test_las_tildes_no_crean_una_actividad_nueva(self):
        primera = actividades_service.registrar_actividad("Inspección de housing")
        segunda = actividades_service.registrar_actividad("Inspeccion de housing")

        self.assertEqual(primera.pk, segunda.pk)

    def test_se_guarda_el_texto_tal_como_se_escribio(self):
        """La clave normaliza para comparar; lo que se imprime es lo escrito."""
        actividad = actividades_service.registrar_actividad(
            "Calibración del equipo"
        )

        self.assertEqual(actividad.nombre, "Calibración del equipo")

    def test_cada_uso_suma(self):
        actividades_service.registrar_actividad("Revision de baterias")
        actividad = actividades_service.registrar_actividad("Revision de baterias")

        self.assertEqual(actividad.veces_usada, 2)

    def test_el_uso_queda_ligado_al_tipo_de_equipo(self):
        actividad = actividades_service.registrar_actividad(
            "Revision de cintas", tipo=self.tipo
        )

        self.assertTrue(
            ActividadTipoDispositivo.objects.filter(
                actividad=actividad, tipo=self.tipo
            ).exists()
        )

    def test_el_catalogo_nace_vacio(self):
        """No se importa nada: la hoja de calculo traia tareas contaminadas."""
        self.assertEqual(ActividadMantenimiento.objects.count(), 0)

    def test_no_se_sugiere_con_dos_letras(self):
        actividades_service.registrar_actividad("Limpieza general", tipo=self.tipo)

        self.assertEqual(actividades_service.sugerir("li", tipo=self.tipo), [])

    def test_sugiere_lo_que_ya_se_escribio(self):
        actividades_service.registrar_actividad("Limpieza general", tipo=self.tipo)

        sugerencias = actividades_service.sugerir("limp", tipo=self.tipo)

        self.assertEqual(len(sugerencias), 1)
        self.assertEqual(sugerencias[0].nombre, "Limpieza general")

    def test_sugiere_buscando_sin_tildes(self):
        actividades_service.registrar_actividad(
            "Inspección externa del equipo", tipo=self.tipo
        )

        self.assertTrue(actividades_service.sugerir("inspeccion", tipo=self.tipo))

    def test_lo_mas_usado_sale_primero(self):
        actividades_service.registrar_actividad("Revision de pantalla", tipo=self.tipo)
        for _ in range(3):
            actividades_service.registrar_actividad(
                "Revision de baterias", tipo=self.tipo
            )

        sugerencias = actividades_service.sugerir("revision", tipo=self.tipo)

        self.assertEqual(sugerencias[0].nombre, "Revision de baterias")

    def test_una_actividad_vacia_no_entra(self):
        with self.assertRaises(ValueError):
            actividades_service.registrar_actividad("   ")

    def test_una_actividad_de_tres_letras_no_entra(self):
        """Una linea que no se entiende despues no documenta nada."""
        with self.assertRaises(ValidationError):
            ActividadMantenimiento(nombre="abc").save()


class OrdenDeTrabajoTests(TestCase):
    """La hoja: su numero, que admite y que no."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_orden",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)
        cls.tipo = cls.dispositivo.tipo

    def _orden(self, **extra):
        datos = {
            "tipo": self.tipo,
            "fecha": timezone.localdate(),
            "operario": self.usuario,
            "creado_por": self.usuario,
        }
        datos.update(extra)
        orden = OrdenTrabajoMantenimiento(**datos)
        orden.save()

        return orden

    def test_el_numero_lleva_el_prefijo_de_su_serie(self):
        """Sin prefijo, el 7 de mantenimiento y el 7 de baja se escriben igual."""
        orden = self._orden()

        self.assertTrue(orden.numero_orden.startswith("OTM-"))
        self.assertNotEqual(
            OrdenTrabajoMantenimiento.PREFIJO,
            OrdenTrabajoBajaDispositivo.PREFIJO,
        )

    def test_el_anio_del_numero_es_el_del_trabajo(self):
        """Una orden de diciembre digitada en enero sigue siendo de diciembre."""
        orden = self._orden(fecha=datetime.date(2025, 12, 20))

        self.assertIn("-2025-", orden.numero_orden)

    def test_la_fecha_del_trabajo_no_puede_ser_futura(self):
        with self.assertRaises(ValidationError):
            self._orden(fecha=timezone.localdate() + datetime.timedelta(days=1))

    def test_la_solicitud_en_papel_exige_quien_la_pidio(self):
        """Si no, no hay a quien volver cuando falte un dato de la hoja."""
        with self.assertRaises(ValidationError):
            self._orden(origen=OrigenOrdenTrabajo.PAPEL)

    def test_la_solicitud_no_puede_ser_posterior_al_trabajo(self):
        with self.assertRaises(ValidationError):
            self._orden(
                origen=OrigenOrdenTrabajo.PAPEL,
                solicitado_por="Jefa de laboratorio",
                fecha=timezone.localdate() - datetime.timedelta(days=3),
                fecha_solicitud=timezone.localdate(),
            )

    def test_el_equipo_tiene_que_ser_del_tipo_de_la_hoja(self):
        """La lista de actividades es comun: mezclar tipos la vuelve mentira."""
        otro_usuario = User.objects.create_user(
            username="zz_orden_otro", password="x"
        )
        otro = _dispositivo_de_prueba(otro_usuario)
        orden = self._orden()

        with self.assertRaises(ValidationError):
            EquipoEnOrdenTrabajo(orden=orden, dispositivo=otro).save()

    def test_el_motor_rechaza_el_mismo_equipo_dos_veces(self):
        """Dos personas llenando la hoja a la vez pasan las dos el clean()."""
        orden = self._orden()
        EquipoEnOrdenTrabajo.objects.create(
            orden=orden, dispositivo=self.dispositivo
        )

        with self.assertRaises(IntegrityError):
            EquipoEnOrdenTrabajo.objects.bulk_create(
                [EquipoEnOrdenTrabajo(orden=orden, dispositivo=self.dispositivo)]
            )

    def test_la_hora_final_va_despues_de_la_de_inicio(self):
        orden = self._orden()

        with self.assertRaises(ValidationError):
            EquipoEnOrdenTrabajo(
                orden=orden,
                dispositivo=self.dispositivo,
                hora_inicio=datetime.time(10, 0),
                hora_final=datetime.time(9, 0),
            ).save()

    def test_los_minutos_salen_de_las_horas(self):
        orden = self._orden()
        fila = EquipoEnOrdenTrabajo.objects.create(
            orden=orden,
            dispositivo=self.dispositivo,
            hora_inicio=datetime.time(9, 15),
            hora_final=datetime.time(10, 0),
        )

        self.assertEqual(fila.minutos, 45)

    def test_el_motor_rechaza_la_misma_actividad_dos_veces(self):
        orden = self._orden()
        actividad = actividades_service.registrar_actividad("Limpieza general")
        ActividadEnOrdenTrabajo.objects.create(
            orden=orden, actividad=actividad, registrado_por=self.usuario
        )

        with self.assertRaises(IntegrityError):
            ActividadEnOrdenTrabajo.objects.bulk_create(
                [
                    ActividadEnOrdenTrabajo(
                        orden=orden,
                        actividad=actividad,
                        registrado_por=self.usuario,
                    )
                ]
            )

    def test_la_linea_impresa_incluye_el_detalle(self):
        orden = self._orden()
        actividad = actividades_service.registrar_actividad("Cambio de filtro")
        linea = ActividadEnOrdenTrabajo.objects.create(
            orden=orden,
            actividad=actividad,
            detalle="filtro de entrada, estaba saturado",
            registrado_por=self.usuario,
        )

        self.assertIn("Cambio de filtro", linea.texto)
        self.assertIn("saturado", linea.texto)


class PantallasDeMantenimientoTests(TestCase):
    """Que las pantallas abran. Una pantalla sin prueba se rompe sin aviso."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_pantallas_mant",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_el_panel_abre(self):
        respuesta = self.client.get(reverse("panel_mantenimiento_equipos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Preventivos atrasados")

    def test_el_calendario_abre(self):
        respuesta = self.client.get(reverse("calendario_mantenimiento_equipos"))

        self.assertEqual(respuesta.status_code, 200)

    def test_un_mes_ilegible_no_rompe_el_calendario(self):
        """Se muestra el mes en curso, que es lo que se queria ver."""
        respuesta = self.client.get(
            reverse("calendario_mantenimiento_equipos"), {"mes": "marzo"}
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_la_pantalla_de_programar_abre(self):
        respuesta = self.client.get(
            reverse("programar_mantenimiento_equipos", args=[self.dispositivo.pk])
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_el_listado_de_ordenes_abre(self):
        respuesta = self.client.get(reverse("listado_ordenes_equipos"))

        self.assertEqual(respuesta.status_code, 200)

    def test_la_hoja_de_trabajo_abre(self):
        orden = OrdenTrabajoMantenimiento.objects.create(
            tipo=self.dispositivo.tipo,
            fecha=timezone.localdate(),
            operario=self.usuario,
            creado_por=self.usuario,
        )

        respuesta = self.client.get(
            reverse("orden_trabajo_equipos", args=[orden.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, orden.numero_orden)

    def test_la_hoja_imprimible_abre(self):
        orden = OrdenTrabajoMantenimiento.objects.create(
            tipo=self.dispositivo.tipo,
            fecha=timezone.localdate(),
            operario=self.usuario,
            creado_por=self.usuario,
        )

        respuesta = self.client.get(
            reverse("imprimir_orden_equipos", args=[orden.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Relación de equipos")

    def test_programar_crea_el_plan_y_su_calendario(self):
        respuesta = self.client.post(
            reverse("programar_mantenimiento_equipos", args=[self.dispositivo.pk]),
            {
                "responsable": self.usuario.pk,
                "frecuencia_meses": 6,
                "fecha_inicio": (
                    timezone.localdate() + datetime.timedelta(days=10)
                ).isoformat(),
                "trabaja_fines_de_semana": "",
                "observaciones": "",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        plan = PlanMantenimiento.objects.get(dispositivo=self.dispositivo)
        self.assertGreaterEqual(plan.visitas.count(), 4)

    def test_la_primera_visita_no_puede_quedar_en_el_pasado(self):
        respuesta = self.client.post(
            reverse("programar_mantenimiento_equipos", args=[self.dispositivo.pk]),
            {
                "responsable": self.usuario.pk,
                "frecuencia_meses": 6,
                "fecha_inicio": (
                    timezone.localdate() - datetime.timedelta(days=1)
                ).isoformat(),
                "trabaja_fines_de_semana": "",
                "observaciones": "",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(
            PlanMantenimiento.objects.filter(dispositivo=self.dispositivo).exists()
        )

    def test_la_ficha_del_equipo_dice_que_no_tiene_plan(self):
        respuesta = self.client.get(
            reverse("detalle_dispositivo_equipos", args=[self.dispositivo.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Sin plan de mantenimiento")


class ActividadesEnLaHojaTests(TestCase):
    """Escribir lo que se hizo, linea por linea y sin recargar."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_hoja",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.usuario)

    def setUp(self):
        self.client.force_login(self.usuario)
        self.orden = OrdenTrabajoMantenimiento.objects.create(
            tipo=self.dispositivo.tipo,
            fecha=timezone.localdate(),
            operario=self.usuario,
            creado_por=self.usuario,
        )

    def _agregar(self, nombre, detalle=""):
        return self.client.post(
            reverse("agregar_actividad_orden_equipos", args=[self.orden.pk]),
            data=json.dumps({"nombre": nombre, "detalle": detalle}),
            content_type="application/json",
        )

    def test_escribir_una_actividad_la_agrega_a_la_hoja(self):
        respuesta = self._agregar("Limpieza general del equipo")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.orden.actividades.count(), 1)

    def test_escribir_una_actividad_la_guarda_en_el_catalogo(self):
        """Es lo que hace que la proxima vez se pueda sugerir."""
        self._agregar("Revision del cable de alimentacion")

        self.assertTrue(
            ActividadMantenimiento.objects.filter(
                clave=normalizar_actividad("Revision del cable de alimentacion")
            ).exists()
        )

    def test_la_respuesta_avisa_de_que_la_linea_es_nueva(self):
        datos = self._agregar("Verificacion de la valvula de seguridad").json()

        self.assertTrue(datos["linea"]["nueva_en_catalogo"])

    def test_la_segunda_vez_ya_no_es_nueva(self):
        self._agregar("Limpieza general del equipo")

        otra_orden = OrdenTrabajoMantenimiento.objects.create(
            tipo=self.dispositivo.tipo,
            fecha=timezone.localdate(),
            operario=self.usuario,
            creado_por=self.usuario,
        )
        respuesta = self.client.post(
            reverse("agregar_actividad_orden_equipos", args=[otra_orden.pk]),
            data=json.dumps({"nombre": "limpieza general del equipo"}),
            content_type="application/json",
        )

        self.assertFalse(respuesta.json()["linea"]["nueva_en_catalogo"])

    def test_la_misma_linea_dos_veces_en_la_hoja_se_rechaza_con_un_motivo(self):
        self._agregar("Limpieza general del equipo")
        respuesta = self._agregar("Limpieza general del equipo")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("ya está en esta orden", respuesta.json()["error"])

    def test_las_lineas_conservan_el_orden_en_que_se_trabajo(self):
        self._agregar("Inspeccion externa del equipo")
        self._agregar("Revision del cable de alimentacion")
        self._agregar("Limpieza general del equipo")

        posiciones = list(
            self.orden.actividades.order_by("posicion").values_list(
                "posicion", flat=True
            )
        )

        self.assertEqual(posiciones, [1, 2, 3])

    def test_una_linea_demasiado_corta_se_rechaza(self):
        respuesta = self._agregar("ok")

        self.assertEqual(respuesta.status_code, 400)

    def test_quitar_una_linea_no_la_borra_del_catalogo(self):
        """La palabra ya forma parte del vocabulario del taller."""
        self._agregar("Limpieza general del equipo")
        linea = self.orden.actividades.first()

        respuesta = self.client.post(
            reverse("quitar_actividad_orden_equipos", args=[linea.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.orden.actividades.count(), 0)
        self.assertEqual(ActividadMantenimiento.objects.count(), 1)

    def test_el_autocompletado_responde(self):
        self._agregar("Limpieza general del equipo")

        respuesta = self.client.get(
            reverse("sugerir_actividades_equipos"),
            {"q": "limpieza", "tipo": self.dispositivo.tipo_id},
        )

        self.assertEqual(respuesta.status_code, 200)
        nombres = [s["nombre"] for s in respuesta.json()["sugerencias"]]
        self.assertIn("Limpieza general del equipo", nombres)

    def test_agregar_un_equipo_a_la_hoja(self):
        respuesta = self.client.post(
            reverse("agregar_equipo_orden_equipos", args=[self.orden.pk]),
            {
                "dispositivo": self.dispositivo.pk,
                "ambiente": "SALA 3",
                "hora_inicio": "09:00",
                "hora_final": "09:40",
                "observaciones": "",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["fila"]["minutos"], 40)

    def test_no_se_puede_cerrar_una_hoja_sin_equipos(self):
        self._agregar("Limpieza general del equipo")

        self.client.post(reverse("cerrar_orden_equipos", args=[self.orden.pk]))
        self.orden.refresh_from_db()

        self.assertEqual(self.orden.estado, EstadoOrdenTrabajo.ABIERTA)

    def test_no_se_puede_cerrar_una_hoja_que_no_dice_que_se_hizo(self):
        EquipoEnOrdenTrabajo.objects.create(
            orden=self.orden, dispositivo=self.dispositivo
        )

        self.client.post(reverse("cerrar_orden_equipos", args=[self.orden.pk]))
        self.orden.refresh_from_db()

        self.assertEqual(self.orden.estado, EstadoOrdenTrabajo.ABIERTA)

    def test_una_hoja_completa_se_cierra(self):
        EquipoEnOrdenTrabajo.objects.create(
            orden=self.orden, dispositivo=self.dispositivo
        )
        self._agregar("Limpieza general del equipo")

        self.client.post(reverse("cerrar_orden_equipos", args=[self.orden.pk]))
        self.orden.refresh_from_db()

        self.assertEqual(self.orden.estado, EstadoOrdenTrabajo.CERRADA)
        self.assertEqual(self.orden.cerrada_por, self.usuario)

    def test_una_hoja_cerrada_ya_no_admite_lineas(self):
        EquipoEnOrdenTrabajo.objects.create(
            orden=self.orden, dispositivo=self.dispositivo
        )
        self._agregar("Limpieza general del equipo")
        self.client.post(reverse("cerrar_orden_equipos", args=[self.orden.pk]))

        respuesta = self._agregar("Revision del cable de alimentacion")

        self.assertEqual(respuesta.status_code, 400)


class RegistrarVisitaDesdeElCalendarioTests(TestCase):
    """Registrar una visita abre la hoja, y varias visitas comparten hoja."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser(
            username="zz_registrar",
            password="clave-de-prueba",
        )
        cls.primero = _dispositivo_de_prueba(cls.usuario)

        # Un segundo equipo del mismo tipo: es el caso de la salida a revisar
        # cinco monitores de la misma sala.
        cls.segundo = Dispositivo.objects.create(
            tipo=cls.primero.tipo,
            marca=cls.primero.marca,
            modelo=cls.primero.modelo,
            area_gestora=cls.primero.area_gestora,
            modalidad_procedencia=cls.primero.modalidad_procedencia,
            procedencia=cls.primero.procedencia,
            creado_por=cls.usuario,
            modificado_por=cls.usuario,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def _plan_de(self, dispositivo):
        return crear_plan(
            dispositivo=dispositivo,
            responsable=self.usuario,
            frecuencia_meses=6,
            fecha_inicio=timezone.localdate() + datetime.timedelta(days=10),
            trabaja_fines_de_semana=True,
            creado_por=self.usuario,
        )

    def test_registrar_una_visita_abre_la_hoja(self):
        plan = self._plan_de(self.primero)
        visita = plan.proxima_visita

        respuesta = self.client.post(
            reverse("realizar_visita_equipos", args=[visita.pk]),
            {
                "fecha_realizada": timezone.localdate().isoformat(),
                "observaciones": "",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        visita.refresh_from_db()
        self.assertEqual(visita.estado, EstadoVisitaPreventiva.REALIZADA)
        self.assertIsNotNone(visita.orden_id)
        self.assertIn(str(visita.orden_id), respuesta["Location"])

    def test_dos_equipos_del_mismo_tipo_el_mismo_dia_comparten_hoja(self):
        """Una salida a revisar cinco monitores es una hoja, no cinco."""
        hoy = timezone.localdate().isoformat()

        for dispositivo in (self.primero, self.segundo):
            plan = self._plan_de(dispositivo)
            self.client.post(
                reverse("realizar_visita_equipos", args=[plan.proxima_visita.pk]),
                {"fecha_realizada": hoy, "observaciones": ""},
            )

        self.assertEqual(OrdenTrabajoMantenimiento.objects.count(), 1)
        self.assertEqual(
            OrdenTrabajoMantenimiento.objects.first().equipos.count(), 2
        )

    def test_mover_una_visita_desde_el_calendario(self):
        plan = self._plan_de(self.primero)
        visita = plan.proxima_visita
        nueva = visita.fecha_programada + datetime.timedelta(days=7)

        respuesta = self.client.post(
            reverse("mover_visita_equipos", args=[visita.pk]),
            data=json.dumps({"fecha": nueva.isoformat()}),
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["fecha"], nueva.isoformat())

    def test_no_se_puede_mover_una_visita_al_pasado(self):
        """Seria registrarla como hecha por la puerta de atras."""
        plan = self._plan_de(self.primero)
        visita = plan.proxima_visita

        respuesta = self.client.post(
            reverse("mover_visita_equipos", args=[visita.pk]),
            data=json.dumps(
                {
                    "fecha": (
                        timezone.localdate() - datetime.timedelta(days=1)
                    ).isoformat()
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_un_equipo_que_entro_por_el_calendario_no_se_quita_de_la_hoja(self):
        plan = self._plan_de(self.primero)
        visita = plan.proxima_visita
        self.client.post(
            reverse("realizar_visita_equipos", args=[visita.pk]),
            {
                "fecha_realizada": timezone.localdate().isoformat(),
                "observaciones": "",
            },
        )

        visita.refresh_from_db()
        fila = visita.orden.equipos.first()

        respuesta = self.client.post(
            reverse("quitar_equipo_orden_equipos", args=[fila.pk])
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(visita.orden.equipos.count(), 1)


class PermisosDeMantenimientoTests(TestCase):
    """Quien no tiene el permiso no pasa, y los puntos JSON lo dicen en JSON."""

    @classmethod
    def setUpTestData(cls):
        cls.con_permiso = User.objects.create_superuser(
            username="zz_permiso_si",
            password="clave-de-prueba",
        )
        cls.dispositivo = _dispositivo_de_prueba(cls.con_permiso)

        # Un usuario sin rol ni unidad: existe, inicia sesion, y no tiene
        # ningun permiso del modulo.
        cls.sin_permiso = User.objects.create_user(
            username="zz_permiso_no",
            password="clave-de-prueba",
        )
        cls.orden = OrdenTrabajoMantenimiento.objects.create(
            tipo=cls.dispositivo.tipo,
            fecha=timezone.localdate(),
            operario=cls.con_permiso,
            creado_por=cls.con_permiso,
        )

    def test_sin_permiso_el_punto_json_responde_403_en_json(self):
        """Un redirect a HTML llegaria como un trozo que el JavaScript no lee."""
        self.client.force_login(self.sin_permiso)

        respuesta = self.client.post(
            reverse("agregar_actividad_orden_equipos", args=[self.orden.pk]),
            data=json.dumps({"nombre": "Limpieza general del equipo"}),
            content_type="application/json",
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("error", respuesta.json())

    def test_sin_permiso_la_pantalla_lleva_a_acceso_denegado(self):
        self.client.force_login(self.sin_permiso)

        respuesta = self.client.get(reverse("panel_mantenimiento_equipos"))

        self.assertEqual(respuesta.status_code, 302)

    def test_el_get_no_cambia_nada_en_un_punto_json(self):
        """Un GET que modificara dejaria la hoja a merced de un enlace."""
        self.client.force_login(self.con_permiso)

        respuesta = self.client.get(
            reverse("agregar_actividad_orden_equipos", args=[self.orden.pk])
        )

        self.assertEqual(respuesta.status_code, 405)
