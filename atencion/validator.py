from core.validators.fecha_validator import validar_fecha
from core.utils.utilidades_fechas import convertir_fecha
from core.validators.paciente import validar_paciente
from servicio.validators import validar_area_atencion
from core.services.expediente_service import ExpedienteService
from expediente.validator import ExpedienteValidator
from django.core.exceptions import ValidationError
from atencion.models import Atencion
from core.constants.domain_constants import EXP_UBICA_ADMISION_ID


class AtencionValidator:


   @classmethod
   def validar_atencion(cls, id_atencion):
      """
      Verifica que la atención exista y retorna la instancia.
      """

      try:
         return Atencion.objects.get(id=id_atencion)

      except Atencion.DoesNotExist:
         raise ValidationError(
               "La atención seleccionada no existe."
         )



   @classmethod
   def validar_atencion_propietario(cls, atencion, paciente):
      """
      Verifica que el paciente de una atención existente no pueda modificarse.
      """

      if atencion.paciente_id != paciente.id:
         raise ValidationError(
               "No es permitido cambiar el paciente de una atención registrada."
         )

      return atencion


   @classmethod
   def validar(cls, atencion):

      fecha = convertir_fecha(atencion.fecha)
      atencion.fecha = validar_fecha(fecha)

      atencion.area_atencion = validar_area_atencion(atencion.area_atencion_id)
      atencion.paciente = validar_paciente(atencion.paciente_id)

      atencion.ubicacionExpediente = ExpedienteService.obtener_o_crear_ubicacion_area(atencion.area_atencion)

      # Solo para edicion de  atenciones
      if atencion.id:

         atencion.atencion = cls.validar_atencion(atencion.id)

         cls.validar_atencion_propietario(
            atencion.atencion,
            atencion.paciente
         )
         return atencion

   
      atencion.expediente = ExpedienteValidator.validar_disponible(
            atencion.paciente.expediente_numero
      )

      return atencion

