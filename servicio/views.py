from django.shortcuts import render
from dal import autocomplete
from django.http import JsonResponse
from core.services.servicio_service import ServicioService
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views import View
import json

# Create your views here.
class CamaAutocomplete(autocomplete.Select2QuerySetView):
    
    def get_queryset(self):
        return ServicioService.obtener_camas_activas()
    
    def get_result_label(self, result):
        return f"{result.numero_cama} {result.sala}"

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        camas = self.get_queryset()
        
        # Filtramos las camas según el término de búsqueda
        if query:
            camas = camas.filter(
                Q(numero_cama__icontains=query) |
                Q(sala__nombre_sala__icontains=query)
            )
                    
        # Creamos la respuesta en formato JSON
        results = [
            {
                'id': cama.numero_cama,
                'text': f"{cama.numero_cama} {cama.sala}",
                'id_sala': cama.sala.id,
            }
            for cama in camas
        ]
        
        return JsonResponse({'results': results})
"""
class SalaAutocomplete(autocomplete.Select2QuerySetView):
    
    def get_queryset(self):
        return ServicioService.obtener_salas_activas()
    
    def get_result_label(self, result):
        return f"{result.nombre_sala} {result.servicio}"

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        salas = self.get_queryset()
        
        # Filtramos las camas según el término de búsqueda
        if query:
            salas = salas.filter(
                Q(nombre_sala__icontains=query) |
                Q(servicio__nombre_servicio__icontains=query)
            )
                    
        # Creamos la respuesta en formato JSON
        results = [
            {
                'id': sala.id,
                'text': f"{sala.nombre_sala} {sala.servicio.nombre_servicio}",
            }
            for sala in salas
        ]
        
        return JsonResponse({'results': results})
"""

class ListarSala(View):
    def get(self, request):
        # Llamamos al servicio de obtener municipios por departamento
        zonas = ServicioService.obtener_salas_activas()

        return JsonResponse(zonas, safe=False)
    

class ListarEspecialidadServicio(View):
    def get(self, request):
        id_servicio = request.GET.get('id_servicio')

        # Validación: existencia
        if not id_servicio:
            return JsonResponse({'error': ('Parámetro "id_servicio" requerido.')}, status=400)

        # Validación: número entero
        try:
            id_servicio = int(id_servicio)
        except ValueError:
            return JsonResponse({'error': ('El parámetro "id_servicio" debe ser un número entero.')}, status=400)

        # Obtener especialidades activas
        especialidades = ServicioService.obtener_especialidades_activas_servicio(id_servicio)

        return JsonResponse(especialidades, safe=False)


class ListarZona(View):
    def get(self, request):
        # Llamamos al servicio de obtener municipios por departamento
        zonas = ServicioService.obtener_zonas()
        return JsonResponse(zonas, safe=False)
    
@csrf_exempt 
def cambiarZona(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            
            nueva_zona = ServicioService.cambiar_zona(request, data)

            if nueva_zona:
                return JsonResponse({
                    'zona': nueva_zona.codigo,
                    'nombre_zona': nueva_zona.nombre_zona
                }, status=200)
            else:
                return JsonResponse({'error': 'Zona no válida'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)