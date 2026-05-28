from clinico import models as modelosClinico
from django.db import transaction
from django.db.models import Case, When, Value, CharField
from core.constants.choices_constants import PrioridadAtencion

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
    
    @staticmethod
    def obtener_tipos_atencion():

        tipos = (
            modelosClinico.Tipo_atencion.objects
            .filter(estado=1)
            .annotate(
                prioridad_texto=Case(
                    When(
                        prioridad=PrioridadAtencion.ORDINARIA,
                        then=Value(PrioridadAtencion.ORDINARIA.label)
                    ),
                    When(
                        prioridad=PrioridadAtencion.PREFERENTE,
                        then=Value(PrioridadAtencion.PREFERENTE.label)
                    ),
                    default=Value(""),
                    output_field=CharField()
                )
            )
            .values(
                "id",
                "nombre_tipo_atencion",
                "nombre_corto_tipo_atencion",
                "prioridad",
                "prioridad_texto",
            )
        )

        return list(tipos)

