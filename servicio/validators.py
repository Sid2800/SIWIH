from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from servicio.models import Area_atencion
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