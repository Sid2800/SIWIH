from django.contrib import admin
from .models import Unidad, PerfilUnidad

class UnidadAdmin(admin.ModelAdmin):
    list_display = ('id','nombre_unidad',)
    search_fields = ('id','nombre_unidad',)

class PerfilUnidadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'unidad_nombre', 'rol')
    list_filter = ('rol', 'unidad__nombre_unidad')
    search_fields = ('usuario__username', 'unidad__nombre_unidad', 'rol')

    def unidad_nombre(self, obj):
        return obj.unidad.nombre_unidad
    unidad_nombre.short_description = 'Unidad'

admin.site.register(Unidad, UnidadAdmin)
admin.site.register(PerfilUnidad, PerfilUnidadAdmin)
