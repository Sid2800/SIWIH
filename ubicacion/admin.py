from django.contrib import admin
from .models import Departamento, Municipio, Sector, Aldea

# Register your models here.


class DeptoAdmin(admin.ModelAdmin):
   list_display=('nombre_departamento',)
   readonly_fields = ('created', 'updated')
   search_fields = ('nombre_departamento',)

class MuniAdmin(admin.ModelAdmin):
   list_display=('nombre_municipio','nombre_departamento')
   readonly_fields = ('created', 'updated')
   search_fields = ('nombre_municipio','departamento__nombre_departamento')
   list_filter = ('departamento__nombre_departamento',)

   def nombre_departamento(self,obj):
      return obj.departamento.nombre_departamento
   #en lugar de que la columna aparezca con el nombre de la función (nombre_departamento), se mostrará como "Departamento"
   nombre_departamento.short_description = 'Departamento'

class AldeaAdmin(admin.ModelAdmin):
   list_display=('nombre_aldea','municipio')
   readonly_fields = ('created', 'updated')
   search_fields = ('nombre_aldea',)

class SectorAdmin(admin.ModelAdmin):
   list_display=('id','sectorConcatenada')
   readonly_fields = ('created', 'updated')
   autocomplete_fields = ["aldea"] 
   search_fields = ('id','aldea__municipio__nombre_municipio','aldea__municipio__departamento__nombre_departamento','nombre_sector')
   list_filter = ('aldea__municipio__departamento__nombre_departamento',)

   def sectorConcatenada(self,obj):
      return f"{obj.aldea.municipio.departamento.nombre_departamento}, {obj.aldea.municipio.nombre_municipio}, {obj.nombre_sector} " 

   sectorConcatenada.short_description = 'Ubicacion'


admin.site.register(Departamento,DeptoAdmin)
admin.site.register(Municipio,MuniAdmin)
admin.site.register(Sector,SectorAdmin)
admin.site.register(Aldea, AldeaAdmin)