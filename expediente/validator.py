
from  expediente.models import Expediente
from django.core.exceptions import ValidationError
from core.constants.domain_constants import EXP_UBICA_ADMISION_ID, PRESTAMO_ESTADO_ACTIVO_ID, APARTADO_ESTADO_ACTIVO_ID

class ExpedienteValidator:

   @staticmethod
   def validar_disponible(numero_expediente):
      """
      Verifica que el expediente se encuentre disponible
      para ser utilizado por otro proceso.
      """

      expediente = Expediente.objects.get(numero=numero_expediente)

      prestamo = getattr(expediente, "prestamo_info", None)

      if prestamo:
         if prestamo.estado_id == PRESTAMO_ESTADO_ACTIVO_ID:
               raise ValidationError(
               "El expediente fue prestado")
         elif prestamo.estado_id == APARTADO_ESTADO_ACTIVO_ID:
               raise ValidationError(
               "El expediente esta apartado")


      if expediente.ubicacion.id != EXP_UBICA_ADMISION_ID:
         raise ValidationError(
               "El expediente no se encuentra disponible en Admisión."
         )

      return expediente