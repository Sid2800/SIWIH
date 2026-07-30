from django.urls import path
from . import views

# Este archivo conecta rutas internas del modulo con funciones de views.py.
# SIWI/urls.py incluye este archivo bajo el prefijo principal /equipos/.
urlpatterns = [
    path('', views.inicio, name='inicio_equipos'),
    path(
        'registrar-dispositivo/',
        views.registrar_dispositivo,
        name='registrar_dispositivo_equipos'
    ),
    path(
        'listado-dispositivos/',
        views.listado_dispositivos,
        name='listado_dispositivos_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/',
        views.detalle_dispositivo,
        name='detalle_dispositivo_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/editar/',
        views.editar_dispositivo,
        name='editar_dispositivo_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/imagenes/agregar/',
        views.agregar_imagen_dispositivo,
        name='agregar_imagen_dispositivo_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/tramite-baja/',
        views.tramite_baja_dispositivo,
        name='tramite_baja_dispositivo_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/tramite-baja/ficha/',
        views.ficha_baja_dispositivo_pdf,
        name='ficha_baja_dispositivo_equipos'
    ),
    path(
        'dispositivos/<int:dispositivo_id>/qr/',
        views.qr_dispositivo,
        name='qr_dispositivo_equipos'
    ),
    path(
        'buscar-dispositivo/',
        views.buscar_dispositivo,
        name='buscar_dispositivo_equipos'
    ),
    path(
        'buscar-empleados/',
        views.buscar_empleados,
        name='buscar_empleados_equipos'
    ),

    # Catalogo de marcas y modelos. Es el unico lugar donde se dan de alta:
    # el formulario de equipos solo permite elegir entre los existentes.
    path(
        'catalogo/marcas/',
        views.catalogo_marcas_modelos,
        name='catalogo_marcas_equipos'
    ),
    path(
        'catalogo/marcas/agregar/',
        views.agregar_marca_catalogo,
        name='agregar_marca_equipos'
    ),
    path(
        'catalogo/marcas/<int:marca_id>/estado/',
        views.cambiar_estado_marca,
        name='cambiar_estado_marca_equipos'
    ),
    path(
        'catalogo/marcas/<int:marca_id>/modelos/agregar/',
        views.agregar_modelo_catalogo,
        name='agregar_modelo_equipos'
    ),
    path(
        'catalogo/modelos/<int:modelo_id>/estado/',
        views.cambiar_estado_modelo,
        name='cambiar_estado_modelo_equipos'
    ),

    # Autocompletado de los Select2 dependientes del formulario de equipos.
    path(
        'buscar-marcas/',
        views.buscar_marcas,
        name='buscar_marcas_equipos'
    ),
    path(
        'buscar-modelos/',
        views.buscar_modelos,
        name='buscar_modelos_equipos'
    ),
]
