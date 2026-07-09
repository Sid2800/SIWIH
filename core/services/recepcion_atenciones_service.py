from atencion.models import RecepcionAtencion, RecepcionAtencionDetalle, Atencion
from expediente.models import PacienteAsignacion
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Concat
from django.db import transaction
from core.services.expediente_service import ExpedienteService
from ingreso.models import Ingreso
from django.utils import timezone
from datetime import timedelta
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.constants.domain_constants import EXP_UBICA_ADMISION_ID

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

                detalles = []
                atenciones_actualizar = []
                expedientes = set()

                fecha_recepcion = timezone.now()

                for item in atenciones:

                    id_atencion = item.get("id")
                    id_servicio = item.get("idServicio")
                    id_paciente = item.get("idPaciente")

                    atencion = Atencion.objects.select_related(
                        "paciente"
                    ).get(
                        id=id_atencion,
                        paciente_id=id_paciente,
                        area_atencion__servicio_id=id_servicio
                    )

                    atencion.fecha_recepcion = fecha_recepcion
                    atencion.modificado_por = usuario

                    atenciones_actualizar.append(atencion)

                    detalles.append(
                        RecepcionAtencionDetalle(
                            recepcion=recepcion,
                            atencion=atencion
                        )
                    )

                    expedientes.add(
                        atencion.paciente.expediente_numero
                    )


                Atencion.objects.bulk_update(
                    atenciones_actualizar,
                    ["fecha_recepcion", "modificado_por"]
                )

                RecepcionAtencionDetalle.objects.bulk_create(
                    detalles
                )

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
                f"[FALLO_RECEPCION_ATENCION] usuario={usuario.id} total_atenciones={len(atenciones)} detalle={str(e)}",
                app=LogApp.ATENCION
            )

            raise



    def obtener_detalles(self): # lo usa reporte

        if not self.recepcion:  # Si no hay recepcion, retorna None
            return None
        

        expediente_subquery = PacienteAsignacion.objects.filter(
            paciente=OuterRef('atencion__paciente__id'),
            estado=1
        ).order_by('-id').values('expediente__numero')[:1]

        detalles = self.recepcion.detalles.select_related(
            'atencion', 'atencion__paciente', 'atencion__area_atencion__servicio'
        ).annotate(
            expediente_numero=Subquery(expediente_subquery)
        ).order_by(
        'atencion__area_atencion__servicio__nombre_servicio',  
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
                'atencion__area_atencion__servicio__nombre_servicio',
                ))

