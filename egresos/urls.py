from django.urls import path
from egresos import views

urlpatterns = [
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
]
