from django.contrib import admin
from .models import (
    MotivoSolicitud, EstadoSolicitud, EstadoExpedienteFisico,
    ExpedientePrestamo, SolicitudPrestamo, ExpedienteEstadoLog
)


@admin.register(MotivoSolicitud)
class MotivoSolicitudAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)
    list_editable = ('activo',)


@admin.register(EstadoSolicitud)
class EstadoSolicitudAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')


@admin.register(EstadoExpedienteFisico)
class EstadoExpedienteFisicoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre')
    search_fields = ('codigo', 'nombre')


@admin.register(ExpedientePrestamo)
class ExpedientePrestamoAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'estado', 'ubicacion_fisica')
    list_filter = ('estado',)
    search_fields = ('expediente__numero',)


@admin.register(SolicitudPrestamo)
class SolicitudPrestamoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'estado_flujo', 'fecha_creacion')
    list_filter = ('estado_flujo', 'fecha_creacion')
    search_fields = ('id', 'usuario__username')


@admin.register(ExpedienteEstadoLog)
class ExpedienteEstadoLogAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'expediente', 'estado_anterior', 'estado_nuevo', 'usuario')
    list_filter = ('estado_nuevo', 'fecha')
    search_fields = ('expediente__numero', 'usuario__username')
    readonly_fields = ('fecha', 'expediente', 'estado_anterior', 'estado_nuevo', 'usuario', 'solicitud', 'observacion')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
