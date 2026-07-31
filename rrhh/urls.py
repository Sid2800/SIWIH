from django.urls import path
from rrhh import views 


urlpatterns = [
    path('listar-personal-clinico/',views.ListarPersonalClinico.as_view(), name='listar_personal_clinico'),
    path('listar-jornada-laboral/',views.ListarJornadaLaboral.as_view(), name='listar_jornada_laboral'),

]
