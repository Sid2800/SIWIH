from django.urls import path
from egresos import views

urlpatterns = [
    # Entrada única del módulo (una sola opción de menú).
    path('', views.EgresosInicioView.as_view(), name='egresos_inicio'),

    # --- Captura: Estadística toma expedientes desde los ingresos ---
    path('captura/', views.CapturaEgresosView.as_view(), name='egresos_captura'),
    path('api/ingresos-para-egreso/', views.ingresos_para_egreso_api,
         name='egresos_ingresos_para_egreso_api'),
    path('api/crear-lote-captura/', views.crear_lote_captura_api,
         name='egresos_crear_lote_captura_api'),

    # --- Llenado: lista de expedientes tomados y su formulario de egreso ---
    path('llenado/', views.LlenadoView.as_view(), name='egresos_llenado'),
    path('llenar/<int:detalle_id>/', views.EgresoFormView.as_view(),
         name='egresos_llenar'),

    # APIs de llenado
    path('api/pendientes-llenado/', views.pendientes_llenado_api,
         name='egresos_pendientes_llenado_api'),
    path('api/datos-llenado/<int:detalle_id>/', views.datos_llenado_api,
         name='egresos_datos_llenado_api'),
    path('api/guardar-egreso/<int:detalle_id>/', views.guardar_egreso_api,
         name='egresos_guardar_egreso_api'),

    # Catálogos / búsquedas para el formulario
    path('api/areas/', views.areas_api, name='egresos_areas_api'),
    path('api/buscar-cie10/', views.buscar_cie10_api, name='egresos_buscar_cie10_api'),
    path('api/buscar-procedimiento/', views.buscar_procedimiento_api,
         name='egresos_buscar_procedimiento_api'),
    path('api/servicios/', views.servicios_api, name='egresos_servicios_api'),
    path('api/salas/', views.salas_api, name='egresos_salas_api'),
    path('api/buscar-institucion/', views.buscar_institucion_api,
         name='egresos_buscar_institucion_api'),

    # --- Devolución / recepción del lote (Estadística envía; Admisión recibe) ---
    path('api/enviar-lote-admision/<int:lote_id>/', views.enviar_lote_admision_api,
         name='egresos_enviar_lote_admision_api'),
    path('recepcion/', views.RecepcionEgresosView.as_view(), name='egresos_recepcion'),
    path('api/lotes-para-recepcion/', views.lotes_para_recepcion_api,
         name='egresos_lotes_para_recepcion_api'),
    path('api/marcar-devuelto/<int:detalle_id>/', views.marcar_devuelto_api,
         name='egresos_marcar_devuelto_api'),
    path('api/marcar-devueltos/<int:lote_id>/', views.marcar_devueltos_api,
         name='egresos_marcar_devueltos_api'),
    path('api/capturar-parcial/<int:lote_id>/', views.capturar_parcial_api,
         name='egresos_capturar_parcial_api'),
    path('api/cerrar-lote/<int:lote_id>/', views.cerrar_lote_api,
         name='egresos_cerrar_lote_api'),
]
