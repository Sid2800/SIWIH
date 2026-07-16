"""
Paquete de vistas del modulo s_exp (antes un unico views.py monolitico).

Se divide por dominio para mantener cada archivo enfocado y legible. Este
__init__ re-exporta todos los nombres publicos para que urls.py y cualquier
otro importador sigan usando `from s_exp import views` / `views.<nombre>`
sin cambios.
"""

from .comunes import (
    _fmt_local,
    _registrar_log,
    _es_exp_admin,
    _es_usuario_valido_rrhh,
    _es_exp_solicitante,
    _get_unidad_usuario,
    _get_servicio_unidad_from_rrhh,
    _resolver_ubicacion_expediente,
    _set_localizacion_por_solicitud,
    _set_ubicacion_admision,
    SExpAdminMixin,
    SExpUsuarioMixin,
)
from .dashboard import (
    DashboardAdminView,
    GestionSolicitudesView,
    MonitoreoPrestamosView,
    ControlDevolucionesView,
    ReportesView,
    BuscadorExpedientesView,
    SeguimientoView,
    dashboard_stats_api,
    info_usuario_api,
    motivos_api,
)
from .solicitudes import (
    listar_solicitudes_api,
    aprobar_solicitud_api,
    expedientes_revision_api,
    expedientes_solicitud_api,
    imprimir_solicitud_pdf,
    revisar_entrega_api,
    marcar_listo_recojer_api,
    rechazar_solicitud_api,
    crear_solicitud_api,
    mis_solicitudes_api,
)
from .prestamos import (
    prestamos_activos_api,
    marcar_entregado_api,
    pendientes_prestamo_api,
    entregar_pendientes_api,
    cancelar_pendientes_api,
)
from .devoluciones import (
    prestamos_para_devolucion_api,
    solicitar_devolucion_api,
    procesar_devolucion_api,
)
from .buscador import (
    buscar_expedientes_api,
    historial_prestamos_paciente_api,
    historial_prestamos_expediente_api,
)
from .alertas import (
    changes_check_api,
    alertas_usuario_api,
    marcar_notificacion_leida_api,
    marcar_vencimiento_leido_api,
)
from .reportes import (
    reportes_data_api,
    exportar_reporte_excel,
    exportar_reporte_pdf,
)
from .historial import (
    HistorialSolicitudesView,
    historial_solicitudes_api,
    historial_solicitud_detalle_api,
)

__all__ = [
    "_fmt_local",
    "_registrar_log",
    "_es_exp_admin",
    "_es_usuario_valido_rrhh",
    "_es_exp_solicitante",
    "_get_unidad_usuario",
    "_get_servicio_unidad_from_rrhh",
    "_resolver_ubicacion_expediente",
    "_set_localizacion_por_solicitud",
    "_set_ubicacion_admision",
    "SExpAdminMixin",
    "SExpUsuarioMixin",
    "DashboardAdminView",
    "GestionSolicitudesView",
    "MonitoreoPrestamosView",
    "ControlDevolucionesView",
    "ReportesView",
    "BuscadorExpedientesView",
    "SeguimientoView",
    "dashboard_stats_api",
    "info_usuario_api",
    "motivos_api",
    "listar_solicitudes_api",
    "aprobar_solicitud_api",
    "expedientes_revision_api",
    "expedientes_solicitud_api",
    "imprimir_solicitud_pdf",
    "revisar_entrega_api",
    "marcar_listo_recojer_api",
    "rechazar_solicitud_api",
    "crear_solicitud_api",
    "mis_solicitudes_api",
    "prestamos_activos_api",
    "marcar_entregado_api",
    "pendientes_prestamo_api",
    "entregar_pendientes_api",
    "cancelar_pendientes_api",
    "prestamos_para_devolucion_api",
    "solicitar_devolucion_api",
    "procesar_devolucion_api",
    "buscar_expedientes_api",
    "historial_prestamos_paciente_api",
    "historial_prestamos_expediente_api",
    "changes_check_api",
    "alertas_usuario_api",
    "marcar_notificacion_leida_api",
    "marcar_vencimiento_leido_api",
    "reportes_data_api",
    "exportar_reporte_excel",
    "exportar_reporte_pdf",
    "HistorialSolicitudesView",
    "historial_solicitudes_api",
    "historial_solicitud_detalle_api",
]
