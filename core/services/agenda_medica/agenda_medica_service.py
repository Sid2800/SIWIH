from agenda_medica.models import Cupo_agenda, Ausencia
from agenda_medica.validators import AusenciaValidator
from cita.models import Historial_cita
from core.constants.choices_constants import EstadoCupoAgenda, TipoMovimientoCita, EstadoRegistro
from core.utils.utilidades_fechas import filtro_rango_fecha
from django.db.models import Prefetch

from datetime import timedelta

class AgendaMedicaService:

      AGENDA_COLORES_TIPO_ATENCION = {
            1: {
                  "color": "rgba(59, 130, 246, 0.10)",
                  "borderColor": "rgba(59, 130, 246, 0.75)",
            },  # NORMAL/SUBSIGUIENTE

            2: {
                  "color": "rgba(168, 85, 247, 0.10)",
                  "borderColor": "rgba(168, 85, 247, 0.75)",
            },  # SOBRE CUPO

            3: {
                  "color": "rgba(245, 158, 11, 0.10)",
                  "borderColor": "rgba(245, 158, 11, 0.75)",
            },  # VALORACIÓN PRE-OPERATORIA

            4: {
                  "color": "rgba(34, 197, 94, 0.10)",
                  "borderColor": "rgba(34, 197, 94, 0.75)",
            },  # ALTA MÉDICA

            5: {
                  "color": "rgba(20, 184, 166, 0.10)",
                  "borderColor": "rgba(20, 184, 166, 0.75)",
            },  # REFERENCIA

            6: {
                  "color": "rgba(14, 165, 233, 0.10)",
                  "borderColor": "rgba(14, 165, 233, 0.75)",
            },  # SAI

            7: {
                  "color": "rgba(14, 165, 233, 0.10)",
                  "borderColor": "rgba(14, 165, 233, 0.75)",
            },  # REVISIÓN RECIÉN NACIDO

            8: {
                  "color": "rgba(99, 102, 241, 0.10)",
                  "borderColor": "rgba(99, 102, 241, 0.75)",
            },  # ULTRASONIDO

            9: {
                  "color": "rgba(20, 184, 166, 0.10)",
                  "borderColor": "rgba(20, 184, 166, 0.75)",
            },  # PATOLOGÍA CERVICAL

            10: {
                  "color": "rgba(249, 115, 22, 0.10)",
                  "borderColor": "rgba(249, 115, 22, 0.75)",
            },  # LISTA DE ESPERA QUIRÚRGICA

            11: {
                  "color": "rgba(132, 204, 22, 0.10)",
                  "borderColor": "rgba(132, 204, 22, 0.75)",
            },  # ADOLECENTE

            12: {
                  "color": "rgba(244, 63, 94, 0.10)",
                  "borderColor": "rgba(244, 63, 94, 0.75)",
            },  # ALTA DE EMERGENCIA
      }
      

      AGENDA_COLOR_LIBRE = "rgba(34, 197, 94, 1)"
      
      AGENDA_COLORES_MOVIMIENTO = {
            TipoMovimientoCita.ASIGNACION: "rgba(59, 130, 246, 1)",          # Programada
            TipoMovimientoCita.REPROGRAMACION:"rgba(245, 158, 11, 1)",     # Reprogramada
      }

      @classmethod
      def obtener_cupos(cls, criterios):

            historiales = (
                  Historial_cita.objects
                  .filter(
                  actual=True,
                  tipo_movimiento__in=[
                        TipoMovimientoCita.ASIGNACION,
                        TipoMovimientoCita.REPROGRAMACION,
                  ],
                  )
                  .select_related(
                  "cita",
                  "cita__paciente",
                  "usuario",
                  )
            )

            cupos = (
                  Cupo_agenda.objects
                  .filter(
                  personal_salud_id=criterios.medico,
                  fecha__range=(
                        criterios.fecha_inicio,
                        criterios.fecha_fin
                  ),
                  estado__in=[
                        EstadoCupoAgenda.DISPONIBLE,
                        EstadoCupoAgenda.ASIGNADO,
                        EstadoCupoAgenda.BLOQUEADO,
                  ]
                  )
                  .select_related(
                  "configuracion_cupo",
                  "tipo_atencion",
                  "ausencia",
                  )
                  .prefetch_related(
                  Prefetch(
                        "historial_citas",
                        queryset=historiales,
                        to_attr="historial_actual",
                  )
                  )
                  .order_by(
                  "fecha",
                  "hora_inicio",
                  )
            )



            return cupos


      @classmethod
      def transformar_cupos(cls, cupos):
            entries = []
            dias_con_entries = set()

            for cupo in cupos:
                  dias_con_entries.add(cupo.fecha.isoweekday())
                  colores = cls.AGENDA_COLORES_TIPO_ATENCION.get(cupo.tipo_atencion_id,
                                    {
                                          "color": "rgba(0, 0, 0, 0.05)",
                                          "borderColor": "rgba(0, 0, 0, 0.5)",
                                    }
                              )


                  if cupo.ausencia:
                        continue

                  if cupo.historial_actual:

                        historial = cupo.historial_actual[0]
                        cita = historial.cita

                        entry = {
                        "id": cupo.id,
                        "title": str(cita.paciente),
                        "subtitle": str(cupo.tipo_atencion),
                        "start": f"{cupo.fecha}T{cupo.hora_inicio}",
                        "end": f"{cupo.fecha}T{cupo.hora_fin}",
                        "agrupation": str(cupo.tipo_atencion),
                        "color": colores["color"],
                        "borderColor": colores["borderColor"],
                        "iconColor": cls.AGENDA_COLORES_MOVIMIENTO.get(
                              historial.tipo_movimiento,
                              "rgba(0, 0, 0, 1)"
                        ),
                        "icon": "circle",
                        "data": {
                              "cupo_id": cupo.id,
                              "cita_id": cita.id,
                              "ausencia_id": None,
                              "tipo_movimiento": historial.get_tipo_movimiento_display(),
                        }
                        }

                  else:

                        entry = {
                        "id": cupo.id,
                        "title": "Cupo libre",
                        "subtitle": str(cupo.tipo_atencion),
                        "start": f"{cupo.fecha}T{cupo.hora_inicio}",
                        "end": f"{cupo.fecha}T{cupo.hora_fin}",
                        "agrupation": str(cupo.tipo_atencion),
                        "color": colores["color"],
                        "borderColor": colores["borderColor"],
                        "iconColor": cls.AGENDA_COLOR_LIBRE,
                        "icon": "circle",
                        "data": {
                              "cupo_id": cupo.id,
                              "cita_id": None,
                              "ausencia_id": None,
                              "tipo_movimiento": "LIBRE",
                        }
                        }

                  entries.append(entry)

            return entries, sorted(dias_con_entries)


      @classmethod
      def obtenerCuposConHistorialActual(cls, personales_ids, fecha_inicio, fecha_final):


            return (
                  Cupo_agenda.objects
                  .filter(
                        personal_salud_id__in=personales_ids,
                        **filtro_rango_fecha("fecha", fecha_inicio, fecha_final),
                        estado__in=[
                        EstadoCupoAgenda.DISPONIBLE,
                        EstadoCupoAgenda.ASIGNADO,
                        ]
                  )
                  .prefetch_related(
                        Prefetch(
                        "historial_citas",
                        queryset=Historial_cita.objects.filter(
                              actual=True,
                              tipo_movimiento__in=[
                                    TipoMovimientoCita.ASIGNACION,
                                    TipoMovimientoCita.REPROGRAMACION,
                              ]
                        ),
                        to_attr="historial_actual"
                        )
                  )
                  .order_by(
                        "fecha",
                        "-hora_inicio"
                  )
            )