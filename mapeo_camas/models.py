from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AsignacionCamaPaciente(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        CERRADA = "CERRADA", "Cerrada"

    cama = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="asignaciones_cama",
        verbose_name="Cama",
    )
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        related_name="asignaciones_cama",
        verbose_name="Paciente",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de inicio")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de fin")
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ACTIVA,
        db_index=True,
        verbose_name="Estado",
    )
    usuario_asignacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_cama_creadas",
        verbose_name="Usuario de asignacion",
    )
    usuario_cierre = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asignaciones_cama_cerradas",
        verbose_name="Usuario de cierre",
    )

    class Meta:
        db_table = "mapeo_camas_asignacion_cama_paciente"
        verbose_name = "Asignacion de cama por paciente"
        verbose_name_plural = "Asignaciones de cama por paciente"
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(fields=["cama", "estado"], name="idx_asig_cama_estado"),
            models.Index(fields=["paciente", "estado"], name="idx_asig_paciente_estado"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(fecha_fin__isnull=True)
                | models.Q(fecha_fin__gte=models.F("fecha_inicio")),
                name="chk_asig_fechas_validas",
            ),
        ]

    def clean(self):
        errors = {}

        if self.estado == self.Estado.ACTIVA:
            if self.fecha_fin is not None:
                errors["fecha_fin"] = "Una asignacion activa no debe tener fecha de fin."
            if self.usuario_cierre is not None:
                errors["usuario_cierre"] = "Una asignacion activa no debe tener usuario de cierre."

            cama_ocupada = AsignacionCamaPaciente.objects.filter(
                cama=self.cama,
                estado=self.Estado.ACTIVA,
            ).exclude(pk=self.pk)
            if cama_ocupada.exists():
                errors["cama"] = "La cama ya tiene una asignacion activa."

            paciente_con_cama = AsignacionCamaPaciente.objects.filter(
                paciente=self.paciente,
                estado=self.Estado.ACTIVA,
            ).exclude(pk=self.pk)
            if paciente_con_cama.exists():
                errors["paciente"] = "El paciente ya tiene una asignacion activa."

        if self.estado == self.Estado.CERRADA:
            if self.fecha_fin is None:
                errors["fecha_fin"] = "Debe indicar fecha de fin al cerrar una asignacion."
            if self.usuario_cierre is None:
                errors["usuario_cierre"] = "Debe indicar el usuario que cierra la asignacion."

        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            errors["fecha_fin"] = "La fecha de fin no puede ser menor a la fecha de inicio."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Cama {self.cama_id} - Paciente {self.paciente_id} ({self.estado})"


class HistorialEstadoCama(models.Model):
    # Estados físicos de la cama (independientes del ciclo de asignacion)
    class Estado(models.TextChoices):
        LIBRE             = "LIBRE",             "Libre"
        OCUPADA           = "OCUPADA",           "Ocupada"
        PREALTA           = "PREALTA",           "Prealta"
        ALTA              = "ALTA",              "Alta"
        MANTENIMIENTO     = "MANTENIMIENTO",     "Mantenimiento / Fuera de servicio"
        CONSULTA_EXTERNA  = "CONSULTA_EXTERNA",  "Consulta externa"

    cama = models.ForeignKey(
        "servicio.Cama",
        on_delete=models.PROTECT,
        related_name="historial_estado",
        verbose_name="Cama",
    )
    estado_anterior = models.CharField(
        max_length=20,
        choices=Estado.choices,
        null=True,
        blank=True,
        verbose_name="Estado anterior",
    )
    estado_nuevo = models.CharField(
        max_length=20,
        choices=Estado.choices,
        verbose_name="Estado nuevo",
    )
    paciente = models.ForeignKey(
        "paciente.Paciente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="historial_camas",
        verbose_name="Paciente",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="historial_camas_usuario",
        verbose_name="Usuario",
    )
    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y hora",
    )
    observacion = models.CharField(
        max_length=255,
        default="Ingreso (sync)",
        blank=True,
        verbose_name="Observacion",
    )

    class Meta:
        db_table = "mapeo_camas_historial_estado_cama"
        verbose_name = "Historial de estado de cama"
        verbose_name_plural = "Historial de estados de camas"
        ordering = ["-fecha_hora"]
        indexes = [
            models.Index(fields=["cama", "fecha_hora"], name="idx_hist_cama_fecha"),
        ]

    def __str__(self):
        hora_local = timezone.localtime(self.fecha_hora)
        return (
            f"Cama {self.cama_id} | {self.estado_anterior} → {self.estado_nuevo}"
            f" | {hora_local:%d/%m/%Y %H:%M}"
        )
