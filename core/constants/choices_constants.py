
from django.db import models


class EstadoRegistro(models.IntegerChoices):
    ACTIVO = 1, "Activo"
    INACTIVO = 2, "Inactivo"


class AlcanceUsuario(models.IntegerChoices):
    UNIDAD = 1, "POR UNIDAD"
    GLOBAL = 2, "GLOBAL"


class TipoUnidad(models.IntegerChoices):
    CLINICA = 1, "CLINICA"
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