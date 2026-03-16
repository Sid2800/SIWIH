from django.urls import path
from servicio import views 


urlpatterns = [
    path('cama_autocomplete/', views.CamaAutocomplete.as_view(), name='camaAutocomplete' ) ,
    #path('sala_autocomplete/', views.SalaAutocomplete.as_view(), name='salaAutocomplete' ),
    path('listar-zona/',views.ListarZona.as_view(), name='listarZona'),
    path('listar-sala/',views.ListarSala.as_view(), name='listarSala'),
    path('listar-especialidad/',views.ListarEspecialidadServicio.as_view(), name='listarEspecialidad'),

    path('cambiar-zona/', views.cambiarZona, name='cambiarZona'),

]
