from django.urls import path
from agenda_medica import views


urlpatterns = [
    #path('guardar/', views.guardarAtencion, name='atencion_guardar'),
    path('listar-agenda-medica/', views.ListaAgendaMedica.as_view(), name='listar_agenda_medica'),
    path('listar-agenda-medica-API/', views.listarAgendaMedicaAPI, name='listar_agenda_medica_API'),


    
]