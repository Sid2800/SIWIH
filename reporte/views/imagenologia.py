from django.http import HttpResponse, JsonResponse
from core.services.imagenologia_service import EvaluacionService
from core.services.reporte.PDF.reporte_imagenologia_service import ReporteImagenologiaService
from core.validators.fecha_validator import validar_anio, validar_mes
from reporte.validators import validar_informe
from django.views import View
import datetime
import json


class InformesImagenologia(View):
    def post(self, request, *args, **kwargs):
        usuario = request.user

        # --- Cargar JSON ---
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'El cuerpo de la solicitud no contiene JSON válido.'}, status=400)

        # --- Obtener parámetros ---
        anio = data.get("anio")
        mes = data.get("mes")
        informe = data.get("informe")

        # --- Validar que existan ---
        if not all([anio, mes, informe]):
            return JsonResponse({"error": "Debe proporcionar año, mes e informe."}, status=400)

        try:
            anio = validar_anio(anio)                
            mes = validar_mes(mes)
            informe = validar_informe(informe, [1, 2, 3, 4]) 
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        # --- Preparar criterios del reporte ---
        reporte_criterios = {
            'mes': mes,
            'anio': anio,
            'usuario': usuario,
            'usuario_nombre': f"{usuario.first_name} {usuario.last_name}"
        }

        # --- Generar reportes según el tipo ---
        if informe in [1, 2]:
            data = EvaluacionService.generarDataInformeGastoCostoPelicula(mes, anio, informe)
            if not data or not data.get('tabla'):
                return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)

            reporte_criterios.update({
                'data': data.get('tabla'),
                'total': data.get('total'),
                'dias': data.get('dias'),
            })
            return ReporteImagenologiaService.generarInformeGastoCostoPelicula(reporte_criterios, informe)

        elif informe == 3:
            data = EvaluacionService.generarDataInformePacienteSala(mes, anio)
            if not data or not data.get('tabla'):
                return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)

            reporte_criterios.update({
                'data': data.get('tabla'),
                'total': data.get('total'),
                'dias': data.get('dias'),
            })
            return ReporteImagenologiaService.generarInformeGastoCostoPelicula(reporte_criterios, informe)

        elif informe == 4:
            data = EvaluacionService.generarDataInformeEstudioDependecia(mes, anio)
            if not data or not data.get('tabla'):
                return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)

            reporte_criterios.update({
                'data': data.get('tabla'),
                'total': data.get('total'),
                'columnas': data.get('columnas'),
            })
            return ReporteImagenologiaService.generarInformeEstudioDependecia(reporte_criterios)

        return JsonResponse({'error': 'Informe no reconocido.'}, status=400)
    
