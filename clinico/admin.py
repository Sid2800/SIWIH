from django.contrib import admin
from clinico.models import Diagnostico, CIE10, Tipo_personal_salud, Condicion_paciente, Especialidad

# Register your models here.
class CIE10Admin(admin.ModelAdmin):
    list_display = ('codigo','descripcion')
    search_fields = ('codigo','descripcion')


class DiagnosticoAdmin(admin.ModelAdmin):
    list_display = ('nombre_diagnostico','cie10_nombre','estado')
    search_fields = ('nombre_diagnostico', 'cie10__descripcion')
    autocomplete_fields = ['cie10',] 
    list_filter = ('estado',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('cie10') 
    
    @admin.display(description='CIE10', ordering='cie10__descripcion')
    def cie10_nombre(self, obj):
        return f"{obj.cie10.codigo} - {obj.cie10.descripcion}" if obj.cie10 else "Sin CIE10"

class TipoPersonalSaludAdmin(admin.ModelAdmin):
    list_display = ('id','nombre_tipo_personal','estado')
    search_fields = ('nombre_tipo_personal',)
    list_filter = ('estado',)

class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ('nombre_especialidad', 'nombre_corto_especialidad', 'estado')
    search_fields = ('nombre_especialidad', 'nombre_corto_especialidad')
    list_filter = ('estado',)
    ordering = ('nombre_especialidad',)

class CondicionPacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_condicion_paciente','estado')
    search_fields = ('nombre_condicion_paciente',)
    list_filter = ('estado',)
    


class UnidadClinicaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'tipo_unidad_label',
        'descripcion_label',
        'estado'
    )

    list_filter = ('estado',)

    search_fields = (
        'area_atencion__nombre',
        'sala__nombre_sala',
        'servicio_aux__nombre_servicio_aux',
        'establecimiento_ext__nombre',
    )

    autocomplete_fields = [
        'area_atencion',
        'sala',
        'servicio_aux',
        'establecimiento_ext'
    ]

    @admin.display(description='Tipo')
    def tipo_unidad_label(self, obj):
        return obj.get_tipo_unidad()[1]


    @admin.display(description='Descripción')
    def descripcion_label(self, obj):
        if obj.area_atencion:
            return obj.area_atencion.nombre
        if obj.sala:
            return obj.sala.nombre_sala
        if obj.servicio_aux:
            return obj.servicio_aux.nombre_servicio_aux
        if obj.establecimiento_ext:
            return obj.establecimiento_ext.nombre
        return "-"



admin.site.register(CIE10, CIE10Admin)
admin.site.register(Diagnostico,DiagnosticoAdmin)
admin.site.register(Tipo_personal_salud, TipoPersonalSaludAdmin)
admin.site.register(Especialidad, EspecialidadAdmin)
admin.site.register(Condicion_paciente,CondicionPacienteAdmin)
