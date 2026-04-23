from django.db import models
from django.contrib.auth.models import User
from core.constants.choices_constants import AlcanceUsuario, RolUsuario
from servicio.models import Unidad as ServicioUnidad 

class Unidad(models.Model):
    nombre_unidad = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre_unidad


class PerfilUnidad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    servicio_unidad = models.ForeignKey(ServicioUnidad , null=True, blank=True, on_delete=models.PROTECT)
    alcance = models.PositiveSmallIntegerField(
        choices=AlcanceUsuario.choices,
        default=AlcanceUsuario.UNIDAD
    )
    rol = models.CharField(max_length=20, choices=RolUsuario.choices)


    class Meta: # OJOOOO correjir al migrar
        unique_together = ('usuario', 'servicio_unidad', 'alcance')

    def __str__(self):
        return f"{self.usuario.username} - { self.servicio_unidad.nombre_unidad if self.servicio_unidad else "INSTITUCIONAL"} ({self.get_rol_display()})"
