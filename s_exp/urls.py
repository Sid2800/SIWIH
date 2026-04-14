from django.urls import path
from s_exp import views

urlpatterns = [

    # ==========================================
    # VISTAS ADMIN (Template)
    # ==========================================
    path('dashboard/', views.DashboardAdminView.as_view(), name='s_exp_dashboard'),
    path('solicitudes/', views.GestionSolicitudesView.as_view(), name='s_exp_solicitudes'),
    path('monitoreo/', views.MonitoreoPrestamosView.as_view(), name='s_exp_monitoreo'),
    path('devoluciones/', views.ControlDevolucionesView.as_view(), name='s_exp_devoluciones'),
    path('reportes/', views.ReportesView.as_view(), name='s_exp_reportes'),

    # ==========================================
    # VISTAS USUARIO (Template)
    # ==========================================
    path('buscador/', views.BuscadorExpedientesView.as_view(), name='s_exp_buscador'),
    path('seguimiento/', views.SeguimientoView.as_view(), name='s_exp_seguimiento'),

    # ==========================================
    # APIs ADMIN
    # ==========================================
    path('api/dashboard-stats/', views.dashboard_stats_api, name='s_exp_dashboard_stats_api'),
    path('api/listar-solicitudes/', views.listar_solicitudes_api, name='s_exp_listar_solicitudes_api'),
    path('api/aprobar-solicitud/', views.aprobar_solicitud_api, name='s_exp_aprobar_solicitud_api'),
    path('api/marcar-listo/', views.marcar_listo_recojer_api, name='s_exp_marcar_listo_api'),
    path('api/rechazar-solicitud/', views.rechazar_solicitud_api, name='s_exp_rechazar_solicitud_api'),
    path('api/prestamos-activos/', views.prestamos_activos_api, name='s_exp_prestamos_activos_api'),
    path('api/marcar-entregado/', views.marcar_entregado_api, name='s_exp_marcar_entregado_api'),
    path('api/prestamos-devolucion/', views.prestamos_para_devolucion_api, name='s_exp_prestamos_devolucion_api'),
    path('api/procesar-devolucion/', views.procesar_devolucion_api, name='s_exp_procesar_devolucion_api'),
    path('api/reportes-data/', views.reportes_data_api, name='s_exp_reportes_data_api'),

    # ==========================================
    # APIs USUARIO
    # ==========================================
    path('api/buscar-expedientes/', views.buscar_expedientes_api, name='s_exp_buscar_expedientes_api'),
    path('api/crear-solicitud/', views.crear_solicitud_api, name='s_exp_crear_solicitud_api'),
    path('api/mis-solicitudes/', views.mis_solicitudes_api, name='s_exp_mis_solicitudes_api'),
    path('api/solicitar-devolucion/', views.solicitar_devolucion_api, name='s_exp_solicitar_devolucion_api'),

    # ==========================================
    # APIs COMUNES / CATÁLOGOS
    # ==========================================
    path('api/alertas/', views.alertas_usuario_api, name='s_exp_alertas_api'),
    path('api/motivos/', views.motivos_api, name='s_exp_motivos_api'),
    path('api/info-usuario/', views.info_usuario_api, name='s_exp_info_usuario_api'),
    path('api/historial-prestamos-paciente/<int:paciente_id>/',
         views.historial_prestamos_paciente_api,
         name='s_exp_historial_prestamos_paciente_api'),
    path('api/historial-prestamos-expediente/<int:expediente_id>/',
         views.historial_prestamos_expediente_api,
         name='s_exp_historial_prestamos_expediente_api'),
]
