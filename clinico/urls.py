from django.urls import path
from clinico import views

urlpatterns = [
    path('listar-diagnostico/',views.ListarDiagnostico.as_view(), name='listar_diagnostico'),
    path('listar-condiciones/',views.ListarCondicion.as_view(), name='listar_condiciones')

]
