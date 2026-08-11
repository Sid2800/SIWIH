from django.contrib import admin

from .models import Viatico


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
