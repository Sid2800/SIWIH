from django.urls import path
from agenda_medica import views


urlpatterns = [
    #path('guardar/', views.guardarAtencion, name='atencion_guardar'),
    path('listar-agenda-medica/', views.ListaPeriodoLaborales.as_view(), name='listar_agenda_medica'),
    path('listar-agenda-medica-API/', views.listarPeriodosLaboralesAPI, name='listar_agenda_medica_API'),
    path('guardar-periodo-laboral/', views.guardarPeriodoLaboral, name='guardar_periodo_laboral'),
    path('editar-periodo-laboral/', views.editarDiaLaboral, name='editar_periodo_laboral'),
    path('definir-dia-quirurgico/', views.definirDiaQuirurgico, name='definir_dia_quirurgico'),
    path('quitar-dia-quirurgico/', views.quitarDiaQuirurgico, name='quitar_dia_quirurgico'),


    path('listar-ausencias/', views.ListaAusencias.as_view(), name='listar_ausencias'),
    path('listar-tipos-ausencia/', views.ListarTiposAusencias.as_view(), name='listar_tipos_ausencia'),


    
    path('listar-ausencias-API/', views.listarAusenciasAPI, name='listar_ausencias_API'),


    
    path('guardar-dia-laboral/', views.guardarDiaLaboral, name='guardar_dia_laboral'),
    path('guardar-ausencia/', views.guardarAusencia, name='guardar_ausencia'),
    path('editar-ausencia', views.editarAusencia, name='editar_ausencia'),


    path('eliminar-dia-laboral/', views.eliminarDiaLaboral, name='eliminar_dia_laboral'),


    path('validar-impacto-periodo-laboral/', views.validarImpactoPeriodoLaboral, name='validar_impacto-periodo_laboral'),
    path('validar-impacto-dia-laboral/', views.validarImpactoDiaLaboral, name='validar_impacto_dia_laboral'),
    path('validar-impacto-ausencia/', views.validarImpactoAusencia, name='validar_impacto_ausencia'),


    path('obtener-periodo-laboral/', views.obtenerPeriodoLaboral, name='obtener_periodo_laboral'),
    path('obtener-dia-laboral/', views.obtenerDiaLaboral, name='obtener_dia_laboral'),
    path('obtener-ausencia/', views.obtenerAusencia, name='obtener_ausencia'),



    path('configurar-periodo/<int:pk>/<slug:slug>/', views.ConfigurarPeriodo.as_view(), name='configurar_periodo'),


    path('calendario-personal-salud/<int:personal_salud_id>/',views.CalendarioPersonalSalud.as_view(),name='calendario-personal-salud'),
    path('agenda-medica-API/', views.AgendaMedicaAPI.as_view(), name='agenda_medica_api'),


    
]