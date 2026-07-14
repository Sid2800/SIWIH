
from  expediente.models import Expediente
from django.core.exceptions import ValidationError
from core.constants.domain_constants import EXP_UBICA_ADMISION_ID, PRESTAMO_ESTADO_ACTIVO_ID, APARTADO_ESTADO_ACTIVO_ID

class ExpedienteValidator:

      @classmethod
      def obtener_expediente(cls, numero_expediente):
            """
            Obtiene el expediente a partir de su número.
            """
            return Expediente.objects.get(numero=numero_expediente)


      @classmethod
      def validar_no_prestado(cls, numero_expediente):
            """
            Verifica que el expediente no se encuentre
            prestado ni apartado.
            """
            expediente = cls.obtener_expediente(numero_expediente)

            prestamo = getattr(expediente, "prestamo_info", None)

            if prestamo:
                  if prestamo.estado_id == PRESTAMO_ESTADO_ACTIVO_ID:
                        raise ValidationError(
                              "El expediente fue prestado."
                        )

                  if prestamo.estado_id == APARTADO_ESTADO_ACTIVO_ID:
                        raise ValidationError(
                              "El expediente está apartado."
                        )

            return expediente


      @classmethod
      def validar_en_admision(cls, numero_expediente):
            """
            Verifica que el expediente se encuentre
            físicamente en Admisión.
            """
            expediente = cls.obtener_expediente(numero_expediente)

            if expediente.ubicacion.id != EXP_UBICA_ADMISION_ID:
                  raise ValidationError(
                        "El expediente no se encuentra disponible en Admisión."
                  )

            return expediente

      @classmethod
      def validar_disponible(cls, numero_expediente):
            """
            Valida que el expediente esté disponible
            para ser utilizado por otro proceso.
            """
            expediente = cls.validar_no_prestado(numero_expediente)
            cls.validar_en_admision(numero_expediente)
            return expediente



