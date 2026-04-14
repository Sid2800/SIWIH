from django.db import models
from core.constants.choices_constants import EstadoRegistro, TipoPersonalNoClinico
from django.contrib.auth.models import User
from paciente.models import Paciente
from servicio.models import Especialidad, Unidad as ServicioUnidad
from clinico.models import Tipo_personal_salud


class Empleado(models.Model):
    dni = models.CharField(max_length=50, unique=True, db_index=True)
    primer_nombre = models.CharField(max_length=100)
    segundo_nombre = models.CharField(max_length=100, blank=True, null=True)
    primer_apellido = models.CharField(max_length=100)
    segundo_apellido = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    correo = models.EmailField(max_length=150, null=True, blank=True)
    estado = models.SmallIntegerField(
        choices=EstadoRegistro.choices,
        default=EstadoRegistro.ACTIVO
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='empleados_creados'
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='empleados_modificados'
    )
    paciente_ref = models.OneToOneField(
        Paciente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empleado"
    )
    usuario = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empleado"
    )

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido}"
    
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.usuario:
            self.usuario.first_name = self.primer_nombre or ""
            self.usuario.last_name = self.primer_apellido or ""
            self.usuario.save(update_fields=["first_name", "last_name"])

    @property
    def nombre_completo(self):
        return f"{self.primer_nombre} {self.primer_apellido}".strip()

    class Meta:
        indexes = [
            models.Index(fields=["primer_apellido"]),
            models.Index(fields=["dni"]),
        ]



class PersonalSalud(models.Model):
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.PROTECT,
        related_name="personal_salud"
    )
    puede_agendar_citas = models.BooleanField(
        default=False,
        db_index=True
    )
    tipo_personal_salud = models.ForeignKey(
        Tipo_personal_salud,
        on_delete=models.PROTECT,
        related_name="personal_salud"
    )
    especialidad = models.ForeignKey(
        Especialidad,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="personal_salud"
    )
    servicio_unidad = models.ForeignKey(
        ServicioUnidad,
        on_delete=models.PROTECT,
        related_name="personal_salud"
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='personal_salud_creados'
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='personal_salud_modificados'
    )

    def __str__(self):
        return str(self.empleado)

    @property
    def especialidad_nombre(self):
        return self.especialidad.nombre_especialidad if self.especialidad else ""

    class Meta:
        indexes = [
            models.Index(fields=["puede_agendar_citas"])
        ]



class PersonalNoClinico(models.Model):
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.PROTECT,
        related_name="personal_no_clinico"
    )
    tipo = models.PositiveSmallIntegerField(
        choices=TipoPersonalNoClinico.choices,
        default=TipoPersonalNoClinico.ADMINISTRATIVO
    )
    servicio_unidad = models.ForeignKey(
        ServicioUnidad,
        on_delete=models.PROTECT,
        related_name="personal_no_clinico"
    )
    fecha_creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='personal_no_clinico_creados'
    )
    fecha_modificado = models.DateTimeField(auto_now=True)
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='personal_no_clinico_modificados'
    )

    def __str__(self):
        return str(self.empleado)