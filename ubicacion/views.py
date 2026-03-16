from dal import autocomplete
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from core.services.ubicacion_service import UbicacionService

import json

class SectorAutocomplete(autocomplete.Select2QuerySetView):

   def get_queryset(self):
      municipio_id = self.request.GET.get('municipio_id', None)
      query = self.q  # Capturamos la consulta de búsqueda

      # Llamamos al servicio de obtener ubicaciones por municipio
      qs = UbicacionService.obtener_sectores_por_municipio(municipio_id, query)
      
      return qs

   def get_result_label(self, result):
      return f"{result.nombre_sector}"
   

class AldeaAutocomplete(autocomplete.Select2QuerySetView):

   def get_queryset(self):
      municipio_id = self.request.GET.get('municipio_id', None)
      query = self.q  # Capturamos la consulta de búsqueda
      # Llamamos al servicio de obtener ubicaciones por municipio
      qs = UbicacionService.obtener_aldeas_por_municipio(municipio_id, query)
      
      return qs

   def get_result_label(self, result):
      return f"{result.nombre_aldea}"
   

class MunicipiosXdepto(View):
   def get(self, request):
      departamento_id = request.GET.get('departamento_id')
      # Llamamos al servicio de obtener municipios por departamento
      municipios = UbicacionService.obtener_municipios_por_departamento(departamento_id)
      return JsonResponse(municipios, safe=False)


def obtener_detalles_domicilio(request):
   id_sector = request.GET.get('id_sector')

   if not id_sector:
      return JsonResponse({"error": "Falta el parámetro id_sector"}, status=400)

   # Llamamos al servicio de obtener detalles del domicilio
   detalles = UbicacionService.obtener_detalles_domicilio(id_sector)

   return JsonResponse(detalles, safe=False)


def agregar_sector(request):
   if request.method == "POST":
      try:
         # Obtener los datos JSON del body
         data = json.loads(request.body)
         
         nuevoSector = UbicacionService.registrar_sector(data)

         # Si todo está bien, enviar una respuesta positiva
         return JsonResponse({'sector_id': nuevoSector.id,'nombre_sector': nuevoSector.nombre_sector, 'message': 'Sector registrado correctamente'}, status=200)

      except Exception as e:
         # En caso de error, devolver mensaje de error
         return JsonResponse({'error': str(e)}, status=400)

   return JsonResponse({'error': 'Método no permitido'}, status=405)