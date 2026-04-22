from django.contrib import admin
from .models import Empleado, PersonalSalud, PersonalNoClinico


class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('dni', 'nombre_completo', 'telefono', 'correo', 'estado')
    list_filter = ('estado',)
    search_fields = ('dni', 'primer_nombre', 'primer_apellido', 'usuario__username')
    autocomplete_fields = ['paciente_ref']

    def nombre_completo(self, obj):
        return f"{obj.primer_nombre} {obj.primer_apellido}"
    nombre_completo.short_description = "Nombre"


class PersonalSaludAdmin(admin.ModelAdmin):
    list_display = (
        'empleado_nombre',
        'tipo_personal',
        'area_atencion_nombre',
        'servicio_unidad_nombre',
        'puede_agendar_citas'
    )

    list_filter = (
        'tipo_personal_salud',
        'servicio_unidad__nombre_unidad',
        'puede_agendar_citas'
    )

    search_fields = (
        'empleado__primer_nombre',
        'empleado__primer_apellido',
        'empleado__dni',
        'servicio_unidad__nombre_unidad'
    )

    def empleado_nombre(self, obj):
        return obj.empleado.nombre_completo
    empleado_nombre.short_description = "Empleado"

    def tipo_personal(self, obj):
        return obj.tipo_personal_salud.nombre
    tipo_personal.short_description = "Tipo"

    def servicio_unidad_nombre(self, obj):
        return obj.servicio_unidad.nombre_unidad if obj.servicio_unidad else ""
    servicio_unidad_nombre.short_description = "Unidad"



class PersonalNoClinicoAdmin(admin.ModelAdmin):
    list_display = (
        'empleado_nombre',
        'tipo_display',
        'servicio_unidad_nombre'
    )

    list_filter = (
        'tipo',
        'servicio_unidad__nombre_unidad'
    )

    search_fields = (
        'empleado__primer_nombre',
        'empleado__primer_apellido',
        'empleado__dni',
        'servicio_unidad__nombre_unidad'
    )

    def empleado_nombre(self, obj):
        return obj.empleado.nombre_completo
    empleado_nombre.short_description = "Empleado"

    def tipo_display(self, obj):
        return obj.get_tipo_display()
    tipo_display.short_description = "Tipo"

    def servicio_unidad_nombre(self, obj):
        return obj.servicio_unidad.nombre_unidad if obj.servicio_unidad else ""
    servicio_unidad_nombre.short_description = "Unidad"


admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(PersonalSalud, PersonalSaludAdmin)
admin.site.register(PersonalNoClinico, PersonalNoClinicoAdmin)