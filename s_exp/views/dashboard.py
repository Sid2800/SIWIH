"""
dashboard.py - Vistas de plantilla (landing) y APIs de dashboard/catalogos basicos.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET

from django.shortcuts import redirect

from s_exp.models import MotivoSolicitud, ExpedientePrestamo, SolicitudPrestamo, Prestamo
from expediente.models import Expediente


from .comunes import (
    SExpAdminMixin,
    SExpUsuarioMixin,
    _es_exp_admin,
    _get_unidad_usuario,
)


logger = logging.getLogger("s_exp")


# ============================================
# VISTAS ADMIN (Templates)
# ============================================

class DashboardAdminView(SExpAdminMixin, TemplateView):
    """Redirige a Gestión de Solicitudes como landing del admin."""
    def get(self, request, *args, **kwargs):
        return redirect('s_exp_solicitudes')


class GestionSolicitudesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/gestion_solicitudes.html'


class MonitoreoPrestamosView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/monitoreo_prestamos.html'


class ControlDevolucionesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/control_devoluciones.html'


class ReportesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/reportes.html'


# ============================================
# VISTAS USUARIO (Templates)
# ============================================

class BuscadorExpedientesView(SExpUsuarioMixin, TemplateView):
    template_name = 's_exp/buscador_expedientes.html'


class SeguimientoView(SExpUsuarioMixin, TemplateView):
    template_name = 's_exp/seguimiento_usuario.html'


# ============================================
# APIs ADMIN - Dashboard Stats
# ============================================

@require_GET
def dashboard_stats_api(request):
    """Retorna estadísticas para el dashboard del admin."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from expediente.models import Expediente
        total = Expediente.objects.count()

        # Expedientes con préstamo activo
        prestados = ExpedientePrestamo.objects.filter(estado_id='EXP_PRESTADO').count()
        disponibles = total - prestados

        solicitudes_pendientes = SolicitudPrestamo.objects.filter(estado_flujo_id='SOL_PENDIENTE').count()

        ahora = timezone.now()
        prestamos_activos = Prestamo.objects.filter(estado='Entregado').count()
        prestamos_vencidos = Prestamo.objects.filter(
            estado='Entregado',
            fecha_limite__lt=ahora
        ).count()

        # Próximos a vencer (más del 90% de tiempo usado)
        proximos_vencer = 0
        for p in Prestamo.objects.filter(estado='Entregado', fecha_limite__gte=ahora):
            if p.porcentaje_tiempo_usado >= 90:
                proximos_vencer += 1

        devoluciones_parciales = Prestamo.objects.filter(estado='DevolucionParcial').count()

        return JsonResponse({
            "total_expedientes": total,
            "disponibles": disponibles,
            "prestados": prestados,
            "solicitudes_pendientes": solicitudes_pendientes,
            "prestamos_activos": prestamos_activos,
            "prestamos_vencidos": prestamos_vencidos,
            "proximos_vencer": proximos_vencer,
            "devoluciones_parciales": devoluciones_parciales,
        })
    except Exception as e:
        logger.error(f"Error en dashboard_stats_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# API: Catálogo de Motivos
# ============================================

@require_GET
def motivos_api(request):
    """Retorna la lista de motivos activos para el dropdown."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    motivos = MotivoSolicitud.objects.filter(activo=True).order_by('nombre')
    data = [{"id": m.id, "nombre": m.nombre} for m in motivos]
    return JsonResponse({"data": data})


# ============================================
# API: Info del usuario (unidad)
# ============================================

@require_GET
def info_usuario_api(request):
    """Retorna información del usuario para el formulario de solicitud."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    unidad = _get_unidad_usuario(request.user)
    return JsonResponse({
        "unidad": unidad,
        "es_admin": _es_exp_admin(request.user),
    })
