from django.contrib import admin
from atencion.models import Atencion


# Register your models here.
class AtencionAdmin(admin.ModelAdmin):
   list_display = ('paciente_nombre_completo', 'especialidad', 'fecha_atencion', 'creado_por', 'modificado_por')
   autocomplete_fields = ['paciente',]
   search_fields = ('paciente__primer_nombre', 'paciente__primer_apellido', 'especialidad__nombre_especialidad')
   list_filter = ('especialidad', 'creado_por')
   readonly_fields = ('fecha_atencion', 'fecha_creado', 'creado_por', 'fecha_modificado', 'modificado_por')

   def get_queryset(self, request):
      queryset = super().get_queryset(request)
      return queryset.select_related('paciente', 'especialidad', 'especialidad__servicio', 'creado_por', 'modificado_por')

   def paciente_nombre_completo(self, obj):
      return f"{obj.paciente.primer_nombre} {obj.paciente.primer_apellido}"
   paciente_nombre_completo.short_description = 'Paciente'


admin.site.register(Atencion, AtencionAdmin)