from django.contrib import admin
from imagenologia.models import Estudio, MaquinaRX, EvaluacionRx, EvaluacionRxDetalle
from servicio.models import Sala

# Register your models here.

class EvaluacionRxDetalleInline(admin.TabularInline):
    model = EvaluacionRxDetalle
    extra = 1
    autocomplete_fields = ['estudio']



class SalaConRegistrosFilter(admin.SimpleListFilter):
    title = 'Sala'
    parameter_name = 'sala'

    def lookups(self, request, model_admin):
        # Traemos solo las salas que tienen al menos un EvaluacionRx
        salas = Sala.objects.filter(evaluacionrx__isnull=False).distinct()
        return [(s.id, s.nombre_sala) for s in salas]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(sala_id=self.value())
        return queryset


class EvaluacionRxAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'paciente', 'sala', 'area_atencion', 'servicio_auxiliar')
    search_fields = ('paciente__nombre', 'paciente__apellido')
    list_filter = ('fecha', SalaConRegistrosFilter, 'area_atencion', 'servicio_auxiliar')
    readonly_fields = ('fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')
    autocomplete_fields = ('paciente', 'sala', 'area_atencion', 'servicio_auxiliar', 'creado_por', 'modificado_por')
    inlines = [EvaluacionRxDetalleInline]  

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)


class EvaluacionRxDetalleAdmin(admin.ModelAdmin):
    list_display = ('evaluacionRx', 'estudio', 'impreso')
    search_fields = ('evaluacionRx__paciente__nombre', 'evaluacionRx__paciente__apellido', 'estudio__descripcion_estudio')
    list_filter = ('impreso', 'estudio')
    autocomplete_fields = ('evaluacionRx', 'estudio')


class EstudioAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion_estudio', 'estado')
    search_fields = ('codigo', 'descripcion_estudio',)
    list_filter = ('estado',)
    readonly_fields = ('fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)



class MaquinaRXAdmin(admin.ModelAdmin):
    list_display = ('id', 'descripcion_maquina', 'estado')
    search_fields = ('id', 'descripcion_maquina')


# Registro final
admin.site.register(Estudio, EstudioAdmin)
admin.site.register(MaquinaRX, MaquinaRXAdmin)
admin.site.register(EvaluacionRx, EvaluacionRxAdmin)
admin.site.register(EvaluacionRxDetalle, EvaluacionRxDetalleAdmin)