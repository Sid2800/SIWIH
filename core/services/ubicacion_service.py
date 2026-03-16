from ubicacion.models import Sector, Municipio, Aldea, Departamento
from django.db import transaction
from datetime import datetime

class UbicacionService:
    def __init__(self, ubicacion=None):
        self.ubicacion = ubicacion

    @staticmethod
    def obtener_municipios_por_departamento(departamento_id=0):
        """Obtiene los municipios relacionados a un departamento."""
        if departamento_id == 0:
            municipios = Municipio.objects.all().values('id', 'nombre_municipio')
        else:
            municipios = Municipio.objects.filter(departamento__id=departamento_id).values('id', 'nombre_municipio')
        return list(municipios)
    
    @staticmethod
    def obtener_departamentos():
        """Obtiene los departamentos porsibles"""
        departamentos = Departamento.objects.all().values('id', 'nombre_departamento')
        return list(departamentos)
    

    @staticmethod
    def obtener_sectores_por_municipio(municipio_id, query=None):
        """Filtra las ubicaciones dependiendo de un municipio y una consulta de búsqueda."""
        qs = Sector.objects.none()  # Inicializa el queryset vacío

        if municipio_id:
            qs = Sector.objects.filter(aldea__municipio_id=municipio_id)
            if query:  
                qs = qs.filter(nombre_sector__icontains=query)

        return qs
    
    @staticmethod
    def obtener_aldeas_por_municipio(municipio_id, query=None):
        """Filtra las aldeas dependiendo de un municipio y una consulta de búsqueda."""
        qs = Aldea.objects.none()  # Inicializa el queryset vacío

        if municipio_id:
            qs = Aldea.objects.filter(municipio_id=municipio_id)
            if query:  
                qs = qs.filter(nombre_aldea__icontains=query)

        return qs
    
  
    
    @staticmethod
    def obtener_detalles_domicilio(id_sector):
        """Obtiene detalles del domicilio por id."""
        try:
            lugar = Sector.objects.select_related("aldea__municipio__departamento").get(id=id_sector)
            return {
                "id_departamento": lugar.aldea.municipio.departamento.id,
                "id_municipio": lugar.aldea.municipio.id,
                "id_domicilio":lugar.id,
                "nombre_domicilio": lugar.nombre_sector,

            }
        except Sector.DoesNotExist:
            return {"error": "Lugar no encontrado"}


    @staticmethod
    def registrar_sector(data):
        """Obtiene detalles del domicilio por id."""
        try:
            zona = data.get('zona')
            aldea_id = data.get('aldea_id')
            descripcion_sector = data.get('descripcion_sector') 

            if not (zona and aldea_id and descripcion_sector):
                return None  
        
            with transaction.atomic():
                return Sector.objects.create(
                    nombre_sector = descripcion_sector,
                    aldea_id = aldea_id,
                    area_id = zona,
                    created = datetime.now(),
                    updated = datetime.now()
                )
            
                
        except Exception as e:
            return None


    
    @staticmethod
    def obtener_cadena_ubicacion_completa(paciente):
        if not paciente:
            return "Se requiere un paciente válido"

        try:
            return (
                f"{paciente.sector.nombre_sector}, "
                f"{paciente.sector.aldea.municipio.nombre_municipio}, "
                f"{paciente.sector.aldea.municipio.departamento.nombre_departamento}"
            )
        except AttributeError:
            return "Ubicación incompleta o inválida"