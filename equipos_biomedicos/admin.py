from django.contrib import admin

from .models import (
    AsignacionDispositivo,
    BajaDispositivo,
    Dispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    TipoDispositivo,
)


# Catalogos base del modulo. Se mantienen desde Django admin para evitar crear
# pantallas propias solo para tipo, marca y modelo.
@admin.register(TipoDispositivo)
class TipoDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(MarcaDispositivo)
class MarcaDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(ModeloDispositivo)
class ModeloDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    # Permite revisar la ficha del equipo desde admin, pero el flujo normal
    # de registro/edicion sigue estando en las vistas del modulo.
    list_display = (
        "codigo",
        "tipo",
        "tipo_tecnologia",
        "marca",
        "modelo",
        "numero_serie",
        "inventario_bienes_nacionales",
        "inventario_numero_ficha",
        "estado",
        "criticidad",
    )
    list_filter = ("tipo", "marca", "modelo", "tipo_tecnologia", "estado", "criticidad")
    search_fields = (
        "tipo__nombre",
        "marca__nombre",
        "modelo__nombre",
        "numero_serie",
        "inventario_bienes_nacionales",
        "inventario_numero_ficha",
    )
    autocomplete_fields = ("tipo", "marca", "modelo", "creado_por", "modificado_por")
    readonly_fields = ("fecha_creado", "fecha_modificado")

    def save_model(self, request, obj, form, change):
        # Auditoria: registra automaticamente que usuario creo/modifico desde admin.
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(BajaDispositivo)
class BajaDispositivoAdmin(admin.ModelAdmin):
    # Consulta administrativa de equipos dados de baja.
    list_display = (
        "dispositivo",
        "fecha_baja",
        "motivo",
        "registrado_por",
        "fecha_registro",
    )
    list_filter = ("fecha_baja", "registrado_por")
    search_fields = (
        "dispositivo__tipo__nombre",
        "dispositivo__marca__nombre",
        "dispositivo__modelo__nombre",
        "dispositivo__numero_serie",
        "dispositivo__inventario_bienes_nacionales",
        "dispositivo__inventario_numero_ficha",
        "motivo",
        "registrado_por__username",
    )
    autocomplete_fields = ("dispositivo", "registrado_por")
    readonly_fields = ("fecha_registro",)


@admin.register(AsignacionDispositivo)
class AsignacionDispositivoAdmin(admin.ModelAdmin):
    # Historial de ubicaciones y responsables del equipo.
    list_display = (
        "dispositivo",
        "ubicacion",
        "responsable",
        "fecha_inicio",
        "fecha_fin",
    )
    list_filter = ("fecha_fin", "area_clinica", "unidad_no_clinica")
    search_fields = (
        "dispositivo__tipo__nombre",
        "dispositivo__marca__nombre",
        "dispositivo__modelo__nombre",
        "dispositivo__numero_serie",
        "dispositivo__inventario_bienes_nacionales",
        "dispositivo__inventario_numero_ficha",
        "responsable__dni",
        "responsable__primer_nombre",
        "responsable__primer_apellido",
    )
    autocomplete_fields = (
        "dispositivo",
        "area_clinica",
        "unidad_no_clinica",
        "responsable",
        "creado_por",
        "modificado_por",
    )
    readonly_fields = ("fecha_creado", "fecha_modificado")

    def save_model(self, request, obj, form, change):
        # Auditoria equivalente a DispositivoAdmin.
        if not obj.pk:
            obj.creado_por = request.user
        obj.modificado_por = request.user
        super().save_model(request, obj, form, change)
