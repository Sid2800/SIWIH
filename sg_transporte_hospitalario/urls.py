from django.urls import path

from . import views


urlpatterns = [
    path("", views.SGTransporteHospitalarioDashboardView.as_view(), name="sg_transporte_hospitalario_dashboard"),
    path("solicitudes/", views.SolicitudListView.as_view(), name="sg_transporte_hospitalario_solicitud_list"),
    path("solicitudes/nueva/", views.SolicitudCreateView.as_view(), name="sg_transporte_hospitalario_solicitud_nueva"),
    path("solicitudes/<int:pk>/editar/", views.SolicitudUpdateView.as_view(), name="sg_transporte_hospitalario_solicitud_editar"),
    path("solicitudes/<int:pk>/ver/", views.SolicitudDetailView.as_view(), name="sg_transporte_hospitalario_solicitud_ver"),
    path("solicitudes/<int:pk>/eliminar/", views.SolicitudDeleteView.as_view(), name="sg_transporte_hospitalario_solicitud_eliminar"),
    path("api/estado/", views.api_estado_modulo, name="sg_transporte_hospitalario_estado_api"),
    path("api/buscar-pacientes/", views.api_buscar_pacientes, name="sg_transporte_hospitalario_buscar_pacientes"),
    path("api/buscar-empleados/", views.api_buscar_empleados, name="sg_transporte_hospitalario_buscar_empleados"),
    path("api/solicitudes-activas/", views.api_solicitudes_activas, name="sg_transporte_hospitalario_solicitudes_activas"),
    path("api/solicitud-detalle/", views.api_detalle_solicitud, name="sg_transporte_hospitalario_solicitud_detalle"),
    path("api/solicitud-autorizar/", views.api_solicitud_autorizar, name="sg_transporte_hospitalario_solicitud_autorizar"),
    path("api/programacion-viaje/", views.api_programacion_viaje, name="sg_transporte_hospitalario_programacion_viaje"),
    path("api/programacion-agregar/", views.api_programacion_agregar, name="sg_transporte_hospitalario_programacion_agregar"),
    path("api/programacion-quitar/", views.api_programacion_quitar, name="sg_transporte_hospitalario_programacion_quitar"),
    path("api/programacion-anular/", views.api_programacion_anular, name="sg_transporte_hospitalario_programacion_anular"),
    path("api/programacion-confirmar/", views.api_programacion_confirmar, name="sg_transporte_hospitalario_programacion_confirmar"),
    path("api/ejecucion-guardar/", views.api_ejecucion_guardar, name="sg_transporte_hospitalario_ejecucion_guardar"),
]