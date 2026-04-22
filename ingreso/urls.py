from django.urls import path
from ingreso import views


urlpatterns = [

    path('agregar/<int:pk>/<slug:slug>/', views.IngresoAddView.as_view(), name='ingreso_agregar'),
    path('editar/<int:pk>/<slug:slug>/', views.IngresoEditView.as_view(), name='ingreso_editar'),

    path('obtener-acompaniante/', views.obtener_acompaniante, name='obtener-acompaniante'),
    path('inactivar-ingreso/', views.inactivarIngreso, name='inactivar_ingreso'),
    path('validar-ingreso-activo/', views.validar_ingreso_activo, name='validar-ingreso-activo'),
    path('recibir_ingresos_sala/', views.RecepcionIngresosSala.as_view(), name='recibir-ingresos-sala'),
    path('recibir_ingresos_sdgi/', views.RecepcionIngresosSDGI.as_view(), name='recibir-ingresos-sdgi'),
    path('recibir_ingresos_sdgi/', views.RecepcionIngresosSDGI.as_view(), name='recibir-ingresos-sdgi'),
    
    path('listar_ingresos/', views.listarIngresos.as_view(), name='listar_ingresos'),
    path('listar_ingresos_API/', views.listarIngresosAPI, name='listar_ingresos_API'),
    path('listar_ingresos_paciente_API/', views.listarIngresosPacienteAPI, name='listar-ingresos-paciente-API'),

    path('registrar_recepcion_ingresos_sala/', views.registrarRecepcionIngresosSala, name='registrar-recepcion-ingresos-sala'),
    path('registrar_recepcion_ingresos_sdgi/', views.registrarRecepcionIngresosSDGI, name='registrar-recepcion-ingresos-sdgi'),
    

    
]