from django.urls import path

from mapeo_camas import views


urlpatterns = [
    path("", views.MapeoCamasMapaView.as_view(), name="mapeo_camas_mapa"),
    path("api/estado-mapeo/", views.estado_mapeo, name="mapeo_camas_estado_mapeo"),
    path("api/iniciar-mapeo/", views.iniciar_mapeo, name="mapeo_camas_iniciar_mapeo"),
    path("api/terminar-mapeo/", views.terminar_mapeo, name="mapeo_camas_terminar_mapeo"),
    path("api/cancelar-mapeo/", views.cancelar_mapeo, name="mapeo_camas_cancelar_mapeo"),
    path("api/mapa-camas/", views.mapa_camas_data, name="mapeo_camas_data"),
    path("api/buscar-pacientes/", views.buscar_pacientes_mapa, name="mapeo_camas_buscar_pacientes"),
    path("api/actualizar-cama/", views.actualizar_cama_mapa, name="mapeo_camas_actualizar_cama"),
    path("api/camas-disponibles/", views.camas_disponibles_mapa, name="mapeo_camas_camas_disponibles"),
    path("api/mover-paciente/", views.mover_paciente_cama, name="mapeo_camas_mover_paciente"),
    path("api/procesar-cama-mapeo/", views.procesar_cama_mapeo, name="mapeo_camas_procesar_cama_mapeo"),
]
