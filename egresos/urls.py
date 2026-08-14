from django.urls import path
from egresos import views

urlpatterns = [
    # Pantalla de captura (Estadística toma expedientes desde los ingresos)
    path('captura/', views.CapturaEgresosView.as_view(), name='egresos_captura'),

    # APIs
    path('api/ingresos-para-egreso/', views.ingresos_para_egreso_api,
         name='egresos_ingresos_para_egreso_api'),
]
