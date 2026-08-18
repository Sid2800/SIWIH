from django.core.exceptions import ValidationError
from core.constants.choices_constants import EstadoRegistro
from rrhh.models import PersonalSalud


def validar_personal_salud_activo(id_personal):

      personal = PersonalSalud.objects.filter(
         id=id_personal,
         estado=EstadoRegistro.ACTIVO
      ).first()

      if not personal:
         raise ValidationError(
               "El profesional de salud indicado no existe."
         )

      return personal