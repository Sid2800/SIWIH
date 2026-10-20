from django.db import models
from paciente.models  import Paciente
from core.constants.choices_constants import EstadoLaborParto, TipoMovimientoLaborParto, Sexo, EstadoRegistro
from servicio.models import Unidad_clinica
from django.contrib.auth.models import User


# Create your models here.
class Episodio_labor_parto(models.Model):
   paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="episodios_labor_parto", verbose_name="Paciente",)
   estado_actual = models.PositiveSmallIntegerField(choices=EstadoLaborParto.choices, null=True, blank=True, verbose_name="Estado actual",)
   movimiento_actual = models.ForeignKey(
      "Movimiento_labor_parto",
      on_delete=models.PROTECT,
      null=True,
      blank=True,
      related_name="episodios_actuales",
      verbose_name="Movimiento actual",
   )
   unidad_salida = models.ForeignKey(Unidad_clinica, on_delete=models.PROTECT, null=True, blank=True, related_name="episodios_labor_parto", verbose_name="Unidad de salida",)
   unidad_entrada = models.ForeignKey(Unidad_clinica,on_delete=models.PROTECT, null=True, blank=True,related_name="episodios_labor_parto_entrada", verbose_name="Unidad de entrada",)
   fecha_ingreso = models.DateTimeField(verbose_name="Fecha y hora de ingreso")
   estado = models.SmallIntegerField(verbose_name="Estado",
      choices=EstadoRegistro.choices,
      default=1,
   )
   alta = models.BooleanField(default=False, db_index=True, verbose_name="Alta de Labor y Parto",)
   fecha_alta = models.DateTimeField( null=True, blank=True, verbose_name="Fecha y hora de alta",)
   creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="episodios_labor_parto_creados", verbose_name="Creado por",)
   fecha_creado = models.DateTimeField(auto_now_add=True, verbose_name="Fecha creado",)
   modificado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="episodios_labor_parto_modificados", verbose_name="Modificado por",)
   fecha_modificado = models.DateTimeField(auto_now=True, verbose_name="Fecha modificado",)

   class Meta:
      verbose_name = "Episodio de Labor y Parto"
      verbose_name_plural = "Episodios de Labor y Parto"
      ordering = ["-fecha_ingreso"]

   def __str__(self):
      return f"Labor y Parto #{self.pk} - {self.paciente}"




class Bebe_labor_parto(models.Model):
   episodio = models.ForeignKey(
      Episodio_labor_parto,
      on_delete=models.PROTECT,
      related_name="bebes",
      verbose_name="Episodio de Labor y Parto",
   )

   
   sexo = models.CharField(
      choices=Sexo.choices,
      null=True,
      blank=True,
      max_length=1,
      verbose_name="Sexo",
   )

   orden = models.PositiveSmallIntegerField(
      verbose_name="Orden del bebé",
   )

   estado = models.SmallIntegerField(
      choices=EstadoRegistro.choices,
      default=EstadoRegistro.ACTIVO,
      verbose_name="Estado",
   )

   fecha_nacimiento = models.DateTimeField(
         null=True,
         blank=True,
         verbose_name="Fecha y hora de nacimiento",
      )

   observacion = models.CharField(max_length=255, null=True, blank=True, verbose_name="Observaciones",)



class Movimiento_labor_parto(models.Model):
   episodio = models.ForeignKey(Episodio_labor_parto, on_delete=models.PROTECT, related_name="movimientos", verbose_name="Episodio de Labor y Parto",)
   tipo = models.PositiveSmallIntegerField(choices=TipoMovimientoLaborParto.choices, verbose_name="Tipo de movimiento",)
   estado_anterior = models.PositiveSmallIntegerField(choices=EstadoLaborParto.choices,null=True, blank=True, verbose_name="Estado anterior",)
   estado_nuevo = models.PositiveSmallIntegerField(choices=EstadoLaborParto.choices, null=True, blank=True, verbose_name="Estado nuevo",)
   unidad_destino = models.ForeignKey(Unidad_clinica, on_delete=models.PROTECT,null=True, blank=True, related_name="movimientos_labor_parto",verbose_name="Unidad de destino",
   )

   fecha_movimiento = models.DateTimeField( verbose_name="Fecha y hora del movimiento")
   usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name="movimientos_labor_parto", verbose_name="Usuario",)
   observacion = models.CharField(max_length=255, null=True, blank=True, verbose_name="Observación",)

   estado = models.SmallIntegerField(
      choices=EstadoRegistro.choices,
      default=1,
      verbose_name="Estado",
   )

   class Meta:
      verbose_name = "Movimiento de Labor y Parto"
      verbose_name_plural = "Movimientos de Labor y Parto"
      ordering = ["fecha_movimiento"]

   def __str__(self):
      return f"Movimiento #{self.pk} - Episodio {self.episodio_id}"