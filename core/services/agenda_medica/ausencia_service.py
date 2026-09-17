from agenda_medica.models import Ausencia, Cupo_agenda

from django.core.exceptions import ValidationError
from core.constants.choices_constants import EstadoRegistro, TipoAusencia
from core.constants.domain_constants import EstadoTemporalPeriodo
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import log_error
from django.db.models import Q, FilteredRelation, Count
from datetime import date, timedelta
from django.db.models.functions import Coalesce, ExtractYear
from django.db import transaction
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService



class AusenciaService:

      AGENDA_COLOR_AUSENCIA = "rgba(107, 114, 128, 0.10)"
      AGENDA_BORDER_COLOR_AUSENCIA = "rgba(107, 114, 128, 0.75)"
      AGENDA_ICON_COLOR_AUSENCIA = "rgba(239, 68, 68, 1)"

      AGENDA_COLORES_TIPO_AUSENCIA = {

         TipoAusencia.VACACIONES: {
            "color": "rgba(59, 130, 246, 0.10)",
            "borderColor": "rgba(59, 130, 246, 0.75)",
         },

         TipoAusencia.INCAPACIDAD: {
            "color": "rgba(239, 68, 68, 0.10)",
            "borderColor": "rgba(239, 68, 68, 0.75)",
         },

         TipoAusencia.PERMISO: {
            "color": "rgba(245, 158, 11, 0.10)",
            "borderColor": "rgba(245, 158, 11, 0.75)",
         },

         TipoAusencia.CAPACITACION: {
            "color": "rgba(139, 92, 246, 0.10)",
            "borderColor": "rgba(139, 92, 246, 0.75)",
         },

         TipoAusencia.CONGRESO: {
            "color": "rgba(236, 72, 153, 0.10)",
            "borderColor": "rgba(236, 72, 153, 0.75)",
            
         },

         TipoAusencia.PROFILACTICA: {
            "color": "rgba(20, 184, 166, 0.10)",
            "borderColor": "rgba(20, 184, 166, 0.75)",
         },

         TipoAusencia.OTROS: {
            "color": "rgba(107, 114, 128, 0.10)",
            "borderColor": "rgba(107, 114, 128, 0.75)",
         },

      }



   
      @classmethod
      def _consultar_ausencias(cls, personal_salud, fecha_inicio, fecha_fin):
            return Ausencia.objects.filter(
                  personal_salud=personal_salud,
                  estado=EstadoRegistro.ACTIVO,
                  fecha_inicio__lte=fecha_fin,
                  fecha_fin__gte=fecha_inicio
            )


      @classmethod
      def _excluir_fechas_ausencias(cls, fechas, ausencias):
            fechas_validas = []

            for fecha in fechas:
                  tiene_ausencia = False

                  for ausencia in ausencias:
                        if ausencia.fecha_inicio <= fecha <= ausencia.fecha_fin:
                              tiene_ausencia = True
                              break

                  if not tiene_ausencia:
                        fechas_validas.append(fecha)

            return fechas_validas


      @classmethod
      def _crearAusencia(cls, ausencia, usuario):
         return Ausencia.objects.create(
            personal_salud_id=ausencia.personal_id,
            tipo=ausencia.tipo_id,
            fecha_inicio=ausencia.fecha_inicio,
            fecha_fin=ausencia.fecha_final,
            estado=EstadoRegistro.ACTIVO,
            creado_por=usuario,
            modificado_por=usuario,
         )


      @classmethod
      def _ligarCuposAusencia(cls, cupos, ausencia):
         for cupo in cupos:
            cupo.ausencia = ausencia

         if cupos:
            Cupo_agenda.objects.bulk_update(
                  cupos,
                  ["ausencia"]
            )


      @classmethod
      def _obtenerRangoCambioAusencia(cls, ausencia):

         rango = {
            "inicio": None,
            "fin": None,
         }

         # INICIO
         if ausencia.fecha_inicio < ausencia.ausencia_db.fecha_inicio:
            rango["inicio"] = {
                  "tipo": "CRECE",
                  "desde": ausencia.fecha_inicio,
                  "hasta": ausencia.ausencia_db.fecha_inicio - timedelta(days=1),
            }

         elif ausencia.fecha_inicio > ausencia.ausencia_db.fecha_inicio:
            rango["inicio"] = {
                  "tipo": "DECRECE",
                  "desde": ausencia.ausencia_db.fecha_inicio,
                  "hasta": ausencia.fecha_inicio - timedelta(days=1),
            }

         # FIN
         if ausencia.fecha_final < ausencia.ausencia_db.fecha_fin:
            rango["fin"] = {
                  "tipo": "DECRECE",
                  "desde": ausencia.fecha_final + timedelta(days=1),
                  "hasta": ausencia.ausencia_db.fecha_fin,
            }

         elif ausencia.fecha_final > ausencia.ausencia_db.fecha_fin:
            rango["fin"] = {
                  "tipo": "CRECE",
                  "desde": ausencia.ausencia_db.fecha_fin + timedelta(days=1),
                  "hasta": ausencia.fecha_final,
            }

         return rango


      @classmethod
      def _procesarCuposAfectados(cls, cupos, ausencia_db, usuario):
         """
         Procesa los cupos afectados por una ausencia.

         Requiere:
            cupos: Lista de Cupo_agenda con `historial_actual` precargado.
            ausencia_db: Ausencia a la que se asociarán los cupos.
            usuario: Usuario que realiza la operación.
         """
         from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
         from core.services.cita.cita_service import CitaService

         historiales_afectados = [
            cupo.historial_actual[0]
            for cupo in cupos
            if cupo.historial_actual
         ]

         # Ligar los cupos a la ausencia
         cls._ligarCuposAusencia(
            cupos,
            ausencia_db
         )

         # Las citas afectadas quedan sin cupo
         if historiales_afectados:
            CitaService.cancelarRelacionCupo(
                  historiales_afectados,
                  usuario
            )

         # Inactivar cupos
         ConfiguracionDiaService._inactivarCupos(
            cupos,
            usuario
         )

         return {
            "cupos": len(cupos),
            "citas": len(historiales_afectados)
         }




      @classmethod
      def anios_ausencias(cls):
         anios_inicio = Ausencia.objects.annotate(
            year=ExtractYear('fecha_inicio')
         ).values_list('year', flat=True)

         anios_fin = Ausencia.objects.annotate(
            year=ExtractYear('fecha_fin')
         ).values_list('year', flat=True)

         anios = set(anios_inicio.union(anios_fin))  

         anios.add(date.today().year)  

         return list(sorted(anios))


      @classmethod
      def obtener_fechas_validas(cls, fechas, personal_salud):

            if not fechas:
                  return []

            fecha_inicio = min(fechas)
            fecha_fin = max(fechas)

            ausencias = cls._consultar_ausencias(
                  personal_salud,
                  fecha_inicio,
                  fecha_fin
            )

            return cls._excluir_fechas_ausencias(
                  fechas,
                  ausencias
            )


      @classmethod
      def obtener_ausencia(cls, id):

         try:
            ausencia = (Ausencia.objects
                           .select_related(
                                 "personal_salud",
                           )
                           .filter(
                                 id=id,
                                 estado=EstadoRegistro.ACTIVO
                           )
                           .first()
                        )
            return ausencia  
         except Ausencia.DoesNotExist:
            return None



      
      @classmethod
      def obtener_ausencias(cls, criterios):
            ausencias = (
                  Ausencia.objects
                        .filter(
                              personal_salud_id=criterios.medico,
                              fecha_inicio__lte=criterios.fecha_fin,
                              fecha_fin__gte=criterios.fecha_inicio,
                        )
                        .exclude(
                              estado=EstadoRegistro.INACTIVO
                        ).annotate(
                              cantidad_cupos=Count("cupos_afectados")
                        )
                  )

            return ausencias

      @classmethod
      def transformar_ausencias(cls, ausencias):

            entries = []
            dias_con_entries = set()

            for ausencia in ausencias:

                  fecha = ausencia.fecha_inicio

                  while fecha <= ausencia.fecha_fin:
                        dias_con_entries.add(fecha.isoweekday())
                        fecha += timedelta(days=1)

                  entry = {
                        "id": ausencia.id,
                        "title": ausencia.get_tipo_display().upper(),
                        "subtitle": (
                              f"{ausencia.cantidad_cupos} CUPOS AFECTADOS"
                        ),
                        "start": str(ausencia.fecha_inicio),
                        "end": str(ausencia.fecha_fin),
                        "description": str(ausencia.observaciones or ""),
                        "icon": "circle",
                        "iconColor": cls.AGENDA_ICON_COLOR_AUSENCIA,
                        "color": cls.AGENDA_COLOR_AUSENCIA,
                        "borderColor": cls.AGENDA_BORDER_COLOR_AUSENCIA,
                        "data": {
                              "cupo_id": None,
                              "cita_id": None,
                              "ausencia_id": ausencia.id,
                              "tipo_movimiento": "AUSENCIA",

                        }
                  }

                  entries.append(entry)

            return entries, sorted(dias_con_entries)


      @classmethod
      def analizarImpactoAusencia(cls, ausencia):

         from core.services.agenda_medica.agenda_medica_service import AgendaMedicaService
         from agenda_medica.validators import AusenciaValidator
         from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService

         try:

            # Validaciones críticas
            AusenciaValidator.validarReglasCriticasAusencias(ausencia)

            resultado = {
                  "impacto":False,
                  "cambios":False,
                  "cupos": {
                     "eliminados": 0,
                     "creados": 0
                  },
                  "citas": {
                     "sin_cupo": 0,
                  },
                  "fecha_modificado": None   
            }

            if ausencia.ausencia_db:  # Si existe la instancia, estamos editando

               #retornamos resultado vacio si no hay cambios y los hay continueamos
               if (
                     ausencia.personal_id == ausencia.ausencia_db.personal_salud_id
                     and ausencia.tipo_id == ausencia.ausencia_db.tipo
                     and ausencia.fecha_inicio == ausencia.ausencia_db.fecha_inicio
                     and ausencia.fecha_final == ausencia.ausencia_db.fecha_fin
                     and ausencia.estado == ausencia.ausencia_db.estado
                     and ausencia.observaciones == ausencia.ausencia_db.observaciones
                  ):
                     resultado["cambios"] = False
                     return resultado
               else:
                     resultado["cambios"] = True


               # 1. DESACTIVACIÓN (SOLO FUTURO)
               if ausencia.estado == EstadoRegistro.INACTIVO:
                  # Se libera todo el rango original guardado en BD //
                  # / debemos ver si para ese mismo personal exite un perio laboral configurado
                  fechas_resultado = PeriodoLaboralService.obtener_configuraciones_para_rango(
                     ausencia.ausencia_db.personal_salud_id,
                     ausencia.ausencia_db.fecha_inicio,
                     ausencia.ausencia_db.fecha_fin
                  )

                  for item in fechas_resultado:
                     for configuracion in item["configuraciones"]:
                        resultado["cupos"]["creados"] += configuracion.cupos

                  resultado["impacto"] = len(fechas_resultado) > 0


                  return resultado


               # 2. EDICIÓN DE AUSENCIA ACTIVA
               else:

                  rango = cls._obtenerRangoCambioAusencia(ausencia)


                  for extremo in ["inicio", "fin"]:

                     tramo = rango[extremo]

                     if not tramo:
                        continue

                     desde = tramo["desde"]
                     hasta = tramo["hasta"]

                     if tramo["tipo"] == "DECRECE":
                        configuraciones = PeriodoLaboralService.obtener_configuraciones_para_rango(
                                                   ausencia.personal_id,
                                                   desde,
                                                   hasta
                                             )

                        for item in configuraciones:
                           for configuracion in item["configuraciones"]:
                              resultado["cupos"]["creados"] += configuracion.cupos

                     elif tramo["tipo"] == "CRECE":
                        cupos = AgendaMedicaService.obtenerCuposConHistorialActual(
                              [ausencia.personal_id],
                              desde,
                              hasta
                        )

                        resultado["cupos"]["eliminados"] += len(cupos)

                        resultado["citas"]["sin_cupo"] += sum(
                           len(cupo.historial_actual)
                           for cupo in cupos
                        )

                  resultado["impacto"] = (
                     resultado["cupos"]["creados"] > 0
                     or resultado["cupos"]["eliminados"] > 0
                  )

                  return resultado

            else:  # Si no existe, estamos agregando
                  cupos = AgendaMedicaService.obtenerCuposConHistorialActual(
                     [ausencia.personal_id],
                     ausencia.fecha_inicio,
                     ausencia.fecha_final
                  )
                  resultado["impacto"] = cupos.exists()
                  resultado["cupos"]["eliminados"] = cupos.count()

                  resultado["citas"]["sin_cupo"] = sum(
                     len(cupo.historial_actual)
                     for cupo in cupos
                  )

            return resultado

         except ValidationError:
            raise

         except Exception:
            log_error(
                  "[AusenciaService]: analizarImpactoAusencia",
                  LogApp.AGENDA
            )
            raise



      @classmethod
      def crearAusencia(cls, ausencia, usuario ):
         from core.services.agenda_medica.agenda_medica_service import AgendaMedicaService
         from agenda_medica.validators import AusenciaValidator




         resultado = {
               "success":False,
               "cupos": {
                  "eliminados": 0,
                  "agregados": 0
               },
               "citas": {
                  "sin_cupo": 0,
               },
         }

         try:
         
            # Validaciones críticas
            AusenciaValidator.validarReglasCriticasAusencias(ausencia)
            cupos = list(
                  AgendaMedicaService.obtenerCuposConHistorialActual(
                     [ausencia.personal_id],
                     ausencia.fecha_inicio,
                     ausencia.fecha_final
                  )
            )


            with transaction.atomic():


               # Crear ausencia
               ausencia_db = cls._crearAusencia(
                  ausencia,
                  usuario
               )


               cupoCitas = cls._procesarCuposAfectados(cupos, ausencia_db, usuario)

               
               resultado["cupos"]["eliminados"] = cupoCitas["cupos"]
               resultado["citas"]["sin_cupo"] = cupoCitas["citas"]
               resultado["success"] = True

               return resultado

         except ValidationError:
                     raise
         
         except Exception:
            log_error(
                  "[AusenciaService]: crearAusencia fallo",
                  LogApp.AGENDA
            )
            raise


      @classmethod
      def editarAusencia(cls, ausencia, usuario ):
         from core.services.agenda_medica.agenda_medica_service import AgendaMedicaService
         from agenda_medica.validators import AusenciaValidator
         from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
         from core.services.cita.cita_service import CitaService

         
         resultado = {
               "success":False,
               "cupos": {
                  "eliminados": 0,
                  "agregados": 0
               },
               "citas": {
                  "sin_cupo": 0,
               },
         }

         try:
            # Validaciones críticas
            AusenciaValidator.validarReglasCriticasAusencias(ausencia)
            AusenciaValidator.validarPersistenciaAusencia(ausencia.ausencia_db, ausencia.fecha_modificado)

            #inicio de la edicion 
            # 1. DESACTIVACIÓN (SOLO FUTURO)
            if ausencia.estado == EstadoRegistro.INACTIVO:
               # Se libera todo el rango original guardado en BD //
               # / debemos ver si para ese mismo personal exite un perio laboral configurado
               with transaction.atomic():
                  fechas_resultado = PeriodoLaboralService.obtener_configuraciones_para_rango(
                     ausencia.ausencia_db.personal_salud_id,
                     ausencia.ausencia_db.fecha_inicio,
                     ausencia.ausencia_db.fecha_fin
                  )


                  resultado["cupos"]["agregados"] = (
                        ConfiguracionDiaService._crear_cupos_agenda_por_fechas(
                           fechas_resultado,
                           usuario
                        )
                  )

                  #  actualizamos la ausencia
                  ausencia.ausencia_db.estado = ausencia.estado
                  ausencia.ausencia_db.observaciones = ausencia.observaciones
                  ausencia.ausencia_db.modificado_por = usuario

                  ausencia.ausencia_db.save()

                  resultado["success"] = True

                  return resultado
               
            # 2. EDICIÓN DE AUSENCIA ACTIVA
            else:

               rango = cls._obtenerRangoCambioAusencia(ausencia)

               with transaction.atomic():

                  for extremo in ["inicio", "fin"]:

                     tramo = rango[extremo]

                     if not tramo:
                           continue

                     desde = tramo["desde"]
                     hasta = tramo["hasta"]

                     if tramo["tipo"] == "DECRECE":
                           #crear nuevos cupos que previamnte borro al crearse
                           fechas_resultado = (
                              PeriodoLaboralService.obtener_configuraciones_para_rango(
                                 ausencia.personal_id,
                                 desde,
                                 hasta
                              )
                           )

                           resultado["cupos"]["agregados"] += (
                              ConfiguracionDiaService._crear_cupos_agenda_por_fechas(
                                 fechas_resultado,
                                 usuario
                              )
                           )

                     elif tramo["tipo"] == "CRECE":
                        # elimnar cupos  y editar historial citas 
                        cupos = list(
                           AgendaMedicaService.obtenerCuposConHistorialActual(
                                 [ausencia.personal_id],
                                 desde,
                                 hasta
                           )
                        )

                        # Aquí procesaremos los cupos
                        # y las citas afectadas
                        cupoCitas = cls._procesarCuposAfectados(
                           cupos,
                           ausencia.ausencia_db,
                           usuario
                        )

                        resultado["cupos"]["eliminados"] += cupoCitas["cupos"]
                        resultado["citas"]["sin_cupo"] += cupoCitas["citas"]

                           

                  # Actualizar la ausencia AL FINAL
                  ausencia.ausencia_db.fecha_inicio = ausencia.fecha_inicio
                  ausencia.ausencia_db.fecha_fin = ausencia.fecha_final
                  ausencia.ausencia_db.tipo = ausencia.tipo_id
                  ausencia.ausencia_db.observaciones = ausencia.observaciones
                  ausencia.ausencia_db.modificado_por = usuario

                  ausencia.ausencia_db.save()

                  resultado["success"] = True


                  return resultado


               

         except ValidationError:
                     raise
         
         except Exception:
            log_error(
                  "[AusenciaService]: editarAusencia fallo",
                  LogApp.AGENDA
            )
            raise