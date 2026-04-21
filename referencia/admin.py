from django.contrib import admin
from referencia.models import Motivo_envio, Referencia_diagnostico,Referencia, Referencia_especialidad, Respuesta_Area_Capta, Respuesta, SeguimientoTic


# Register your models here.
class MotivoAdmin(admin.ModelAdmin):
    list_display = ('id','nombre_motivo_envio','estado',)
    search_fields = ('nombre_motivo_envio',)
    list_filter = ('estado',)


class ReferenciaDiagnosticoInline(admin.TabularInline):
    model = Referencia_diagnostico
    extra = 1
    autocomplete_fields = ['diagnostico'] 

class ReferenciaAdmin(admin.ModelAdmin):
    list_display = ('fecha_elaboracion','fecha_recepcion','paciente','tipo','motivo','institucion_origen__gestor__nombre_gestor')
    autocomplete_fields = ['paciente','institucion_origen','institucion_destino'] 
    search_fields = ('id','paciente__primer_nombre', 'paciente__primer_apellido','institucion_origen__nombre_institucion_salud','institucion_destino__nombre_institucion_salud')
    list_filter = ('tipo', 'motivo', 'atencion_requerida','elaborada_por','oportuna','justificada','estado','institucion_origen__gestor','institucion_origen__proveedor_salud','especialidad_destino__nombre_referencia_especialidad',)
    readonly_fields = ('fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')
    inlines = [ReferenciaDiagnosticoInline]  

    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('paciente', 'institucion_origen', 'institucion_destino', 'motivo', 'elaborada_por', 'creado_por', 'modificado_por')  # Optimizamos las consultas


    def paciente(self, obj):
        return f"{obj.paciente.primer_nombre} {obj.paciente.primer_apellido}"  # Mostrar nombre completo del paciente relacionado
    paciente.short_description = 'Paciente'

class ReferenciaEspecialidadAdmin(admin.ModelAdmin):
    list_display = ('nombre_referencia_especialidad','estado',)
    search_fields = ('nombre_referencia_especialidad',)
    list_filter = ('estado',)

class RespuestaAreaCaptaAdmin(admin.ModelAdmin):
    list_display = ('nombre_area', 'estado',)
    search_fields = ('nombre_area',)
    list_filter = ('estado',)


class SeguimientoTicAdmin(admin.ModelAdmin):
    list_display = (
        'referencia',
        'paciente',
        'metodo_comunicacion',
        'establece_comunicacion',
        'asistio_referencia',
        'fuente_info',
        'condicion_paciente',
        'fecha_registro',
        'creado_por',
    )

    # Autocomplete para relaciones
    autocomplete_fields = ['referencia', 'condicion_paciente']

    # Búsqueda por ID de referencia y nombre/apellidos del paciente
    search_fields = (
        'referencia__id',
        'referencia__paciente__dni',
        'referencia__paciente__primer_nombre',
        'referencia__paciente__primer_apellido'
    )

    # Filtros para trabajo administrativo
    list_filter = (
        'metodo_comunicacion',
        'establece_comunicacion',
        'asistio_referencia',
        'fuente_info',
        'condicion_paciente',
        'fecha_registro',
    )

    readonly_fields = ('fecha_registro', 'creado_por')

    # Para mostrar la columna paciente fácilmente
    def paciente(self, obj):
        return f"{obj.referencia.paciente}"
    paciente.admin_order_field = 'referencia__paciente'
    paciente.short_description = "Paciente"

    # Guardar usuario creador
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # Optimizar consultas
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('referencia', 'referencia__paciente', 'condicion_paciente', 'creado_por')



class RespuestaAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_elaboracion',
        'fecha_atencion',
        'referencia',
        'paciente',
        'tipo',
        'motivo',
        'atencion_requerida',
        'elaborada_por',
    )

    autocomplete_fields = [
        'referencia',
        'area_capta',
        'area_reponde_sala',
        'area_reponde_area_atencion',
        'area_reponde_servicio_auxiliar',
        'area_seguimiento_area_atencion',
        'institucion_destino',
        'elaborada_por',
        'motivo',
    ]

    search_fields = (
        'id',
        'referencia__paciente__primer_nombre',
        'referencia__paciente__primer_apellido',
        'referencia__institucion_origen__nombre_institucion_salud',
        'referencia__institucion_destino__nombre_institucion_salud',
    )

    list_filter = (
        'motivo',
        'atencion_requerida',
        'elaborada_por',
        'area_capta',
        'area_reponde_area_atencion',
        'fecha_elaboracion',
    )

    readonly_fields = ('fecha_elaboracion',)

    def save_model(self, request, obj, form, change):
        # Registrar usuario creador y modificador
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'referencia__paciente',
            'referencia__institucion_origen',
            'referencia__institucion_destino',
            'area_capta',
            'area_reponde_sala',
            'area_reponde_area_atencion',
            'area_reponde_servicio_auxiliar',
            'elaborada_por',
            'motivo',
        )

    def paciente(self, obj):
        return f"{obj.referencia.paciente.primer_nombre} {obj.referencia.paciente.primer_apellido}"
    paciente.short_description = 'Paciente'

    def tipo(self, obj):
        return dict(obj.referencia._meta.get_field('tipo').choices).get(obj.referencia.tipo, 'Desconocido')
    tipo.short_description = 'Tipo'


admin.site.register(Respuesta, RespuestaAdmin)






admin.site.register(Motivo_envio, MotivoAdmin)
admin.site.register(Referencia, ReferenciaAdmin)
admin.site.register(Referencia_especialidad, ReferenciaEspecialidadAdmin)
admin.site.register(SeguimientoTic, SeguimientoTicAdmin)
admin.site.register(Respuesta_Area_Capta, RespuestaAreaCaptaAdmin)