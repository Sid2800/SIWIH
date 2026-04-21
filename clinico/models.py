from django.db import models

# Create your models here.

class CIE10(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    descripcion = models.CharField(max_length=300)

    class Meta:
        verbose_name = "CIE10"
        verbose_name_plural = "CIE10"
        ordering = ['descripcion']

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class Diagnostico(models.Model):
    nombre_diagnostico = models.CharField(max_length=200, unique=True)
    cie10 = models.ForeignKey(CIE10, null=True, blank=True, on_delete=models.SET_NULL)
    estado = models.BooleanField(default=1, verbose_name="Estado")
    
    class Meta:
        verbose_name = "Diagnostico"
        verbose_name_plural = "Diagnosticos"
        ordering = ['nombre_diagnostico']

    def __str__(self):
        return self.nombre_diagnostico


class Tipo_personal_salud(models.Model):
    nombre_tipo_personal = models.CharField(max_length=100, unique=True)
    estado = models.BooleanField(default=1, verbose_name="Estado")
    
    class Meta:
        verbose_name = "Tipo de personal de salud"
        verbose_name_plural = "Tipos de personal de salud"
        ordering = ['nombre_tipo_personal']

    def __str__(self):
        return self.nombre_tipo_personal
    


class Especialidad(models.Model):
    nombre_especialidad = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la especialidad")
    nombre_corto_especialidad = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Nombre corto")
    estado = models.BooleanField(default=True, verbose_name="Activo" )

    def __str__(self):
        return self.nombre_especialidad

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"
        ordering = ['nombre_especialidad']
    


class Condicion_paciente(models.Model):
    nombre_condicion_paciente = models.CharField(max_length=100, unique=True)
    estado = models.BooleanField(default=1, verbose_name="Estado")
    
    class Meta:
        verbose_name = "Condicion del paciente"
        verbose_name_plural = "Condiciones del paciente"
        ordering = ['nombre_condicion_paciente']

    def __str__(self):
        return self.nombre_condicion_paciente