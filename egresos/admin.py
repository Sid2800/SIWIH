"""Admin del módulo de Egresos (útil para gestionar catálogos y revisar datos)."""
from django.contrib import admin

from .models import (
    AreaEgreso, Procedimiento, Egreso, EgresoDiagnostico,
    LoteEgreso, LoteEgresoDetalle,
)


@admin.register(AreaEgreso)
class AreaEgresoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'orden', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('orden',)


@admin.register(Procedimiento)
class ProcedimientoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'descripcion')


class EgresoDiagnosticoInline(admin.TabularInline):
    model = EgresoDiagnostico
    extra = 0


@admin.register(Egreso)
class EgresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_egreso', 'area', 'paciente', 'numero', 'en_censo')
    list_filter = ('area', 'en_censo', 'sexo', 'condicion')
    search_fields = ('numero', 'paciente__dni', 'paciente__primer_nombre')
    date_hierarchy = 'fecha_egreso'
    inlines = [EgresoDiagnosticoInline]


class LoteEgresoDetalleInline(admin.TabularInline):
    model = LoteEgresoDetalle
    extra = 0


@admin.register(LoteEgreso)
class LoteEgresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'estado', 'usuario_estadistica', 'fecha_captura_estadistica',
                    'usuario_admision', 'fecha_captura_admision')
    list_filter = ('estado',)
    inlines = [LoteEgresoDetalleInline]
