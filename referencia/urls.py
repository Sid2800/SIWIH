from django.urls import path
from referencia import views


urlpatterns = [
    path('agregar/<int:pk>/<slug:slug>/', views.ReferenciaAddView.as_view(), name='referencia_agregar'),
    path('editar/<int:pk>/<slug:slug>/', views.ReferenciaEditView.as_view(), name='referencia_editar'),
    path('respuesta-agregar', views.RespuestaCreateUpdateView.as_view(), name='respuesta_agregar'),
    path('seguimiento-agregar-editar', views.SeguimientoCreateUpdateView.as_view(), name='seguimiento_agregar_editar'),
    path("seguimiento-obtener/", views.obtener_seguimiento_tic, name="seguimiento_tic_obtener"),
    path('listar_referencias/', views.listarReferencias.as_view(), name='listar_referencias'),
    path('listar-referencias-API/', views.listarEvaluacionrxAPI, name='listar_referencias_API'),


]