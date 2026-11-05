from django.urls import path
from comunicacion_hospitalaria import views


urlpatterns = [

    path('monitor-labor-parto/', views.MonitorLaborParto.as_view(), name='monitor_labor_parto'),
    path('monitor-labor-parto-publico/', views.MonitorLaborPartoPublico.as_view(), name='monitor_labor_parto_publico'),

    path('listar-episodios-API/', views.listarEpisodiosLaborPartoAPI, name='listar_episodios_API'),
    path('listar-episodios-publico-API/', views.listarEpisodiosLaborPartoPublicoAPI, name='listar_episodios_publico_API'),

    path('obtener-episodio-labor-parto/', views.obtenerEpisodioLaborParto, name='obtener_episodio_labor_parto'),
    path('obtener-movimiento-labor-parto/', views.obtenerMovimientoLaborParto, name='obtener_movimiento_labor_parto'),
    path('obtener-bebe-labor-parto/', views.obtenerBebeLaborParto, name='obtener_bebe_labor_parto'),

    




    path('guardar-episodio-labor-parto/', views.guardarEpisodioLaborParto,name='guardar_episodio_labor_parto'),
    path('procesar-movimiento-labor-parto/', views.procesarMovimientoLaborParto,name='procesar_movimiento_labor_parto'),

    path('gestionar-movimiento-labor-parto/',views.gestionarMovimientoLaborParto,name='gestionar_movimiento_labor_parto',),
    path('registrar-alta-labor-parto/',views.registrarAltaLaborParto, name='registrar_alta_labor_parto',),
    path('procesar-bebe-labor-parto/',views.procesarBebeLaborParto, name='procesar_bebe_labor_parto',),

    path("labor-parto/salida-temporal/", views.registrarSalidaTemporalLaborParto, name="registrar_salida_temporal_labor_parto",
),



]