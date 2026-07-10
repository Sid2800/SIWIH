from ingreso.models import RecepcionIngresoSala, RecepcionIngresoDetalleSala,RecepcionIngresoSDGI,RecepcionIngresoDetalleSDGI
from expediente.models import PacienteAsignacion
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Concat
from django.db import transaction
from core.services.expediente_service import ExpedienteService
from ingreso.models import Ingreso
from django.utils import timezone
from core.constants.domain_constants import LogApp, EXP_UBICA_ADMISION_ID, EXP_UBICA_ESTADISTICA_ID
from core.utils.utilidades_logging import *

class RecepcionIngresoServiceSala:
    def __init__(self, RecepcionIngresoSala=None):
        self.recepcion = RecepcionIngresoSala


    @staticmethod
    def definir_recepcion_ingreso_sala(idRecepcion):
        try:
            return (
                RecepcionIngresoSala.objects
                .select_related("recibido_por", "modificado_por")  
                .get(id=idRecepcion)
            )
        except RecepcionIngresoSala.DoesNotExist:
            return None


    def obtener_detalles_sala(self): # lo usa reporte

        if not self.recepcion:  # Si no hay recepcion, retorna None
            return None
        

        expediente_subquery = PacienteAsignacion.objects.filter(
            paciente=OuterRef('ingreso__paciente__id'),
            estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        detalles = self.recepcion.detalles.select_related(
            'ingreso', 'ingreso__paciente', 'ingreso__sala', 'ingreso__sala__servicio'
        ).annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).order_by(
        'ingreso__sala__nombre_sala',  
        'expediente_numero' 
        )

        return list(detalles.values(
                'ingreso__fecha_ingreso',
                'expediente_numero',
                'ingreso__paciente__dni',
                'ingreso__paciente__primer_nombre',
                'ingreso__paciente__segundo_nombre',
                'ingreso__paciente__primer_apellido',
                'ingreso__paciente__segundo_apellido',
                'ingreso__sala__nombre_sala',
                'ingreso__sala__servicio__nombre_corto',
            ))


    @staticmethod
    def procesar_recepcion_ingreso_sala(observaciones, ingresos, usuario):
        try:
            with transaction.atomic():
                recepcion = RecepcionIngresoSala.objects.create(
                    recibido_por=usuario,
                    modificado_por=usuario,
                    observaciones=observaciones
                )

                detalles = []
                ingresos_actualizar = []
                expedientes = set()

                fecha_egreso= timezone.now()

                for item in ingresos:
                    id_ingreso = item.get('id')
                    id_sala = item.get('idSala')
                    id_paciente = item.get('idPaciente')

                    ingreso = Ingreso.objects.select_related(
                        'paciente'
                    ).get(
                        id=id_ingreso,
                        paciente_id=id_paciente,
                        sala_id=id_sala
                    )

                    ingreso.fecha_egreso = fecha_egreso
                    ingreso.modificado_por = usuario

                    ingresos_actualizar.append(ingreso)

                    detalles.append(
                        RecepcionIngresoDetalleSala(
                            recepcion=recepcion,
                            ingreso=ingreso)
                        )
                    
                    expedientes.add(
                        ingreso.paciente.expediente_numero
                    )

                #ACTUALIZACIOPN DE LOS INGRESOS 
                Ingreso.objects.bulk_update(
                    ingresos_actualizar,
                    ['fecha_egreso','modificado_por']
                )

                # CREACION EN LOTES DEL DETALLE DE RECEPCION
                RecepcionIngresoDetalleSala.objects.bulk_create(
                    detalles
                )


                #cambiar la ubicacion de todos los expediente de ingresos recibidos
                ExpedienteService.cambiar_ubicacion_lotes(
                    expedientes,
                    EXP_UBICA_ESTADISTICA_ID
                )


            return {
                'mensaje': "El proceso se realizó correctamente",
                'idRecepcion': recepcion.id
            }

        except Exception as e:
            log_error(
                f"[FALLO_RECEPCION_INGRESO_SALA] usuario={usuario.id} total_ingresos={len(ingresos)} detalle={str(e)}",
                app=LogApp.ATENCION
            )
            raise




class RecepcionIngresoServiceSDGI:
    def __init__(self, RecepcionIngresoSDGI=None):
        self.recepcion = RecepcionIngresoSDGI

    @staticmethod
    def definir_recepcion_ingreso_sdgi(idRecepcion):
        try:
            return (
                RecepcionIngresoSDGI.objects
                .select_related("recibido_por", "modificado_por")  # agregá aquí las relaciones que querés precargar
                .get(id=idRecepcion)
            )
        except RecepcionIngresoSDGI.DoesNotExist:
            return None


    @staticmethod
    def procesar_recepcion_ingreso_sdgi(observaciones, ingresos, usuario):

        try:
            with transaction.atomic():

                recepcion = RecepcionIngresoSDGI.objects.create(
                    recibido_por=usuario,
                    modificado_por=usuario,
                    observaciones=observaciones
                )

                detalles = []
                ingresos_actualizar = []
                expedientes = set()

                fecha_recepcion_sdgi = timezone.now()

                for item in ingresos:

                    id_ingreso = item.get("id")
                    id_paciente = item.get("idPaciente")

                    ingreso = Ingreso.objects.select_related(
                        "paciente"
                    ).get(
                        id=id_ingreso,
                        paciente_id=id_paciente
                    )

                    ingreso.fecha_recepcion_sdgi = fecha_recepcion_sdgi
                    ingreso.modificado_por = usuario

                    ingresos_actualizar.append(ingreso)

                    detalles.append(
                        RecepcionIngresoDetalleSDGI(
                            recepcion=recepcion,
                            ingreso=ingreso
                        )
                    )

                    expedientes.add(
                        ingreso.paciente.expediente_numero
                    )

                # Actualizar ingresos
                Ingreso.objects.bulk_update(
                    ingresos_actualizar,
                    ["fecha_recepcion_sdgi", "modificado_por"]
                )

                # Crear detalles de recepción
                RecepcionIngresoDetalleSDGI.objects.bulk_create(
                    detalles
                )

                # Cambiar ubicación de los expedientes a Admisión
                log_info(expedientes)
                ExpedienteService.cambiar_ubicacion_lotes(
                    expedientes,
                    EXP_UBICA_ADMISION_ID
                )

            return {
                "mensaje": "El proceso se realizó correctamente",
                "idRecepcion": recepcion.id
            }

        except Exception as e:

            log_error(
                f"[FALLO_RECEPCION_INGRESO_SDGI] usuario={usuario.id} total_ingresos={len(ingresos)} detalle={str(e)}",
                app=LogApp.ATENCION
            )

            raise

    def obtener_detalles_sdgi(self): # lo usa reporte

        if not self.recepcion:  # Si no hay recepcion, retorna None
            return None
        

        expediente_subquery = PacienteAsignacion.objects.filter(
            paciente=OuterRef('ingreso__paciente__id'),
            estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        detalles = self.recepcion.detalles.select_related(
            'ingreso', 'ingreso__paciente', 'ingreso__sala', 'ingreso__sala__servicio'
        ).annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).order_by(
        'ingreso__sala__nombre_sala',  
        'expediente_numero' 
        )

        return list(detalles.values(
                'ingreso__fecha_ingreso',
                'ingreso__fecha_egreso',
                'expediente_numero',
                'ingreso__paciente__dni',
                'ingreso__paciente__primer_nombre',
                'ingreso__paciente__segundo_nombre',
                'ingreso__paciente__primer_apellido',
                'ingreso__paciente__segundo_apellido',
                'ingreso__sala__nombre_sala',
                'ingreso__sala__servicio__nombre_corto',
            ))