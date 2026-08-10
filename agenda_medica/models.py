from django.db import models
from datetime import date
from rrhh.models import PersonalSalud, Jornada_laboral
from clinico.models import Tipo_atencion
from core.constants.choices_constants import EstadoRegistro, DiaSemana, EstadoCupoAgenda, TipoAusencia
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
        
    @property
    def periodo_formateado(self):
        return (
            f"{self.fecha_inicio.strftime('%d/%m/%Y')} "
            f"al "
            f"{self.fecha_fin.strftime('%d/%m/%Y')}"
    )

    @property
    def total_cupos(self):
        return Cupo_agenda.objects.filter(
            configuracion_cupo__dia_laboral__periodo_laboral=self
        ).exclude(
            estado=EstadoCupoAgenda.INACTIVO
        ).count()

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
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='dia_laboral_creados', null=True, blank=True)
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True )
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='dia_laboral_modificados', null=True, blank=True )

    @property
    def total_cupos(self):
        return Cupo_agenda.objects.filter(
            configuracion_cupo__dia_laboral=self
        ).exclude(
            estado=EstadoCupoAgenda.INACTIVO
        ).count()


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
    

class Configuracion_cupo(models.Model):
    dia_laboral = models.ForeignKey(Dia_laboral, verbose_name=("Dia laboral"), on_delete=models.CASCADE, related_name="cupos")
    tipo_atencion = models.ForeignKey(Tipo_atencion, verbose_name="Tipo Atencion", on_delete=models.PROTECT)
    cupos = models.PositiveSmallIntegerField(verbose_name="Cupos")
    duracion_minutos = models.PositiveSmallIntegerField()
    orden = models.PositiveSmallIntegerField(default=1)
    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )

    @property
    def total_cupos(self):
        return self.cupos_agenda.exclude(
            estado=EstadoCupoAgenda.INACTIVO
        ).count()

    class Meta: 
        unique_together = ("dia_laboral", "tipo_atencion") 
        ordering = ["id"]
        verbose_name = "Configuracion cupo"
        verbose_name_plural = "Configuracion cupos"
        indexes = [
            models.Index(fields=["estado"])
        ]

    def clean(self): 
        if self.cupos <= 0: 
            raise ValidationError("Los cupos deben ser mayores a cero.") 
        
        if self.duracion_minutos <= 0: 
            raise ValidationError("La duración debe ser mayor a cero.") 
    
    def __str__(self): return f"{self.tipo_atencion} - {self.cupos} cupos"


class Ausencia(models.Model):
    personal_salud = models.ForeignKey(PersonalSalud, on_delete=models.PROTECT, related_name="ausencias")
    fecha_inicio = models.DateField(verbose_name="Fecha inicio")
    fecha_fin = models.DateField(verbose_name="Fecha Fin")
    tipo = models.SmallIntegerField(choices=TipoAusencia.choices)
    observaciones = models.TextField(null=True, blank=True)
    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ausencias_creadas', null=True, blank=True)
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True )
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ausencias_modificadas', null=True, blank=True )
    
    class Meta:
        verbose_name = "Ausencia"
        verbose_name_plural = "Ausencias"
        ordering = ["-fecha_inicio"]

        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["personal_salud"]),
            models.Index(fields=["fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return (
            f"{self.personal_salud} "
            f"{self.fecha_inicio} - {self.fecha_fin}"
        )


class Cupo_agenda(models.Model):
    personal_salud = models.ForeignKey(PersonalSalud, on_delete=models.PROTECT, related_name="cupos_agenda")
    configuracion_cupo = models.ForeignKey(Configuracion_cupo, on_delete=models.PROTECT,  related_name="cupos_agenda")
    tipo_atencion = models.ForeignKey(Tipo_atencion, on_delete=models.PROTECT, related_name="cupos_agenda")
    ausencia = models.ForeignKey(Ausencia, on_delete=models.PROTECT, related_name="cupos_afectados", null=True, blank=True )
    fecha = models.DateField(verbose_name="Fecha cupo")
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.SmallIntegerField(
        choices=EstadoCupoAgenda.choices,
        default=EstadoCupoAgenda.DISPONIBLE
    )
    fecha_creado = models.DateTimeField(verbose_name="Fecha Creado", auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cupos_agenda_creados', null=True, blank=True)
    fecha_modificado = models.DateTimeField(verbose_name="Fecha Editado", auto_now=True )
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cupos_agenda_modificados', null=True, blank=True )

    @property
    def especialidad(self):
        return self.personal_salud.especialidad
    


    class Meta:
        verbose_name = "Cupo agenda"
        verbose_name_plural = "Cupos agenda"
        ordering = ["fecha", "hora_inicio"]

        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha"]),
            models.Index(fields=["personal_salud", "fecha"]),
            models.Index(fields=["tipo_atencion", "fecha"]),
        ]

    def __str__(self):
        return (
            f"{self.personal_salud} "
            f"{self.tipo_atencion} "
            f"{self.fecha} "
            f"{self.hora_inicio}"
        )
