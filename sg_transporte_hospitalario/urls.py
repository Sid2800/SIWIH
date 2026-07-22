from django.urls import path

from . import views


urlpatterns = [
    path("", views.SGTransporteHospitalarioDashboardView.as_view(), name="sg_transporte_hospitalario_dashboard"),
    path("solicitudes/", views.SolicitudListView.as_view(), name="sg_transporte_hospitalario_solicitud_list"),
    path("solicitudes/nueva/", views.SolicitudCreateView.as_view(), name="sg_transporte_hospitalario_solicitud_nueva"),
    path("solicitudes/<int:pk>/editar/", views.SolicitudUpdateView.as_view(), name="sg_transporte_hospitalario_solicitud_editar"),
    path("solicitudes/<int:pk>/ver/", views.SolicitudDetailView.as_view(), name="sg_transporte_hospitalario_solicitud_ver"),
    path("api/estado/", views.api_estado_modulo, name="sg_transporte_hospitalario_estado_api"),
    path("api/buscar-pacientes/", views.api_buscar_pacientes, name="sg_transporte_hospitalario_buscar_pacientes"),
    path("api/buscar-empleados/", views.api_buscar_empleados, name="sg_transporte_hospitalario_buscar_empleados"),
    path("api/solicitudes-activas/", views.api_solicitudes_activas, name="sg_transporte_hospitalario_solicitudes_activas"),
    path("api/solicitud-detalle/", views.api_detalle_solicitud, name="sg_transporte_hospitalario_solicitud_detalle"),
]