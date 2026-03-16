from django.contrib import admin
from .models import *

class NacionalidadAdmin(admin.ModelAdmin):
    list_display = ('descripcion_nacionalidad',)
    search_fields = ('descripcion_nacionalidad',)
    list_filter = ('estado',)

class Estado_civicAdmin(admin.ModelAdmin):
    list_display = ('descripcion_estado_civil',)
    search_fields = ('descripcion_estado_civil',)
    list_filter = ('estado',)

class OcupacionAdmin(admin.ModelAdmin):
    list_display = ('descripcion_ocupacion',)
    search_fields = ('descripcion_ocupacion',)
    list_filter = ('estado',)

class EtniaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion_etnia',)
    search_fields = ('codigo', 'descripcion_etnia',)
    list_filter = ('estado',)

class PadreAdmin(admin.ModelAdmin):
    list_display = ('dni','get_nombre_completo','tipo','paciente_ref')
    search_fields = ('dni','nombre1',)
    readonly_fields = ('fecha_creado', 'fecha_modificado')
    autocomplete_fields = ["direccion",'paciente_ref'] 
    list_filter = ('tipo',)

    def get_nombre_completo(self, obj):
        return f"{obj.nombre1} {obj.nombre2} {obj.apellido1} {obj.apellido2}"
    get_nombre_completo.short_description = 'Nombre completo'

class TipoAdmin(admin.ModelAdmin):
    list_display = ('descripcion_tipo',)
    search_fields = ('descripcion_tipo',)
    list_filter = ('estado',)

class Clasificacion_diagnosticoAdmin(admin.ModelAdmin):
    list_display = ('descripcion_clasificacion',)
    search_fields = ('descripcion_clasificacion',)
    list_filter = ('estado',)


class DefuncionAdmin(admin.ModelAdmin):
    list_display = (
        'get_dni',
        'get_nombre_completo',
        'fecha_defuncion',
        'sala',
        'motivo',
        'registrado_por',
        'fecha_registro',
    )
    search_fields = (
        'paciente__dni',
        'paciente__primer_nombre',
        'paciente__segundo_nombre',
        'paciente__primer_apellido',
        'paciente__segundo_apellido',
    )
    autocomplete_fields = ['paciente', 'sala']
    list_filter = ('fecha_defuncion', 'sala', 'registrado_por',)
    readonly_fields = ('fecha_registro',)

    def get_dni(self, obj):
        return obj.paciente.dni
    get_dni.short_description = "DNI"

    def get_nombre_completo(self, obj):
        p = obj.paciente
        return f"{p.primer_nombre} {p.segundo_nombre or ''} {p.primer_apellido} {p.segundo_apellido or ''}".strip()
    get_nombre_completo.short_description = "Nombre completo"




class PacienteAdmin(admin.ModelAdmin):
    list_display = ('dni','get_nombre_completo','fecha_nacimiento','sexo','tipo','get_direccion_completa')
    search_fields = ('dni','primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'  )
    autocomplete_fields = ['sector'] 
    list_filter = ('sexo','ocupacion','tipo','clasificacion','zona','creado_por','estado','sai', 'etnia')
    readonly_fields = ('fecha_creado', 'fecha_modificado','creado_por','modificado_por')

    def get_nombre_completo(self, obj):
        return f"{obj.primer_nombre} {obj.segundo_nombre} {obj.primer_apellido} {obj.segundo_apellido}"
    get_nombre_completo.short_description = 'Nombre completo'

    def get_direccion_completa (self, obj):
        return f"{obj.sector.aldea.municipio.departamento.nombre_departamento} {obj.sector.aldea.municipio.nombre_municipio} {obj.sector.nombre_sector}"
    get_direccion_completa.short_description = 'Direccion Completa'



admin.site.register(Nacionalidad,NacionalidadAdmin)
admin.site.register(Estado_civil,Estado_civicAdmin)
admin.site.register(Ocupacion,OcupacionAdmin)
admin.site.register(Etnia, EtniaAdmin)
admin.site.register(Padre,PadreAdmin)
admin.site.register(Tipo,TipoAdmin)
admin.site.register(Clasificacion_diagnostico, Clasificacion_diagnosticoAdmin)
admin.site.register(Defuncion, DefuncionAdmin)
admin.site.register(Paciente,PacienteAdmin)



