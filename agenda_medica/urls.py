from django.urls import path
from agenda_medica import views


urlpatterns = [
    #path('guardar/', views.guardarAtencion, name='atencion_guardar'),
    path('listar-agenda-medica/', views.ListaPeriodoLaborales.as_view(), name='listar_agenda_medica'),
    path('listar-agenda-medica-API/', views.listarPeriodosLaboralesAPI, name='listar_agenda_medica_API'),
    path('guardar-periodo-laboral/', views.guardarPeriodoLaboral, name='guardar_periodo_laboral'),
    path('dia-periodo-laboral/', views.guardarDiaLaboral, name='guardar_dia_periodo_laboral'),

    path('validar-impacto-periodo-laboral/', views.validarImpactoPeriodoLaboral, name='validar_impacto-periodo_laboral'),
    path('obtener-periodo-laboral/', views.obtenerPeriodoLaboral, name='obtener_periodo_laboral'),

    path('configurar-agenda/<int:pk>/<slug:slug>/', views.ConfigurarAgenda.as_view(), name='configurar_agenda'),

    
]