from django.db import models
from datetime import date
from rrhh.models import PersonalSalud, Jornada_laboral
from clinico.models import Tipo_atencion
from core.constants.choices_constants import EstadoRegistro, DiaSemana
from core.constants.domain_constants import EstadoTemporalPeriodo
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

# Create your models here.
class Periodo_laboral(models.Model):
    personal_salud = models.ForeignKey(PersonalSalud, on_delete=models.PROTECT)
    jornada_laboral = models.ForeignKey(Jornada_laboral, on_delete=models.PROTECT)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='periodos_creados')
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='periodos_modificados')

    @property
    def estado_temporal(self):
        hoy = date.today()

        if hoy < self.fecha_inicio:
            return EstadoTemporalPeriodo.FUTURO.value
        elif self.fecha_inicio <= hoy <= self.fecha_fin:
            return EstadoTemporalPeriodo.EN_EJECUCION.value
        else:
            return  EstadoTemporalPeriodo.FINALIZADO.value

    def clean(self): 
        if self.fecha_inicio > self.fecha_fin: 
            raise ValidationError("La fecha de inicio no puede ser mayor que la fecha de fin.")
        

    def __str__(self): 
        return f"{self.personal_salud.empleado} rango ({self.fecha_inicio} - {self.fecha_fin})"
    
    class Meta:
        verbose_name = "Periodo laboral"
        verbose_name_plural = "Periodos laborales"
        ordering = ['personal_salud__empleado']
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["estado", "fecha_inicio"]),
            models.Index(fields=["personal_salud", "fecha_inicio"])
        ]


class Dia_laboral(models.Model):
    periodo_laboral = models.ForeignKey(Periodo_laboral, on_delete=models.CASCADE, related_name="dias_laborales")
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices, null=False, blank=False, db_index=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )

    class Meta: 
        unique_together = ("periodo_laboral", "dia_semana") 
        ordering = ["dia_semana"]
        verbose_name = "Dia laboral"
        verbose_name_plural = "Dias laborales"
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["periodo_laboral", "dia_semana"]),
        ]

    def clean(self): 
        # Validar horario 
        if self.hora_inicio >= self.hora_fin: 
            raise ValidationError("La hora de inicio debe ser menor que la hora de fin.") 
        
        # Validar que esté dentro de la jornada del periodo 
        if self.periodo_laboral and self.periodo_laboral.jornada_laboral: 
            if self.hora_inicio < self.periodo_laboral.jornada_laboral.hora_inicio or self.hora_fin > self.periodo_laboral.jornada_laboral.hora_fin: 
                raise ValidationError("El horario del día debe estar dentro de la jornada definida.")
            
    def __str__(self): 
        return f"{self.get_dia_semana_display()} - {self.periodo_laboral}"
    

class Cupo_atencion(models.Model):
    dia_laboral = models.ForeignKey(Dia_laboral, verbose_name=("Dia laboral"), on_delete=models.CASCADE, related_name="cupos")
    tipo_atencion = models.ForeignKey(Tipo_atencion, verbose_name="Tipo Atencion", on_delete=models.PROTECT)
    cupos = models.PositiveSmallIntegerField(verbose_name="Cupos")
    duracion_minutos = models.PositiveSmallIntegerField()
    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )

    class Meta: 
        unique_together = ("dia_laboral", "tipo_atencion") 
        ordering = ["id"]
        verbose_name = "Cupo atencion"
        verbose_name_plural = "Cupos Atenciones"
        indexes = [
            models.Index(fields=["estado"])
        ]

    def clean(self): 
        if self.cupos <= 0: 
            raise ValidationError("Los cupos deben ser mayores a cero.") 
        
        if self.duracion_minutos <= 0: 
            raise ValidationError("La duración debe ser mayor a cero.") 
    
    def __str__(self): return f"{self.tipo_atencion} - {self.cupos} cupos"