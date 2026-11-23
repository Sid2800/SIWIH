
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views import View

from core.services.mapeo_camas_service import MapeoCamasService
from core.services.reporte.PDF.reporte_mapeo_service import ReporteMapeoService
from django.http.response import JsonResponse
# from reportes.services.mapeo_camas import ReporteMapeoCamasService


class ReporteMapeoSesion(LoginRequiredMixin, View):
    """
    Genera el PDF correspondiente a una sesión de mapeo de camas.
    """

    def get(self, request, sesion_id):
        # 1. Obtener los datos de la sesión para el reporte.
        usuario = request.user

        data = MapeoCamasService.construir_data_reporte_sesion(
            sesion_id=sesion_id
        )
        
        if not data:
            raise Http404("La sesión de mapeo de camas no existe.")


        
        return ReporteMapeoService.generar_reporte_sesion(data, usuario)
        

