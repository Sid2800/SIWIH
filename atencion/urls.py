from django.urls import path
from atencion import views


urlpatterns = [
    path('guardar/', views.guardarAtencion, name='atencion_guardar'),
    path('listar_atenciones/', views.listarAtenciones.as_view(), name='listar_atenciones'),
    path('listar_atenciones_API/', views.listarAtencionesAPI, name='listar_atenciones_API'),
    path('obtener-atencion/', views.obtener_atencion, name='obtener_atencion'),
    path('recibir_atenciones/', views.RecepcionAtenciones.as_view(), name='recibir-atenciones'),

    path('registrar_recepcion_atenciones/', views.registrarRecepcionAtencion, name='registrar-recepcion-atenciones'),
    path('listar_atenciones_paciente_API/', views.listarAtencionPacienteAPI, name='listar-atenciones-paciente-API'),
    path('verificar-atencion-reciente/', views.verificar_atencion_h, name='verificar_atencion_reciente'),

    
]