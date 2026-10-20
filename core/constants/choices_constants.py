from django.core.exceptions import ValidationError
from django.db import models


class EstadoRegistro(models.IntegerChoices):
    ACTIVO = 1, "Activo"
    INACTIVO = 2, "Inactivo"


class AlcanceUsuario(models.IntegerChoices):
    UNIDAD = 1, "POR UNIDAD"
    GLOBAL = 2, "GLOBAL"


class TipoUnidad(models.IntegerChoices):
    # CLINICA = 1, "CLINICA"
    ADMINISTRATIVA = 2, "ADMINISTRATIVA"
    APOYO = 3, "APOYO"


class Sexo(models.TextChoices):
    HOMBRE = "H", "Hombre"
    MUJER = "M", "Mujer"
    NO_IDENTIFICADO = "N", "No identificado"

    @classmethod
    def validar(cls, sexo):
        if sexo not in cls.values:
            raise ValidationError(
                "El sexo seleccionado no es válido."
            )

        return cls(sexo)


class EstadoCama(models.IntegerChoices):
    DISPONIBLE = 1, "DISPONIBLE"
    OCUPADA = 2, "OCUPADA"
    EN_MANTENIMIENTO = 3, "EN MANTENIMIENTO"

class NivelAtencion(models.IntegerChoices):
    PRIMER_NIVEL = 1, "PRIMER NIVEL"
    SEGUNDO_NIVEL = 2, "SEGUNDO NIVEL"
    OTROS = 3, "OTROS"

class TipoPersonalNoClinico(models.IntegerChoices):
    ADMINISTRATIVO = 1, "ADMINISTRATIVO"
    APOYO = 2, "APOYO"
    TECNICO = 3, "TECNICO"
    RESPONSABLE = 4, "RESPONSABLE"
    AUXILIAR = 5, "AUXILIAR"


class RolUsuario(models.TextChoices):
    ADMIN = 'admin', 'Administrador'
    DIGITADOR = 'digitador', 'Digitador'
    AUDITOR = 'auditor', 'Auditor'
    VISITANTE = 'visitante', 'Visitante'
    DIRECTIVO = 'directivo', 'Directivo'


class AtencionRequerida(models.IntegerChoices):
    EMERGENCIA_OBSTETRICA = 1, "EMERGENCIA OBSTETRICA"
    EMERGENCIA_GENERAL = 2, "EMERGENCIA GENERAL"
    CONSULTA_EXTERNA = 3, "CONSULTA EXTERNA"
    HOSPITALIZACION = 4, "HOSPITALIZACION"
    OTROS = 5, "OTROS"


class MetodoSeguimiento(models.IntegerChoices):
    LLAMADA_TELEFONICA = 1, "LLAMADA TELEFONICA"
    WHATSAPP = 2, "WHATSAPP"
    VISITA_DOMICILIARIA = 3, "VISITA DOMICILIARIA"
    CORREO_ELECTRONICO = 4, "CORREO ELECTRONICO"
    OTRO = 5, "OTRO METODO"


class FuenteSeguimiento(models.IntegerChoices):
    PACIENTE = 1, "PACIENTE"
    FAMILIAR = 2, "FAMILIAR"
    AMIGO = 3, "AMIGO"
    PROFESIONAL_SALUD = 4, "PROFESIONAL DE SALUD"
    OTRO = 5, "OTRO"

class TipoControlCalidadReferencia(models.IntegerChoices):
    REFERENCIA = 1, "REFERENCIA"
    RESPUESTA = 2, "RESPUESTA"


class TipoDefuncion(models.IntegerChoices):
    INTRAHOSPITALARIA = 1, "Intrahospitalaria"
    EXTRAHOSPITALARIA = 2, "Extrahospitalaria"
    
class DiaSemana(models.IntegerChoices):
    LUNES = 1, "LUNES"
    MARTES = 2, "MARTES"
    MIERCOLES = 3, "MIÉRCOLES"
    JUEVES = 4, "JUEVES"
    VIERNES = 5, "VIERNES"
    SABADO = 6, "SÁBADO"
    DOMINGO = 7, "DOMINGO"

class PrioridadAtencion(models.IntegerChoices):
    ORDINARIA = 1, "ORDINARIA"
    PREFERENTE = 2, "PREFERENTE"


class EstadoCupoAgenda(models.IntegerChoices):
    # Cupo libre y disponible para asignar una cita
    DISPONIBLE = 1, "DISPONIBLE"
    # Cupo asociado actualmente a una cita activa
    ASIGNADO = 2, "ASIGNADO"
    # Cupo bloqueado por ausencia, permiso o restricción operativa
    BLOQUEADO = 3, "BLOQUEADO"
    # Cupo deshabilitado por cambios administrativos:
    # reducción de cupos, modificación de agenda,
    # eliminación de configuración o cambios de horario
    INACTIVO = 4, "INACTIVO"


class TipoAusencia(models.IntegerChoices):
    VACACIONES = 1, "VACACIONES"
    INCAPACIDAD = 2, "INCAPACIDAD"
    PERMISO = 3, "PERMISO"
    CAPACITACION = 4, "CAPACITACIÓN"
    CONGRESO = 5, "CONGRESO"
    OTROS = 6, "OTROS"


class EstadoMapeoCategoria(models.TextChoices):
    ESTADO_CAMA = "ESTADO_CAMA", "Estado de cama"
    ESTADO_SESION = "ESTADO_SESION", "Estado de sesion"
    TIPO_ACCION = "TIPO_ACCION", "Tipo de accion"
    OBSERVACION = "OBSERVACION", "Observacion"



class EstadoLaborParto(models.IntegerChoices):
    LABOR = 1, "TRABAJO DE PARTO"
    EXPULSIVO = 2, "EXPULSIVO"
    PUERPERIO_INMEDIATO = 3, "PUERPERIO INMEDIATO"
    INTERMEDIO = 4, "CUIDADOS INTERMEDIOS"

    @classmethod
    def opciones(cls):
        return [
            {
                "value": value,
                "texto": label,
                **cls.obtener_color(value),
            }
            for value, label in cls.choices
        ]

    @classmethod
    def obtener_texto(cls, estado):
        return cls(estado).label

    @classmethod
    def obtener_color(cls, estado):

        colores = {

    cls.LABOR: {
        "color": "rgb(83, 108, 166)",
        "fondo": "rgba(83, 108, 166, 0.06)",
        "borderColor": "rgba(83, 108, 166, 0.50)",
        "icono": "trabajo_parto",
    },

    cls.EXPULSIVO: {
        "color": "rgb(150, 63, 82)",
        "fondo": "rgba(150, 63, 82, 0.07)",
        "borderColor": "rgba(150, 63, 82, 0.50)",
        "icono": "expulsivo",
    },

    cls.PUERPERIO_INMEDIATO: {
        "color": "rgb(65, 137, 113)",
        "fondo": "rgba(65, 137, 113, 0.06)",
        "borderColor": "rgba(65, 137, 113, 0.50)",
        "icono": "puerperio_inmediato",
    },

    cls.INTERMEDIO: {
        "color": "rgb(143, 103, 166)",
        "fondo": "rgba(143, 103, 166, 0.06)",
        "borderColor": "rgba(143, 103, 166, 0.50)",
        "icono": "cuidados_intermedios",
    },

}

        return colores.get(estado)

    @classmethod
    def validar(cls, estado):
        if estado not in cls.values:
            raise ValidationError(
                "El estado de Labor y Parto no es válido."
            )

        return cls(estado)



class TipoMovimientoLaborParto(models.IntegerChoices):
    CAMBIO_ESTADO = 1, "CAMBIO DE ESTADO"
    SALIDA = 2, "SALIDA"
    RETORNO = 3, "RETORNO"
