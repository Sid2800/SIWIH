from django.urls import path
from encuestas import views

urlpatterns = [
    # Inicio del módulo (encabezado + elegir servicio).
    path('', views.EncuestasInicioView.as_view(), name='encuestas_inicio'),

    # Formulario de una encuesta por servicio + guardado.
    path('nueva/<str:servicio>/', views.EncuestaFormView.as_view(), name='encuestas_nueva'),
    path('api/guardar/', views.guardar_encuesta_api, name='encuestas_guardar_api'),
]
