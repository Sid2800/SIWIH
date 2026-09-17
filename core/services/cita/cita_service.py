from cita.models import Historial_cita
from core.constants.choices_constants import TipoMovimientoCita


class CitaService:

   @classmethod
   def obtenerCitasActualesPorConfiguraciones(cls, ids_configuraciones):

      return Historial_cita.objects.filter(
         actual=True,
         tipo_movimiento__in=[
               TipoMovimientoCita.ASIGNACION,
               TipoMovimientoCita.REPROGRAMACION
         ],
         cupo_agenda__configuracion_cupo_id__in=ids_configuraciones
      )


   @classmethod
   def _crearHistorialCancelacionCupo(cls, historiales, usuario):
      nuevos_historiales = []

      for historial in historiales:

         nuevos_historiales.append(
               Historial_cita(
                  cita=historial.cita,
                  cupo_agenda=historial.cupo_agenda,
                  tipo_movimiento=TipoMovimientoCita.CANCELACION_CUPO,
                  actual=True,
                  usuario=usuario,
                  
               )
         )

      Historial_cita.objects.bulk_create(
         nuevos_historiales
      )



   @classmethod
   def cancelarRelacionCupo(cls, historiales, usuario):

      for historial in historiales:
         historial.actual = False

      Historial_cita.objects.bulk_update(
         historiales,
         ["actual"]
      )

      cls._crearHistorialCancelacionCupo(
         historiales,
         usuario
      )