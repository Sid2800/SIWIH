from django.db import models
from django.contrib.auth.models import User
from paciente.models import Paciente
from agenda_medica.models import Cupo_agenda
from core.constants.choices_constants import TipoMovimientoCita


class Cita(models.Model):
      observacion = models.TextField(null=True,blank=True)
      fecha_creado = models.DateTimeField(verbose_name="Fecha Creado",auto_now_add=True)
      creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="citas_creadas")
      fecha_modificado = models.DateTimeField(verbose_name="Fecha Modificado", auto_now=True)
      modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="citas_modificadas")
      paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT,related_name="citas")

      class Meta:
         verbose_name = "Cita"
         verbose_name_plural = "Citas"
         ordering = ["-fecha_creado"]
         indexes = [
               models.Index(fields=["paciente"]),
               models.Index(fields=["fecha_creado"]),
         ]

      def __str__(self):
         return f"Cita #{self.id} - {self.paciente}"


class Historial_cita(models.Model):
   tipo_movimiento = models.PositiveSmallIntegerField(choices=TipoMovimientoCita.choices)
   fecha_movimiento = models.DateTimeField(auto_now_add=True)
   usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="historial_citas")
   actual = models.BooleanField(default=True)
   cupo_agenda = models.ForeignKey(Cupo_agenda, on_delete=models.PROTECT, related_name="historial_citas")
   cita = models.ForeignKey(Cita,on_delete=models.CASCADE, related_name="historial")

   class Meta:
      verbose_name = "Historial de cita"
      verbose_name_plural = "Historial de citas"
      ordering = ["-fecha_movimiento"]
      indexes = [
            models.Index(fields=["cupo_agenda"]),
            models.Index(fields=["cita"]),
            models.Index(fields=["cita", "actual"]),
            models.Index(fields=["cita", "fecha_movimiento"]),
      ]
      constraints = [
         models.UniqueConstraint(
            fields=["cita"],
            condition=models.Q(actual=True),
            name="una_relacion_actual_por_cita"
         )
      ]

   def __str__(self):
      return f"Cita #{self.cita_id} - Cupo #{self.cupo_agenda_id}"