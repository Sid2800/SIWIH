from django.urls import path
from expediente import views
urlpatterns = [
    path('expediente-libre/', views.traer_expediente_libre, name='expediente-libre'),
    path('obtener-paciente-ingreso-expediente/', views.obtenerPacienteIngresoExpediente, name='obtener_paciente_ingreso_expediente'),
    path('obtener-paciente-registro-expediente/', views.obtenerPacienteRegistroExpediente, name='obtener_paciente_registro_expediente'),


    
    
    path('listar_expedientes_API/', views.listarExpedientesAPI, name="listar_expedientes_API"),
    path('listar_expedientes_propietarios_API/', views.listarPropietariosExpedienteAPI, name="listar_expedientes_propietarios_API"),
    path('listar_expedientes/',views.listarExpedientes.as_view(),name="listar_expedientes"),
    path('agregar/', views.ExpedienteAddView.as_view(), name='expediente_agregar'),
    path('ver/<int:pk>/', views.ExpedienteDetailView.as_view(), name='expediente_ver'),



]