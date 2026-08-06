from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from servicio.models import Area_atencion, Unidad_clinica
from core.constants.choices_constants import EstadoRegistro


def validar_area_atencion(id_area_atencion):
   """
   Verifica que el área de atención exista y se encuentre activa.
   """

   if not id_area_atencion:
      raise ValidationError("Debe especificarse un área de atención válida.")

   area_atencion = get_object_or_404(
      Area_atencion,
      id=id_area_atencion
   )

   if area_atencion.estado != EstadoRegistro.ACTIVO:
      raise ValidationError(
         "El área de atención seleccionada no se encuentra activa."
      )

   return area_atencion


def validar_instancia_area_atencion(area_atencion):
   """
   Verifica que la instancia del área de atención exista
   y se encuentre activa.
   """

   if not area_atencion:
      raise ValidationError(
         "Debe especificarse un área de atención válida."
      )

   if area_atencion.estado != EstadoRegistro.ACTIVO:
      raise ValidationError(
         "El área de atención seleccionada no se encuentra activa."
      )

   return area_atencion



def validar_unidad_clinica_activa(id_unidad_clinica):
   """
   Verifica que la unidad clínica exista y se encuentre activa.
   """

   if not id_unidad_clinica:
      raise ValidationError(
         "Debe especificarse una unidad clínica válida."
      )

   unidad_clinica = get_object_or_404(
      Unidad_clinica,
      id=id_unidad_clinica
   )

   if unidad_clinica.estado != EstadoRegistro.ACTIVO:
      raise ValidationError(
         "La unidad clínica seleccionada no se encuentra activa."
      )

   return unidad_clinica


def validar_instancia_unidad_clinica_activa(unidad_clinica):
   """
   Verifica que la instancia de unidad clínica exista y se encuentre activa.
   """

   if not unidad_clinica:
      raise ValidationError(
         "Debe indicar una unidad clínica."
      )

   if unidad_clinica.estado != EstadoRegistro.ACTIVO:
      raise ValidationError(
         "La unidad clínica seleccionada no se encuentra activa."
      )

   return unidad_clinica