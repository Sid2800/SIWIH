from django.contrib import admin

from .models import (
   Episodio_labor_parto,
   Bebe_labor_parto,
   Movimiento_labor_parto,
)


class BebeLaborPartoInline(admin.TabularInline):
   model = Bebe_labor_parto
   extra = 1


class MovimientoLaborPartoInline(admin.TabularInline):
   model = Movimiento_labor_parto
   extra = 0
   autocomplete_fields = (
      "unidad_destino",
      "usuario",
   )
   readonly_fields = (
      "fecha_movimiento",
      "usuario",
   )


class EpisodioLaborPartoAdmin(admin.ModelAdmin):

   list_display = (
      "paciente",
      "estado_actual",
      "fecha_ingreso",
      "alta",
      "fecha_alta",
      "estado",
   )

   list_filter = (
      "estado_actual",
      "alta",
      "estado",
   )

   search_fields = (
      "paciente__primer_nombre",
      "paciente__segundo_nombre",
      "paciente__primer_apellido",
      "paciente__segundo_apellido",
      "paciente__dni",
      "paciente__expediente_numero",
   )

   autocomplete_fields = (
      "paciente",
      "unidad_entrada",
   )

   readonly_fields = (
      "fecha_creado",
      "creado_por",
      "fecha_modificado",
      "modificado_por",
   )

   inlines = [
      BebeLaborPartoInline,
      MovimientoLaborPartoInline,
   ]

   ordering = (
      "-fecha_ingreso",
   )

   def save_model(self, request, obj, form, change):
      if not obj.pk:
         obj.creado_por = request.user

      obj.modificado_por = request.user

      super().save_model(request, obj, form, change)


class BebeLaborPartoAdmin(admin.ModelAdmin):

   list_display = (
      "episodio",
      "sexo",
      "orden",
   )

   list_filter = (
      "sexo",
   )

   search_fields = (
      "episodio__paciente__primer_nombre",
      "episodio__paciente__primer_apellido",
      "episodio__paciente__dni",
      "episodio__paciente__expediente_numero",
   )

   autocomplete_fields = (
      "episodio",
   )

   ordering = (
      "episodio",
      "orden",
   )


class MovimientoLaborPartoAdmin(admin.ModelAdmin):

   list_display = (
      "episodio",
      "tipo",
      "estado_anterior",
      "estado_nuevo",
      "unidad_destino",
      "fecha_movimiento",
      "usuario",
      "estado",
   )

   list_filter = (
      "tipo",
      "estado_anterior",
      "estado_nuevo",
      "estado",
   )

   search_fields = (
      "episodio__paciente__primer_nombre",
      "episodio__paciente__primer_apellido",
      "episodio__paciente__dni",
      "episodio__paciente__expediente_numero",
   )

   autocomplete_fields = (
      "episodio",
      "unidad_destino",
      "usuario",
   )

   readonly_fields = (
      "usuario",
   )

   ordering = (
      "-fecha_movimiento",
   )

   def save_model(self, request, obj, form, change):
      if not change:
         obj.usuario = request.user

      super().save_model(request, obj, form, change)

admin.site.register(Episodio_labor_parto, EpisodioLaborPartoAdmin)
admin.site.register(Bebe_labor_parto, BebeLaborPartoAdmin)
admin.site.register(Movimiento_labor_parto, MovimientoLaborPartoAdmin)