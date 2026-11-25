from referencia.models import Referencia, SeguimientoTic, ControlCalidadReferencia, ControlCalidadRespuesta
from servicio.models import Institucion_salud
from core.services.referencia.referencia_diagnostico_service import RefDiagnosticoService
from core.constants.domain_constants import HEAC_INSTITUCION_ID
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import (
    Case,
    When,
    F,
    Value,
    CharField,
)
from django.db.models.functions import Concat


class ReferenciaService:

    

    @staticmethod
    def crear_referencia_enviada_segun_repuesta(data: dict, diagnosticos, user=None, control_calidad = None):
        
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
                    "personal_salud_refiere": data.get("personal_salud_refiere"),
                    "elaborada_por": data.get("elaborada_por"),
                    "unidad_clinica_refiere": data.get("unidad_clinica_refiere"),
                    "especialidad_destino": data.get("especialidad_destino"),
                    "observaciones": data.get("observaciones"),
                    "estado": True
                }

                if user:
                    campos["creado_por"] = user
                    campos["modificado_por"] = user

                referencia = Referencia.objects.create(**campos)

                # Forzar confirmados y limpinaro el ID de db porque no le pertence 
                for diag in diagnosticos:
                    diag['confirmado'] = True
                    diag['idDiagDB'] = None

                # Procesar diagnósticos (ya usa raise internamente)
                RefDiagnosticoService.procesar_diagnosticos_referencia(
                    referencia_id=referencia.id,
                    diagnosticos=diagnosticos
                )

                ReferenciaService.procesar_control_calidad_referencia(referencia, control_calidad, user)
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
    def procesar_control_calidad_referencia(referencia, criterios,usuario):
        """
        Crea o actualiza el control de calidad asociado a una referencia.

        Si el control ya existe, únicamente se actualiza cuando
        alguno de los criterios cambió.
        """

        try:
            control = referencia.control_calidad

        except ControlCalidadReferencia.DoesNotExist:
            ControlCalidadReferencia.objects.create(
                referencia=referencia,
                creado_por=usuario,
                modificado_por=usuario,
                **criterios
            )
            return

        hubo_cambios = False

        for campo, valor in criterios.items():

            if getattr(control, campo) != valor:
                setattr(control, campo, valor)
                hubo_cambios = True

        if hubo_cambios:
            control.modificado_por = usuario
            control.save()


    @staticmethod
    def procesar_control_calidad_respuesta(respuesta, criterios,usuario):
        """
        Crea o actualiza el control de calidad asociado a una referencia.

        Si el control ya existe, únicamente se actualiza cuando
        alguno de los criterios cambió.
        """

        try:
            control = respuesta.control_calidad

        except ControlCalidadRespuesta.DoesNotExist:
            ControlCalidadRespuesta.objects.create(
                respuesta=respuesta,
                creado_por=usuario,
                modificado_por=usuario,
                **criterios
            )
            return

        hubo_cambios = False

        for campo, valor in criterios.items():

            if getattr(control, campo) != valor:
                setattr(control, campo, valor)
                hubo_cambios = True

        if hubo_cambios:
            control.modificado_por = usuario
            control.save()


    @staticmethod
    def buscar_duplicidad_referencia(criterios):
        """
        Busca posibles referencias duplicadas según:
        - Paciente
        - Fecha de recepción
        - Fecha de elaboración
        - Tipo de referencia

        Retorna la cantidad total y hasta cinco coincidencias.
        """

        # Validaciones básicas
        if (
            not criterios.paciente_id
            or criterios.fecha_recepcion is None
            or criterios.fecha_elaboracion is None
            or criterios.tipo not in (0, 1)
        ):
            raise ValidationError(
                "Buscar duplicidad: no se recibieron todos los criterios requeridos."
            )

        try:
            qs = Referencia.objects.filter(
                paciente_id=criterios.paciente_id,
                fecha_recepcion__date=criterios.fecha_recepcion,
                fecha_elaboracion__date=criterios.fecha_elaboracion,
                tipo=criterios.tipo
            ).annotate(
                institucion=Case(
                    When(
                        tipo=0,
                        then=Concat(
                            F('institucion_origen__nivel_complejidad_institucional__siglas'),
                            Value('-'),
                            F('institucion_origen__nombre_institucion_salud')
                        )
                    ),
                    When(
                        tipo=1,
                        then=Concat(
                            F('institucion_destino__nivel_complejidad_institucional__siglas'),
                            Value('-'),
                            F('institucion_destino__nombre_institucion_salud')
                        )
                    ),
                    default=Value('Sin Institucion'),
                    output_field=CharField()
                )
            ).values(
                "id",
                "fecha_recepcion",
                "fecha_elaboracion",
                "institucion"
            ).order_by("-id")

            cantidad = qs.count()

            duplicados = []

            for referencia in qs[:5]:
                referencia["N"] = referencia.pop("id")

                referencia["recibida"] = formatear_fecha_dd_mm_yyyy(
                    referencia.pop("fecha_recepcion")
                )

                referencia["elaborada"] = formatear_fecha_dd_mm_yyyy(
                    referencia.pop("fecha_elaboracion")
                )


                duplicados.append(referencia)
            return {
                "cantidad": cantidad,
                "referencias": duplicados
            }

        except Exception as e:
            log_error(f"[duplicados referencia] {e}", LogApp.REFERENCIAS)
            raise ValidationError(
                f"Ocurrió un error al buscar posibles referencias duplicadas: {e}"
            )