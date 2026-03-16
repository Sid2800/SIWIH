from django.contrib import admin
from .models import *

# Registro de modelos en el admin de Django

class LocalizacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'descripcion_localizacion',)
    search_fields = ('descripcion_localizacion',)


class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'get_paciente', 'localizacion', 'estado')
    search_fields = ('numero',)
    list_filter = ('localizacion', 'estado') 
    readonly_fields = ('fecha_creado', 'fecha_modificado')

    def get_paciente(self, obj):
        asignacion = PacienteAsignacion.objects.filter(expediente=obj,estado='1').first()  # Filtra por estado 'activo' y el expediente actual

        if asignacion:
            paciente = asignacion.paciente
            return f"{paciente.primer_nombre or ''} {paciente.primer_apellido or ''}".strip()
        return "No asignado"  # Si no hay asignación activa, mostramos un texto alternativo
    get_paciente.short_description = 'Paciente'

class PacienteAsignacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_paciente', 'expediente', 'estado', 'fecha_asignacion')
    search_fields = ('paciente__primer_nombre', 'paciente__primer_apellido', 'paciente__dni', 'expediente__numero')
    list_filter = ('estado', 'expediente') 

    def get_paciente(self, obj):
        # Maneja correctamente el caso en que el paciente no tiene nombre o apellido
        return f"{obj.paciente.primer_nombre or ''} {obj.paciente.primer_apellido or ''}".strip()
    get_paciente.short_description = 'Paciente'

# Registro de modelos en la interfaz de administración
admin.site.register(Localizacion, LocalizacionAdmin)
admin.site.register(Expediente, ExpedienteAdmin)
admin.site.register(PacienteAsignacion, PacienteAsignacionAdmin)
