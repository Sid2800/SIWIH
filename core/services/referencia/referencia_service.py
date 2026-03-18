from referencia.models import Referencia_diagnostico, Respuesta_diagnostico, Referencia, Respuesta, SeguimientoTic
from core.utils.utilidades_fechas import generar_rango_mes, filtro_rango_fecha
from django.db.models import Q, F, Case, When, Value, CharField, Count, Sum, IntegerField
from django.db.models.functions import ExtractMonth, Concat, Trim, ExtractYear, Now
from core.utils.utilidades_calculos import calcular_porcentaje
from servicio.models import Institucion_salud
from core.services.referencia.referencia_diagnostico_service import RefDiagnosticoService
from core.constants.domain_constants import HEAC_INSTITUCION_ID
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from django.db import transaction
from datetime import date,datetime
from django.utils import timezone
import calendar
from collections import defaultdict


class ReferenciaService:

    

    @staticmethod
    def crear_referencia_enviada_segun_repuesta(data: dict, diagnosticos, user=None):

        try:
            with transaction.atomic():

                campos = {
                    "fecha_elaboracion": data.get("fecha_elaboracion"),
                    "tipo": data.get("tipo"),
                    "paciente": data.get("paciente"),
                    "institucion_origen": Institucion_salud.objects.get(id=HEAC_INSTITUCION_ID),
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

                # Forzar confirmados
                for diag in diagnosticos:
                    diag['confirmado'] = True

                # Procesar diagnósticos (ya usa raise internamente)
                RefDiagnosticoService.procesar_diagnosticos_referencia(
                    referencia_id=referencia.id,
                    diagnosticos=diagnosticos
                )
                return referencia

        except Exception:
            log_error(
                f"Error creando referencia de seguimiento paciente {data.get('paciente')} destino {data.get('institucion_destino')}",
                app=LogApp.REFERENCIAS
            )
            raise


    @staticmethod
    def crear_actualizar_seguimiento(seguimiento, user):
        try:
            with transaction.atomic():
                # creacioa
                if seguimiento.idSeguimiento == '0':
                    # Bloqueo para evitar duplicados concurrentes
                    existe = (
                        SeguimientoTic.objects
                        .select_for_update()
                        .filter(referencia_id=seguimiento.idReferencia)
                        .exists()
                    )

                    if existe:
                        log_warning(
                            f"Intento duplicado seguimiento referencia {seguimiento.idReferencia}",
                            app=LogApp.REFERENCIAS
                        )
                        raise ValueError("Esta referencia ya tiene un seguimiento registrado")

                    nuevo = SeguimientoTic.objects.create(
                        referencia_id=seguimiento.idReferencia,
                        metodo_comunicacion=seguimiento.metodo,
                        establece_comunicacion=seguimiento.establece_comunicacion,
                        asistio_referencia=seguimiento.asistio_referencia,
                        fuente_info=seguimiento.fuente_info,
                        condicion_paciente_id=seguimiento.condicion_paciente,
                        observaciones=seguimiento.observaciones,
                        creado_por=user
                    )
                    return nuevo.id  


                # actualizacion
                else:

                    try:
                        seg = (
                            SeguimientoTic.objects
                            .select_for_update()
                            .get(pk=seguimiento.idSeguimiento)
                        )
                    except SeguimientoTic.DoesNotExist:
                        log_warning(
                            f"Seguimiento {seguimiento.idSeguimiento} no existe para actualizar",
                            app=LogApp.REFERENCIAS
                        )
                        raise ValueError("No existe el seguimiento a actualizar")

                    cambio = False

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

                    if not cambio:
                        # No es error → solo devolver id
                        return seg.id

                    seg.save()
                    return seg.id

        except ValueError:
            raise

        except Exception:
            log_error(
                f"Error en crear/actualizar seguimiento referencia {seguimiento.idReferencia}",
                app=LogApp.REFERENCIAS
            )
            raise


    @staticmethod
    def obtener_seguimiento_id(idSeguimiento):
        try:
            relaciones = ['referencia','creado_por']
            seguimiento = SeguimientoTic.objects.select_related(*relaciones).get(id=idSeguimiento)
            return seguimiento
        except SeguimientoTic.DoesNotExist:
            return None
