# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Dashboard operativo de KPIs y monitoreo en tiempo real."""

from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, DurationField, ExpressionWrapper, F, OuterRef, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from core.constants.permisos import (
    MAPEO_CAMAS_DASHBOARD_ROLES,
    MAPEO_CAMAS_DASHBOARD_UNIDADES,
)
from core.mixins import UnidadRolRequiredMixin
from ingreso.models import Ingreso
from servicio.models import Cama

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    HistorialEstadoCama,
    MovimientoCama,
)

from ._helpers import (
    _hora_local_iso,
    _nombre_cama,
    _nombre_usuario,
    _paciente_payload,
)
from ._permisos import _tiene_permiso_dashboard
from ._sesion import _obtener_sesion_mapeo_activa


__all__ = [
    "DashboardMapeoCamasView",
    "dashboard_kpis",
    "dashboard_ocupacion_servicio",
    "dashboard_distribucion_camas",
    "dashboard_ocupacion_hora",
    "dashboard_saturacion_sala",
    "dashboard_ultimos_movimientos",
]


# =============================================================================
# [2026-05-28] Dashboard de KPIs hospitalarios en tiempo real
# =============================================================================
class DashboardMapeoCamasView(UnidadRolRequiredMixin, TemplateView):
    """[2026-05-28] Dashboard operativo de KPIs y gráficas en tiempo real."""
    template_name = "mapeo_camas/dashboard/dashboard.html"
    required_roles = MAPEO_CAMAS_DASHBOARD_ROLES
    required_unidades = MAPEO_CAMAS_DASHBOARD_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Dashboard · Mapeo de Camas"
        context["subtitulo"] = "Indicadores operativos y monitoreo continuo"
        return context


def _dashboard_response(data, meta=None):
    """[2026-05-28] Envoltura estándar de respuesta para endpoints del dashboard."""
    payload = {
        "ok": True,
        "ts": timezone.localtime(timezone.now()).isoformat(),
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    return JsonResponse(payload)


def _dashboard_error(msg, status=500):
    """[2026-05-28] Respuesta de error uniforme para el dashboard."""
    return JsonResponse(
        {"ok": False, "error": str(msg), "ts": timezone.localtime(timezone.now()).isoformat()},
        status=status,
    )


def _dashboard_inicio_dia():
    """[2026-05-28] Inicio del día actual en zona horaria local."""
    ahora = timezone.localtime(timezone.now())
    return ahora.replace(hour=0, minute=0, second=0, microsecond=0)


def _dashboard_parse_range(request):
    """
    [2026-05-28] Parsea ?desde=ISO&hasta=ISO. Devuelve (desde, hasta) aware.
    Default: día actual completo (00:00 → ahora).
    """
    tz = timezone.get_current_timezone()
    ahora = timezone.localtime(timezone.now())

    def _parse(s):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, tz)
        return dt

    desde = _parse(request.GET.get("desde"))
    hasta = _parse(request.GET.get("hasta"))

    if desde is None:
        desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    if hasta is None:
        hasta = ahora
    if hasta < desde:
        desde, hasta = hasta, desde
    return desde, hasta


def _dashboard_granularidad(desde, hasta):
    """[2026-05-28] hora si span ≤ 2 días, día si ≤ 60 días, mes si >."""
    span = hasta - desde
    if span.total_seconds() <= 2 * 86400:
        return "hora"
    if span.days <= 60:
        return "dia"
    return "mes"


def _snapshot_estado_camas(hasta):
    """
    [2026-05-28] {codigo_estado: cantidad} de TODAS las camas activas
    según su estado en el momento `hasta`.
    """
    ahora = timezone.now()
    delta = (ahora - hasta).total_seconds() if hasta <= ahora else 0
    if 0 <= delta <= 60:
        ultima_asig_id = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=OuterRef("cama_id"))
            .order_by("-fecha_inicio", "-id")
            .values("id")[:1]
        )
        rows = (
            AsignacionCamaPaciente.objects
            .filter(id=Subquery(ultima_asig_id))
            .values("cama_id", "estado__codigo")
        )
        estado_por_cama = {r["cama_id"]: r["estado__codigo"] for r in rows}
    else:
        ult_hist = (
            HistorialEstadoCama.objects
            .filter(cama_id=OuterRef("pk"), fecha_hora__lte=hasta)
            .order_by("-fecha_hora", "-id")
            .values("estado_nuevo__codigo")[:1]
        )
        rows = (
            Cama.objects.filter(estado=1)
            .annotate(_estado_hist=Subquery(ult_hist))
            .values("numero_cama", "_estado_hist")
        )
        estado_por_cama = {r["numero_cama"]: r["_estado_hist"] for r in rows}

    conteo = {}
    for cama_id in Cama.objects.filter(estado=1).values_list("numero_cama", flat=True):
        cod = estado_por_cama.get(cama_id) or "VACIA"
        conteo[cod] = conteo.get(cod, 0) + 1
    return conteo


def _snapshot_estado_por_cama(hasta):
    """[2026-05-28] {cama_id: codigo_estado} en el momento `hasta`."""
    ahora = timezone.now()
    delta = (ahora - hasta).total_seconds() if hasta <= ahora else 0
    if 0 <= delta <= 60:
        ultima_asig_id = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=OuterRef("cama_id"))
            .order_by("-fecha_inicio", "-id")
            .values("id")[:1]
        )
        return {
            r["cama_id"]: r["estado__codigo"]
            for r in AsignacionCamaPaciente.objects
            .filter(id=Subquery(ultima_asig_id))
            .values("cama_id", "estado__codigo")
        }
    ult_hist = (
        HistorialEstadoCama.objects
        .filter(cama_id=OuterRef("pk"), fecha_hora__lte=hasta)
        .order_by("-fecha_hora", "-id")
        .values("estado_nuevo__codigo")[:1]
    )
    return {
        r["numero_cama"]: r["_estado_hist"] or "VACIA"
        for r in Cama.objects.filter(estado=1)
        .annotate(_estado_hist=Subquery(ult_hist))
        .values("numero_cama", "_estado_hist")
    }


def _rango_meta(desde, hasta):
    """[2026-05-28] Meta serializable del rango aplicado."""
    return {
        "desde": timezone.localtime(desde).isoformat(),
        "hasta": timezone.localtime(hasta).isoformat(),
        "granularidad": _dashboard_granularidad(desde, hasta),
    }


@login_required
@require_GET
def dashboard_kpis(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)

        conteo_por_estado = _snapshot_estado_camas(hasta)
        total_camas = Cama.objects.filter(estado=1).count()
        ocupadas = conteo_por_estado.get("OCUPADA", 0)
        disponibles = conteo_por_estado.get("VACIA", 0) + conteo_por_estado.get("LIBRE", 0)
        fuera_servicio = (
            conteo_por_estado.get("FUERA_SERVICIO", 0) + conteo_por_estado.get("MANTENIMIENTO", 0)
        )
        pct = round((ocupadas / total_camas) * 100, 1) if total_camas else 0

        altas_rango = Ingreso.objects.filter(
            fecha_egreso__gte=desde, fecha_egreso__lte=hasta
        ).count()
        traslados = MovimientoCama.objects.filter(
            fecha_hora__gte=desde, fecha_hora__lte=hasta
        ).count()

        sesion = _obtener_sesion_mapeo_activa(request.user)
        cambios_mapeo = 0
        camas_validadas = 0
        if sesion:
            cambios_mapeo = DetalleMapeoCama.objects.filter(
                sesion_mapeo=sesion, hubo_cambio=True
            ).count()
            camas_validadas = (
                DetalleMapeoCama.objects.filter(sesion_mapeo=sesion, fue_validada=True)
                .values("cama_id").distinct().count()
            )

        duracion_expr = ExpressionWrapper(
            F("fecha_egreso") - F("fecha_ingreso"), output_field=DurationField()
        )
        prom = (
            Ingreso.objects.filter(
                fecha_egreso__gte=desde,
                fecha_egreso__lte=hasta,
                fecha_ingreso__isnull=False,
            )
            .annotate(duracion=duracion_expr)
            .aggregate(prom=Avg("duracion"))
            .get("prom")
        )
        if prom:
            horas = prom.total_seconds() / 3600.0
            if horas >= 24:
                tiempo_prom_str = f"{horas / 24:.1f} d"
            else:
                tiempo_prom_str = f"{horas:.1f} h"
        else:
            tiempo_prom_str = "—"

        return _dashboard_response({
            "total_camas": total_camas,
            "ocupadas": ocupadas,
            "disponibles": disponibles,
            "fuera_servicio": fuera_servicio,
            "porcentaje_ocupacion": pct,
            "altas_dia": altas_rango,
            "traslados": traslados,
            "cambios_mapeo": cambios_mapeo,
            "camas_validadas": camas_validadas,
            "tiempo_promedio": tiempo_prom_str,
        }, meta=_rango_meta(desde, hasta))
    except Exception as exc:
        return _dashboard_error(exc)


@login_required
@require_GET
def dashboard_ocupacion_servicio(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)
        estado_por_cama = _snapshot_estado_por_cama(hasta)

        camas = (
            Cama.objects.filter(estado=1, sala__estado=1, sala__servicio__estado=1)
            .values("numero_cama", "sala__servicio_id", "sala__servicio__nombre_servicio")
        )
        agg = {}
        for cama in camas:
            key = (cama["sala__servicio_id"], cama["sala__servicio__nombre_servicio"])
            bucket = agg.setdefault(key, {"servicio": key[1], "ocupadas": 0, "disponibles": 0, "otros": 0})
            cod = estado_por_cama.get(cama["numero_cama"]) or "VACIA"
            if cod == "OCUPADA":
                bucket["ocupadas"] += 1
            elif cod in ("VACIA", "LIBRE"):
                bucket["disponibles"] += 1
            else:
                bucket["otros"] += 1

        items = sorted(agg.values(), key=lambda x: x["servicio"])
        return _dashboard_response({"items": items}, meta=_rango_meta(desde, hasta))
    except Exception as exc:
        return _dashboard_error(exc)


@login_required
@require_GET
def dashboard_distribucion_camas(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)
        conteo = _snapshot_estado_camas(hasta)
        items = [
            {"estado": cod, "cantidad": qty}
            for cod, qty in sorted(conteo.items(), key=lambda kv: kv[0])
        ]
        return _dashboard_response({"items": items}, meta=_rango_meta(desde, hasta))
    except Exception as exc:
        return _dashboard_error(exc)


@login_required
@require_GET
def dashboard_ocupacion_hora(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)
        granularidad = _dashboard_granularidad(desde, hasta)
        total_camas = max(Cama.objects.filter(estado=1).count(), 1)

        conteo_inicio = _snapshot_estado_camas(desde)
        ocupadas_inicio = conteo_inicio.get("OCUPADA", 0)

        eventos = (
            HistorialEstadoCama.objects
            .filter(fecha_hora__gte=desde, fecha_hora__lte=hasta)
            .values("fecha_hora", "estado_nuevo__codigo")
        )

        def _bin_key(dt):
            local = timezone.localtime(dt)
            if granularidad == "hora":
                return local.replace(minute=0, second=0, microsecond=0)
            if granularidad == "dia":
                return local.replace(hour=0, minute=0, second=0, microsecond=0)
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        def _bin_label(dt):
            if granularidad == "hora":
                return dt.strftime("%d/%m %H:00")
            if granularidad == "dia":
                return dt.strftime("%d/%m")
            return dt.strftime("%m/%Y")

        def _bin_next(dt):
            if granularidad == "hora":
                return dt + timedelta(hours=1)
            if granularidad == "dia":
                return dt + timedelta(days=1)
            year = dt.year + (1 if dt.month == 12 else 0)
            month = 1 if dt.month == 12 else dt.month + 1
            return dt.replace(year=year, month=month)

        bins = []
        cursor = _bin_key(desde)
        fin = timezone.localtime(hasta)
        while cursor <= fin:
            bins.append(cursor)
            cursor = _bin_next(cursor)

        ocupa = {b: 0 for b in bins}
        libera = {b: 0 for b in bins}
        for ev in eventos:
            b = _bin_key(ev["fecha_hora"])
            if b not in ocupa:
                continue
            cod = ev["estado_nuevo__codigo"]
            if cod == "OCUPADA":
                ocupa[b] += 1
            elif cod in ("VACIA", "LIBRE", "ALTA"):
                libera[b] += 1

        items = []
        ocupadas = ocupadas_inicio
        for b in bins:
            ocupadas = max(0, ocupadas + ocupa[b] - libera[b])
            items.append({
                "hora": _bin_label(b),
                "porcentaje": round((ocupadas / total_camas) * 100, 1),
            })
        return _dashboard_response(
            {"items": items, "granularidad": granularidad},
            meta=_rango_meta(desde, hasta),
        )
    except Exception as exc:
        return _dashboard_error(exc)


@login_required
@require_GET
def dashboard_saturacion_sala(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)
        estado_por_cama = _snapshot_estado_por_cama(hasta)
        camas = (
            Cama.objects.filter(estado=1, sala__estado=1, sala__servicio__estado=1)
            .values(
                "numero_cama",
                "sala_id",
                "sala__nombre_sala",
                "sala__servicio__nombre_servicio",
            )
        )
        agg = {}
        for cama in camas:
            servicio = cama["sala__servicio__nombre_servicio"]
            sala = cama["sala__nombre_sala"]
            key = (servicio, sala)
            bucket = agg.setdefault(key, {"total": 0, "ocupadas": 0})
            bucket["total"] += 1
            if estado_por_cama.get(cama["numero_cama"]) == "OCUPADA":
                bucket["ocupadas"] += 1

        series_map = {}
        for (servicio, sala), bucket in agg.items():
            pct = round((bucket["ocupadas"] / bucket["total"]) * 100, 1) if bucket["total"] else 0
            series_map.setdefault(servicio, []).append({"sala": sala, "porcentaje": pct})

        series = [
            {"servicio": servicio, "salas": sorted(salas, key=lambda s: s["sala"])}
            for servicio, salas in sorted(series_map.items())
        ]
        return _dashboard_response({"series": series}, meta=_rango_meta(desde, hasta))
    except Exception as exc:
        return _dashboard_error(exc)


@login_required
@require_GET
def dashboard_ultimos_movimientos(request):
    if not _tiene_permiso_dashboard(request.user):
        return _dashboard_error("Acceso denegado.", status=403)
    try:
        desde, hasta = _dashboard_parse_range(request)
        try:
            limit = int(request.GET.get("limit") or 30)
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(limit, 500))

        movimientos = (
            MovimientoCama.objects
            .filter(fecha_hora__gte=desde, fecha_hora__lte=hasta)
            .select_related(
                "cama_origen__sala__servicio",
                "cama_destino__sala__servicio",
                "ingreso__paciente",
                "usuario",
            )
            .order_by("-fecha_hora")[:limit]
        )
        items = []
        for mov in movimientos:
            paciente = _paciente_payload(
                mov.ingreso.paciente if mov.ingreso_id else None,
                ingreso_id=mov.ingreso_id,
            )
            servicio_origen = getattr(getattr(mov.cama_origen, "sala", None), "servicio", None)
            servicio_nombre = getattr(servicio_origen, "nombre_servicio", "") or ""
            items.append({
                "fecha": _hora_local_iso(mov.fecha_hora),
                "tipo": mov.tipo_movimiento,
                "cama_origen": _nombre_cama(mov.cama_origen),
                "cama_destino": _nombre_cama(mov.cama_destino),
                "paciente": paciente["nombre"] if paciente else "",
                "servicio": servicio_nombre,
                "usuario": _nombre_usuario(mov.usuario),
            })
        return _dashboard_response({"items": items}, meta=_rango_meta(desde, hasta))
    except Exception as exc:
        return _dashboard_error(exc)
