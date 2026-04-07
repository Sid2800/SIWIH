from django.contrib import admin

from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama


@admin.register(AsignacionCamaPaciente)
class AsignacionCamaPacienteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cama",
        "paciente",
        "estado",
        "fecha_inicio",
        "fecha_fin",
        "usuario_asignacion",
        "usuario_cierre",
    )
    list_filter = ("estado", "fecha_inicio", "fecha_fin")
    search_fields = (
        "cama__numero_cama",
        "paciente__primer_nombre",
        "paciente__primer_apellido",
        "paciente__dni",
    )
    
    # PROTECCIÓN: Esta tabla es histórica y nunca debe modificarse manualmente
    # Se necesitan todos los registros (incluso los CERRADA) para mapeos posteriores
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistorialEstadoCama)
class HistorialEstadoCamaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cama",
        "estado_anterior",
        "estado_nuevo",
        "paciente",
        "usuario",
        "fecha_hora",
        "observacion",
    )
    list_filter = ("estado_nuevo", "estado_anterior", "fecha_hora")
    search_fields = (
        "cama__numero_cama",
        "paciente__primer_nombre",
        "paciente__primer_apellido",
        "paciente__dni",
        "observacion",
    )
    # Solo lectura: el historial nunca se modifica manualmente
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
