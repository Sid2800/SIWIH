from servicio import models as modelosServicio
from servicio.models import Institucion_salud
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
        qs = modelosServicio.Cama.objects.filter(estado=1)  # Filtramos las camas activas (estado=1)
        return qs
    

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
    def obtener_areas_atencion_activas_servicio(idServicio=0):
        """Obtiene las area_atencion activas de un servicio específico."""
        if idServicio == 0:
            salas = modelosServicio.Area_atencion.objects.filter(estado=1).values(
                'id',
                'nombre_area_atencion',
                'servicio__nombre_corto'
            )
        else:
            # Filtramos por el servicio específico
            salas = modelosServicio.Area_atencion.objects.filter(estado=1,servicio_id=idServicio).values(
            'id',
            'nombre_area_atencion',
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
    def obtener_area_atencion_id(idAreaAtencion):
        try:
            area_atencion = modelosServicio.Area_atencion.objects.get(estado=1, id=idAreaAtencion)
            return area_atencion
        except modelosServicio.Area_atencion.DoesNotExist:
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
    def obtener_unidades_clinicas(incluir_externo=True, solo_emergencia=False):
        qs = modelosServicio.Unidad_clinica.objects.filter(estado=1)

        if not incluir_externo:
            qs = qs.filter(establecimiento_ext__isnull=True)

        qs = qs.annotate(
            tipo=Value('', output_field=CharField()),  # lo ajustamos abajo
            nombre=Value('', output_field=CharField()),
            origen=Value('', output_field=CharField()),
        )

        unidades_clinicas = []


        for uc in qs.select_related(
            'area_atencion__servicio',
            'sala',
            'servicio_aux',
            'establecimiento_ext__nivel_complejidad_institucional'
        ):

            if uc.area_atencion:
                tipo = (
                    'EMERG' if uc.area_atencion.servicio_id == 1000 else
                    'OBS' if uc.area_atencion.servicio_id == 700 else
                    'CEXT' if uc.area_atencion.servicio_id == 50 else ''
                )


                # filtro solo emergencia
                if solo_emergencia and tipo not in ['EMERG', 'OBS' ]:
                    continue

                unidades_clinicas.append({
                    'clave': f"{uc.id}",
                    'nombre': uc.area_atencion.nombre_area_atencion,
                    'tipo': tipo,
                    'origen': 'AREA ATENCION'
                })

            elif uc.sala:
                unidades_clinicas.append({
                    'clave': f"{uc.id}",
                    'nombre': uc.sala.nombre_sala,
                    'tipo': 'HOSP',
                    'origen': 'SALA'
                })

            elif uc.servicio_aux:
                unidades_clinicas.append({
                    'clave': f"{uc.id}",
                    'nombre': uc.servicio_aux.nombre_servicio_a,
                    'tipo': 'SAUX',
                    'origen': 'SERVICIO AUXILIAR'
                })

            elif uc.establecimiento_ext:
                unidades_clinicas.append({
                    'clave': f"{uc.id}",
                    'nombre': f"{uc.establecimiento_ext.nivel_complejidad_institucional.siglas} | {uc.establecimiento_ext.nombre_institucion_salud}",
                    'tipo': 'EXT',
                    'origen': 'INSTITUCIÓN EXTERNA'
                })

        return unidades_clinicas


    @staticmethod
    def obtener_unidad_clinica(id):
        if not id:
            raise ValidationError("Clave invalida")


        uc = modelosServicio.Unidad_clinica.objects.select_related(
            'area_atencion',
            'sala',
            'servicio_aux',
            'establecimiento_ext'
        ).filter(id=id, estado=1).first()

        if not uc:
            raise ValidationError("Unidad clinica no encontrada.")

    
        return uc


    @staticmethod
    def encontrar_unidad_clinica_en_instance(instance):
        uc = instance.unidad_clinica

        if not uc:
            return None

        tipo_codigo, _ = uc.get_tipo_unidad()

        if uc.area_atencion:
            return {
                "clave": f"{uc.id}",
                "nombre": uc.area_atencion.nombre_area_atencion,
                "tipo": tipo_codigo
            }

        elif uc.sala:
            return {
                "clave": f"{uc.id}",
                "nombre": uc.sala.nombre_sala,
                "tipo": tipo_codigo
            }

        elif uc.servicio_aux:
            return {
                "clave": f"{uc.id}",
                "nombre": uc.servicio_aux.nombre_servicio_a,
                "tipo": tipo_codigo
            }

        elif uc.establecimiento_ext:
            return {
                "clave": f"{uc.id}",
                "nombre": uc.establecimiento_ext.nombre_institucion_salud,
                "tipo": tipo_codigo
            }

        return None