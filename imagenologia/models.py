from django.db import models
from django.contrib.auth.models import User
from paciente.models import Paciente
from servicio.models import Sala, Area_atencion, ServiciosAux, Unidad_clinica
from django.core.exceptions import ValidationError

class TipoPaciente:
    INTERNO = 1
    EXTERNO = 2
# Create your models here.
class PacienteExterno(models.Model):
    dni = models.CharField(
        max_length=50,
        verbose_name="Número de identificación",
        blank=True,
        null=True,
        db_index=True
    )
    primer_nombre = models.CharField("Primer nombre", max_length=100)
    segundo_nombre = models.CharField("Segundo nombre", max_length=100, blank=True, null=True)
    primer_apellido = models.CharField("Primer apellido", max_length=100)
    segundo_apellido = models.CharField("Segundo apellido", max_length=100, blank=True, null=True)
    
    fecha_nacimiento = models.DateField("Fecha de nacimiento", db_index=True)
    
    sexo = models.CharField(
        "Sexo",
        max_length=1,
        choices=[("H", "Hombre"), ("M", "Mujer"), ("N", "No identificado")],
        default="M"
    )
    activo = models.BooleanField(default=1, verbose_name="Activo (si/no)")
    fecha_creado = models.DateTimeField("Fecha creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pacientesexternos_creados')

    fecha_modificado = models.DateTimeField("Fecha modificado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pacientesexternos_modificados')

    class Meta:
        verbose_name = "Paciente externo"
        verbose_name_plural = "Pacientes externos"
        ordering = ['-fecha_creado']

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} ({self.dni or 'Sin ID'})"


class ClasificacionEstudio(models.Model):
    descripcion = models.CharField(max_length=100, unique=True)
    
    class Meta:
        verbose_name = "Clasificación de Estudio"
        verbose_name_plural = "Clasificaciones de Estudios"
        ordering = ['descripcion']

    def __str__(self):
        return self.descripcion


class Estudio(models.Model):
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Codigo CIE", blank=False, null=False, db_index=True)
    clasificacion = models.ForeignKey(ClasificacionEstudio, on_delete=models.PROTECT, related_name='estudios')
    coste_impresion = models.IntegerField(verbose_name="Costo impresion", default=0)
    descripcion_estudio = models.CharField(max_length=100, blank=False, null=False, db_index=True, verbose_name="Descripcion", unique=True)
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='estudios_creados')
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='estudios_modificados')

    class Meta:
        verbose_name = "Estudio"
        verbose_name_plural = "Estudios"
        ordering = ["descripcion_estudio",]

    def __str__(self):
        return f"{self.descripcion_estudio}"

class MaquinaRX(models.Model):  # <- AGREGADO
    descripcion_maquina = models.CharField(max_length=100, blank=False, null=False, db_index=True, verbose_name="Descripcion maquina", unique=True)
    estado = models.BooleanField(default=1, verbose_name="Estado (activo/inactivo)")

    class Meta:
        verbose_name = "MaquinaRX"
        verbose_name_plural = "MaquinasRX"
        ordering = ["descripcion_maquina",]

    def __str__(self):
        return f"{self.descripcion_maquina}"


class EvaluacionRx(models.Model):  # <- AGREGADO
    fecha = models.DateField(verbose_name="Fecha de evaluacion")
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, verbose_name="Paciente", related_name='evalacionesRx', blank=True, null=True)
    paciente_externo = models.ForeignKey(PacienteExterno, on_delete=models.PROTECT, verbose_name="Paciente Externo", blank=True, null=True)
    unidad_clinica = models.ForeignKey(Unidad_clinica,on_delete=models.PROTECT, null=True, blank=True)
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    observaciones = models.TextField(verbose_name="Observaciones", null=True,blank=True)
    maquinarx = models.ForeignKey(MaquinaRX, null=False, blank=False, on_delete=models.PROTECT, default=1)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='evaluaciones_creadas')
    fecha_modificado = models.DateTimeField(verbose_name="Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='evaluaciones_modificadas')
    estado = models.SmallIntegerField(
        verbose_name="Estado",
        choices=[(1, "Activo"), (2, "Inactivo")],
        default=1
    )

    def obtener_tipo_y_paciente_id(self):
        """
        Retorna el tipo de paciente y su ID.
        Tipo puede ser: 'interno' o 'externo'.
        """
        if self.paciente_id:
            return TipoPaciente.INTERNO, self.paciente_id
        if self.paciente_externo_id:
            return TipoPaciente.EXTERNO, self.paciente_externo_id
        raise ValueError("La evaluación no tiene paciente asociado")

    class Meta:
        verbose_name = "EvaluacionRx"
        verbose_name_plural = "EvaluacionRxs"
        ordering = ["-fecha",]

    def __str__(self):
        return f"Evaluación de {self.paciente} el {self.fecha}"



class EvaluacionRxDetalle(models.Model):
    evaluacionRx = models.ForeignKey(EvaluacionRx, on_delete=models.PROTECT, verbose_name="Evaluacion RX", related_name="detalles")
    estudio = models.ForeignKey(Estudio, on_delete=models.PROTECT, verbose_name="Estudio")  # <- AGREGADO
    impreso = models.BooleanField(default=0, verbose_name="Impreso (si/no)")
    activo = models.BooleanField(default=1, verbose_name="Activo (si/no)")


    class Meta:
        verbose_name = "EvaluacionRxDetalle"
        verbose_name_plural = "EvaluacionRxDetalles"

    def __str__(self):
        return f"{self.evaluacionRx} - {self.estudio}"



