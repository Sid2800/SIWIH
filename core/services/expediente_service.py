from expediente.models import Expediente, PacienteAsignacion
from django.db import models, transaction
from datetime import datetime
from django.db.models import Min, Max
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError


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
            return expediente
    
    @staticmethod
    def comprobar_y_asignar(expediente_numero, paciente_id, usuario_id):
        with transaction.atomic(): 
            expediente = ExpedienteService.comprobar_libre(expediente_numero, usuario_id)

            if not expediente:
                expediente = ExpedienteService.asignar_expediente_paciente(None, paciente_id, usuario_id)
            else:
                expediente = ExpedienteService.asignar_expediente_paciente(expediente, paciente_id, usuario_id)
                
            return expediente
    

    @staticmethod
    def asignar_expediente_paciente( expediente, paciente_id, usuario_id):
        if expediente == None:
            expediente = ExpedienteService.obtener_expediente_libre(usuario_id)

        with transaction.atomic():

            asignado = PacienteAsignacion.objects.filter(expediente=expediente,estado="1").exists()
            if asignado:                                           
                expediente = ExpedienteService.obtener_expediente_libre(usuario_id)
            PacienteAsignacion.objects.create(
                estado=1,
                fecha_asignacion=datetime.now(),
                paciente_id=paciente_id,
                expediente_id=expediente.id            
            )
            expediente.estado = 1
            expediente.save()
            if PacienteAsignacion.objects.filter(expediente=expediente, estado="1").count() > 1:
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
                    print(e)
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
            # Si no se encuentra el expediente, retornar False
            return False
        
        try:
            # Buscar la asignación activa entre el paciente y el expediente
            asignacion = PacienteAsignacion.objects.get(expediente_id=expediente.id, paciente_id=id_paciente, estado=1)
            # Si la asignación existe, retornar True indicando que el paciente es el propietario
            return True
        except PacienteAsignacion.DoesNotExist:
            # Si no existe la asignación activa, retornar False
            return False
        
    
    @staticmethod
    def cambiar_ubicacion(pacienteId, ubicacionId, usuarioId):
        pacienteA = PacienteAsignacion.objects.filter(
            paciente_id=pacienteId,
            estado=1
        ).select_related('expediente').first()

        if pacienteA and pacienteA.expediente:
            expediente = pacienteA.expediente
            expediente.localizacion_id = ubicacionId
            expediente.modificado_por_id = usuarioId
            expediente.save()
            return True

        return False
