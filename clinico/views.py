from django.shortcuts import render
from django.views import View
from django.http import JsonResponse


from core.services.clinico_service import ClinicoService

# Create your views here.
class ListarDiagnostico(View):
    def get(self, request):
        # hacmos usao del service para entregar los diaganosticos activos
        diagnosticos = ClinicoService.obtener_diagnosticos_activos()

        return JsonResponse(diagnosticos, safe=False)
    
class ListarCondicion(View):
    def get(self, request):
        condiciones = ClinicoService.obtener_condiciones_activos()
        return JsonResponse(condiciones, safe=False)
