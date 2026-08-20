from django.urls import path
from encuestas import views

urlpatterns = [
    # Pestaña 1: Encuestas (inicio + formulario inline).
    path('', views.EncuestasInicioView.as_view(), name='encuestas_inicio'),
    path('nueva/<str:servicio>/', views.EncuestaFormView.as_view(), name='encuestas_nueva'),
    path('fragmento/<str:servicio>/', views.encuesta_fragmento, name='encuestas_fragmento'),
    path('api/guardar/', views.guardar_encuesta_api, name='encuestas_guardar_api'),

    # Pestaña 2: Encuestas ingresadas (lista + detalle).
    path('lista/', views.MisEncuestasView.as_view(), name='encuestas_lista'),
    path('api/mis-encuestas/', views.mis_encuestas_api, name='encuestas_mis_encuestas_api'),
    path('api/detalle/<int:encuesta_id>/', views.detalle_encuesta_api,
         name='encuestas_detalle_api'),

    # Pestaña 3: Reportes (en construcción).
    path('reportes/', views.ReportesView.as_view(), name='encuestas_reportes'),
]
