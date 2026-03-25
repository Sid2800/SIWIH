from django.contrib import admin
from .models import (
    ExpedientePrestamo,
    SolicitudPrestamo,
    SolicitudExpedienteDetalle,
    Prestamo,
    Devolucion,
    LogHistorico
)


# ============================================
# POLÍTICA GLOBAL: SIN ELIMINACIÓN
# ============================================
class NoDeleteModelAdmin(admin.ModelAdmin):
    """Base que deshabilita la eliminación en todos los modelos de s_exp."""

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


class SolicitudExpedienteDetalleInline(admin.TabularInline):
    model = SolicitudExpedienteDetalle
    extra = 0
    raw_id_fields = ['expediente_prestamo']
    readonly_fields = ['paciente_identidad', 'paciente_nombre', 'numero_expediente']

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExpedientePrestamo)
class ExpedientePrestamoAdmin(NoDeleteModelAdmin):
    list_display = ['expediente', 'estado', 'ubicacion_fisica']
    list_filter = ['estado']
    search_fields = ['expediente__numero']
    list_editable = ['estado', 'ubicacion_fisica']


@admin.register(SolicitudPrestamo)
class SolicitudPrestamoAdmin(NoDeleteModelAdmin):
    list_display = ['id', 'usuario', 'fecha_creacion', 'estado_flujo', 'motivo', 'area_destino']
    list_filter = ['estado_flujo', 'fecha_creacion']
    search_fields = ['usuario__username', 'motivo']
    inlines = [SolicitudExpedienteDetalleInline]


@admin.register(Prestamo)
class PrestamoAdmin(NoDeleteModelAdmin):
    list_display = ['id', 'solicitud', 'estado', 'fecha_aprobacion', 'fecha_entrega', 'fecha_limite', 'admin_aprobador']
    list_filter = ['estado', 'fecha_aprobacion']
    search_fields = ['solicitud__usuario__username']


@admin.register(Devolucion)
class DevolucionAdmin(NoDeleteModelAdmin):
    list_display = ['id', 'prestamo', 'fecha_devolucion', 'cantidad_esperada', 'cantidad_recibida', 'estado']
    list_filter = ['estado', 'fecha_devolucion']


@admin.register(LogHistorico)
class LogHistoricoAdmin(NoDeleteModelAdmin):
    list_display = ['id', 'accion', 'timestamp', 'usuario', 'objeto_tipo', 'objeto_id']
    list_filter = ['accion', 'timestamp']
    search_fields = ['usuario__username', 'detalle']
    readonly_fields = ['accion', 'timestamp', 'usuario', 'detalle', 'objeto_tipo', 'objeto_id']
