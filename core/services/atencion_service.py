from atencion.models import Atencion
from servicio.models import Servicio
from expediente.models import PacienteAsignacion
from core.services.servicio_service import ServicioService
from core.services.expediente_service import ExpedienteService
from django.db import transaction
from django.db.models import Func, F, Q, OuterRef, Subquery, DateField, Value, Count
from django.db.models.functions import Concat
from django.utils import timezone as django_timezone
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
import pytz
from django.utils import timezone
from datetime import timedelta
class AtencionService:

      @staticmethod
      def procesar_atencion(atencion):

            def actualizar_datos_si_necesario(atencionRegistro):
                  cambios = False
                  if atencionRegistro.fecha_atencion != atencion.fecha:
                        atencionRegistro.fecha_atencion = atencion.fecha
                        cambios = True

                  especialidad_id_nuevo = int(atencion.especialidad_id)
                  if atencionRegistro.especialidad.id != especialidad_id_nuevo:
                        nueva_especialidad = ServicioService.obtener_especialidad_id(especialidad_id_nuevo)
                        if nueva_especialidad:
                              atencionRegistro.especialidad = nueva_especialidad
                              cambios = True

                  if atencionRegistro.observaciones != atencion.observaciones:
                        atencionRegistro.observaciones = atencion.observaciones
                        cambios = True

                  if cambios:
                        atencionRegistro.save()
                        return True
                  return False

            if atencion.id:
                  try:
                        atencionRegistro = Atencion.objects.get(id=atencion.id)
                        return actualizar_datos_si_necesario(atencionRegistro)
                  except Atencion.DoesNotExist:
                        log_warning(
                              f"Atención no encontrada id={atencion.id}",
                              app=LogApp.ATENCION
                        )
                        return False

            elif atencion.fecha and atencion.paciente_id and atencion.especialidad_id:
                  try:
                        especialidad_id = int(atencion.especialidad_id)
                        with transaction.atomic():
                              atencionObjeto = Atencion.objects.create(
                                    fecha_atencion=atencion.fecha,
                                    especialidad_id=especialidad_id,
                                    observaciones=atencion.observaciones,
                                    paciente_id=atencion.paciente_id,
                                    creado_por_id=atencion.usuario_id,
                                    modificado_por_id=atencion.usuario_id
                              )

                        # Determinar ubicación del expediente
                        mapa_ubicaciones = {
                              1: 4,  # Emergencia general
                              2: 5,  # Emergencia obstétrica
                              3: 6   # Consulta externa
                        }

                        ubicacion = mapa_ubicaciones.get(especialidad_id, 0)
                        if ubicacion:
                              ExpedienteService.cambiar_ubicacion(
                                    atencionObjeto.paciente.id,
                                    ubicacion,
                                    atencion.usuario_id
                              )
                        return True

                  except Exception:
                        log_error(
                              f"Error actualizando atención id={atencion.id}",
                              app=LogApp.ATENCION
                              )
                        return False

            return False
            

      @staticmethod
      def obtener_atencion(id_atencion):
            """
            Retorna la instancia de Atencion con sus relaciones cargadas, o None si no existe.
            """
            try:
                  # Relaciones directas (JOIN en SQL)
                  qs = Atencion.objects.select_related(
                  'especialidad',
                  'especialidad__servicio',
                  'creado_por',
                  'modificado_por'
                  )

                  # Relaciones inversas o "many-to-many" simuladas (consulta separada optimizada)
                  qs = qs.prefetch_related(
                  'recepcion_detalles_atencion__recepcion__recibido_por'
                  )

                  # Obtenemos el objeto
                  atencion = qs.get(id=id_atencion)
                  return atencion

            except Atencion.DoesNotExist:
                  return None
            

      @staticmethod
      def obtener_servicio_atenciones_activas():
            atenciones_activas = Atencion.objects.filter(fecha_recepcion__isnull=True).select_related('especialidad__servicio')
            servicios_ids = atenciones_activas.values_list('especialidad__servicio__id', flat=True).distinct()
            servicios = Servicio.objects.filter(id__in=servicios_ids, estado=1).values("id", "nombre_servicio")
            return servicios


      @staticmethod
      def obtener_atenciones_activas():
            expediente_subquery = PacienteAsignacion.objects.filter(
                  paciente=OuterRef('paciente_id'),
                  estado=1
            ).order_by('-id').values('expediente__numero')[:1]

            atenciones = Atencion.objects.annotate(
                  expediente_numero=Subquery(expediente_subquery)
            ).filter(
                  fecha_recepcion__isnull=True
            ).values(
                  "id",
                  "fecha_atencion",
                  "expediente_numero",
                  "paciente_id",
                  "paciente__dni",
                  "paciente__primer_nombre",
                  "paciente__primer_apellido",
                  "especialidad__servicio__id",
            )
            return atenciones
      

      @staticmethod
      def listar_atenciones_por_paciente(id_paciente):
            try:
                  atenciones_qs = Atencion.objects.filter(
                        paciente_id=id_paciente
                  ).select_related(
                        'especialidad__servicio',
                        'modificado_por'
                  ).prefetch_related(
                        'recepcion_detalles_atencion__recepcion__recibido_por'
                  )

                  atenciones = []
                  for atencion in atenciones_qs:
                        try:
                              recepcion_detalle = atencion.recepcion_detalles_atencion.first()
                              usuario_recibio = (
                                    recepcion_detalle.recepcion.recibido_por.username
                                    if recepcion_detalle and recepcion_detalle.recepcion and recepcion_detalle.recepcion.recibido_por
                                    else None
                              )
                        except Exception:
                              usuario_recibio = None

                        atenciones.append({
                        "id": atencion.id,
                        "fecha_atencion": atencion.fecha_atencion,
                        "fecha_recepcion": atencion.fecha_recepcion,
                        "especialidad__nombre_especialidad": atencion.especialidad.nombre_especialidad if atencion.especialidad else None,
                        "especialidad__servicio__nombre_corto": atencion.especialidad.servicio.nombre_corto if atencion.especialidad and atencion.especialidad.servicio else None,
                        "modificado_por__username": atencion.modificado_por.username if atencion.modificado_por else None,
                        "fecha_modificado": atencion.fecha_modificado,
                        "usuario_recibio": usuario_recibio,
                        })

                  return atenciones
            except Exception as e:
                  # Si ocurre algo inesperado, retornamos lista vacía o podrías loguear el error
                  return []


      @staticmethod
      def tiene_atencion_activo(id_paciente):
            return Atencion.objects.filter(
                  Q(paciente_id=id_paciente) & (Q(fecha_recepcion__isnull=True))
            ).exists()


      @staticmethod
      def verificar_atencion_hora(id_paciente, horas=1):
            limite_central = timezone.now() - timedelta(hours=horas)
            
            atencion = (
                  Atencion.objects
                  .filter(
                        paciente_id=id_paciente,
                        fecha_creado__gte=limite_central  # filtramos directamente por fecha de creación
                  )
                  .select_related('paciente', 'especialidad')
                  .order_by('-fecha_creado')  # la más reciente según creación
                  .values(
                        'id',
                        'paciente__primer_nombre',
                        'paciente__segundo_nombre',
                        'paciente__primer_apellido',
                        'paciente__segundo_apellido',
                        'especialidad__nombre_especialidad',
                        'fecha_atencion',
                        'fecha_creado',
                  )
                  .first()
            )

            return atencion
                                                      

      @staticmethod
      def GenerarDataAtencion(reporte_criterios, modo='resumido'):
            """
            Filtra y procesa datos de atenciones según criterios.
            Puede retornar datos detallados o un resumen agrupado.
            """
            try:
                  qs = Atencion.objects.all()
                  #qs = qs.filter(estado=1)  # Solo atenciones activas
                  # --- Bloque de Filtros ---
                  if 'campoFiltro' in reporte_criterios and 'valorFiltro' in reporte_criterios:
                        if reporte_criterios['campoFiltro'] != 'ninguno':
                              campo = reporte_criterios['campoFiltro']
                              valor = reporte_criterios['valorFiltro']
                              qs = qs.filter(**{campo: valor})

                  if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                        campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                        qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

                  if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                        campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                        qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})

            

                  # --- Diccionario de agrupaciones para Atencion ---
                  agrupacion_campos = {
                        'creado_por_id': ('creado_por__username', 'usuario creador'),
                        'modificado_por_id': ('modificado_por__username', 'usuario editor'),
                        'paciente__sector__aldea__municipio__departamento_id': (
                        'paciente__sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'
                        ),
                        'paciente__sector__aldea__municipio_id': (
                        'paciente__sector__aldea__municipio__nombre_municipio', 'Municipio'
                        ),
                        'especialidad__servicio_id': ('especialidad__servicio__nombre_servicio', 'servicio'),
                        'especialidad_id': ('especialidad__nombre_especialidad', 'Especialidad'),
                  }

                  agrupacion_key = reporte_criterios.get('agrupacion', 'id')
                  campo_agrupado, nombre_amigable = agrupacion_campos.get(
                        agrupacion_key,
                        (agrupacion_key, agrupacion_key)
                  )

                  # --- Lógica de Modo Detallado vs. Modo Resumido ---
                  if modo == 'detallado':
                        limite = 5000  # Límite de registros para evitar sobrecarga

                        # Precargamos relaciones para evitar N+1
                        qs = qs.select_related(
                        'paciente', 
                        'especialidad', 
                        'especialidad__servicio', 
                        'creado_por', 
                        'modificado_por'
                        ).prefetch_related(
                              'recepcion_detalles_atencion__recepcion__recibido_por'
                        )
                        # Si tienes relaciones similares a las recepciones, agrégalas aquí:
                        # .prefetch_related(
                        #     'relacion_similar__campo__usuario'
                        # )

                        qs_ordenado = qs.order_by(campo_agrupado, 'fecha_atencion')[:limite]


                        # Transformamos a lista de diccionarios (ajustar campos según tu modelo Atencion)
                        lista_dicts = list(qs_ordenado.values(
                        'id',
                        'paciente__dni',
                        'paciente__expediente_numero',
                        'paciente__primer_nombre',
                        'paciente__segundo_nombre',
                        'paciente__primer_apellido',
                        'paciente__segundo_apellido',
                        'paciente__sector__aldea__municipio__departamento__nombre_departamento',
                        'paciente__sector__aldea__municipio__nombre_municipio',

                        'especialidad__nombre_especialidad',
                        'especialidad__servicio__nombre_servicio',
                        'especialidad__servicio__nombre_corto',

                        # Agregar otros campos específicos de Atencion:
                        'fecha_creado',
                        'fecha_atencion', 
                        'fecha_recepcion', 
                        'creado_por__username',
                        'creado_por__first_name',
                        'creado_por__last_name',
                        'modificado_por__username',
                        'modificado_por__first_name',
                        'modificado_por__last_name',
                        'recepcion_detalles_atencion__recepcion__recibido_por__username'
                        # Si tienes campos similares a las recepciones, agrégalos:
                        # 'campo_usuario_relacionado__username',
                        ))

                        return {
                        'campo_agrupado': campo_agrupado,
                        'etiqueta': nombre_amigable,
                        'data': lista_dicts
                        }

                  elif modo == 'resumido':
                        # Lógica de agrupación y resumen
                        if agrupacion_key == 'especialidad_id':
                              # Agrupación especial combinando especialidad y servicio
                              qs_con_combinacion = qs.annotate(
                                    nombre_combinado_especialidad_servicio=Concat(
                                          'especialidad__nombre_especialidad',
                                          Value(' | '),
                                          'especialidad__servicio__nombre_servicio'
                                    )
                              )

                              resumen_raw = qs_con_combinacion.values('nombre_combinado_especialidad_servicio').annotate(
                                    total=Count('id')
                              ).order_by('-total')

                              nombre_amigable = "Especialidad y Servicio"
                              campo_agrupado = 'nombre_combinado_especialidad_servicio'
                        else:
                              # Agrupación estándar
                              resumen_raw = qs.values(campo_agrupado).annotate(
                                    total=Count('id')
                              ).order_by('-total')

                        # Calcular totales y porcentajes
                        total = qs.count()
                        resumen = []

                        for item in resumen_raw:
                              porcentaje = (item['total'] / total) * 100 if total > 0 else 0
                              resumen.append({
                                    campo_agrupado: item[campo_agrupado],
                                    'total': item['total'],
                                    'porcentaje': round(porcentaje, 2)
                              })

                        return {
                        'campo_agrupado': campo_agrupado,
                        'etiqueta': nombre_amigable,
                        'total': total,
                        'resumen': resumen
                        }
            
            except Exception as e:
                  log_error(
                        f"Error generando reporte de atención modo={modo}",
                        app=LogApp.REPORTE
                  )
                  return None