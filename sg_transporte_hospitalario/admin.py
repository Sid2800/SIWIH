from django.contrib import admin

from .models import Motorista, Vehiculo, Viatico


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "placa",
        "descripcion",
        "activo",
        "created_at",
        "updated_at",
    )
    list_filter = ("activo",)
    search_fields = ("codigo", "placa", "descripcion")
    ordering = ("codigo", "placa")
    list_editable = ("activo",)
    readonly_fields = ("codigo",)


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = (
        "empleado",
        "activo",
        "created_at",
        "updated_at",
    )
    list_filter = ("activo",)
    search_fields = (
        "empleado__dni",
        "empleado__primer_nombre",
        "empleado__primer_apellido",
    )
    ordering = ("empleado__primer_nombre", "empleado__primer_apellido")
    list_editable = ("activo",)
    autocomplete_fields = ("empleado",)


@admin.register(Viatico)
class ViaticoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "monto_vigente",
        "activo",
        "created_at",
        "updated_at",
    )
    list_filter = ("activo",)
    search_fields = ("codigo", "nombre")
    ordering = ("nombre", "codigo")
    list_editable = ("activo",)
    readonly_fields = ("codigo",)
