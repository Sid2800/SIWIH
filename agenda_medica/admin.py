from django.contrib import admin
from agenda_medica.models import Periodo_laboral, Dia_laboral, Cupo_atencion
from rrhh.models import PersonalSalud
# Register your models here.


class CupoAtencionInline(admin.TabularInline):
    model = Cupo_atencion
    extra = 1
    autocomplete_fields = ['tipo_atencion']


class PersonalSaludConPeriodosFilter(admin.SimpleListFilter):
    title = 'Personal de Salud'
    parameter_name = 'personal_salud'

    def lookups(self, request, model_admin):
        personal = (
            PersonalSalud.objects
            .filter(periodo_laboral__isnull=False)
            .distinct()
        )

        return [(p.id, str(p)) for p in personal]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(personal_salud_id=self.value())
        return queryset
    

class PeriodoLaboralAdmin(admin.ModelAdmin):
    list_display = ('personal_salud', 'fecha_inicio', 'fecha_fin', 'jornada_laboral', 'estado')
    search_fields = ('personal_salud__empleado__primer_nombre', 'personal_salud__empleado__primer_apellido', 'personal_salud__empleado__especialidad__nombre_especialidad')
    list_filter = ('estado', PersonalSaludConPeriodosFilter)
    autocomplete_fields = ('personal_salud', 'jornada_laboral')

    readonly_fields = ('fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')

    ordering = ('-fecha_inicio',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)


class DiaLaboralAdmin(admin.ModelAdmin):
    list_display = ('periodo_laboral', 'dia_semana', 'hora_inicio', 'hora_fin', 'estado')
    list_filter = ('dia_semana', 'estado')
    search_fields = ('periodo_laboral__personal_salud__empleado__primer_nombre','periodo_laboral__personal_salud__empleado__especialidad__nombre_especialidad','dia_semana')

    autocomplete_fields = ('periodo_laboral',)

    inlines = [CupoAtencionInline]

    ordering = ('periodo_laboral', 'dia_semana')

class CupoAtencionAdmin(admin.ModelAdmin):
    list_display = ('dia_laboral', 'tipo_atencion', 'cupos', 'duracion_minutos', 'estado')
    list_filter = ('estado', 'tipo_atencion')
    search_fields = (
    'dia_laboral__periodo_laboral__personal_salud__empleado__primer_nombre',
    'dia_laboral__periodo_laboral__personal_salud__empleado__especialidad__nombre_especialidad'
    )

    autocomplete_fields = ('dia_laboral', 'tipo_atencion')

    ordering = ('dia_laboral',)


admin.site.register(Periodo_laboral, PeriodoLaboralAdmin)
admin.site.register(Dia_laboral, DiaLaboralAdmin)
admin.site.register(Cupo_atencion, CupoAtencionAdmin)