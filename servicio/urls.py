from django.urls import path
from servicio import views 


urlpatterns = [
    path('cama_autocomplete/', views.CamaAutocomplete.as_view(), name='camaAutocomplete' ) ,
    #path('sala_autocomplete/', views.SalaAutocomplete.as_view(), name='salaAutocomplete' ),
    path('listar-zona/',views.ListarZona.as_view(), name='listarZona'),
    path('listar-sala/',views.ListarSala.as_view(), name='listarSala'),
    path('listar-dependencias/',views.ListarUnidadesClinicas.as_view(), name='listar_dependencias'),

    path('listar-area-atencion/',views.ListarAreaAtencionServicio.as_view(), name='listarAreaAtencion'),

    path('cambiar-zona/', views.cambiarZona, name='cambiarZona'),

]
