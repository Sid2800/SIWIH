from django.urls import path
from . import views

# Este archivo conecta rutas internas del modulo con funciones de views.py.
# SIWI/urls.py incluye este archivo bajo el prefijo /equipos-biomedicos/.
urlpatterns = [
    path('', views.inicio, name='inicio_biomedicos'),
    path(
        'registrar-dispositivo/',
        views.registrar_dispositivo,
        name='registrar_dispositivo_biomedicos'
    ),
    path(
        'listado-dispositivos/',
        views.listado_dispositivos,
        name='listado_dispositivos_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/',
        views.detalle_dispositivo,
        name='detalle_dispositivo_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/editar/',
        views.editar_dispositivo,
        name='editar_dispositivo_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/imagenes/agregar/',
        views.agregar_imagen_dispositivo,
        name='agregar_imagen_dispositivo_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/tramite-baja/',
        views.tramite_baja_dispositivo,
        name='tramite_baja_dispositivo_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/tramite-baja/ficha/',
        views.ficha_baja_dispositivo_pdf,
        name='ficha_baja_dispositivo_biomedicos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/qr/',
        views.qr_dispositivo,
        name='qr_dispositivo_biomedicos'
    ),
    path(
        'buscar-dispositivo/',
        views.buscar_dispositivo,
        name='buscar_dispositivo_biomedicos'
    ),
    path(
        'buscar-empleados/',
        views.buscar_empleados,
        name='buscar_empleados_biomedicos'
    ),
]
