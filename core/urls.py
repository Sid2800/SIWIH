from django.urls import path
from .views import (
   CustomLoginView,
   HomePageView,
   MantenimientoView,
   media_equipo_proxy,
   samplePageView,
)
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView


urlpatterns = [
   path('',HomePageView.as_view(), name="home"),
   path('sample/',samplePageView.as_view(), name="sample"),
   # Ruta para el login / prueba
   path('login/', CustomLoginView.as_view(template_name='core/login.html'), name='login'),
   path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
   path('acceso-denegado/', TemplateView.as_view(template_name='core/acceso_denegado.html'), name='acceso_denegado'),
   path('mantenimiento/', MantenimientoView.as_view(), name='mantenimiento'),
   # El telefono descarga las fotos desde el mismo host de SIWIH; el backend
   # mantiene privada la direccion real de SIWIH Images.
   path(
      'media/equipos/<path:ruta_archivo>',
      media_equipo_proxy,
      name='media_equipo_proxy',
   ),

]

