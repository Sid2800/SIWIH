from django.urls import path
from encuestas import views

urlpatterns = [
    # Inicio del módulo (encabezado + elegir servicio).
    path('', views.EncuestasInicioView.as_view(), name='encuestas_inicio'),
]
