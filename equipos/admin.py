from django.contrib import admin

from .models import (
    ActividadEnOrdenTrabajo,
    ActividadMantenimiento,
    AreaGestora,
    CategoriaEquipo,
    AsignacionDispositivo,
    BajaDispositivo,
    ColorDispositivo,
    Dispositivo,
    GarantiaDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    EquipoEnOrdenTrabajo,
    OrdenTrabajoBajaDispositivo,
    OrdenTrabajoMantenimiento,
    PlanMantenimiento,
    Procedencia,
    TecnologiaEquipo,
    TipoDispositivo,
    UbicacionFisica,
    VisitaPreventiva,
)


# Catalogos base del modulo. El admin queda como respaldo administrativo;
# tipos, marcas, modelos y procedencias tambien tienen pantallas operativas.
@admin.register(CategoriaEquipo)
class CategoriaEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(TecnologiaEquipo)
class TecnologiaEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(UbicacionFisica)
class UbicacionFisicaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(TipoDispositivo)
class TipoDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "tecnologia", "activo")
    list_filter = ("categoria", "tecnologia", "activo")
    search_fields = ("nombre", "categoria__nombre")
    autocomplete_fields = ("categoria", "tecnologia")
    filter_horizontal = ("categorias_secundarias", "marcas")


@admin.register(MarcaDispositivo)
class MarcaDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(ModeloDispositivo)
class ModeloDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "marca", "activo")
    list_filter = ("tipo", "marca", "activo")
    search_fields = ("nombre", "marca__nombre", "tipo__nombre")
    autocomplete_fields = ("tipo", "marca")


@admin.register(AreaGestora)
class AreaGestoraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(ColorDispositivo)
class ColorDispositivoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(Procedencia)
class ProcedenciaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "rtn", "telefono", "activo")
    list_filter = ("tipo", "activo")
    search_fields = ("nombre", "rtn", "telefono", "contacto", "correo")


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    # Permite revisar la ficha del equipo desde admin, pero el flujo normal
    # de registro/edicion sigue estando en las vistas del modulo.
    list_display = (
        "codigo",
        "tipo",
        "marca",
        "modelo",
        "area_gestora",
        "modalidad_procedencia",
        "procedencia",
        "numero_serie",
        "inventario_bienes_nacionales",
        "inventario_numero_ficha",
        "estado",
        "criticidad",
    )
    list_filter = (
        "tipo",
        "marca",
        "modelo",
        "area_gestora",
        "modalidad_procedencia",
        "procedencia",
        "colores",
        "tipo__tecnologia",
        "estado",
        "criticidad",
    )
    search_fields = (
        "tipo__nombre",
        "marca__nombre",
        "modelo__nombre",
        "area_gestora__nombre",
        "procedencia__nombre",
        "numero_referencia",
        "colores__nombre",
        "numero_serie",
        "inventario_bienes_nacionales",
        "inventario_numero_ficha",
    )
    autocomplete_fields = (
        "tipo",
        "marca",
        "modelo",
        "area_gestora",
        "procedencia",
        "creado_por",
        "modificado_por",
    )
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
    autocomplete_fields = (
        "dispositivo",
        "registrado_por",
    )
    readonly_fields = ("fecha_registro",)


@admin.register(OrdenTrabajoBajaDispositivo)
class OrdenTrabajoBajaDispositivoAdmin(admin.ModelAdmin):
    # La numeración es de auditoría: desde admin se consulta, no se altera.
    list_display = (
        "numero_orden",
        "dispositivo",
        "creado_por",
        "fecha_creado",
    )
    search_fields = (
        "dispositivo__tipo__nombre",
        "dispositivo__numero_serie",
        "creado_por__username",
    )
    list_filter = ("fecha_creado", "creado_por")
    readonly_fields = (
        "dispositivo",
        "creado_por",
        "fecha_creado",
        "numero_orden",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GarantiaDispositivo)
class GarantiaDispositivoAdmin(admin.ModelAdmin):
    """Consulta del historial de coberturas. Se opera desde el modulo."""

    list_display = (
        "dispositivo",
        "fecha_inicio",
        "fecha_fin",
        "meses",
        "fecha_cierre",
        "motivo_cierre",
    )
    list_filter = ("motivo_cierre", "fecha_fin", "fecha_cierre")
    search_fields = (
        "dispositivo__numero_serie",
        "dispositivo__inventario_numero_ficha",
        "referencia",
    )
    autocomplete_fields = ("dispositivo", "registrado_por")
    readonly_fields = ("fecha_creado",)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)


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
    list_filter = ("fecha_fin", "ubicacion", "ubicacion_fisica")
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
        # La ubicacion sale de un catalogo compartido de pocas decenas de
        # filas: un desplegable normal basta y evita depender del admin de
        # expediente, que no declara search_fields.
        "ubicacion_fisica",
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


# ---------------------------------------------------------------------------
# MANTENIMIENTO
#
# El trabajo diario se hace en las pantallas del modulo, no aqui. El admin
# sirve para lo otro: corregir una actividad mal escrita del catalogo, mirar
# una orden vieja sin pasar por el calendario, o desactivar un plan cuando la
# pantalla no alcanza.
# ---------------------------------------------------------------------------

@admin.register(ActividadMantenimiento)
class ActividadMantenimientoAdmin(admin.ModelAdmin):
    """El catalogo que se llena con el uso.

    Es el unico sitio donde corregir una errata que ya se escribio. Se puede
    retirar una linea de las sugerencias con `activa`, sin borrarla: las
    ordenes viejas que la usaron tienen que seguir diciendo lo mismo.
    """

    list_display = ("nombre", "veces_usada", "activa", "fecha_ultimo_uso")
    list_filter = ("activa",)
    search_fields = ("nombre", "clave")
    # clave y veces_usada los mantiene el sistema: la primera se deriva del
    # nombre y el segundo lo lleva el servicio con F() para no perder usos
    # cuando dos personas cierran ordenes a la vez.
    readonly_fields = ("clave", "veces_usada", "fecha_primer_uso", "fecha_ultimo_uso")
    ordering = ("-veces_usada", "nombre")


@admin.register(PlanMantenimiento)
class PlanMantenimientoAdmin(admin.ModelAdmin):
    list_display = (
        "dispositivo",
        "responsable",
        "frecuencia_meses",
        "fecha_inicio",
        "trabaja_fines_de_semana",
        "activo",
    )
    list_filter = ("activo", "trabaja_fines_de_semana", "frecuencia_meses")
    search_fields = ("dispositivo__numero_serie", "responsable__username")
    autocomplete_fields = ("dispositivo", "responsable", "creado_por")
    readonly_fields = ("fecha_creado", "fecha_modificado")


@admin.register(VisitaPreventiva)
class VisitaPreventivaAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "fecha_programada",
        "estado",
        "fecha_realizada",
        "movida_a_mano",
    )
    list_filter = ("estado", "movida_a_mano")
    date_hierarchy = "fecha_programada"
    # Se deja en solo lectura a proposito: una visita se mueve, se registra o
    # se omite desde el calendario, porque cada una de esas tres cosas
    # arrastra consecuencias -el corrimiento de las siguientes, el recalculo
    # desde la fecha realizada- que editar la fila a mano no dispara.
    readonly_fields = ("movida_a_mano",)


class EquipoEnOrdenInline(admin.TabularInline):
    model = EquipoEnOrdenTrabajo
    extra = 0
    autocomplete_fields = ("dispositivo",)


class ActividadEnOrdenInline(admin.TabularInline):
    model = ActividadEnOrdenTrabajo
    extra = 0
    autocomplete_fields = ("actividad",)


@admin.register(OrdenTrabajoMantenimiento)
class OrdenTrabajoMantenimientoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_orden",
        "fecha",
        "tipo",
        "clase",
        "operario",
        "estado",
    )
    list_filter = ("estado", "clase", "origen")
    search_fields = ("tipo__nombre", "solicitado_por")
    date_hierarchy = "fecha"
    autocomplete_fields = ("tipo", "operario", "jefe_servicio", "creado_por")
    readonly_fields = ("fecha_creado", "fecha_cierre", "cerrada_por")
    inlines = (EquipoEnOrdenInline, ActividadEnOrdenInline)

    @admin.display(description="Orden")
    def numero_orden(self, orden):
        return orden.numero_orden
