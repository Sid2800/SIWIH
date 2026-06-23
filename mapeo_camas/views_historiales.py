# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Vistas e historiales de auditoría: listado y detalle (sesiones de mapeo,
historial por cama y movimientos)."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from core.constants.permisos import (
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)
from core.constants.mapeo_camas_constants import DETALLE_PAGE_SIZE_DEFAULT, DETALLE_PAGE_SIZE_MAX
from core.mixins import UnidadRolRequiredMixin
from core.services.mapeo_camas_service import MapeoCamasService
from core.utils.utilidades_fechas import parse_fecha_filtro_dia

from ._permisos import _tiene_permiso_historiales


__all__ = [
    "MapeoCamasHistorialView",
    "MapeoCamasHistorialDetalleView",
    "historiales_camas_filtro",
    "historiales_data",
    "historiales_cards_data",
]


class MapeoCamasHistorialView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales.html"
    # [2026-06-22 AUDIT] Se mantiene el mixin en la vista, pero el acceso real
    # a historiales es el criterio especial superusuario/global sin permiso extra.
    required_roles = MAPEO_CAMAS_VISUALIZACION_ROLES
    required_unidades = MAPEO_CAMAS_VISUALIZACION_UNIDADES

    def dispatch(self, request, *args, **kwargs):
        # [2026-06-23] super() primero para que LoginRequiredMixin redirija a login si no autenticado
        respuesta_mixin = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return respuesta_mixin
        if not _tiene_permiso_historiales(request.user):
            return redirect("acceso_denegado")
        return respuesta_mixin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Historiales de Camas"
        context["subtitulo"] = "Consulta de historial, movimientos y mapeos"
        return context


class MapeoCamasHistorialDetalleView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales_detalle.html"
    # [2026-06-22 AUDIT] Se mantiene el mixin en la vista, pero el acceso real
    # a historiales es el criterio especial superusuario/global sin permiso extra.
    required_roles = MAPEO_CAMAS_VISUALIZACION_ROLES
    required_unidades = MAPEO_CAMAS_VISUALIZACION_UNIDADES

    def dispatch(self, request, *args, **kwargs):
        # [2026-06-23] super() primero para que LoginRequiredMixin redirija a login si no autenticado
        respuesta_mixin = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return respuesta_mixin
        if not _tiene_permiso_historiales(request.user):
            return redirect("acceso_denegado")
        return respuesta_mixin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Detalle de Historial"
        context["subtitulo"] = "Cards de detalle por registro"
        return context


@login_required
@require_GET
def historiales_camas_filtro(request):
    """Retorna catálogo de camas para el select de filtros."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    return JsonResponse({"ok": True, "results": MapeoCamasService.obtener_camas_historial_filtro()})


@login_required
@require_GET
def historiales_data(request):
    """Lista registros según tipo: mapeo, historial o movimiento."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    # 2026-06-09: usa helper general de core para parseo de filtros de fecha.
    tipo = (request.GET.get("tipo") or "mapeo").strip().lower()
    cama_id = (request.GET.get("cama_id") or "").strip()
    fecha_inicio = parse_fecha_filtro_dia(request.GET.get("fecha_inicio"), fin_del_dia=False)
    fecha_fin = parse_fecha_filtro_dia(request.GET.get("fecha_fin"), fin_del_dia=True)

    if tipo not in {"mapeo", "historial", "movimiento"}:
        return JsonResponse({"ok": False, "error": "Tipo de historial no valido."}, status=400)

    payload, status = MapeoCamasService.obtener_historiales_data(
        tipo,
        cama_id=cama_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
    return JsonResponse(payload, status=status)


@login_required
@require_GET
def historiales_cards_data(request):
    """Devuelve cards de detalle según tipo seleccionado y registro."""
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    tipo = (request.GET.get("tipo") or "").strip().lower()
    registro_id = (request.GET.get("id") or "").strip()

    try:
        page = max(int(request.GET.get("page") or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get("page_size") or DETALLE_PAGE_SIZE_DEFAULT)
    except (TypeError, ValueError):
        page_size = DETALLE_PAGE_SIZE_DEFAULT
    page_size = max(1, min(page_size, DETALLE_PAGE_SIZE_MAX))

    payload, status = MapeoCamasService.obtener_historiales_cards_data(
        tipo,
        registro_id,
        page=page,
        page_size=page_size,
    )
    return JsonResponse(payload, status=status)
