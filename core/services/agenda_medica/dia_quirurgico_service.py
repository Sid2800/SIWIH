from agenda_medica.models import Dia_quirurgico, Dia_laboral
from agenda_medica.validators import DiaQuirurgicoValidator
from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from core.constants.choices_constants import EstadoRegistro
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import log_error
from core.utils.utilidades_fechas import obtener_fechas_por_dia_semana
from django.db import transaction
from django.core.exceptions import ValidationError

class DiaQuirurgicoService:

   AGENDA_COLOR_DIA_QUIRURGICO = "rgba(139, 92, 246, 0.10)"
   AGENDA_BORDER_COLOR_DIA_QUIRURGICO = "rgba(139, 92, 246, 0.75)"
   AGENDA_ICON_COLOR_DIA_QUIRURGICO = "rgba(139, 92, 246, 1)"


   @classmethod
   def _crear_registro_dia_quirurgico(cls, dia_laboral, usuario):
      return Dia_quirurgico.objects.create(
         dia_laboral=dia_laboral,
         estado=EstadoRegistro.ACTIVO,
         creado_por=usuario,
         modificado_por=usuario
      )


   @classmethod
   def crear_dia_quirurgico(cls, data, usuario):
      try:
         with transaction.atomic():
               dia_quirurgico_configurado = DiaQuirurgicoValidator.validarDiaQuirurgico(data)
               periodo = dia_quirurgico_configurado.periodo_registro
               dia_laboral = ConfiguracionDiaService._crear_dia_laboral(
                  periodo=periodo,
                  dia_numero=dia_quirurgico_configurado.dia_numero,
                  hora_inicio=periodo.jornada_laboral.hora_inicio,
                  hora_fin=periodo.jornada_laboral.hora_fin,
                  usuario=usuario
               )
               DiaQuirurgicoService._crear_registro_dia_quirurgico(
                  dia_laboral,
                  usuario
               )
         return True
      except ValidationError:
         raise
      except Exception:
         log_error("[DiaQuirurgicoService]: crear_dia_quirurgico", LogApp.AGENDA)
         raise


   @classmethod
   def quitar_dia_quirurgico(cls, data, usuario):
      try:
         with transaction.atomic():
               dia_qx = DiaQuirurgicoValidator.validarQuitarDiaQuirurgico(data)
               dia_qx.delete()
         return True
      except ValidationError:
         raise
      except Exception:
         log_error("[DiaQuirurgicoService]: quitar_dia_quirurgico", LogApp.AGENDA)
         raise


   @classmethod
   def obtener_dias_quirurgicos(cls, criterios):
      dias_quirurgicos = (
         Dia_quirurgico.objects
               .filter(
                  dia_laboral__periodo_laboral__personal_salud_id=criterios.medico,
                  dia_laboral__periodo_laboral__fecha_inicio__lte=criterios.fecha_fin,
                  dia_laboral__periodo_laboral__fecha_fin__gte=criterios.fecha_inicio,
                  dia_laboral__periodo_laboral__estado=EstadoRegistro.ACTIVO,
                  dia_laboral__estado=EstadoRegistro.ACTIVO,
               )
               .exclude(
                  estado=EstadoRegistro.INACTIVO
               )
               .select_related(
                  "dia_laboral",
                  "dia_laboral__periodo_laboral",
                  "dia_laboral__periodo_laboral__jornada_laboral"
               )
      )

      return dias_quirurgicos

   @classmethod
   def transformar_dias_quirurgicos(cls, dias_quirurgicos):
         from datetime import datetime
         entries = []
         dias_con_entries = set()

         for dia in dias_quirurgicos:
               periodo = dia.dia_laboral.periodo_laboral

               fechas_dia = PeriodoLaboralService.obtener_fechas_validas_dia_laboral(periodo, dia.dia_laboral.dia_semana)

               if not fechas_dia:
                  continue

               dias_con_entries.add(dia.dia_laboral.dia_semana)

               for fecha in fechas_dia:

                     fecha_inicio = datetime.combine(
                        fecha,
                        periodo.jornada_laboral.hora_inicio
                     )

                     fecha_fin = datetime.combine(
                        fecha,
                        periodo.jornada_laboral.hora_fin
                     )

                     entry = {
                           "id": dia.id,
                           "title": "QUIRÚRGICO",
                           "subtitle": (
                                 f"{periodo.jornada_laboral.hora_inicio.strftime('%H:%M')} - "
                                 f"{periodo.jornada_laboral.hora_fin.strftime('%H:%M')}"
                           ),
                           "start": fecha_inicio.isoformat(),
                           "end": fecha_fin.isoformat(),
                           "description": "",
                           "icon": "circle",
                           "iconColor": cls.AGENDA_ICON_COLOR_DIA_QUIRURGICO,
                           "color": cls.AGENDA_COLOR_DIA_QUIRURGICO,
                           "borderColor": cls.AGENDA_BORDER_COLOR_DIA_QUIRURGICO,
                           "data": {
                                 "cupo_id": None,
                                 "cita_id": None,
                                 "ausencia_id": None,
                                 "tipo_atencion_id": None,
                                 "tipo_movimiento": "DIA_QUIRURGICO",

                           }
                     }

                     entries.append(entry)

         return entries, sorted(dias_con_entries)

