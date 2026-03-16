from ingreso.models import RecepcionIngresoSala, RecepcionIngresoDetalleSala,RecepcionIngresoSDGI,RecepcionIngresoDetalleSDGI
from expediente.models import PacienteAsignacion
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Concat
from django.db import transaction
from core.services.expediente_service import ExpedienteService
from ingreso.models import Ingreso
from django.utils import timezone
from django.utils import timezone

class RecepcionIngresoServiceSala:
    def __init__(self, RecepcionIngresoSala=None):
        self.recepcion = RecepcionIngresoSala


    @staticmethod
    def definir_recepcion_ingreso_sala(idRecepcion):
        try:
            return (
                RecepcionIngresoSala.objects
                .select_related("recibido_por", "modificado_por")  # agregá aquí las relaciones que querés precargar
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

                for ingreso in ingresos:
                    id_ingreso = ingreso.get('id')
                    id_sala = ingreso.get('idSala')
                    id_paciente = ingreso.get('idPaciente')
                    resultado = RecepcionIngresoServiceSala.procesar_recepcion_ingreso_detalle_sala(
                        id_ingreso, id_sala, id_paciente, recepcion, usuario
                    )

                    if resultado.get('error'):
                        raise Exception(resultado['mensaje'])

        except Exception as e:
            return {'error': True, 'mensaje': f"Error al generar los registros: {str(e)}"}

        return {'error': False, 'mensaje': "El proceso se realizó correctamente", 'idRecepcion': recepcion.id}

    @staticmethod
    def procesar_recepcion_ingreso_detalle_sala(idIngreso, idSala, idPaciente, recepcion, usuario):
        try:
            ingreso = Ingreso.objects.only("fecha_egreso").get(
                id=idIngreso,
                paciente_id=idPaciente,
                sala_id=idSala
            )
            ingreso.fecha_egreso = timezone.now()
            ingreso.modificado_por = usuario
            ingreso.save()

            RecepcionIngresoDetalleSala.objects.create(
                recepcion=recepcion,
                ingreso=ingreso
            )
            #en neceario cmabiar la ubicacion del expedienteasi 
            cambio = ExpedienteService.cambiar_ubicacion(idPaciente,3, usuario.id) #e el id de SDGI

            if not cambio:
                raise Exception("No se logro cambiar la ubicacion del expedediente")


        except Ingreso.DoesNotExist:
            return {
                'error': True,
                'mensaje': "El ingreso indicado no existe"
            }

        except Exception as e:
            return {
                'error': True,
                'mensaje': f"Error al crear el detalle: {str(e)}"
            }

        return {'error': False, 'mensaje': "Detalle procesado correctamente"}


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

                for ingreso in ingresos:
                    id_ingreso = ingreso.get('id')
                    id_paciente = ingreso.get('idPaciente')
                    resultado = RecepcionIngresoServiceSDGI.procesar_recepcion_ingreso_detalle_sdgi(
                        id_ingreso, id_paciente, recepcion, usuario
                    )

                    if resultado.get('error'):
                        raise Exception(resultado['mensaje'])

        except Exception as e:
            return {'error': True, 'mensaje': f"Error al generar los registros: {str(e)}"}

        return {'error': False, 'mensaje': "El proceso se realizó correctamente", 'idRecepcion': recepcion.id}

    @staticmethod
    def procesar_recepcion_ingreso_detalle_sdgi(idIngreso, idPaciente, recepcion, usuario):
        try:
            ingreso = Ingreso.objects.only("fecha_recepcion_sdgi").get(
                id=idIngreso,
                paciente_id=idPaciente
            )
            ingreso.fecha_recepcion_sdgi = timezone.now()
            ingreso.modificado_por = usuario
            ingreso.save()

            RecepcionIngresoDetalleSDGI.objects.create(
                recepcion=recepcion,
                ingreso=ingreso
            )
            #en neceario cmabiar la ubicacion del expedienteasi 
            cambio = ExpedienteService.cambiar_ubicacion(idPaciente,1, usuario.id) #e el id de SDGI Archivo

            if not cambio:
                raise Exception("No se logro cambiar la ubicacion del expedediente")


        except Ingreso.DoesNotExist:
            return {
                'error': True,
                'mensaje': "El ingreso indicado no existe"
            }

        except Exception as e:
            return {
                'error': True,
                'mensaje': f"Error al crear el detalle: {str(e)}"
            }

        return {'error': False, 'mensaje': "Detalle procesado correctamente"}




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