from agenda_medica.models import Dia_quirurgico, Dia_laboral
from agenda_medica.validators import DiaQuirurgicoValidator
from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
from core.constants.choices_constants import EstadoRegistro
from django.db import transaction

class DiaQuirurgicoService:

   @classmethod
   def crear_dia_quirurgico(cls, data, usuario):

      dia_quirurgico_configurado = (
         DiaQuirurgicoValidator
         .validarDiaQuirurgico(data)
      )

      with transaction.atomic():

         periodo = dia_quirurgico_configurado.periodo_registro

         dia_laboral = ConfiguracionDiaService._crear_dia_laboral(
               periodo=periodo,
               dia_numero=dia_quirurgico_configurado.dia_numero,
               hora_inicio=periodo.jornada_laboral.hora_inicio,
               hora_fin=periodo.jornada_laboral.hora_fin,
               usuario=usuario
         )

         Dia_quirurgico.objects.create(
               dia_laboral=dia_laboral,
               estado=EstadoRegistro.ACTIVO,
               creado_por=usuario,
               modificado_por=usuario
         )

      return True


   @classmethod
   def quitar_dia_quirurgico(cls, data, usuario):

      dia_laboral = (
         DiaQuirurgicoValidator
         .validarQuitarDiaQuirurgico(data)
      )

      with transaction.atomic():
         dia_laboral.delete()

      return True