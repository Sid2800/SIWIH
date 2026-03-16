from referencia.models import Referencia_diagnostico, Respuesta_diagnostico, Referencia, Respuesta, SeguimientoTic
from core.utils.utilidades_fechas import generar_rango_mes, filtro_rango_fecha
from django.db.models import Q, F, Case, When, Value, CharField, Count, Sum, IntegerField
from django.db.models.functions import ExtractMonth, Concat, Trim, ExtractYear, Now
from core.utils.utilidades_calculos import calcular_porcentaje
from servicio.models import Institucion_salud
from core.services.referencia.referencia_diagnostico_service import RefDiagnosticoService
from django.db import transaction
from datetime import date,datetime
from django.utils import timezone
import calendar
from collections import defaultdict


class ReferenciaService:

    

    @staticmethod
    def crear_referencia_enviada_segun_repuesta(data: dict, diagnosticos,  user=None):

        campos = {
            "fecha_elaboracion": data.get("fecha_elaboracion"),
            "tipo": data.get("tipo"),
            "paciente": data.get("paciente"),
            "institucion_origen": Institucion_salud.objects.get(id=65),# siempre sera el enrique osea nosotros 
            "institucion_destino": data.get("institucion_destino"),
            "motivo": data.get("motivo"),
            "motivo_detalle": data.get("motivo_detalle"),
            "atencion_requerida": data.get("atencion_requerida"),
            "elaborada_por": data.get("elaborada_por"), 
            "area_refiere_sala": data.get("area_refiere_sala"),
            "area_refiere_especialidad": data.get("area_refiere_especialidad"),
            "area_refiere_servicio_auxiliar": data.get("area_refiere_servicio_auxiliar"),
            "especialidad_destino": data.get("especialidad_destino"),
            "observaciones": data.get("observaciones"),
            "estado": True    
        }

        if user:
            campos["creado_por"] = user
            campos["modificado_por"] = user

        referencia = Referencia.objects.create(**campos)

        
        for diag in diagnosticos:
            diag['confirmado'] = True

        result_diagnostico = RefDiagnosticoService.procesar_diagnosticos_referencia(
                    referencia_id=referencia.id,
                    diagnosticos=diagnosticos
                )


        return referencia
    

    @staticmethod
    def crear_actualizar_seguimiento(seguimiento, user):
        if seguimiento.idSeguimiento == '0':
            try:
                SeguimientoTic.objects.get(referencia_id=seguimiento.idReferencia)
                return False, 0, "Esta referencia ya tiene un seguimiento registrado"
            except SeguimientoTic.DoesNotExist:
                pass

            try:
                nuevo = SeguimientoTic.objects.create(
                    referencia_id = seguimiento.idReferencia,
                    metodo_comunicacion = seguimiento.metodo,
                    establece_comunicacion = seguimiento.establece_comunicacion,
                    asistio_referencia = seguimiento.asistio_referencia,
                    fuente_info = seguimiento.fuente_info,
                    condicion_paciente_id = seguimiento.condicion_paciente,
                    observaciones = seguimiento.observaciones,
                    creado_por = user
                )

                return True, nuevo.id, "Seguimiento creado correctamente"

            except Exception as e:
                return False, 0, "No se pudo crear el seguimiento, intente nuevamente"

        #ACTUALIZACIÓN
        else:
            try:
                seg = SeguimientoTic.objects.get(pk=seguimiento.idSeguimiento)
            except SeguimientoTic.DoesNotExist:
                return False, 0, "No existe el seguimiento a actualizar"

            cambio = False

            # Comparar campo por campo
            if seg.metodo_comunicacion != seguimiento.metodo:
                seg.metodo_comunicacion = seguimiento.metodo
                cambio = True

            if seg.establece_comunicacion != seguimiento.establece_comunicacion:
                seg.establece_comunicacion = seguimiento.establece_comunicacion
                cambio = True

            if seg.asistio_referencia != seguimiento.asistio_referencia:
                seg.asistio_referencia = seguimiento.asistio_referencia
                cambio = True

            if seg.fuente_info != seguimiento.fuente_info:
                seg.fuente_info = seguimiento.fuente_info
                cambio = True

            if seg.condicion_paciente_id != seguimiento.condicion_paciente:
                seg.condicion_paciente_id = seguimiento.condicion_paciente
                cambio = True

            if seg.observaciones != seguimiento.observaciones:
                seg.observaciones = seguimiento.observaciones
                cambio = True

            # Ningún campo cambió
            if not cambio:
                return True, seg.id, "No hubo cambios en el seguimiento"

            #  algo cambió  guardar
            try:
                seg.save()
                return True, seg.id, "Seguimiento actualizado correctamente"
            except Exception as e:  
                return False, 0, "No se pudo actualizar el seguimiento"


    @staticmethod
    def obtener_seguimiento_id(idSeguimiento):
        try:
            relaciones = ['referencia','creado_por']
            seguimiento = SeguimientoTic.objects.select_related(*relaciones).get(id=idSeguimiento)
            return seguimiento
        except SeguimientoTic.DoesNotExist:
            return None
