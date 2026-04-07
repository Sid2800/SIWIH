from django.urls import path
#from .views import PacienteListView
from . import views 

busquedas = [
    path('busqueda-censo/', views.busqueda_censo, name='busqueda-censo'),
    path('busqueda-paciente/', views.busquedaPacientesAPI, name='busqueda-paciente'),
    path('obtener-paciente-censo/', views.obtener_paciente_censo, name='obtener-paciente-censo'),
    path('obtener-padre/', views.obtener_padre, name='obtener-padre'),
    path('busqueda-avanzada/', views.busquedaAvanzada, name='busqueda_avanzada'),
    path('obtener-paciente-ingreso-dni/', views.obtenerPacienteIngresoDNI, name='obtener_paciente_ingreso_dni'),
    path('obtener-paciente-registro-dni/', views.obtenerPacienteRegistroDNI, name='obtener_paciente_registro_dni'),
    path('dispensaciones-paciente/', views.dispensacion_view, name='dispensaciones_paciente'),

]

defunciones = [
    path('defuncion-guardar/', views.guardarDefuncion, name='paciente_guardar_defuncion'),
    path('obito-guardar/', views.guardarObito, name='paciente_guardar_obito'),

    path('obtener-defuncion/', views.obtener_defuncion_paciente, name='obtener_defuncion'),
    path('obtener-obito/', views.obtener_obito_paciente, name='obtener_obito'),
    path('verificar-defuncion/', views.verificar_defuncion, name='verificar_defuncion'),
    path('registrar-entrega-cadaver/', views.registrarEntregaCadaver, name='registrar_entrega_cadaver'),
    path('listar-obitos-paciente/', views.obtener_obitos_paciente, name='listar_obitos_paciente'),


]

otros = [
    path('listar_pacientes/', views.listarPacientes, name='listar_pacientes'),
    path('listar_pacientes_API/', views.listarPacientesAPI, name='listar_pacientes_API'),
    path('editar/<int:pk>/<slug:slug>/', views.PacienteEditView.as_view(), name='paciente_editar'),
    path('agregar/', views.PacienteAddView.as_view(), name='paciente_agregar'),
    path('verificar-inactivo/', views.verificar_inactivo, name='verificar_paciente_inactivo'),
    path('verificar-similares/',views.verificar_duplicidad, name='verificar_paciente_similar'),
    path('historial/<int:pk>/<slug:slug>/',views.HistorialPaciente.as_view(), name='historial_paciente'),
    path('consulta-reclasificar-rn/', views.EjecutarReclasificacion, name='consulta_reclasificar_rn')



]

urlpatterns = busquedas + defunciones + otros