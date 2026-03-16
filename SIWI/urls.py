"""
URL configuration for SIWI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('core.urls')),
    path('paciente/',include('paciente.urls')),
    path('ubicacion/',include('ubicacion.urls')),
    path('expediente/',include('expediente.urls')),
    path('servicio/',include('servicio.urls')),
    path('ingreso/',include('ingreso.urls')),
    path('reporte/',include('reporte.urls')),
    path('atencion/',include('atencion.urls')),
    path('imagenologia/',include('imagenologia.urls')),
    path('referencia/',include('referencia.urls')),
    path('clinico/',include('clinico.urls')),
    path('admin/', admin.site.urls),
]
