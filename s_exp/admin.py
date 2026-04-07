from django.contrib import admin
from .models import (
    MotivoSolicitud,
    ExpedientePrestamo,
    SolicitudPrestamo,
    SolicitudExpedienteDetalle,
    Prestamo,
    Devolucion,
    LogHistorico,
)


# ============================================
# Base: Deshabilitar eliminación en modelos operativos
# ============================================
class NoDeleteModelAdmin(admin.ModelAdmin):
    """Base para modelos operativos: prohíbe eliminación."""
    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


# ============================================
# CATÁLOGO: Motivos (CRUD completo para admin)
# ============================================
@admin.register(MotivoSolicitud)
class MotivoSolicitudAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    list_editable = ('activo',)


# ============================================
# MODELOS OPERATIVOS (sin eliminación)
# ============================================
@admin.register(ExpedientePrestamo)
class ExpedientePrestamoAdmin(NoDeleteModelAdmin):
    list_display = ('expediente', 'estado', 'ubicacion_fisica')
    list_filter = ('estado',)
    search_fields = ('expediente__numero',)


class SolicitudExpedienteDetalleInline(admin.TabularInline):
    model = SolicitudExpedienteDetalle
    extra = 0
    readonly_fields = ('expediente_prestamo', 'paciente_identidad', 'paciente_nombre', 'numero_expediente', 'devuelto')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SolicitudPrestamo)
class SolicitudPrestamoAdmin(NoDeleteModelAdmin):
    list_display = ('id', 'usuario', 'motivo', 'estado_flujo', 'area_destino', 'fecha_creacion')
    list_filter = ('estado_flujo', 'motivo')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')
    readonly_fields = ('fecha_creacion',)
    inlines = [SolicitudExpedienteDetalleInline]


@admin.register(Prestamo)
class PrestamoAdmin(NoDeleteModelAdmin):
    list_display = ('id', 'solicitud', 'estado', 'admin_aprobador', 'fecha_aprobacion', 'fecha_limite')
    list_filter = ('estado',)
    readonly_fields = ('fecha_aprobacion',)


@admin.register(Devolucion)
class DevolucionAdmin(NoDeleteModelAdmin):
    list_display = ('id', 'prestamo', 'estado', 'cantidad_recibida', 'fecha_devolucion')
    list_filter = ('estado',)
    readonly_fields = ('fecha_devolucion',)


@admin.register(LogHistorico)
class LogHistoricoAdmin(NoDeleteModelAdmin):
    list_display = ('timestamp', 'accion', 'usuario', 'objeto_tipo', 'objeto_id')
    list_filter = ('accion', 'objeto_tipo')
    search_fields = ('usuario__username', 'detalle')
    readonly_fields = ('timestamp', 'accion', 'usuario', 'detalle', 'objeto_tipo', 'objeto_id')

    def has_add_permission(self, request):
        return False
