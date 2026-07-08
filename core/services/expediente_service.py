from expediente.models import Expediente, PacienteAsignacion
from django.db import models, transaction
from datetime import datetime
from django.db.models import Min, Max
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from core.constants.domain_constants import LogApp
from core.utils.utilidades_textos import formatear_expediente
from core.utils.utilidades_logging import *
from types import SimpleNamespace
from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy_hh_mm
from s_exp.models import ExpedientePrestamo
from expediente.models import ExpedienteUbicacion
from servicio.models import Unidad_clinica, Unidad


class ExpedienteService:

        
    """ Verifica si un expediente está libre o asigna uno nuevo. """
    @staticmethod
    def comprobar_libre(expediente_numero, usuario_id):
        with transaction.atomic():
            expediente = Expediente.objects.select_for_update(skip_locked=True).filter(
                numero=expediente_numero
            ).exclude(
                expedienteAsignados__estado="1"
            ).first()
            if not expediente:
                log_warning(
                        f"No disponible expediente={expediente_numero} usuario={usuario_id}",
                        app=LogApp.EXPEDIENTE
                )
            return expediente
    
    @staticmethod
    def comprobar_y_asignar(expediente_numero, paciente_id, usuario_id):
        with transaction.atomic(): 
            expediente = ExpedienteService.comprobar_libre(expediente_numero, usuario_id)

            if not expediente:
                log_warning(
                    f"[OCUPADO] expediente={expediente_numero} paciente={paciente_id}",
                    app=LogApp.EXPEDIENTE
                )
                expediente = ExpedienteService.asignar_expediente_paciente(None, paciente_id, usuario_id)
            else:
                expediente = ExpedienteService.asignar_expediente_paciente(expediente, paciente_id, usuario_id)
                
            return expediente
    

    @staticmethod
    def asignar_expediente_paciente( expediente, paciente_id, usuario_id):
        if expediente == None:
            expediente = ExpedienteService.obtener_expediente_libre(usuario_id)

        with transaction.atomic():

            asignado = PacienteAsignacion.objects.filter(
                expediente=expediente,
                estado="1"
            ).exists()

            if asignado:
                log_warning(
                    f"[OCUPADO] expediente={expediente.numero} paciente={paciente_id} reasignando",
                    app=LogApp.EXPEDIENTE
                )
                expediente = ExpedienteService.obtener_expediente_libre(usuario_id)

            PacienteAsignacion.objects.create(
                estado=1,
                fecha_asignacion=datetime.now(),
                paciente_id=paciente_id,
                expediente_id=expediente.id
            )

            expediente.estado = 1
            expediente.save()

            duplicados = list(
                PacienteAsignacion.objects.filter(
                    expediente=expediente,
                    estado="1"
                ).values_list("id", flat=True)[:2]
            )

            if len(duplicados) > 1:
                log_error(
                    f"[DUPLICADO] expediente={expediente.numero} paciente={paciente_id}",
                    app=LogApp.EXPEDIENTE
                )
                raise ValidationError("No se logró asignar el expediente: duplicado detectado.")
        return expediente

    """ Busca un expediente libre o crea uno nuevo si no hay disponibles. """
    @staticmethod
    def obtener_expediente_libre( usuario_id):
        with transaction.atomic():
            # Buscar expedientes que tengan asignaciones, excluyendo los activos
            expedientes_asignados = Expediente.objects.filter(
                expedienteAsignados__isnull=False
            ).exclude(
                expedienteAsignados__estado="1"  # Excluir los asignados con estado 'Actual'
            )

            # Buscar el número de expediente más bajo entre los disponibles
            expediente_disponible = expedientes_asignados.aggregate(min_numero=Min('numero'))['min_numero']
            expediente = Expediente.objects.select_for_update(skip_locked=True).filter(numero=expediente_disponible).first() if expediente_disponible else None

            # Si no hay expedientes reutilizables, buscar los no asignados
            if not expediente:
                expedientes_no_asignados = Expediente.objects.filter(expedienteAsignados__isnull=True)
                expediente_disponible = expedientes_no_asignados.aggregate(min_numero=Min('numero'))['min_numero']
                expediente = Expediente.objects.select_for_update(skip_locked=True).filter(numero=expediente_disponible).first()

            # Si no hay expedientes disponibles, generar uno nuevo
            if not expediente:
                numero_disponible = 1
                queryset = Expediente.objects.order_by('numero').values_list('numero', flat=True)

                for numero in queryset.iterator():
                    if numero != numero_disponible:
                        break
                    numero_disponible += 1

                try:
                    expediente = Expediente.objects.create(
                        numero=numero_disponible,
                        estado=2,
                        creado_por_id=usuario_id,
                        modificado_por_id=usuario_id,
                        fecha_modificado=datetime.now()
                    )
                except IntegrityError as e:
                    log_error(
                        f"[ERROR_DB] Creacion {str(e)} usuario={usuario_id}",
                        app=LogApp.EXPEDIENTE
                    )
                    transaction.set_rollback(True)
                    return None  # Indicar que hubo un error al crear el expediente

        return expediente
        """ Asigna un expediente a un paciente. """
    
    @staticmethod
    def obtener_expediente_activo_paciente(pacienteId):
        pacienteA = PacienteAsignacion.objects.filter(paciente_id=pacienteId, estado=1).select_related('expediente').first()
        return pacienteA.expediente if pacienteA else None
    
    @staticmethod
    def obtener_paciente_asignacion(expediente_id):#expedeitne id mismo que el numero
        try:
            pacienteA = PacienteAsignacion.objects.get(expediente_id=expediente_id, estado=1)
            return pacienteA
        except PacienteAsignacion.DoesNotExist:
            return None
        
    @staticmethod
    def obtener_paciente_propietario(numero):
        try:
            pacienteA = PacienteAsignacion.objects.select_related("paciente").get(expediente__numero=numero, estado="1")
            return pacienteA  # Accedemos directamente a paciente sin otra consulta
        except PacienteAsignacion.DoesNotExist:
            return None
    
        
    @staticmethod
    def comprobar_propietario(numero_expediente, id_paciente):
        try:
            # Obtener el expediente por número
            expediente = Expediente.objects.get(numero=numero_expediente)
        except Expediente.DoesNotExist:
            log_warning(
                f"[NO_EXISTE] expediente={numero_expediente}",
                app=LogApp.EXPEDIENTE
            )
            # Si no se encuentra el expediente, retornar False
            return False
        
        try:
            # Buscar la asignación activa entre el paciente y el expediente
            _ = PacienteAsignacion.objects.get(expediente_id=expediente.id, paciente_id=id_paciente, estado=1)
            # Si la asignación existe, retornar True indicando que el paciente es el propietario
            return True
        except PacienteAsignacion.DoesNotExist:
            # Si no existe la asignación activa, retornar False
            log_warning(
                f"[NO_PROPIETARIO] expediente={numero_expediente} paciente={id_paciente}",
                app=LogApp.EXPEDIENTE
            )
            return False
        


    @staticmethod
    def _obtener_info_expediente(paciente_id):
        expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente_id)

        if not expediente:
            return None

        estado = ExpedienteService.obtener_ubicacion_estado_expediente(
            expediente.numero
        )

        return {
            "numero": formatear_expediente(expediente.numero),
            "estado": estado,
        }
    

    @staticmethod
    def obtener_ubicacion_estado_expediente(numero_expediente):
        from core.services.ingreso.ingreso_service import IngresoService
        from core.services.atencion_service import AtencionService
        from core.constants.domain_constants import (
            EXP_UBICA_ADMISION_ID,
            PRESTAMO_ESTADO_ACTIVO_ID,
            EXP_UBICA_ESTADISTICA_ID,
            APARTADO_ESTADO_ACTIVO_ID,
            DISPONIBLE_ESTADO_ACTIVO_ID,
            MotivoEstadoExpediente
        )

        def _crear_estado(
            ubicacion,
            estado,
            badge,
            motivo=None,
            responsable=None,
            fecha=None,
        ):
            return SimpleNamespace(
                ubicacion=ubicacion,
                estado=estado,
                badge=badge,
                motivo=motivo,
                responsable=responsable,
                fecha=fecha,
            )

        def _crear_estado_disponible():
            return _crear_estado(
                ubicacion=ubicacion,
                estado="DISPONIBLE",
                badge="icon-verde icon-verde-tenue",
                motivo=MotivoEstadoExpediente.RESGUARDO,
            )
        

        expediente = (
            Expediente.objects
            .select_related(
                "ubicacion",
                "prestamo_info__estado",
            )
            .get(numero=numero_expediente)
        )

        ubicacion = (
            expediente.ubicacion.descripcion
            if expediente.ubicacion
            else "SIN UBICACIÓN"
        )

        es_clinica = (
            expediente.ubicacion.es_clinica
            if expediente.ubicacion
            else False
        )

        # ------------------------------------------------------------------
        # Ubicación clínica
        # ------------------------------------------------------------------

        if es_clinica:

            estado_ingreso = IngresoService.obtener_estado_expediente(
                numero_expediente
            )

            if estado_ingreso:
                return _crear_estado(
                    ubicacion=ubicacion,
                    estado="NO DISPONIBLE",
                    badge="icon-amarillo icon-amarillo-tenue",
                    motivo=MotivoEstadoExpediente.HOSPITALIZACION,
                    fecha=formatear_fecha_dd_mm_yyyy_hh_mm(
                        estado_ingreso["fecha"]
                    ),
                )

            estado_atencion = AtencionService.obtener_estado_expediente(
                numero_expediente
            )

            if estado_atencion:
                return _crear_estado(
                    ubicacion=ubicacion,
                    estado="NO DISPONIBLE",
                    badge="icon-amarillo icon-amarillo-tenue",
                    motivo=MotivoEstadoExpediente.ATENCION_AMBULATORIA,
                    fecha=formatear_fecha_dd_mm_yyyy_hh_mm(
                        estado_atencion["fecha"]
                    ),
                )

        # ------------------------------------------------------------------
        # Estadística (Digitalización)
        # ------------------------------------------------------------------

        if expediente.ubicacion_id == EXP_UBICA_ESTADISTICA_ID:

            estado_ingreso = IngresoService.obtener_estado_expediente(
                numero_expediente
            )

            if not estado_ingreso:
                return _crear_estado(
                    ubicacion=ubicacion,
                    estado="NO DISPONIBLE",
                    badge="icon-amarillo icon-amarillo-tenue",
                    motivo=MotivoEstadoExpediente.DIGITALIZACION,
                )

            return _crear_estado(
                ubicacion=ubicacion,
                estado="NO DISPONIBLE",
                badge="icon-amarillo icon-amarillo-tenue",
                motivo=MotivoEstadoExpediente.DIGITALIZACION,
                fecha=formatear_fecha_dd_mm_yyyy_hh_mm(
                    estado_ingreso["fecha"]
                ),
            )

        # ------------------------------------------------------------------
        # Préstamo
        # ------------------------------------------------------------------

        prestamo = getattr(expediente, "prestamo_info", None)

        if prestamo:

            if prestamo.estado_id == DISPONIBLE_ESTADO_ACTIVO_ID:
                return _crear_estado_disponible()

            if prestamo.estado_id == PRESTAMO_ESTADO_ACTIVO_ID:
                estado = "PRESTADO"
                motivo = MotivoEstadoExpediente.PRESTAMO
            elif prestamo.estado_id == APARTADO_ESTADO_ACTIVO_ID:
                estado = "NO DISPONIBLE"
                motivo = MotivoEstadoExpediente.APARTADO
            else:
                estado = "NO DISPONIBLE"
                motivo = None

            detalle = (
                prestamo.detalle_solicitudes
                .filter(
                    aprobado=True,
                    devuelto=False,
                )
                .select_related(
                    "solicitud",
                    "solicitud__usuario__empleado",
                    "solicitud__servicio_unidad",
                )
                .first()
            )

            responsable = None
            fecha = None

            if detalle:
                responsable = detalle.solicitud.usuario.empleado.nombre_completo
                fecha = detalle.solicitud.fecha_creacion

            return _crear_estado(
                ubicacion=ubicacion,
                estado=estado,
                badge="icon-amarillo icon-amarillo-tenue",
                motivo=motivo,
                responsable=responsable,
                fecha=(
                    formatear_fecha_dd_mm_yyyy_hh_mm(fecha)
                    if fecha
                    else None
                ),
            )

        # ------------------------------------------------------------------
        # Disponible en Admisión
        # ------------------------------------------------------------------

        if expediente.ubicacion_id == EXP_UBICA_ADMISION_ID:
            return _crear_estado_disponible()

        # ------------------------------------------------------------------
        # Estado no determinado
        # ------------------------------------------------------------------

        return _crear_estado(
            ubicacion=ubicacion,
            estado="DESCONOCIDO",
            badge="icon-gris icon-gris-tenue",
            motivo=MotivoEstadoExpediente.NO_LOCALIZADO,
        )
    

    @staticmethod
    def _obtener_o_crear_ubicacion_clinica(unidad_clinica):

        ubicacion, _ = ExpedienteUbicacion.objects.get_or_create(
            unidad_clinica=unidad_clinica,
            defaults={
                "tipo": ExpedienteUbicacion.TIPO_CLINICA,
                "estado": True,
            },
        )
        return ubicacion
    
    @staticmethod
    def _obtener_o_crear_ubicacion_no_clinica(unidad):

        ubicacion, _ = ExpedienteUbicacion.objects.get_or_create(
            unidad_no_clinica=unidad,
            defaults={
                "tipo": ExpedienteUbicacion.TIPO_NO_CLINICA,
                "estado": True,
            },
        )

        return ubicacion
    

    @staticmethod
    def obtener_o_crear_ubicacion_area(id_area_atencion):
        unidad_clinica = Unidad_clinica.objects.get(area_atencion=id_area_atencion)

        return ExpedienteService._obtener_o_crear_ubicacion_clinica(unidad_clinica)
    

    @staticmethod
    def obtener_o_crear_ubicacion_sala(id_sala):
        unidad_clinica = Unidad_clinica.objects.get(sala=id_sala)

        return ExpedienteService._obtener_o_crear_ubicacion_clinica(unidad_clinica)
    

    @staticmethod
    def obtener_o_crear_ubicacion_unidad(id_unidad):
        unidad = Unidad.objects.get(id=id_unidad)

        return ExpedienteService._obtener_o_crear_ubicacion_no_clinica(unidad)
    


    @staticmethod
    def cambiar_ubicacion(expediente_numero, ubicacion):
        """
        Actualiza la ubicación física de un expediente.

        Args:
            expediente_id (int): ID del expediente.
            ubicacion (ExpedienteUbicacion): Nueva ubicación.
        """

            #     ).exclude(
            # ubicacion=ubicacion

        return Expediente.objects.filter(
            numero=expediente_numero
        ).update(
            ubicacion=ubicacion
        )
    
    @staticmethod
    def cambiar_ubicacion_lotes(numeros_expediente,ubicacion):
        """
        Cambia la ubicación de varios expedientes.
        """

        return (
            Expediente.objects
            .filter(numero__in=numeros_expediente)
            .update(ubicacion_id=ubicacion)
        )
    


    # ejecion de una vez borrar 

    @staticmethod
    @transaction.atomic
    def sincronizar_ubicaciones_desde_ingresos():
        """
            Sincroniza la ubicación física de los expedientes con el estado
            actual de los ingresos.

            Reglas:

            - fecha_recepcion_sdgi != NULL
                No hacer nada (ya fue recibido por SDGI).

            - fecha_egreso == NULL
                El expediente permanece en la sala.

            - fecha_egreso != NULL
            AND fecha_recepcion_sdgi == NULL
                El expediente debe quedar en Estadística.

            El proceso es idempotente; puede ejecutarse varias veces.
        """

        from core.constants.domain_constants import EXP_UBICA_ESTADISTICA_ID
        from ingreso.models import Ingreso
        #
        # Mapa Sala -> Unidad Clínica
        #
        mapa_salas = {
            unidad.sala_id: unidad
            for unidad in (
                Unidad_clinica.objects
                .select_related("sala")
                .exclude(sala=None)
            )
        }

        #
        # Ubicación Estadística
        #
        ubicacion_estadistica = ExpedienteUbicacion.objects.get(
            pk=EXP_UBICA_ESTADISTICA_ID
        )

        #
        # Todos los ingresos pendientes de recepción por SDGI
        #
        ingresos = (
            Ingreso.objects
            .filter(
                estado=1,
                fecha_recepcion_sdgi__isnull=True,
            )
            .select_related(
                "paciente",
                "sala",
            )
        )

        #
        # Mapa Paciente -> Expediente
        #
        asignaciones = {
            asignacion.paciente_id: asignacion.expediente
            for asignacion in (
                PacienteAsignacion.objects
                .filter(estado=1)
                .select_related("expediente")
            )
        }

        expedientes_actualizar = []

        total_sala = 0
        total_estadistica = 0
        total_sin_expediente = 0
        total_sin_unidad = 0

        for ingreso in ingresos:

            expediente = asignaciones.get(ingreso.paciente_id)

            if expediente is None:
                total_sin_expediente += 1
                continue

            #
            # INGRESO ACTIVO
            #
            if ingreso.fecha_egreso is None:

                unidad = mapa_salas.get(ingreso.sala_id)

                if unidad is None:
                    total_sin_unidad += 1
                    continue

                ubicacion = ExpedienteService._obtener_o_crear_ubicacion_clinica(
                    unidad
                )

                if expediente.ubicacion_id != ubicacion.id:
                    expediente.ubicacion = ubicacion
                    expedientes_actualizar.append(expediente)
                    total_sala += 1

            #
            # EGRESADO PENDIENTE SDGI
            #
            else:

                if expediente.ubicacion_id != ubicacion_estadistica.id:
                    expediente.ubicacion = ubicacion_estadistica
                    expedientes_actualizar.append(expediente)
                    total_estadistica += 1

        if expedientes_actualizar:
            Expediente.objects.bulk_update(
                expedientes_actualizar,
                ["ubicacion"],
                batch_size=500,
            )

        return {
            "actualizados": len(expedientes_actualizar),
            "en_sala": total_sala,
            "en_estadistica": total_estadistica,
            "sin_expediente": total_sin_expediente,
            "sin_unidad_clinica": total_sin_unidad,
        }