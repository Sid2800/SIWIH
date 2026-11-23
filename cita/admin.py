from django.contrib import admin

from cita.models import Cita, Historial_cita


class CitaAdmin(admin.ModelAdmin):
   list_display = (
      'id',
      'paciente',
      'fecha_creado',
      'creado_por',
      'fecha_modificado',
      'modificado_por',
   )

   search_fields = (
      'paciente__numero_expediente',
      'paciente__identidad',
      'paciente__primer_nombre',
      'paciente__segundo_nombre',
      'paciente__primer_apellido',
      'paciente__segundo_apellido',
   )

   autocomplete_fields = [
      'paciente',
      'creado_por',
      'modificado_por',
   ]

   ordering = ('-fecha_creado',)

   def get_queryset(self, request):

      queryset = super().get_queryset(request)

      return queryset.select_related(
         'paciente',
         'creado_por',
         'modificado_por',
      )


class HistorialCitaAdmin(admin.ModelAdmin):

   list_display = (
      'id',
      'cita',
      'tipo_movimiento_display',
      'cupo_agenda',
      'usuario',
      'fecha_movimiento',
      'actual',
   )

   list_filter = (
      'tipo_movimiento',
      'actual',
      'fecha_movimiento',
   )

   search_fields = (
      'cita__id',
      'cita__paciente__numero_expediente',
      'cita__paciente__identidad',
      'cita__paciente__primer_nombre',
      'cita__paciente__segundo_nombre',
      'cita__paciente__primer_apellido',
      'cita__paciente__segundo_apellido',
   )

   autocomplete_fields = [
      'cita',
      'cupo_agenda',
      'usuario',
   ]

   readonly_fields = (
      'fecha_movimiento',
   )

   ordering = ('-fecha_movimiento',)

   def get_queryset(self, request):

      queryset = super().get_queryset(request)

      return queryset.select_related(
         'cita',
         'cita__paciente',
         'cupo_agenda',
         'cupo_agenda__personal_salud',
         'cupo_agenda__tipo_atencion',
         'usuario',
      )

   @admin.display(
      description='Movimiento',
      ordering='tipo_movimiento'
   )
   def tipo_movimiento_display(self, obj):

      return obj.get_tipo_movimiento_display()


admin.site.register(Cita, CitaAdmin)
admin.site.register(Historial_cita, HistorialCitaAdmin)