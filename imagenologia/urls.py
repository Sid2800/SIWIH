from django.urls import path
from imagenologia import views


urlpatterns = [
    path('evaluacionrx/agregar/<int:pk>/<slug:slug>/', views.EvaluacionRxAddView.as_view(), name='evaluacionrx_agregar'),
    path('evaluacionrx/editar/<int:pk>/<slug:slug>/', views.EvaluacionRxEditView.as_view(), name='evaluacionrx_editar'),
    path('evaluacionrx/listar-evaluacionesrx/', views.listarEvaluacionrx.as_view(), name='listar_evalucionesrx'),
    path('evaluacionrx/listar-evaluacionesrx_API/', views.listarEvaluacionrxAPI, name='listar_evalucionesrx_API'),
    path('evaluacionrx/listar-evalucionesrx-paciente-API/', views.listarEvaluacionRxPacienteAPI, name='listar_evalucionesrx_paciente_API'),
    path('evaluacionrx/obtener-imagenes-evaluacion/', views.obtenerImagenesEvaluacion, name='obtener_imagenes_evaluacion'),



    path('evaluacionrx/obtener-paciente-externo-dni/', views.obtenerPacienteExterno, name='obtener_paciente_externo_dni'),
    path('inactivar-evalucion-rx/', views.inactivarEvalucionRX, name='inactivar_evalucion_rx'),


    path('demo/', views.DemoView.as_view(), name='demo')

]