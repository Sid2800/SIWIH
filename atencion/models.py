from django.db import models

from django.contrib.auth.models import User
from paciente.models import Paciente
from servicio.models import Area_atencion

class Atencion(models.Model):
   paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, verbose_name="Paciente",related_name='atenciones')
   area_atencion = models.ForeignKey(Area_atencion, on_delete=models.PROTECT, verbose_name="Area Atencion")
   fecha_atencion = models.DateTimeField()
   fecha_recepcion = models.DateTimeField(null=True, blank=True)

   creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='atencion_medica_creada')
   modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='atencion_medica_modificada')
   fecha_creado = models.DateTimeField(auto_now_add=True)
   fecha_modificado = models.DateTimeField(auto_now=True)
   observaciones = models.TextField(null=True, blank=True)

   class Meta:
      verbose_name = "Atención"
      verbose_name_plural = "Atenciones"
      ordering = ['-fecha_atencion']

   def __str__(self):
      return f"Atención - {self.paciente} - {self.fecha_atencion.strftime('%Y-%m-%d %H:%M')}"




class RecepcionAtencion(models.Model):
   fecha_recepcion = models.DateTimeField(auto_now_add=True)
   recibido_por = models.ForeignKey(
      User,
      on_delete=models.PROTECT,
      related_name='recepciones_atenciones_recibidas'  # más legible y tipo snake_case
   )
   fecha_modificado = models.DateTimeField(
      verbose_name="Fecha de modificación",
      auto_now=True
   )
   modificado_por = models.ForeignKey(
      User,
      on_delete=models.PROTECT,
      related_name='recepciones_atenciones_modificadas'
   )
   observaciones = models.TextField(
      verbose_name="Observaciones",
      null=True,
      blank=True
   )

   class Meta:
      verbose_name = "Recepción de atencion"
      verbose_name_plural = "Recepciones de atenciones"
      ordering = ["-fecha_recepcion"]  # Lo más reciente primero (opcional)

   def __str__(self):
      return f"Recepción #{self.id} - {self.fecha_recepcion.date()} por {self.recibido_por.username}"
   
   

class RecepcionAtencionDetalle(models.Model):
   recepcion = models.ForeignKey(
      RecepcionAtencion,
      on_delete=models.CASCADE,
      related_name='detalles'
   )

   atencion = models.ForeignKey(
      Atencion,
      on_delete=models.PROTECT,
      related_name='recepcion_detalles_atencion'  # nombre más claro
   )

   class Meta:
      verbose_name = "Detalle de recepción atencion"
      verbose_name_plural = "Detalles de recepción de atenciones"
      unique_together = ('recepcion', 'atencion')  # evita ingresos duplicados en la misma recepción

   def __str__(self):
      return f"Atencion #{self.atencion.id} en recepción #{self.recepcion.id}"
   
