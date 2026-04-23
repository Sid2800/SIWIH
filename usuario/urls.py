from django.urls import path
from usuario import views


urlpatterns = [
    path('procesar_imagen_usuario/', views.Procesar_imagen_usuario.as_view(), name='procesar_imagen_usuario'),
]