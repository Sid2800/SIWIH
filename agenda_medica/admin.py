from django.contrib import admin

from agenda_medica.models import (
    Periodo_laboral,
    Dia_laboral,
    Configuracion_cupo,
    Cupo_agenda,
    Ausencia,
    Dia_quirurgico
)

from rrhh.models import PersonalSalud


class CupoAtencionInline(admin.TabularInline):
    model = Configuracion_cupo
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
            return queryset.filter(
                personal_salud_id=self.value()
            )
        return queryset


class PeriodoLaboralAdmin(admin.ModelAdmin):

    list_display = (
        'personal_salud',
        'fecha_inicio',
        'fecha_fin',
        'jornada_laboral',
        'estado'
    )

    search_fields = (
        'personal_salud__empleado__primer_nombre',
        'personal_salud__empleado__primer_apellido',
        'personal_salud__especialidad__nombre_especialidad'
    )

    list_filter = (
        'estado',
        PersonalSaludConPeriodosFilter
    )

    autocomplete_fields = (
        'personal_salud',
        'jornada_laboral'
    )

    readonly_fields = (
        'fecha_creado',
        'creado_por',
        'fecha_modificado',
        'modificado_por'
    )

    ordering = ('-fecha_inicio',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user

        obj.modificado_por = request.user
        super().save_model(
            request,
            obj,
            form,
            change
        )


class DiaLaboralAdmin(admin.ModelAdmin):
    list_display = (
        'periodo_laboral',
        'dia_semana',
        'hora_inicio',
        'hora_fin',
        'estado'
    )

    list_filter = (
        'dia_semana',
        'estado'
    )

    search_fields = (
        'periodo_laboral__personal_salud__empleado__primer_nombre',
        'periodo_laboral__personal_salud__especialidad__nombre_especialidad',
        'dia_semana'
    )

    autocomplete_fields = (
        'periodo_laboral',
    )

    inlines = [CupoAtencionInline]

    ordering = (
        'periodo_laboral',
        'dia_semana'
    )


class ConfiguracionCupoAdmin(admin.ModelAdmin):

    list_display = (
        'dia_laboral',
        'tipo_atencion',
        'orden',
        'cupos',
        'duracion_minutos',
        'estado'
    )

    list_filter = (
        'estado',
        'tipo_atencion'
    )

    search_fields = (
        'dia_laboral__periodo_laboral__personal_salud__empleado__primer_nombre',
        'dia_laboral__periodo_laboral__personal_salud__especialidad__nombre_especialidad'
    )

    autocomplete_fields = (
        'dia_laboral',
        'tipo_atencion'
    )

    ordering = ('dia_laboral',)


class CupoAgendaAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'personal_salud',
        'tipo_atencion',
        'fecha',
        'hora_inicio',
        'hora_fin',
        'estado',
    )

    list_filter = (
        'estado',
        'tipo_atencion',
        'fecha',
    )

    search_fields = (
        'id',
        'personal_salud__empleado__primer_nombre',
        'personal_salud__empleado__primer_apellido',
        'personal_salud__especialidad__nombre_especialidad',
        'tipo_atencion__nombre_tipo_atencion',
    )

    autocomplete_fields = (
        'personal_salud',
        'configuracion_cupo',
        'tipo_atencion',
        'ausencia',
    )

    readonly_fields = (
        'fecha_creado',
        'creado_por',
        'fecha_modificado',
        'modificado_por',
    )

    ordering = (
        '-fecha',
        'hora_inicio',
    )

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return queryset.select_related(
            'personal_salud',
            'personal_salud__empleado',
            'personal_salud__especialidad',
            'configuracion_cupo',
            'tipo_atencion',
            'ausencia',
            'creado_por',
            'modificado_por',
        )

    def save_model(self, request, obj, form, change):

        if not obj.pk:
            obj.creado_por = request.user

        obj.modificado_por = request.user

        super().save_model(
            request,
            obj,
            form,
            change
        )

class AusenciaAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'personal_salud',
        'fecha_inicio',
        'fecha_fin',
        'tipo',
        'estado',
    )

    list_filter = (
        'tipo',
        'estado',
        'fecha_inicio',
        'fecha_fin',
    )

    search_fields = (
        'personal_salud__empleado__primer_nombre',
        'personal_salud__empleado__primer_apellido',
        'personal_salud__especialidad__nombre_especialidad',
        'observaciones',
    )

    autocomplete_fields = (
        'personal_salud',
        'creado_por',
        'modificado_por',
    )

    readonly_fields = (
        'fecha_creado',
        'creado_por',
        'fecha_modificado',
        'modificado_por',
    )

    ordering = (
        '-fecha_inicio',
    )

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return queryset.select_related(
            'personal_salud',
            'personal_salud__empleado',
            'personal_salud__especialidad',
            'creado_por',
            'modificado_por',
        )

    def save_model(self, request, obj, form, change):

        if not obj.pk:
            obj.creado_por = request.user

        obj.modificado_por = request.user

        super().save_model(
            request,
            obj,
            form,
            change
        )


class DiaQuirurgicoAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'dia_laboral',
        'estado',
    )

    list_filter = (
        'estado',
        'dia_laboral__dia_semana',
    )

    search_fields = (
        'dia_laboral__periodo_laboral__personal_salud__empleado__primer_nombre',
        'dia_laboral__periodo_laboral__personal_salud__empleado__primer_apellido',
    )

    autocomplete_fields = (
        'dia_laboral',
        'creado_por',
        'modificado_por',
    )

    readonly_fields = (
        'fecha_creado',
        'creado_por',
        'fecha_modificado',
        'modificado_por',
    )

    ordering = (
        'dia_laboral__periodo_laboral',
        'dia_laboral__dia_semana',
    )

    def get_queryset(self, request):

        queryset = super().get_queryset(request)

        return queryset.select_related(
            'dia_laboral',
            'dia_laboral__periodo_laboral',
            'dia_laboral__periodo_laboral__personal_salud',
            'dia_laboral__periodo_laboral__personal_salud__empleado',
            'creado_por',
            'modificado_por',
        )

    def save_model(self, request, obj, form, change):

        if not obj.pk:
            obj.creado_por = request.user

        obj.modificado_por = request.user

        super().save_model(
            request,
            obj,
            form,
            change
        )



admin.site.register(Dia_quirurgico, DiaQuirurgicoAdmin)

admin.site.register(Periodo_laboral, PeriodoLaboralAdmin)
admin.site.register(Dia_laboral, DiaLaboralAdmin)
admin.site.register(Configuracion_cupo, ConfiguracionCupoAdmin)
admin.site.register(Cupo_agenda, CupoAgendaAdmin)
admin.site.register(Ausencia, AusenciaAdmin)
