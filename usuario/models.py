from django.db import models
from django.contrib.auth.models import User

class Unidad(models.Model):
    nombre_unidad = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre_unidad

ROLES = (
    ('admin', 'Administrador'),
    ('digitador', 'Digitador'),
    ('auditor', 'Auditor'),
    ('visitante', 'Visitante'),
    ('exp_admin', 'Admin Expedientes'),
    ('exp_solicitante', 'Solicitante Expedientes'),
)

class PerfilUnidad(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE)
    rol = models.CharField(max_length=20, choices=ROLES)

    class Meta:
        unique_together = ('usuario', 'unidad')

    def __str__(self):
        return f"{self.usuario.username} - {self.unidad.nombre_unidad} ({self.get_rol_display()})"
