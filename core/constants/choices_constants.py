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

class TipoMovimientoCita(models.IntegerChoices):

    # Se utiliza cuando una cita obtiene un cupo por primera vez.
    ASIGNACION = 1, "ASIGNACION"

    # Se utiliza cuando la cita pierde el cupo que tenía asignado
    # por una situación de agenda, pero la cita continúa vigente
    # y debe ser reprogramada.
    CANCELACION_CUPO = 2, "CANCELACION CUPO"

    # Se utiliza cuando una cita cambia de un cupo a otro.
    # Puede ocurrir directamente por solicitud del paciente,
    # por decisión del personal o después de una cancelación de cupo.
    REPROGRAMACION = 3, "REPROGRAMACION"

    # Se utiliza cuando se cancela definitivamente la cita.
    # El cupo que tenía asignado se libera para poder ser utilizado
    # por otra cita.
    CANCELACION_CITA = 4, "CANCELACION CITA"

    

class TipoAusencia(models.IntegerChoices):
    VACACIONES = 1, "VACACIONES"
    INCAPACIDAD = 2, "INCAPACIDAD"
    PERMISO = 3, "PERMISO"
    CAPACITACION = 4, "CAPACITACIÓN"
    CONGRESO = 5, "CONGRESO"
    PROFILACTICA = 6, "PROFILÁCTICA"
    OTROS = 7, "OTROS"
    FERIADO = 8, "FERIADO"

    @classmethod
    def opciones(cls):
        return [
            {
                "value": value,
                "texto": label
            }
            for value, label in cls.choices
        ]

    @classmethod
    def validar(cls, tipo):
        if tipo not in cls.values:
            raise ValidationError("El tipo de ausencia no es válido.")

        return cls(tipo)


class EstadoMapeoCategoria(models.TextChoices):
    ESTADO_CAMA = "ESTADO_CAMA", "Estado de cama"
    ESTADO_SESION = "ESTADO_SESION", "Estado de sesion"
    TIPO_ACCION = "TIPO_ACCION", "Tipo de accion"
    OBSERVACION = "OBSERVACION", "Observacion"
