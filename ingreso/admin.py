from django.contrib import admin
from .models import Acompanante, Ingreso




class AcompananteAdmin(admin.ModelAdmin):
    list_display = ('dni', 'get_nombre_completo', 'telefono')
    search_fields = ('dni', 'primer_nombre', 'primer_apellido',)


    def get_nombre_completo(self, obj):
        return f"{obj.primer_nombre} {obj.segundo_nombre} {obj.primer_apellido} {obj.segundo_apellido}"
    get_nombre_completo.short_description = 'Nombre Completo'


class IngresoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'servicioCompleto', 'cama', 'fecha_ingreso', 'fecha_egreso', 'zona')
    autocomplete_fields = ['paciente','cama','acompaniante'] 
    search_fields = ('id','paciente__primer_nombre', 'paciente__primer_apellido','sala__nombre_sala','cama__numero_cama')
    list_filter = ('sala', 'zona', 'creado_por')
    readonly_fields = ('fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('paciente', 'sala', 'cama', 'zona', 'creado_por', 'modificado_por')  # Optimizamos las consultas
    

    def paciente(self, obj):
        return f"{obj.paciente.primer_nombre} {obj.paciente.primer_apellido}"  # Mostrar nombre completo del paciente relacionado
    paciente.short_description = 'Paciente'


    def servicioCompleto(self, obj):
        return f"{obj.sala.servicio.nombre_servicio} {obj.sala.nombre_sala}"
    servicioCompleto.short_description = 'servicioCompleto'



admin.site.register(Ingreso, IngresoAdmin)
admin.site.register(Acompanante, AcompananteAdmin)