from servicio import models as modelosServicio
from servicio.models import Institucion_salud
from mapeo_camas.models import AsignacionCamaPaciente
from core.constants.domain_constants import HEAC_INSTITUCION_ID
from core.constants.domain_constants import SALAS_EXCLUIDAS, SERVICIOS_AUX_EXTERNOS
from django.db import transaction
from django.db.models import Value, F, CharField
from django.db.models.functions import Concat
from django.core.exceptions import ValidationError
from itertools import chain
import json

class ServicioService:

    @staticmethod
    def obtener_institucion_heac_reporte():
        """
        Obtiene la información institucional del HEAC utilizada en reportes.
        """

        relaciones = [
            "region_salud",
            "nivel_complejidad_institucional",
            "proveedor_salud",
            "direccion__aldea__municipio__departamento",
        ]

        institucion = (
            Institucion_salud.objects
            .select_related(*relaciones)
            .get(id=HEAC_INSTITUCION_ID)
        )

        nivel = institucion.nivel_complejidad_institucional
        region = institucion.region_salud
        proveedor = institucion.proveedor_salud

        return {
            "institucion_nombre": f"{nivel.siglas}-{institucion.nombre_institucion_salud}",
            "institucion_red": f"#{region.codigo}-{region.nombre_region_salud}",
            "institucion_proveedor_salud": proveedor.nombre_proveedor_salud,
            "institucion_proveedor_salud_id": proveedor.id,
            "institucion_nivel": nivel.siglas,
            "institucion_centralizado": institucion.centralizado,
            "institucion_complejidad": nivel.nivel_complejidad,
            "institucion_complejidad_nombre": nivel.siglas,
        }


    @staticmethod
    def obtener_camas_activas():
        # La disponibilidad se define unicamente por el estado de asignacion de cama.
            
        camas_disponibles_ids = AsignacionCamaPaciente.objects.filter(
            estado=AsignacionCamaPaciente.Estado.VACIA
        ).values_list("cama_id", flat=True)

        return (
            modelosServicio.Cama.objects
            .filter(numero_cama__in=camas_disponibles_ids)
            .select_related("sala")
            .order_by("numero_cama")
        )
    

    @staticmethod
    def obtener_salas_activas():
        salas = modelosServicio.Sala.objects.filter(estado=1).values(
            'id',
            'nombre_sala',
            'servicio__nombre_corto'
            )  
        
        return list(salas)
    

    @staticmethod
    def obtener_zonas():
        zonas = modelosServicio.Zona.objects.filter(estado=True).values('codigo', 'nombre_zona')
        return list(zonas)
    

    @staticmethod
    def obtener_servicios():
        """Obtiene los Departamentos incluso los inactivos"""
        servicios = modelosServicio.Servicio.objects.all().values('id', 'nombre_servicio')
        return list(servicios)
    
    @staticmethod
    def obtener_servicios_aux_activas():
        """Obtiene los Departamentos incluso los inactivos"""
        servicios_aux = modelosServicio.ServiciosAux.objects.filter(estado=1).values('id', 'nombre_servicio_a')
        return list(servicios_aux)
    

    @staticmethod
    def obtener_especialidades_activas_servicio(idServicio=0):
        """Obtiene las especialidades activas de un servicio específico."""
        if idServicio == 0:
            salas = modelosServicio.Especialidad.objects.filter(estado=1).values(
                'id',
                'nombre_especialidad',
                'servicio__nombre_corto'
            )
        else:
            # Filtramos por el servicio específico
            salas = modelosServicio.Especialidad.objects.filter(estado=1,servicio_id=idServicio).values(
            'id',
            'nombre_especialidad',
            'servicio__nombre_corto'
            )  
        
        return list(salas)


    @staticmethod
    def obtener_sala_id(idSala):
        try:
            sala = modelosServicio.Sala.objects.get(estado=1, id=idSala)
            return sala
        except modelosServicio.Sala.DoesNotExist:
            return None
    

    @staticmethod
    def obtener_especialidad_id(idEspecialidad):
        try:
            especialidad = modelosServicio.Especialidad.objects.get(estado=1, id=idEspecialidad)
            return especialidad
        except modelosServicio.Especialidad.DoesNotExist:
            return None
    

    @staticmethod
    def cambiar_zona(request, data):
        try:
            zona_id = data.get('zona')

            if not zona_id:
                return None

            with transaction.atomic():
                nueva_zona = modelosServicio.Zona.objects.get(codigo=zona_id)

                # Actualizar la sesión del usuario
                request.session['zona_codigo'] = nueva_zona.codigo
                request.session['zona_nombre_zona'] = nueva_zona.nombre_zona
                return nueva_zona

        except modelosServicio.Zona.DoesNotExist:
            raise Exception("La zona no existe.")
        except Exception as e:
            raise e
        
    """
    sirve las depencias posibeles para (Evalucion Rx, Referecina)
    ojo a la variable que excluye ciertas salas
    """
    @staticmethod    
    def obtener_dependencias(incluir_externo=True, solo_emergencia=False):


        salas_excluidas = SALAS_EXCLUIDAS

        serv_auxiliares_externos = [] if incluir_externo else SERVICIOS_AUX_EXTERNOS

        def _especialidades_por_servicio(servicio_id, tipo):
            return (
                modelosServicio.Especialidad.objects
                .filter(estado=1, servicio_id=servicio_id)
                .annotate(
                    tipo=Value(tipo, output_field=CharField()),
                    nombre=F('nombre_especialidad'),
                    origen=Value('ESPECIALIDAD', output_field=CharField()),
                    clave=Concat(Value('E-'), F('id'), output_field=CharField())
                )
                .values('clave', 'nombre', 'tipo', 'origen')
            )

        # Salas hospitalarias activas (excluyendo las no seleccionables)
        salas = (
            modelosServicio.Sala.objects
            .filter(estado=1)
            .exclude(id__in=salas_excluidas)
            .annotate(
                tipo=Value('HOSP', output_field=CharField()),
                nombre=F('nombre_sala'),
                origen=Value('SALA', output_field=CharField()),
                clave=Concat(Value('S-'), F('id'), output_field=CharField())
            )
            .values('clave', 'nombre', 'tipo', 'origen')
        )

        especialidades = []

        # Especialidades emergencia servicio 1000 emercia
        especialidades.append(_especialidades_por_servicio(1000, 'EMERG'))

        if not solo_emergencia:
            # Especialidades servicio 50 consulta externa
            especialidades.append(_especialidades_por_servicio(50, 'CEXT'))

            # Especialidades emergencia servicio 700 obstetricia
            especialidades.append(_especialidades_por_servicio(700, 'OBS'))

        # Servicios auxiliares todos los activos 
        servicios = (modelosServicio.ServiciosAux.objects
                    .filter(estado=1)
                    .exclude(id__in=serv_auxiliares_externos)
                    .annotate(
                        tipo=Value('SAUX', output_field=CharField()),
                        nombre=F('nombre_servicio_a'),
                        origen=Value('SERVICIO AUXILIAR', output_field=CharField()),
                        clave=Concat(Value('A-'), F('id'), output_field=CharField())
                    )
                    .values('clave', 'nombre', 'tipo', 'origen')
        )

        # Unir todas las listas
        especialidades = list(chain(*especialidades))
        dependencias = list(chain(salas, especialidades, servicios))

        return dependencias
    


    @staticmethod
    def obtener_dependencia_y_campo(clave):
        if not clave or '-' not in clave:
            raise ValidationError("Clave inválida")

        prefijo, pk = clave.split('-', 1)

        try:
            pk = int(pk)
        except ValueError:
            raise ValidationError("ID inválido")

        if prefijo == 'S':
            obj = modelosServicio.Sala.objects.filter(id=pk, estado=1).first()
            if not obj:
                raise ValidationError("Sala no encontrada.")
            return obj, 'sala'

        elif prefijo == 'E':
            obj = modelosServicio.Especialidad.objects.filter(id=pk, estado=1).first()
            if not obj:
                raise ValidationError("Especialidad no encontrada.")
            return obj, 'especialidad'

        elif prefijo == 'A':
            obj = modelosServicio.ServiciosAux.objects.filter(id=pk, estado=1).first()
            if not obj:
                raise ValidationError("Servicio auxiliar no encontrado.")
            return obj, 'servicio_auxiliar'

        else:
            raise ValidationError("Prefijo no reconocido.")
        

    @staticmethod
    def encontrar_dependencia_en_instance(instance, prefijo=""):
        """
        prefijo = "" → sala
        prefijo = "area_refiere_" → area_refiere_sala
        """

        sala = getattr(instance, f"{prefijo}sala", None)
        especialidad = getattr(instance, f"{prefijo}especialidad", None)
        servicio_aux = getattr(instance, f"{prefijo}servicio_auxiliar", None)

        if sala:
            return {
                "clave": f"S-{sala.id}",
                "nombre": sala.nombre_sala,
                "tipo": "HOSP"
            }

        elif especialidad:
            return {
                "clave": f"E-{especialidad.id}",
                "nombre": especialidad.nombre_especialidad,
                "tipo": "CEXT"  # lo dejamos así por ahora ✔️
            }

        elif servicio_aux:
            return {
                "clave": f"A-{servicio_aux.id}",
                "nombre": servicio_aux.nombre_servicio_a,
                "tipo": "SAUX"
            }

        return None