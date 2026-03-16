from django.urls import path
#from .views import PacienteListView
from . import views 



urlpatterns = [
   path('sector_autocomplete/', views.SectorAutocomplete.as_view(), name='sectorAutocomplete'),
   path('municipio-por-departamento/', views.MunicipiosXdepto.as_view(), name='municipioXdepartamento'),
   path('domicilio_detalles/', views.obtener_detalles_domicilio, name='obtenerDetallesDomicilio' ),
   path('agregar_sector/', views.agregar_sector, name='agregarSector' ), 
   path('aldea_autocomplete/', views.AldeaAutocomplete.as_view(), name='aldeaAutocomplete' ) 

   #path('trasmutar-ubicacion/', views.intercambiarMunicipioAldeaAbicacion, name='trasmutar-ubicacion'),



]
