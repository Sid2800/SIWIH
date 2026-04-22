from django.contrib import admin
from .models import PerfilUnidad

class PerfilUnidadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'servicio_unidad_nombre', 'rol', 'alcance')
    list_filter = ('rol', 'servicio_unidad__nombre_unidad', 'alcance')
    search_fields = ('usuario__username','alcance', 'servicio_unidad__nombre_unidad', 'rol')

    def servicio_unidad_nombre(self, obj):
        if not obj.servicio_unidad:
            return ""
        return obj.servicio_unidad.nombre_unidad
    servicio_unidad_nombre.short_description = 'Unidad'


admin.site.register(PerfilUnidad, PerfilUnidadAdmin)
