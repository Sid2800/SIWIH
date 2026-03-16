from atencion.models import RecepcionAtencion, RecepcionAtencionDetalle, Atencion
from expediente.models import PacienteAsignacion
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Concat
from django.db import transaction
from core.services.expediente_service import ExpedienteService
from ingreso.models import Ingreso
from django.utils import timezone
from datetime import timedelta

class RecepcionAtencionService:
    def __init__(self, RecepcionAtencion=None):
        self.recepcion = RecepcionAtencion


    @staticmethod
    def definir_recepcion_atencion(idRecepcion):
        try:
            return (
                RecepcionAtencion.objects
                .select_related("recibido_por", "modificado_por")  # agregá aquí las relaciones que querés precargar
                .get(id=idRecepcion)
            )
        except RecepcionAtencion.DoesNotExist:
            return None

        
    @staticmethod
    def procesar_recepcion_atencion(observaciones, atenciones, usuario):
        
        try:
            with transaction.atomic():
                recepcion = RecepcionAtencion.objects.create(
                    recibido_por=usuario,
                    modificado_por=usuario,
                    observaciones=observaciones
                )

                for atencion in atenciones:
                    id_atencion = atencion.get('id')
                    id_servicio = atencion.get('idServicio')
                    id_paciente = atencion.get('idPaciente')
                    
                    resultado = RecepcionAtencionService.procesar_recepcion_atencion_detalle(
                        id_atencion, id_servicio, id_paciente, recepcion, usuario
                    )

                    if resultado.get('error'):
                        raise Exception(resultado['mensaje'])

        except Exception as e:
            return {'error': True, 'mensaje': f"Error al generar los registros: {str(e)}"}

        return {'error': False, 'mensaje': "El proceso se realizó correctamente", 'idRecepcion': recepcion.id}


    @staticmethod
    def procesar_recepcion_atencion_detalle(idAtencion, idServicio, idPaciente, recepcion, usuario):
        
        try:
            atencion = Atencion.objects.only("fecha_recepcion").get(
                id=idAtencion,
                paciente_id=idPaciente,
                especialidad__servicio_id=idServicio
            )
            atencion.fecha_recepcion = timezone.now()
            atencion.modificado_por = usuario
            atencion.save()

            RecepcionAtencionDetalle.objects.create(
                recepcion=recepcion,
                atencion=atencion
            )
            #en neceario cmabiar la ubicacion del expedienteasi 
            cambio = ExpedienteService.cambiar_ubicacion(idPaciente,1, usuario.id) #1 el id de Archivo

            if not cambio:
                raise Exception("No se logro cambiar la ubicacion del expediente")


        except Ingreso.DoesNotExist:
            return {
                'error': True,
                'mensaje': "La atencion indicada no existe"
            }

        except Exception as e:
            return {
                'error': True,
                'mensaje': f"Error al crear el detalle: {str(e)}"
            }

        return {'error': False, 'mensaje': "Detalle procesado correctamente"}


    def obtener_detalles(self): # lo usa reporte

        if not self.recepcion:  # Si no hay recepcion, retorna None
            return None
        

        expediente_subquery = PacienteAsignacion.objects.filter(
            paciente=OuterRef('atencion__paciente__id'),
            estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        detalles = self.recepcion.detalles.select_related(
            'atencion', 'atencion__paciente', 'atencion__especialidad__servicio'
        ).annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).order_by(
        'atencion__especialidad__servicio__nombre_servicio',  
        'expediente_numero' 
        )

        return list(detalles.values(
                'atencion__fecha_atencion',
                'expediente_numero',
                'atencion__paciente__dni',
                'atencion__paciente__primer_nombre',
                'atencion__paciente__segundo_nombre',
                'atencion__paciente__primer_apellido',
                'atencion__paciente__segundo_apellido',
                'atencion__especialidad__servicio__nombre_servicio',
                ))


 