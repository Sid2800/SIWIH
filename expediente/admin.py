from django.contrib import admin
from .models import *

# Registro de modelos en el admin de Django


class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'get_paciente', 'get_ubicacion_actual','estado')
    search_fields = ('numero',)
    list_filter = ('estado','ubicacion') 
    readonly_fields = ('fecha_creado', 'fecha_modificado')

    def get_paciente(self, obj):
        asignacion = PacienteAsignacion.objects.filter(expediente=obj,estado='1').first()  # Filtra por estado 'activo' y el expediente actual

        if asignacion:
            paciente = asignacion.paciente
            return f"{paciente.primer_nombre or ''} {paciente.primer_apellido or ''}".strip()
        return "No asignado"  # Si no hay asignación activa, mostramos un texto alternativo
    get_paciente.short_description = 'Paciente'


    def get_ubicacion_actual(self, obj):
        ubicacion = obj.ubicacion

        if ubicacion:
            return ubicacion.descripcion

        return "Sin ubicación"

    get_ubicacion_actual.short_description = "Ubicación"


class PacienteAsignacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_paciente', 'expediente', 'estado', 'fecha_asignacion')
    search_fields = ('paciente__primer_nombre', 'paciente__primer_apellido', 'paciente__dni', 'expediente__numero')
    list_filter = ('estado', 'expediente') 

    def get_paciente(self, obj):
        # Maneja correctamente el caso en que el paciente no tiene nombre o apellido
        return f"{obj.paciente.primer_nombre or ''} {obj.paciente.primer_apellido or ''}".strip()
    get_paciente.short_description = 'Paciente'


class ExpedienteUbicacionAdmin(admin.ModelAdmin):
    """
    Admin del catálogo unificado de ubicaciones.
    Muestra la descripción resuelta en vivo (clínica o no clínica).
    """
    list_display = ('id', 'get_descripcion', 'get_tipo', 'estado')
    list_filter = ('tipo', 'estado')
    raw_id_fields = ('unidad_clinica', 'unidad_no_clinica')

    def get_descripcion(self, obj):
        return obj.descripcion
    get_descripcion.short_description = 'Ubicación'

    def get_tipo(self, obj):
        return obj.get_tipo_display()
    get_tipo.short_description = 'Tipo'


# Registro de modelos en la interfaz de administración
admin.site.register(Expediente, ExpedienteAdmin)
admin.site.register(PacienteAsignacion, PacienteAsignacionAdmin)
admin.site.register(ExpedienteUbicacion, ExpedienteUbicacionAdmin)
