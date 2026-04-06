from django.contrib import admin
from servicio.models import Zona, Servicio, Sala, Cama, Especialidad, ServiciosAux, Proveedor_salud, Nivel_complejidad_institucional, Gestor, Institucion_salud

class ZonaAdmin(admin.ModelAdmin):
    list_display = ('codigo','nombre_zona', 'estado')
    search_fields = ('codigo','nombre_zona')


class ServicioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_servicio', 'estado', 'fecha_creado', 'fecha_modificado')
    search_fields = ('nombre_servicio',)
    list_filter = ('estado',)
    readonly_fields = ('fecha_creado', 'fecha_modificado')

class SalaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_sala', 'sexo_esperado', 'edad_minima_meses', 'edad_maxima_meses', 'estado', 'servicio', 'fecha_creado', 'fecha_modificado')
    search_fields = ('nombre_sala', 'servicio__nombre_servicio')
    list_filter = ('estado', 'sexo_esperado', 'servicio')
    readonly_fields = ('fecha_creado', 'fecha_modificado')


from django.contrib import admin
from .models import Cubiculo, Cama


class CamaInline(admin.TabularInline):
    model = Cama
    extra = 0
    fields = ('numero_cama', 'estado', 'sala')
    readonly_fields = ('numero_cama',)
    show_change_link = True


@admin.register(Cubiculo)
class CubiculoAdmin(admin.ModelAdmin):
    list_display = (
        'numero',
        'nombre_cubiculo',
        'sala',
        'estado',
        'total_camas'
    )

    search_fields = (
        'numero',
        'nombre_cubiculo',
        'sala__nombre_sala'
    )

    list_filter = (
        'estado',
        'sala'
    )

    ordering = ('sala', 'numero')

    inlines = [CamaInline]

    # Conteo de camas por cubiculo
    def total_camas(self, obj):
        return obj.camas.count()
    total_camas.short_description = "Camas"

    # Validacion opcional 
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Asegurar coherencia: todas las camas del cubiculo tengan la misma sala
        for cama in obj.camas.all():
            if cama.sala != obj.sala:
                cama.sala = obj.sala
                cama.save()

                

class CamaAdmin(admin.ModelAdmin):
    list_display = ('numero_cama', 'estado','cubiculo', 'sala', 'fecha_creado', 'fecha_modificado')
    search_fields = ('numero_cama', 'sala__nombre_sala')
    list_filter = ('estado','cubiculo', 'sala')
    readonly_fields = ('fecha_creado', 'fecha_modificado')

class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ('nombre_especialidad', 'servicio_nombre', 'estado')
    search_fields = ('nombre_especialidad', 'servicio__nombre_servicio')
    list_filter = ('estado', 'servicio')

    def servicio_nombre(self, obj):
        return obj.servicio.nombre_servicio
    servicio_nombre.short_description = 'Servicio'

class ServicioAuxAdmin(admin.ModelAdmin):
    list_display = ('nombre_servicio_a', 'estado')
    search_fields = ('nombre_servicio_a',)
    list_filter = ('estado',)

class ProveedorSaludAdmin(admin.ModelAdmin):
    list_display= ('nombre_proveedor_salud','estado')
    search_fields = ('nombre_proveedor_salud',)
    list_filter = ('estado',)

class NivelComplejidadInstitucionalAdmin(admin.ModelAdmin):
    list_display= ('nivel_complejidad','detalle_nivel_complejidad','siglas','estado')
    search_fields = ('nivel_complejidad','detalle_nivel_complejidad',)
    list_filter = ('estado',)

class GestorAdmin(admin.ModelAdmin):
    list_display = ('nombre_gestor','detalle_gestor','estado')
    search_fields = ('nombre_gestor',)
    list_filter = ('estado',)


class InstitucionSaludAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_sesal',
        'nombre_institucion_salud',
        'mostrar_proveedor_salud',
        'mostrar_nivel_complejidad',
        'mostrar_gestor',
        'nivel_atencion',
        'centralizado',
        'estado'
    )
    
    search_fields = ('id', 'codigo_sesal', 'nombre_institucion_salud')
    list_filter = (
        'estado',
        'nivel_atencion',
        'proveedor_salud',
        'nivel_complejidad_institucional',
        'centralizado',
        'gestor'
    )
    
    autocomplete_fields = ('direccion',)
    readonly_fields = ('fecha_creado', 'fecha_modificado', 'creado_por', 'modificado_por')
    
    # Evita consultas adicionales por cada ForeignKey al mostrar list_display
    list_select_related = ('proveedor_salud', 'nivel_complejidad_institucional', 'gestor')
    
    def mostrar_proveedor_salud(self, obj):
        return obj.proveedor_salud.nombre_proveedor_salud
    mostrar_proveedor_salud.short_description = 'Proveedor de Salud'
    
    def mostrar_nivel_complejidad(self, obj):
        return obj.nivel_complejidad_institucional.detalle_nivel_complejidad
    mostrar_nivel_complejidad.short_description = 'Nivel Complejidad'
    
    def mostrar_gestor(self, obj):
        return obj.gestor.nombre_gestor if obj.gestor else '-'
    mostrar_gestor.short_description = 'Gestor'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)

        
# Registro de modelos en la interfaz de administración
admin.site.register(Servicio, ServicioAdmin)
admin.site.register(Sala, SalaAdmin)
admin.site.register(Cama, CamaAdmin)
admin.site.register(Zona,ZonaAdmin)
admin.site.register(ServiciosAux, ServicioAuxAdmin)
admin.site.register(Especialidad, EspecialidadAdmin)

#referenciaa

admin.site.register(Proveedor_salud,ProveedorSaludAdmin)
admin.site.register(Nivel_complejidad_institucional,NivelComplejidadInstitucionalAdmin)
admin.site.register(Gestor, GestorAdmin)
admin.site.register(Institucion_salud,InstitucionSaludAdmin)