from clinico import models as modelosClinico
from django.db import transaction

class ClinicoService:

    @staticmethod
    def obtener_diagnosticos_activos():
        """Obtiene todos los diagnósticos activos (estado=1) como diccionarios, solo los campos necesarios."""
        diagnosticos = modelosClinico.Diagnostico.objects.filter(estado=1).values(
            'id',
            'nombre_diagnostico',
            'cie10__codigo'
        )
        return list(diagnosticos)
    

    @staticmethod
    def obtener_condiciones_activos():
        """Obtiene todos los diagnósticos activos (estado=1) como diccionarios, solo los campos necesarios."""
        condiciones = modelosClinico.Condicion_paciente.objects.filter(estado=1).values(
            'id',
            'nombre_condicion_paciente'
        )
        return list(condiciones)
    
