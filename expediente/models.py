from django.db import models, transaction
from django.core.exceptions import ValidationError
from paciente.models import Paciente
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator

from datetime import datetime

# Modelo de Ubicación
class Localizacion(models.Model):
    descripcion_localizacion = models.CharField(max_length=100, unique=True, verbose_name="Localizacion")
    estado = models.BooleanField(default=True) 

    class Meta:
        verbose_name = "Localizacion"
        verbose_name_plural = "Localizaciones"
        ordering = ["descripcion_localizacion"]

    def __str__(self):
        return self.descripcion_localizacion



# Modelo de Expediente
class Expediente(models.Model):
    numero = models.PositiveIntegerField(
        verbose_name="Número de expediente",
        help_text="Número de expediente único (máximo 199999)",
        validators=[MaxValueValidator(199999)],
        unique=True
    )
    localizacion = models.ForeignKey(
        Localizacion,
        on_delete=models.PROTECT,
        default=1
    )
    estado = models.IntegerField(
        verbose_name="Estado",
        choices=[(1, "Asignado"), (2, "Libre")],
        default=2
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='expedientes_creados')
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='expedientes_modificados')

    class Meta:
        verbose_name = "Expediente"
        verbose_name_plural = "Expedientes"
        ordering = ["numero"]

    def __str__(self):
        return str(self.numero)  




# Modelo de Paciente Asignación
class PacienteAsignacion(models.Model):
    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.PROTECT
    )
    expediente = models.ForeignKey(
        Expediente,
        on_delete=models.PROTECT,
        related_name="expedienteAsignados"
    )
    estado = models.CharField(max_length=10, choices=[("1", "Actual"), ("0", "Historico")], default="1")
    fecha_asignacion = models.DateField(auto_now_add=True)
    fecha_liberacion = models.DateField(null=True, blank=True)

    def clean(self):
        super().clean()
        
        # Si el estado es 'Actual', valida que no haya otro registro 'Actual' para el mismo paciente
        if self.estado == '1':
            # Busca otras asignaciones 'Actuales' para el mismo paciente
            qs = PacienteAsignacion.objects.filter(
                paciente=self.paciente,
                estado='1'
            )
            
            # Si estamos editando un objeto existente, lo excluimos de la búsqueda
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            
            # Si se encuentra algún otro registro, lanza un error
            if qs.exists():
                raise ValidationError({
                    'estado': 'Este paciente ya tiene una asignación "Actual". Solo puede haber una asignación actual por paciente.'
                })

    def __str__(self):
        return f"{self.paciente.primer_nombre} f{self.paciente.primer_apellido} - Expediente {self.expediente.numero}"

    

