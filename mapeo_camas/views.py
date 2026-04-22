from datetime import datetime, timedelta
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from mapeo_camas.models import (
    AsignacionCamaPaciente,
    DetalleMapeoCama,
    HistorialEstadoCama,
    MapeoSesionCama,
    MovimientoCama,
)
from core.services.mapeo_camas_service import MapeoCamasService
from ingreso.models import Ingreso
from paciente.models import Paciente
from servicio.models import Cama, Cubiculo, Sala, Servicio


# =============================================================================
# Constantes de configuración operativa
# -----------------------------------------------------------------------------
# MAX_CAMBIOS_CAMA: número máximo de movimientos permitidos por sala dentro
# de la ventana temporal, para usuarios que no son superadmin.
# VENTANA_LIMITE_CAMBIOS_SALA_HORAS: tamaño de la ventana de tiempo (horas)
# que se usa para contabilizar los cambios manuales y resetear el conteo.
# Las constantes OBSERVACION_* son los textos fijos grabados en el historial,
# usados también como criterio de filtrado al contar cambios por sala.
# =============================================================================
MAX_CAMBIOS_CAMA = 5
# Parametro de ventana para reinicio del limite por sala (horas)
VENTANA_LIMITE_CAMBIOS_SALA_HORAS = 1
OBSERVACION_CAMBIO_MANUAL_MAPA = "Cambio manual desde mapa"
OBSERVACION_CAMBIO_MANUAL_MAPA_DETALLE = "Cambio manual desde mapa (detalle)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA = "Movimiento de paciente entre camas (mapa)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE = "Movimiento de paciente entre camas (mapa detalle)"
OBSERVACION_LIBERACION_ALTA_AUTOMATICA = "Liberacion automatica de cama en PRE_ALTA por nueva ocupacion"


# =============================================================================
# MapeoCamasMapaView
# -----------------------------------------------------------------------------
# Vista de tipo TemplateView que únicamente renderiza el HTML base del mapa.
# No lleva datos de camas en el contexto: la estructura completa se obtiene
# después vía la API mapa_camas_data (llamada desde JavaScript al cargar la página).
# =============================================================================
class MapeoCamasMapaView(LoginRequiredMixin, TemplateView):
    template_name = "mapeo_camas/mapa.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Mapa de Camas"
        context["subtitulo"] = "Asignacion por paciente y estado de cama"
        return context


class MapeoCamasHistorialView(LoginRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Historiales de Camas"
        context["subtitulo"] = "Consulta de historial, movimientos y mapeos"
        return context


class MapeoCamasHistorialDetalleView(LoginRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales_detalle.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Detalle de Historial"
        context["subtitulo"] = "Cards de detalle por registro"
        return context


# --- Helpers privados --------------------------------------------------------

def _nombre_paciente(paciente):
    """Construye el nombre completo del paciente concatenando los cuatro campos.
    Retorna 'Sin nombre' si todos están vacíos."""
    partes = [
        getattr(paciente, "primer_nombre", ""),
        getattr(paciente, "segundo_nombre", ""),
        getattr(paciente, "primer_apellido", ""),
        getattr(paciente, "segundo_apellido", ""),
    ]
    nombre = " ".join([p for p in partes if p]).strip()
    return nombre or "Sin nombre"


def _nombre_usuario(usuario):
    """Retorna nombre visible del usuario; usa username como fallback."""
    if not usuario:
        return ""
    nombre = ""
    if hasattr(usuario, "get_full_name"):
        nombre = (usuario.get_full_name() or "").strip()
    return nombre or getattr(usuario, "username", "") or ""


def _hora_local_iso(dt):
    """Convierte datetime a ISO local para consumo del frontend."""
    if not dt:
        return ""
    return timezone.localtime(dt).isoformat()


def _estado_visual(asignacion):
    """Devuelve el estado de la asignación para mostrarlo en el mapa.
    Si la cama no tiene asignación registrada, retorna 'SIN_ASIGNACION'."""
    if not asignacion:
        return "SIN_ASIGNACION"
    return asignacion.estado


def _paciente_payload(paciente):
    """Serializa los datos mínimos del paciente para el JSON del mapa.
    Retorna None si no hay paciente (cama vacía)."""
    if not paciente:
        return None
    return {
        "id": paciente.id,
        "nombre": _nombre_paciente(paciente),
        "dni": getattr(paciente, "dni", None) or "",
    }


def _es_superadmin(usuario):
    """Indica si el usuario es superadmin, lo que exime del límite de cambios."""
    return bool(usuario and usuario.is_superuser)


def _inicio_ventana_limite_sala():
    """Calcula el datetime de inicio de la ventana temporal para el conteo de cambios."""
    return timezone.now() - timedelta(hours=VENTANA_LIMITE_CAMBIOS_SALA_HORAS)


def _contar_cambios_manual_por_sala(sala_id):
    """Cuenta cuántos movimientos de paciente se han registrado en la sala
    dentro de la ventana temporal activa. Se usa para aplicar el límite
    MAX_CAMBIOS_CAMA a usuarios no superadmin."""
    if not sala_id:
        return 0

    return HistorialEstadoCama.objects.filter(
        cama__sala_id=sala_id,
        observacion=OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        fecha_hora__gte=_inicio_ventana_limite_sala(),
    ).count()


def _obtener_sesion_mapeo_activa(usuario):
    """Retorna la sesion EN_PROGRESO activa mas reciente del usuario."""
    return (
        MapeoSesionCama.objects.filter(
            usuario=usuario,
            estado=MapeoSesionCama.Estado.EN_PROGRESO,
            fecha_fin__isnull=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )


def _ubicacion_cama(cama):
    """Construye una etiqueta compacta de ubicacion: servicio/sala/modulo."""
    servicio = getattr(getattr(cama, "sala", None), "servicio", None)
    sala_nombre = getattr(getattr(cama, "sala", None), "nombre_sala", "") or "SIN_SALA"
    servicio_nombre = getattr(servicio, "nombre_servicio", "") or "SIN_SERVICIO"
    modulo_nombre = getattr(getattr(cama, "cubiculo", None), "nombre_cubiculo", "") or "SIN_MODULO"
    return f"{servicio_nombre}/{sala_nombre}/{modulo_nombre}"


def _registrar_detalle_mapeo(
    *,
    usuario,
    cama,
    asignacion,
    tipo_accion,
    hubo_cambio,
    observacion="",
    fue_validada=True,
    sesion_mapeo=None,
):
    """Guarda el detalle por cama en tiempo real dentro de la sesion activa."""
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    if not sesion:
        return None

    return DetalleMapeoCama.objects.create(
        sesion_mapeo=sesion,
        cama=cama,
        fue_validada=fue_validada,
        hubo_cambio=hubo_cambio,
        estado_actual=asignacion.estado if asignacion else "SIN_ASIGNACION",
        paciente_actual=asignacion.paciente if asignacion else None,
        ubicacion=_ubicacion_cama(cama),
        tipo_accion=tipo_accion,
        usuario=usuario,
        observacion=observacion or "",
    )


def _camas_mapeadas_sesion(sesion):
    """Retorna ids de camas ya mapeadas en la sesion."""
    if not sesion:
        return []
    return list(
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values_list("cama__numero_cama", flat=True)
        .distinct()
    )


def _meta_ultima_actualizacion(historial):
    """Serializa metadatos de la ultima actualizacion de una cama."""
    if not historial:
        return {
            "ultima_actualizacion": "",
            "usuario_ultima_actualizacion": "",
        }
    return {
        "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
        "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
    }


def _parse_fecha_filtro(fecha_texto, fin_del_dia=False):
    """Convierte fecha YYYY-MM-DD a datetime aware en zona local."""
    if not fecha_texto:
        return None
    try:
        fecha = datetime.strptime(fecha_texto, "%Y-%m-%d")
    except ValueError:
        return None
    if fin_del_dia:
        fecha = fecha.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        fecha = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
    return timezone.make_aware(fecha, timezone.get_current_timezone())


def _nombre_cama(cama):
    if not cama:
        return ""
    return str(getattr(cama, "numero_cama", "") or "")


def _ubicacion_desde_cama(cama):
    if not cama:
        return ""
    sala = getattr(cama, "sala", None)
    servicio = getattr(sala, "servicio", None)
    cubiculo = getattr(cama, "cubiculo", None)
    servicio_nombre = getattr(servicio, "nombre_servicio", "") or ""
    sala_nombre = getattr(sala, "nombre_sala", "") or ""
    cubiculo_nombre = getattr(cubiculo, "nombre_cubiculo", "") or "SIN_CUBICULO"
    return f"{servicio_nombre} / {sala_nombre} / {cubiculo_nombre}"


def _estado_css_mapa(estado):
    """Mapea estado de cama a clase visual usada en el mapa."""
    valor = (estado or "").strip().upper()
    if valor == AsignacionCamaPaciente.Estado.VACIA:
        return "mapa-cama--vacia"
    if valor == AsignacionCamaPaciente.Estado.OCUPADA:
        return "mapa-cama--ocupada"
    if valor in {AsignacionCamaPaciente.Estado.PRE_ALTA, HistorialEstadoCama.Estado.ALTA}:
        return "mapa-cama--alta"
    if valor == AsignacionCamaPaciente.Estado.FUERA_SERVICIO:
        return "mapa-cama--fuera-servicio"
    if valor == AsignacionCamaPaciente.Estado.CONSULTA_EXTERNA:
        return "mapa-cama--consulta-externa"
    return "mapa-cama--sin-asignacion"


@login_required
@require_GET
def historiales_camas_filtro(request):
    """Retorna catálogo de camas para el select de filtros."""
    camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("numero_cama")
    )
    data = []
    for cama in camas:
        data.append(
            {
                "id": str(cama.numero_cama),
                "numero_cama": str(cama.numero_cama),
                "ubicacion": _ubicacion_desde_cama(cama),
            }
        )
    return JsonResponse({"ok": True, "results": data})


@login_required
@require_GET
def historiales_data(request):
    """Lista registros según tipo: mapeo, historial o movimiento."""
    tipo = (request.GET.get("tipo") or "mapeo").strip().lower()
    cama_id = (request.GET.get("cama_id") or "").strip()
    fecha_inicio = _parse_fecha_filtro(request.GET.get("fecha_inicio"), fin_del_dia=False)
    fecha_fin = _parse_fecha_filtro(request.GET.get("fecha_fin"), fin_del_dia=True)

    if tipo not in {"mapeo", "historial", "movimiento"}:
        return JsonResponse({"ok": False, "error": "Tipo de historial no valido."}, status=400)

    if tipo == "mapeo":
        sesiones = MapeoSesionCama.objects.select_related("usuario").order_by("-fecha_inicio")
        if fecha_inicio:
            sesiones = sesiones.filter(fecha_inicio__gte=fecha_inicio)
        if fecha_fin:
            sesiones = sesiones.filter(fecha_inicio__lte=fecha_fin)

        sesiones = sesiones.annotate(
            total_detalles=Count("detalles", distinct=True),
            total_camas=Count("detalles__cama", distinct=True),
            total_cambios=Count("detalles", filter=Q(detalles__hubo_cambio=True), distinct=True),
        )[:200]

        results = []
        for sesion in sesiones:
            results.append(
                {
                    "id": sesion.id,
                    "referencia": f"Sesion {sesion.id}",
                    "tipo": "MAPEO",
                    "estado": sesion.estado,
                    "fecha_principal": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_inicio": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_fin": _hora_local_iso(sesion.fecha_fin),
                    "usuario": _nombre_usuario(sesion.usuario),
                    "observacion": sesion.observacion or "Sin Observaciones",
                }
            )
        return JsonResponse({"ok": True, "results": results})

    if tipo == "historial":
        historial_qs = HistorialEstadoCama.objects.select_related(
            "cama__sala__servicio", "cama__cubiculo", "paciente", "usuario"
        )
        if fecha_inicio:
            historial_qs = historial_qs.filter(fecha_hora__gte=fecha_inicio)
        if fecha_fin:
            historial_qs = historial_qs.filter(fecha_hora__lte=fecha_fin)
        if cama_id:
            historial_qs = historial_qs.filter(cama_id=cama_id)

        # Se muestra una fila por cama (último evento) para abrir luego
        # la línea de tiempo completa de esa cama en el detalle.
        historial_qs = historial_qs.order_by("cama_id", "-fecha_hora", "-id")
        resumen_por_cama = {}
        for item in historial_qs:
            cama_key = str(item.cama_id)
            if cama_key not in resumen_por_cama:
                resumen_por_cama[cama_key] = {
                    "ultimo": item,
                    "total": 1,
                }
            else:
                resumen_por_cama[cama_key]["total"] += 1

        results = []
        camas_ordenadas = sorted(
            resumen_por_cama.values(),
            key=lambda x: x["ultimo"].fecha_hora,
            reverse=True,
        )[:300]

        for registro in camas_ordenadas:
            item = registro["ultimo"]
            total_eventos = registro["total"]
            paciente = _paciente_payload(item.paciente)
            results.append(
                {
                    "id": item.cama_id,
                    "referencia": f"Cama {_nombre_cama(item.cama)}",
                    "tipo": "HISTORIAL",
                    "estado": item.estado_nuevo,
                    "fecha_principal": _hora_local_iso(item.fecha_hora),
                    "fecha_inicio": _hora_local_iso(item.fecha_hora),
                    "fecha_fin": "",
                    "usuario": _nombre_usuario(item.usuario),
                }
            )
        return JsonResponse({"ok": True, "results": results})

    movimientos = (
        MovimientoCama.objects.select_related(
            "cama_origen__sala__servicio",
            "cama_origen__cubiculo",
            "cama_destino__sala__servicio",
            "cama_destino__cubiculo",
            "paciente",
            "usuario",
        )
        .order_by("-fecha_hora")
    )
    if fecha_inicio:
        movimientos = movimientos.filter(fecha_hora__gte=fecha_inicio)
    if fecha_fin:
        movimientos = movimientos.filter(fecha_hora__lte=fecha_fin)
    if cama_id:
        movimientos = movimientos.filter(Q(cama_origen_id=cama_id) | Q(cama_destino_id=cama_id))

    movimientos = movimientos[:300]
    results = []
    for mov in movimientos:
        paciente = _paciente_payload(mov.paciente)
        results.append(
            {
                "id": mov.id,
                "referencia": f"Cama {_nombre_cama(mov.cama_origen)} -> {_nombre_cama(mov.cama_destino)}",
                "tipo": "MOVIMIENTO",
                "estado": mov.tipo_movimiento,
                "fecha_principal": _hora_local_iso(mov.fecha_hora),
                "fecha_inicio": _hora_local_iso(mov.fecha_hora),
                "fecha_fin": "",
                "usuario": _nombre_usuario(mov.usuario),
            }
        )
    return JsonResponse({"ok": True, "results": results})


@login_required
@require_GET
def historiales_cards_data(request):
    """Devuelve cards de detalle según tipo seleccionado y registro."""
    tipo = (request.GET.get("tipo") or "").strip().lower()
    registro_id = (request.GET.get("id") or "").strip()

    if not registro_id:
        return JsonResponse({"ok": False, "error": "Debe indicar id."}, status=400)

    if tipo == "mapeo":
        sesion = MapeoSesionCama.objects.filter(pk=registro_id).first()
        if not sesion:
            return JsonResponse({"ok": False, "error": "Sesion no encontrada."}, status=404)

        detalles = (
            DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
            .select_related("cama__sala__servicio", "cama__cubiculo", "paciente_actual", "usuario")
            .order_by("-fecha_hora")
        )
        cards = []
        servicios_map = {}
        for item in detalles:
            paciente = _paciente_payload(item.paciente_actual)
            cama_numero = _nombre_cama(item.cama)
            servicio_obj = getattr(getattr(item.cama, "sala", None), "servicio", None)
            sala_obj = getattr(item.cama, "sala", None)
            cubiculo_obj = getattr(item.cama, "cubiculo", None)

            servicio_id = getattr(servicio_obj, "id", None)
            sala_id = getattr(sala_obj, "id", None)
            cubiculo_id = getattr(cubiculo_obj, "id", None)

            servicio_nombre = getattr(servicio_obj, "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_obj, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = getattr(getattr(item.cama, "cubiculo", None), "nombre_cubiculo", "") or "SIN_CUBICULO"

            if servicio_id is None or sala_id is None:
                continue

            if servicio_id not in servicios_map:
                servicios_map[servicio_id] = {
                    "id": servicio_id,
                    "nombre": servicio_nombre,
                    "salas": {},
                }
            if sala_id not in servicios_map[servicio_id]["salas"]:
                servicios_map[servicio_id]["salas"][sala_id] = {
                    "id": sala_id,
                    "nombre": sala_nombre,
                    "cubiculos": {},
                    "camas_directas": [],
                }

            cama_item = {
                "numero_cama": cama_numero,
                "estado": item.estado_actual,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": item.tipo_accion,
                "hubo_cambio": bool(item.hubo_cambio),
                "fue_validada": bool(item.fue_validada),
                "observacion": item.observacion or "",
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_id]["salas"][sala_id]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_id]["salas"][sala_id]["cubiculos"]
                if cubiculo_id is None:
                    continue
                if cubiculo_id not in cubiculos_map:
                    cubiculos_map[cubiculo_id] = {
                        "id": cubiculo_id,
                        "nombre": cubiculo_nombre,
                        "camas": [],
                    }
                cubiculos_map[cubiculo_id]["camas"].append(cama_item)

            cards.append(
                {
                    "titulo": f"Cama {item.cama_id}",
                    "subtitulo": item.tipo_accion,
                    "estado": item.estado_actual,
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "detalle_1": f"Ubicacion: {item.ubicacion or _ubicacion_desde_cama(item.cama)}",
                    "detalle_2": f"Validada: {'SI' if item.fue_validada else 'NO'}",
                    "detalle_3": f"Hubo cambio: {'SI' if item.hubo_cambio else 'NO'}",
                    "observacion": item.observacion or "",
                }
            )

        def _orden_numero_cama(cama_item):
            numero = str(cama_item.get("numero_cama") or "")
            return (0, int(numero)) if numero.isdigit() else (1, numero)

        estructura = []
        servicios_ordenados = Servicio.objects.filter(estado=1).order_by("nombre_servicio", "id")
        for servicio in servicios_ordenados:
            servicio_data = servicios_map.get(servicio.id)
            if not servicio_data:
                continue

            salas_data = []

            salas_ordenadas = Sala.objects.filter(estado=1, servicio_id=servicio.id).order_by("nombre_sala", "id")
            for sala in salas_ordenadas:
                sala_data = servicio_data["salas"].get(sala.id)
                if not sala_data:
                    continue

                cubiculos_data = []
                cubiculos_ordenados = Cubiculo.objects.filter(estado=1, sala_id=sala.id).order_by("numero", "nombre_cubiculo", "id")
                for cubiculo in cubiculos_ordenados:
                    cubiculo_data = sala_data["cubiculos"].get(cubiculo.id)
                    if not cubiculo_data:
                        continue

                    cubiculo_data["camas"] = sorted(
                        cubiculo_data["camas"],
                        key=_orden_numero_cama,
                    )
                    cubiculos_data.append(cubiculo_data)

                camas_directas = sorted(
                    sala_data["camas_directas"],
                    key=_orden_numero_cama,
                )

                salas_data.append(
                    {
                        "id": sala_data["id"],
                        "nombre": sala_data["nombre"],
                        "cubiculos": cubiculos_data,
                        "camas_directas": camas_directas,
                    }
                )

            estructura.append(
                {
                    "id": servicio_data["id"],
                    "nombre": servicio_data["nombre"],
                    "salas": salas_data,
                }
            )

        return JsonResponse({"ok": True, "cards": cards, "estructura": estructura})

    if tipo == "historial":
        timeline_qs = (
            HistorialEstadoCama.objects.select_related(
                "cama__sala__servicio", "cama__cubiculo", "paciente", "usuario"
            )
            .filter(cama_id=registro_id)
            .order_by("-fecha_hora", "-id")
        )
        if not timeline_qs.exists():
            return JsonResponse({"ok": False, "error": "Historial no encontrado para esta cama."}, status=404)

        cards = []
        for item in timeline_qs:
            paciente = _paciente_payload(item.paciente)
            cards.append(
                {
                    "titulo": f"Cama {_nombre_cama(item.cama)}",
                    "subtitulo": "Evento de historial",
                    "estado": item.estado_nuevo,
                    "estado_css": _estado_css_mapa(item.estado_nuevo),
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "detalle_1": f"Estado anterior: {item.estado_anterior or 'SIN_ESTADO'}",
                    "detalle_2": f"Transicion: {(item.estado_anterior or 'SIN_ESTADO')} -> {item.estado_nuevo}",
                    "detalle_3": f"Ubicacion: {_ubicacion_desde_cama(item.cama)}",
                    "observacion": item.observacion or "",
                }
            )
        return JsonResponse({"ok": True, "cards": cards})

    if tipo == "movimiento":
        mov = (
            MovimientoCama.objects.select_related(
                "cama_origen__sala__servicio",
                "cama_origen__cubiculo",
                "cama_destino__sala__servicio",
                "cama_destino__cubiculo",
                "paciente",
                "usuario",
            )
            .filter(pk=registro_id)
            .first()
        )
        if not mov:
            return JsonResponse({"ok": False, "error": "Movimiento no encontrado."}, status=404)

        paciente = _paciente_payload(mov.paciente)
        cards = [
            {
                "titulo": f"Cama {mov.cama_origen_id}",
                "subtitulo": "Origen",
                "estado": mov.tipo_movimiento,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "usuario": _nombre_usuario(mov.usuario),
                "fecha": _hora_local_iso(mov.fecha_hora),
                "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(mov.cama_origen)}",
                "detalle_2": f"Hacia cama: {mov.cama_destino_id}",
                "detalle_3": "",
                "observacion": mov.observacion or "",
            },
            {
                "titulo": f"Cama {mov.cama_destino_id}",
                "subtitulo": "Destino",
                "estado": mov.tipo_movimiento,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "usuario": _nombre_usuario(mov.usuario),
                "fecha": _hora_local_iso(mov.fecha_hora),
                "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(mov.cama_destino)}",
                "detalle_2": f"Desde cama: {mov.cama_origen_id}",
                "detalle_3": "",
                "observacion": mov.observacion or "",
            },
        ]
        return JsonResponse({"ok": True, "cards": cards})

    return JsonResponse({"ok": False, "error": "Tipo no soportado."}, status=400)


@login_required
@require_POST
def iniciar_mapeo(request):
    """Inicia una sesion de mapeo para el usuario actual."""
    sesion_activa = _obtener_sesion_mapeo_activa(request.user)
    if sesion_activa:
        return JsonResponse(
            {
                "ok": True,
                "sesion_id": sesion_activa.id,
                "estado": sesion_activa.estado,
                "hora_inicio": timezone.localtime(sesion_activa.fecha_inicio).isoformat(),
                "camas_mapeadas": _camas_mapeadas_sesion(sesion_activa),
                "mensaje": "Ya existe una sesion de mapeo en progreso.",
            }
        )

    sesion = MapeoSesionCama.objects.create(
        usuario=request.user,
        estado=MapeoSesionCama.Estado.EN_PROGRESO,
    )
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado,
            "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            "camas_mapeadas": [],
            "mensaje": "Mapeo iniciado correctamente.",
        },
        status=201,
    )


@login_required
@require_GET
def estado_mapeo(request):
    """Devuelve la sesion de mapeo activa y camas ya procesadas para restaurar UI."""
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": True, "sesion_activa": None, "camas_mapeadas": []})

    return JsonResponse(
        {
            "ok": True,
            "sesion_activa": {
                "id": sesion.id,
                "estado": sesion.estado,
                "hora_inicio": timezone.localtime(sesion.fecha_inicio).isoformat(),
            },
            "camas_mapeadas": _camas_mapeadas_sesion(sesion),
        }
    )


@login_required
@require_POST
def terminar_mapeo(request):
    """Finaliza la sesion activa de mapeo del usuario."""
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    # Solo se permite terminar cuando todas las camas visibles del mapa
    # (servicio/sala activos y cubiculo activo o sin cubiculo) fueron procesadas.
    total_camas_objetivo = Cama.objects.filter(
        sala__estado=1,
        sala__servicio__estado=1,
    ).filter(
        Q(cubiculo__isnull=True) | Q(cubiculo__estado=1)
    ).count()
    total_camas_mapeadas = (
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values("cama_id")
        .distinct()
        .count()
    )

    if total_camas_mapeadas < total_camas_objetivo:
        faltantes = total_camas_objetivo - total_camas_mapeadas
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    f"No se puede finalizar el mapeo. Faltan {faltantes} cama(s) por procesar."
                ),
                "faltantes": faltantes,
                "total_camas": total_camas_objetivo,
                "camas_mapeadas": total_camas_mapeadas,
            },
            status=400,
        )

    try:
        body = json.loads(request.body or "{}")
    except (ValueError, AttributeError):
        body = {}
    observacion = (body.get("observacion") or "").strip() or "Sin Observaciones"

    sesion.estado = MapeoSesionCama.Estado.FINALIZADO
    sesion.fecha_fin = timezone.now()
    sesion.observacion = observacion
    sesion.save(update_fields=["estado", "fecha_fin", "observacion"])

    total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado,
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "observacion": sesion.observacion,
            "mensaje": "Mapeo finalizado correctamente.",
        }
    )


@login_required
@require_POST
def cancelar_mapeo(request):
    """Cancela la sesion activa de mapeo del usuario."""
    sesion = _obtener_sesion_mapeo_activa(request.user)
    if not sesion:
        return JsonResponse({"ok": False, "error": "No hay una sesion de mapeo activa."}, status=400)

    sesion.estado = MapeoSesionCama.Estado.CANCELADO
    sesion.fecha_fin = timezone.now()
    sesion.save(update_fields=["estado", "fecha_fin"])

    total_detalles = DetalleMapeoCama.objects.filter(sesion_mapeo=sesion).count()
    return JsonResponse(
        {
            "ok": True,
            "sesion_id": sesion.id,
            "estado": sesion.estado,
            "hora_fin": timezone.localtime(sesion.fecha_fin).isoformat(),
            "total_detalles": total_detalles,
            "mensaje": "Mapeo cancelado correctamente.",
        }
    )


# =============================================================================
# mapa_camas_data
# -----------------------------------------------------------------------------
# API GET que construye y retorna en JSON la estructura completa del mapa:
#   Servicio → Sala → Cubículo → Cama  (con estado visual y datos del paciente)
#                   → Camas directas  (camas sin cubículo asignado)
#
# La función no renderiza HTML: prepara exclusivamente un payload JSON para que
# el frontend pinte dinámicamente la estructura del mapa.
#
# Idea general del algoritmo:
# 1. Obtener la última asignación registrada por cama.
# 2. Calcular cuántos movimientos recientes tiene cada sala.
# 3. Cargar la jerarquía Servicio -> Sala -> Cubículo -> Cama usando prefetch.
# 4. Transformar esa jerarquía en listas/diccionarios serializables a JSON.
#
# La última asignación de cada cama determina su estado visual actual.
# También incluye el conteo de cambios recientes por sala para aplicar
# el límite de movimientos en el frontend.
# =============================================================================
@login_required
def mapa_camas_data(request):
    # 1. Cargar todas las asignaciones históricas y quedarse solo con la más
    #    reciente por cama.
    #
    #    Se ordena por:
    #    - cama_id: para agrupar naturalmente las filas de una misma cama.
    #    - -fecha_inicio: para que la asignación más nueva quede primero.
    #    - -id: desempate final si hubiera dos registros con igual fecha.
    #
    #    Luego se recorre secuencialmente y se guarda solo la primera vez que
    #    aparece cada cama, construyendo un diccionario:
    #        { numero_cama: ultima_asignacion }
    #
    #    Este diccionario permite resolver en O(1) el estado actual de una cama
    #    al momento de armar el árbol del mapa.
    asignaciones = (
        AsignacionCamaPaciente.objects
        .select_related("paciente")
        .order_by("cama_id", "-fecha_inicio", "-id")
    )
    asignacion_por_cama = {}
    for asig in asignaciones:
        if asig.cama_id not in asignacion_por_cama:
            asignacion_por_cama[asig.cama_id] = asig

    # 1.b. Obtener ultima actualizacion registrada por cama para mostrar
    #      hora y usuario responsable en cada card.
    historial_por_cama = {}
    historial_qs = (
        HistorialEstadoCama.objects
        .select_related("usuario")
        .order_by("cama_id", "-fecha_hora", "-id")
    )
    for historial in historial_qs:
        if historial.cama_id not in historial_por_cama:
            historial_por_cama[historial.cama_id] = historial

    # 2. Calcular el número de movimientos manuales recientes por sala.
    #
    #    Este conteo se toma del historial y queda agrupado por cama__sala_id.
    #    El resultado final se transforma en otro diccionario:
    #        { sala_id: total_cambios }
    #
    #    Se usa después para dos cosas:
    #    - mostrar en cada cama cuántos cambios lleva la sala
    #    - permitir que el frontend informe el límite operativo disponible
    cambios_por_sala = {
        item["cama__sala_id"]: item["total"]
        for item in HistorialEstadoCama.objects.filter(
            observacion=OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
            fecha_hora__gte=_inicio_ventana_limite_sala(),
        )
        .values("cama__sala_id")
        .annotate(total=Count("id"))
    }

    # 3. Construcción eficiente de la jerarquía física del hospital.
    #
    #    Se separan dos tipos de camas:
    #    - camas_directas_qs: camas colgadas directamente de una sala.
    #    - camas_cubiculo_qs: camas que pertenecen a un cubículo.
    #
    #    Luego se encadenan prefetch_related para traer toda la estructura en
    #    memoria con el menor número posible de consultas:
    #    Servicio -> Salas -> Cubículos -> Camas
    #                      -> Camas directas
    #
    #    Esto evita el problema N+1 cuando más abajo se recorre cada servicio,
    #    cada sala y cada cubículo para construir el JSON final.
    camas_directas_qs = Cama.objects.filter(cubiculo__isnull=True).order_by("numero_cama")
    camas_cubiculo_qs = Cama.objects.order_by("numero_cama")

    cubiculos_qs = Cubiculo.objects.filter(estado=1).prefetch_related(
        Prefetch("camas", queryset=camas_cubiculo_qs)
    )

    salas_qs = (
        Sala.objects.filter(estado=1)
        .prefetch_related(
            Prefetch("cubiculos", queryset=cubiculos_qs),
            Prefetch("camas_sala", queryset=camas_directas_qs),
        )
        .order_by("nombre_sala")
    )

    servicios = Servicio.objects.filter(estado=1).prefetch_related(
        Prefetch("salas_servicio", queryset=salas_qs)
    ).order_by("nombre_servicio")

    # 4. Transformar la jerarquía ORM en una estructura serializable a JSON.
    #
    #    Formato de salida esperado:
    #    {
    #        "servicios": [
    #            {
    #                "id": ...,
    #                "nombre": ...,
    #                "salas": [
    #                    {
    #                        "id": ...,
    #                        "cubiculos": [...],
    #                        "camas_directas": [...]
    #                    }
    #                ]
    #            }
    #        ]
    #    }
    #
    #    Cada cama expone:
    #    - numero_cama
    #    - estado_visual
    #    - asignacion_estado
    #    - paciente
    #    - cambios_realizados
    #    - max_cambios
    #
    #    Esto le evita al frontend tener que inferir relaciones o recalcular
    #    estados: el backend entrega el árbol listo para pintar.
    data = []
    for servicio in servicios:
        salas_data = []

        for sala in servicio.salas_servicio.all():
            cubiculos_data = []
            camas_sin_cubiculo = []

            # 4.a. Procesar primero las camas directas de la sala.
            #      Para cada cama se busca su última asignación en el diccionario
            #      asignacion_por_cama y, si existe, se toma también el paciente.
            for cama in sala.camas_sala.all():
                asig = asignacion_por_cama.get(cama.numero_cama)
                paciente = asig.paciente if asig else None
                meta_actualizacion = _meta_ultima_actualizacion(
                    historial_por_cama.get(cama.numero_cama)
                )

                camas_sin_cubiculo.append(
                    {
                        "numero_cama": cama.numero_cama,
                        "estado_visual": _estado_visual(asig),
                        "asignacion_estado": asig.estado if asig else "SIN_ASIGNACION",
                        "paciente": _paciente_payload(paciente),
                        "cambios_realizados": cambios_por_sala.get(sala.id, 0),
                        "max_cambios": MAX_CAMBIOS_CAMA,
                        **meta_actualizacion,
                    }
                )

            # 4.b. Procesar los cubículos de la sala.
            #      Cada cubículo genera su propia lista interna de camas, usando
            #      exactamente la misma lógica de resolución de asignación actual.
            for cubiculo in sala.cubiculos.all():
                camas_data = []
                for cama in cubiculo.camas.all():
                    asig = asignacion_por_cama.get(cama.numero_cama)
                    paciente = asig.paciente if asig else None
                    meta_actualizacion = _meta_ultima_actualizacion(
                        historial_por_cama.get(cama.numero_cama)
                    )

                    camas_data.append(
                        {
                            "numero_cama": cama.numero_cama,
                            "estado_visual": _estado_visual(asig),
                            "asignacion_estado": asig.estado if asig else "SIN_ASIGNACION",
                            "paciente": _paciente_payload(paciente),
                            "cambios_realizados": cambios_por_sala.get(sala.id, 0),
                            "max_cambios": MAX_CAMBIOS_CAMA,
                            **meta_actualizacion,
                        }
                    )

                # Si el cubículo no tiene camas, no se incluye en el payload.
                if not camas_data:
                    continue

                # Cada cubículo queda serializado con su metadata básica y la
                # colección de camas ya listas para renderizar en la interfaz.
                cubiculos_data.append(
                    {
                        "id": cubiculo.id,
                        "numero": cubiculo.numero,
                        "nombre": cubiculo.nombre_cubiculo,
                        "camas": camas_data,
                    }
                )

            # Si la sala no tiene cubículos con camas ni camas directas,
            # tampoco se incluye en la respuesta.
            if not cubiculos_data and not camas_sin_cubiculo:
                continue

            # 4.c. Finalmente se agrega la sala con sus dos grupos de camas:
            #      - cubículos con camas internas
            #      - camas directas sin cubículo
            salas_data.append(
                {
                    "id": sala.id,
                    "nombre": sala.nombre_sala,
                    "nombre_corto": sala.nombre_corto_sala,
                    "cubiculos": cubiculos_data,
                    "camas_directas": camas_sin_cubiculo,
                }
            )

        # Si el servicio no tiene salas útiles (con camas), no se retorna.
        if not salas_data:
            continue

        # 4.d. Cada servicio consolida todas sus salas ya serializadas.
        data.append(
            {
                "id": servicio.id,
                "nombre": servicio.nombre_servicio,
                "nombre_corto": servicio.nombre_corto,
                "salas": salas_data,
            }
        )

    # 5. Respuesta final consumida por el JavaScript del mapa.
    return JsonResponse({"servicios": data})


# =============================================================================
# buscar_pacientes_mapa
# -----------------------------------------------------------------------------
# API GET de autocompletado. Devuelve pacientes elegibles para asignar a una
# cama desde el mapa. Se incluyen dos grupos excluyentes entre sí:
#
#   Grupo A — Pre altas recientes:
#     El último registro de AsignacionCamaPaciente del paciente tiene
#     estado = PRE_ALTA. El paciente se encuentra listo para egreso y
#     pendiente de liberación final de la cama.
#
#   Grupo B — Ingreso activo sin cama asignada:
#     El paciente tiene un Ingreso con estado=1, sin fecha_egreso y sin
#     cama registrada en el ingreso (Ingreso.cama es null). Nunca se le
#     asignó cama o fue desvinculado del ingreso.
#
# En ambos grupos se excluyen los pacientes que ya ocupan una cama (OCUPADA).
# Acepta ?q= para filtrar por nombre o DNI y ?tipo= (nombre|dni|todo).
# Retorna un máximo de 20 resultados.
# =============================================================================
@login_required
@require_GET
def buscar_pacientes_mapa(request):
    termino = (request.GET.get("q") or "").strip()
    tipo_busqueda = (request.GET.get("tipo") or "todo").strip().lower()

    # IDs de pacientes que actualmente tienen una cama OCUPADA → excluir siempre.
    pacientes_con_cama_ocupada = AsignacionCamaPaciente.objects.filter(
        estado=AsignacionCamaPaciente.Estado.OCUPADA
    ).values_list("paciente_id", flat=True)

    # Subquery: último estado de cama registrado para cada paciente.
    ultimo_estado_cama_subquery = (
        AsignacionCamaPaciente.objects.filter(paciente_id=OuterRef("pk"))
        .order_by("-fecha_inicio", "-id")
        .values("estado")[:1]
    )

    # Grupo B: IDs de pacientes con ingreso activo y SIN cama asignada en el ingreso.
    ids_ingreso_sin_cama = (
        Ingreso.objects.filter(
            estado=1,
            fecha_egreso__isnull=True,
            cama__isnull=True,
        )
        .values_list("paciente_id", flat=True)
        .distinct()
    )

    pacientes_qs = (
        Paciente.objects.filter(estado__in=["A", "P"])
        .exclude(id__in=pacientes_con_cama_ocupada)
        .annotate(ultimo_estado_cama=Subquery(ultimo_estado_cama_subquery))
        .filter(
            # Grupo A: último estado en tabla de asignación es PRE_ALTA.
            Q(ultimo_estado_cama=AsignacionCamaPaciente.Estado.PRE_ALTA)
            # Grupo B: ingreso activo registrado sin cama en la tabla Ingreso.
            | Q(id__in=ids_ingreso_sin_cama)
        )
        .distinct()
    )

    if termino:
        if tipo_busqueda == "dni":
            pacientes_qs = pacientes_qs.filter(dni__icontains=termino)
        elif tipo_busqueda == "nombre":
            pacientes_qs = pacientes_qs.filter(
                Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )
        else:
            pacientes_qs = pacientes_qs.filter(
                Q(dni__icontains=termino)
                | Q(primer_nombre__icontains=termino)
                | Q(segundo_nombre__icontains=termino)
                | Q(primer_apellido__icontains=termino)
                | Q(segundo_apellido__icontains=termino)
            )

    pacientes = pacientes_qs.order_by("primer_nombre", "primer_apellido")[:20]
    resultados = [_paciente_payload(p) for p in pacientes]
    return JsonResponse({"results": resultados})


# =============================================================================
# camas_disponibles_mapa
# -----------------------------------------------------------------------------
# API GET que retorna todas las camas en estado VACIA disponibles para
# recibir un traslado de paciente.
# Acepta el parámetro ?excluir= para omitir la cama origen del traslado
# y no ofrecerla como opción de destino.
# =============================================================================
@login_required
@require_GET
def camas_disponibles_mapa(request):
    excluir_cama = request.GET.get("excluir") or None

    # Obtener el estado actual de cada cama tomando solo la asignación más reciente.
    asignaciones = AsignacionCamaPaciente.objects.order_by("cama_id", "-fecha_inicio", "-id")
    asignacion_por_cama = {}
    for asig in asignaciones:
        if asig.cama_id not in asignacion_por_cama:
            asignacion_por_cama[asig.cama_id] = asig

    todas_camas = (
        Cama.objects.filter(estado=1)
        .select_related("sala__servicio", "cubiculo")
        .order_by("sala__servicio__nombre_servicio", "sala__nombre_sala", "numero_cama")
    )

    resultados = []
    for cama in todas_camas:
        # Omitir la cama de origen para que no aparezca como destino disponible.
        if excluir_cama and str(cama.numero_cama) == str(excluir_cama):
            continue
        asig = asignacion_por_cama.get(cama.numero_cama)
        estado = asig.estado if asig else AsignacionCamaPaciente.Estado.VACIA
        if estado == AsignacionCamaPaciente.Estado.VACIA:
            resultados.append({
                "numero_cama": cama.numero_cama,
                "sala": cama.sala.nombre_sala,
                "servicio": cama.sala.servicio.nombre_servicio,
                "cubiculo": cama.cubiculo.nombre_cubiculo if cama.cubiculo else None,
            })

    return JsonResponse({"results": resultados})


# =============================================================================
# mover_paciente_cama
# -----------------------------------------------------------------------------
# API POST que ejecuta un traslado atómico de paciente entre camas.
# Flujo dentro de transaction.atomic():
#   1. Libera la cama origen (OCUPADA → VACIA, paciente = None).
#   2. Ocupa la cama destino (VACIA → OCUPADA, asigna el mismo paciente).
#   3. Registra un HistorialEstadoCama por cada cama afectada.
#   4. Crea un MovimientoCama con origen, destino y paciente.
# Para usuarios no superadmin verifica el límite de cambios por sala
# en la ventana temporal activa antes de ejecutar el movimiento.
# =============================================================================
@login_required
@require_POST
def mover_paciente_cama(request):
    cama_origen_id = request.POST.get("cama_origen_id")
    cama_destino_id = request.POST.get("cama_destino_id")

    if not cama_origen_id or not cama_destino_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama origen y la cama destino."}, status=400)

    if str(cama_origen_id) == str(cama_destino_id):
        return JsonResponse({"ok": False, "error": "La cama destino debe ser diferente a la cama origen."}, status=400)

    try:
        cama_origen = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_origen_id)
        cama_destino = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_destino_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Una de las camas indicadas no existe."}, status=404)

    sala_origen_id = cama_origen.sala_id
    sala_destino_id = cama_destino.sala_id

    asig_origen = (
        AsignacionCamaPaciente.objects
        .select_related("paciente")
        .filter(cama_id=cama_origen_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if not asig_origen or asig_origen.estado != AsignacionCamaPaciente.Estado.OCUPADA:
        return JsonResponse({"ok": False, "error": "La cama origen no esta ocupada."}, status=400)

    paciente = asig_origen.paciente
    if not paciente:
        return JsonResponse({"ok": False, "error": "La cama origen no tiene paciente asignado."}, status=400)

    asig_destino = (
        AsignacionCamaPaciente.objects
        .filter(cama_id=cama_destino_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if asig_destino and asig_destino.estado != AsignacionCamaPaciente.Estado.VACIA:
        return JsonResponse({"ok": False, "error": "La cama destino no esta disponible (no esta vacia)."}, status=400)

    if not _es_superadmin(request.user):
        cambios_sala_origen = _contar_cambios_manual_por_sala(sala_origen_id)
        if cambios_sala_origen >= MAX_CAMBIOS_CAMA:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        f"La sala de la cama origen ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                        f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                    ),
                },
                status=400,
            )

        if sala_destino_id != sala_origen_id:
            cambios_sala_destino = _contar_cambios_manual_por_sala(sala_destino_id)
            if cambios_sala_destino >= MAX_CAMBIOS_CAMA:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            f"La sala de la cama destino ya alcanzo el maximo de {MAX_CAMBIOS_CAMA} cambios "
                            f"en las ultimas {VENTANA_LIMITE_CAMBIOS_SALA_HORAS} hora(s)."
                        ),
                    },
                    status=400,
                )

    estado_anterior_destino = asig_destino.estado if asig_destino else AsignacionCamaPaciente.Estado.VACIA

    with transaction.atomic():
        # 1. Liberar cama origen (OCUPADA -> VACIA)
        asig_origen.estado = AsignacionCamaPaciente.Estado.VACIA
        asig_origen.paciente = None
        asig_origen.save()

        # 2. Ocupar cama destino (VACIA -> OCUPADA con el mismo paciente)
        if not asig_destino:
            asig_destino = AsignacionCamaPaciente(
                cama=cama_destino,
                estado=AsignacionCamaPaciente.Estado.OCUPADA,
                paciente=paciente,
                usuario_asignacion=request.user,
            )
        else:
            asig_destino.estado = AsignacionCamaPaciente.Estado.OCUPADA
            asig_destino.paciente = paciente
            asig_destino.usuario_asignacion = request.user
            asig_destino.fecha_fin = None
            asig_destino.usuario_cierre = None
        asig_destino.save()

        # 3. Registrar historial para ambas camas
        historial_origen = HistorialEstadoCama.objects.create(
            cama_id=cama_origen_id,
            estado_anterior=AsignacionCamaPaciente.Estado.OCUPADA,
            estado_nuevo=AsignacionCamaPaciente.Estado.VACIA,
            paciente=None,
            usuario=request.user,
            observacion=OBSERVACION_MOVIMIENTO_PACIENTE_MAPA,
        )
        historial_destino = HistorialEstadoCama.objects.create(
            cama_id=cama_destino_id,
            estado_anterior=estado_anterior_destino,
            estado_nuevo=AsignacionCamaPaciente.Estado.OCUPADA,
            paciente=paciente,
            usuario=request.user,
            observacion=(
                OBSERVACION_MOVIMIENTO_PACIENTE_MAPA
                if sala_destino_id != sala_origen_id
                else OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE
            ),
        )

        MovimientoCama.objects.create(
            tipo_movimiento="TRASLADO",
            cama_origen_id=cama_origen_id,
            cama_destino_id=cama_destino_id,
            paciente=paciente,
            usuario=request.user,
            observacion="Movimiento desde mapa de camas",
        )

        # Registro en tiempo real por cama dentro de sesion de mapeo activa.
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_origen,
            asignacion=asig_origen,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion="Traslado de paciente desde mapa (cama origen).",
        )
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama_destino,
            asignacion=asig_destino,
            tipo_accion=DetalleMapeoCama.TipoAccion.TRASLADO,
            hubo_cambio=True,
            observacion="Traslado de paciente desde mapa (cama destino).",
        )

    cambios_origen_post = _contar_cambios_manual_por_sala(sala_origen_id)
    cambios_destino_post = _contar_cambios_manual_por_sala(sala_destino_id)

    return JsonResponse({
        "ok": True,
        "mensaje": f"Paciente movido a la cama {cama_destino_id} correctamente.",
        "cama_origen": {
            "numero_cama": int(cama_origen_id),
            "estado_visual": AsignacionCamaPaciente.Estado.VACIA,
            "paciente": None,
            "cambios_realizados": cambios_origen_post,
            "max_cambios": MAX_CAMBIOS_CAMA,
            "ultima_actualizacion": _hora_local_iso(historial_origen.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_origen.usuario),
        },
        "cama_destino": {
            "numero_cama": int(cama_destino_id),
            "estado_visual": AsignacionCamaPaciente.Estado.OCUPADA,
            "paciente": _paciente_payload(paciente),
            "cambios_realizados": cambios_destino_post,
            "max_cambios": MAX_CAMBIOS_CAMA,
            "ultima_actualizacion": _hora_local_iso(historial_destino.fecha_hora),
            "usuario_ultima_actualizacion": _nombre_usuario(historial_destino.usuario),
        },
    })


# ===========================================================================
# actualizar_cama_mapa
# ---------------------------------------------------------------------------
# API POST para cambio manual de estado de una cama individual desde el mapa.
# Permite al usuario seleccionar cualquier estado válido y, si el estado
# es OCUPADA, también debe indicar el paciente a asignar.
# Si no existe asignación previa para la cama, la crea en estado VACIA
# antes de aplicar el cambio solicitado.
# Registra el cambio en HistorialEstadoCama con observación de cambio manual.
# ===========================================================================
@login_required
@require_POST
def actualizar_cama_mapa(request):
    cama_id = request.POST.get("cama_id")
    estado_nuevo = (request.POST.get("estado") or "").strip()
    paciente_id = request.POST.get("paciente_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar la cama."}, status=400)

    estados_validos = {item[0] for item in AsignacionCamaPaciente.Estado.choices}
    if estado_nuevo not in estados_validos:
        return JsonResponse({"ok": False, "error": "Estado de cama no valido."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    asignacion = (
        AsignacionCamaPaciente.objects.select_related("paciente")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if not asignacion:
        asignacion = AsignacionCamaPaciente.objects.create(
            cama=cama,
            usuario_asignacion=request.user,
            estado=AsignacionCamaPaciente.Estado.VACIA,
            paciente=None,
        )

    paciente_nuevo = None
    if paciente_id:
        try:
            paciente_nuevo = Paciente.objects.get(pk=paciente_id)
        except Paciente.DoesNotExist:
            return JsonResponse({"ok": False, "error": "El paciente seleccionado no existe."}, status=404)

    if estado_nuevo == AsignacionCamaPaciente.Estado.OCUPADA and not paciente_nuevo:
        return JsonResponse(
            {
                "ok": False,
                "error": "Para estado OCUPADA debe seleccionar un paciente.",
            },
            status=400,
        )

    estado_anterior = asignacion.estado
    paciente_anterior_id = asignacion.paciente_id
    paciente_anterior = asignacion.paciente

    if estado_nuevo == AsignacionCamaPaciente.Estado.VACIA:
        paciente_nuevo = None
    elif estado_nuevo == AsignacionCamaPaciente.Estado.PRE_ALTA and paciente_nuevo is None:
        # Regla solicitada: PRE_ALTA debe conservar el paciente actual si no se envía uno nuevo.
        paciente_nuevo = paciente_anterior

    hubo_cambio = (
        estado_anterior != estado_nuevo
        or paciente_anterior_id != (paciente_nuevo.id if paciente_nuevo else None)
    )

    cambios_realizados = _contar_cambios_manual_por_sala(cama.sala_id)

    if not hubo_cambio:
        _registrar_detalle_mapeo(
            usuario=request.user,
            cama=cama,
            asignacion=asignacion,
            tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
            hubo_cambio=False,
            observacion="Confirmacion sin cambios desde mapa.",
        )
        return JsonResponse(
            {
                "ok": True,
                "mensaje": "No se detectaron cambios para guardar.",
                "cama": {
                    "numero_cama": int(cama_id),
                    "estado_visual": asignacion.estado,
                    "paciente": _paciente_payload(asignacion.paciente),
                    "cambios_realizados": cambios_realizados,
                    "max_cambios": MAX_CAMBIOS_CAMA,
                },
            }
        )

    asignacion_alta_previa = None
    if estado_nuevo == AsignacionCamaPaciente.Estado.OCUPADA and paciente_nuevo:
        asignacion_alta_previa = (
            AsignacionCamaPaciente.objects.select_related("cama")
            .filter(
                paciente_id=paciente_nuevo.id,
                estado=AsignacionCamaPaciente.Estado.PRE_ALTA,
            )
            .exclude(cama_id=cama_id)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    try:
        with transaction.atomic():
            if asignacion_alta_previa:
                cama_alta_previa_id = asignacion_alta_previa.cama_id
                asignacion_alta_previa.estado = AsignacionCamaPaciente.Estado.VACIA
                asignacion_alta_previa.paciente = None
                asignacion_alta_previa.fecha_fin = timezone.now()
                asignacion_alta_previa.usuario_cierre = request.user
                asignacion_alta_previa.save(
                    update_fields=["estado", "paciente", "fecha_fin", "usuario_cierre"]
                )

                HistorialEstadoCama.objects.create(
                    cama_id=cama_alta_previa_id,
                    estado_anterior=AsignacionCamaPaciente.Estado.PRE_ALTA,
                    estado_nuevo=AsignacionCamaPaciente.Estado.VACIA,
                    paciente=None,
                    usuario=request.user,
                    observacion=OBSERVACION_LIBERACION_ALTA_AUTOMATICA,
                )

            asignacion.estado = estado_nuevo
            asignacion.paciente = paciente_nuevo
            asignacion.usuario_asignacion = request.user
            if estado_nuevo == AsignacionCamaPaciente.Estado.OCUPADA:
                asignacion.fecha_fin = None
                asignacion.usuario_cierre = None
            elif estado_nuevo == AsignacionCamaPaciente.Estado.VACIA and estado_anterior == AsignacionCamaPaciente.Estado.OCUPADA:
                # Registrar cierre formal cuando la cama pasa de OCUPADA a VACIA.
                asignacion.fecha_fin = timezone.now()
                asignacion.usuario_cierre = request.user

            asignacion.save()

            es_egreso_directo = (
                estado_anterior == AsignacionCamaPaciente.Estado.OCUPADA
                and estado_nuevo == AsignacionCamaPaciente.Estado.VACIA
            )

            # Cuando la cama pasa de OCUPADA a VACIA, registrar el egreso del paciente anterior.
            if es_egreso_directo and paciente_anterior:
                MovimientoCama.objects.create(
                    tipo_movimiento="EGRESO",
                    cama_origen=cama,
                    cama_destino=cama,
                    paciente=paciente_anterior,
                    usuario=request.user,
                    observacion="Egreso por cambio de estado a VACIA desde mapa",
                )

            if es_egreso_directo:
                # Dejar trazabilidad explícita: OCUPADA -> PRE_ALTA -> VACIA.
                HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=AsignacionCamaPaciente.Estado.OCUPADA,
                    estado_nuevo=AsignacionCamaPaciente.Estado.PRE_ALTA,
                    paciente=paciente_anterior,
                    usuario=request.user,
                    observacion=OBSERVACION_CAMBIO_MANUAL_MAPA,
                )
                historial = HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=AsignacionCamaPaciente.Estado.PRE_ALTA,
                    estado_nuevo=AsignacionCamaPaciente.Estado.VACIA,
                    paciente=None,
                    usuario=request.user,
                    observacion=OBSERVACION_CAMBIO_MANUAL_MAPA,
                )
            else:
                historial = HistorialEstadoCama.objects.create(
                    cama_id=cama_id,
                    estado_anterior=estado_anterior,
                    estado_nuevo=asignacion.estado,
                    paciente=(
                        paciente_anterior
                        if estado_nuevo == AsignacionCamaPaciente.Estado.VACIA
                        else asignacion.paciente
                    ),
                    usuario=request.user,
                    observacion=OBSERVACION_CAMBIO_MANUAL_MAPA,
                )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    _registrar_detalle_mapeo(
        usuario=request.user,
        cama=cama,
        asignacion=asignacion,
        tipo_accion=(
            DetalleMapeoCama.TipoAccion.ALTA
            if asignacion.estado == AsignacionCamaPaciente.Estado.PRE_ALTA
            else DetalleMapeoCama.TipoAccion.CAMBIO
        ),
        hubo_cambio=True,
        observacion="Actualizacion de cama desde mapa.",
    )

    cambios_realizados = _contar_cambios_manual_por_sala(cama.sala_id)
    return JsonResponse(
        {
            "ok": True,
            "mensaje": "Cambio de cama actualizado correctamente.",
            "cama": {
                "numero_cama": int(cama_id),
                "estado_visual": asignacion.estado,
                "paciente": _paciente_payload(asignacion.paciente),
                "cambios_realizados": cambios_realizados,
                "max_cambios": MAX_CAMBIOS_CAMA,
                "ultima_actualizacion": _hora_local_iso(historial.fecha_hora),
                "usuario_ultima_actualizacion": _nombre_usuario(historial.usuario),
            },
        }
    )


@login_required
@require_POST
def procesar_cama_mapeo(request):
    """
    Ciclo principal de mapeo por cama:
    evaluar -> decidir -> ejecutar -> registrar.
    """
    cama_id = request.POST.get("cama_id")
    accion = (request.POST.get("accion") or "").strip().upper()
    observacion = (request.POST.get("observacion") or "").strip()
    paciente_observado_id = request.POST.get("paciente_observado_id") or None
    sesion_mapeo_id = request.POST.get("sesion_mapeo_id") or None

    if not cama_id:
        return JsonResponse({"ok": False, "error": "Debe indicar cama_id."}, status=400)

    acciones_validas = {
        "CONFIRMAR",
        "CONFIRMAR_ALTA",
        "CANCELAR_PREALTA",
        "CAMBIO_TRASLADO",
        "ASIGNACION",
        "ALTA_FORZADA",
    }
    if accion not in acciones_validas:
        return JsonResponse({"ok": False, "error": "Accion de mapeo no valida."}, status=400)

    try:
        cama = Cama.objects.select_related("sala__servicio", "cubiculo").get(pk=cama_id)
    except Cama.DoesNotExist:
        return JsonResponse({"ok": False, "error": "La cama no existe."}, status=404)

    sesion = None
    if sesion_mapeo_id:
        sesion = MapeoSesionCama.objects.filter(
            pk=sesion_mapeo_id,
            usuario=request.user,
            estado=MapeoSesionCama.Estado.EN_PROGRESO,
            fecha_fin__isnull=True,
        ).first()
    if not sesion:
        sesion = _obtener_sesion_mapeo_activa(request.user)

    if not sesion:
        return JsonResponse(
            {"ok": False, "error": "No hay una sesion de mapeo activa. Debe iniciar mapeo primero."},
            status=400,
        )

    asig_actual = (
        AsignacionCamaPaciente.objects.select_related("paciente")
        .filter(cama_id=cama_id)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    paciente_observado = None
    if paciente_observado_id:
        try:
            paciente_observado = Paciente.objects.get(pk=paciente_observado_id)
        except Paciente.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Paciente observado no existe."}, status=404)

    estado_sistema = asig_actual.estado if asig_actual else AsignacionCamaPaciente.Estado.VACIA

    with transaction.atomic():
        # Caso 1: todo correcto (sin cambios en sistema)
        if accion == "CONFIRMAR":
            # Auditoria de mapeo: aunque no haya cambios, se registra la validacion.
            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_sistema,
                estado_nuevo=estado_sistema,
                paciente=asig_actual.paciente if asig_actual else None,
                usuario=request.user,
                observacion="Confirmacion de mapeo sin cambios",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                hubo_cambio=False,
                observacion=observacion or "Confirmacion de estado sin cambios.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cama confirmada sin cambios.", "estado_sistema": estado_sistema})

        # Caso 2A: sistema en PRE_ALTA y paciente ya egreso.
        if accion == "CONFIRMAR_ALTA":
            if not asig_actual:
                return JsonResponse({"ok": False, "error": "No hay asignacion activa para confirmar alta."}, status=400)

            paciente_mov = asig_actual.paciente
            estado_anterior = asig_actual.estado
            asig_actual.estado = AsignacionCamaPaciente.Estado.VACIA
            asig_actual.paciente = None
            asig_actual.fecha_fin = timezone.now()
            asig_actual.usuario_cierre = request.user
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=AsignacionCamaPaciente.Estado.VACIA,
                paciente=None,
                usuario=request.user,
                observacion="Confirmacion de alta desde mapeo",
            )

            if paciente_mov:
                MovimientoCama.objects.create(
                    tipo_movimiento="EGRESO",
                    cama_origen=cama,
                    cama_destino=cama,
                    paciente=paciente_mov,
                    usuario=request.user,
                    observacion="Egreso confirmado en mapeo",
                )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=observacion or "Confirmar alta (egreso).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta confirmada. Cama liberada."})

        # Caso 2B: cancelar prealta (PRE_ALTA -> OCUPADA con mismo paciente)
        if accion == "CANCELAR_PREALTA":
            if not asig_actual or not asig_actual.paciente:
                return JsonResponse({"ok": False, "error": "No existe paciente actual para cancelar prealta."}, status=400)

            estado_anterior = asig_actual.estado
            asig_actual.estado = AsignacionCamaPaciente.Estado.OCUPADA
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=AsignacionCamaPaciente.Estado.OCUPADA,
                paciente=asig_actual.paciente,
                usuario=request.user,
                observacion="Cancelar prealta desde mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.CORRECCION,
                hubo_cambio=True,
                observacion=observacion or "Cancelar prealta, paciente permanece.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Prealta cancelada. Cama en OCUPADA."})

        # Caso 3: paciente diferente (cambio/traslado)
        if accion == "CAMBIO_TRASLADO":
            if not paciente_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar paciente_observado_id para cambio/traslado."},
                    status=400,
                )

            if asig_actual and asig_actual.paciente_id == paciente_observado.id:
                # Auditoria de mapeo: se registra validacion aunque paciente y estado coincidan.
                HistorialEstadoCama.objects.create(
                    cama=cama,
                    estado_anterior=estado_sistema,
                    estado_nuevo=estado_sistema,
                    paciente=asig_actual.paciente,
                    usuario=request.user,
                    observacion="Confirmacion de mapeo sin cambios (paciente coincide)",
                )

                _registrar_detalle_mapeo(
                    usuario=request.user,
                    cama=cama,
                    asignacion=asig_actual,
                    tipo_accion=DetalleMapeoCama.TipoAccion.CONFIRMACION,
                    hubo_cambio=False,
                    observacion=observacion or "Paciente coincide con sistema.",
                    sesion_mapeo=sesion,
                )
                return JsonResponse({"ok": True, "mensaje": "Sin cambios: paciente ya coincide con sistema."})

            estado_anterior = asig_actual.estado if asig_actual else AsignacionCamaPaciente.Estado.VACIA
            if asig_actual and asig_actual.paciente:
                asig_actual.estado = AsignacionCamaPaciente.Estado.VACIA
                asig_actual.paciente = None
                asig_actual.fecha_fin = timezone.now()
                asig_actual.usuario_cierre = request.user
                asig_actual.save()

            nueva_asig = AsignacionCamaPaciente.objects.create(
                cama=cama,
                paciente=paciente_observado,
                estado=AsignacionCamaPaciente.Estado.OCUPADA,
                usuario_asignacion=request.user,
            )

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=AsignacionCamaPaciente.Estado.OCUPADA,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Cambio/traslado desde mapeo",
            )

            MovimientoCama.objects.create(
                tipo_movimiento="TRASLADO",
                cama_origen=cama,
                cama_destino=cama,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Cambio de paciente en cama durante mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=nueva_asig,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=observacion or "Cambio/traslado de paciente.",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Cambio/traslado aplicado correctamente."})

        # Caso 4: sistema libre, pero hay paciente real.
        if accion == "ASIGNACION":
            if not paciente_observado:
                return JsonResponse(
                    {"ok": False, "error": "Debe indicar paciente_observado_id para asignacion."},
                    status=400,
                )

            if asig_actual and asig_actual.estado == AsignacionCamaPaciente.Estado.OCUPADA:
                return JsonResponse(
                    {"ok": False, "error": "La cama ya figura ocupada en sistema. Use CAMBIO_TRASLADO."},
                    status=400,
                )

            if asig_actual:
                asig_actual.estado = AsignacionCamaPaciente.Estado.OCUPADA
                asig_actual.paciente = paciente_observado
                asig_actual.usuario_asignacion = request.user
                asig_actual.fecha_fin = None
                asig_actual.usuario_cierre = None
                asig_actual.save()
                asignacion_obj = asig_actual
            else:
                asignacion_obj = AsignacionCamaPaciente.objects.create(
                    cama=cama,
                    paciente=paciente_observado,
                    estado=AsignacionCamaPaciente.Estado.OCUPADA,
                    usuario_asignacion=request.user,
                )

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=AsignacionCamaPaciente.Estado.VACIA,
                estado_nuevo=AsignacionCamaPaciente.Estado.OCUPADA,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Asignacion detectada durante mapeo",
            )

            MovimientoCama.objects.create(
                tipo_movimiento="ASIGNACION",
                cama_origen=cama,
                cama_destino=cama,
                paciente=paciente_observado,
                usuario=request.user,
                observacion="Asignacion manual durante mapeo",
            )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asignacion_obj,
                tipo_accion=DetalleMapeoCama.TipoAccion.CAMBIO,
                hubo_cambio=True,
                observacion=observacion or "Sistema libre, paciente presente (asignacion).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Asignacion aplicada correctamente."})

        # Caso 5: sistema ocupado, pero cama vacia en la realidad.
        if accion == "ALTA_FORZADA":
            if not asig_actual or asig_actual.estado != AsignacionCamaPaciente.Estado.OCUPADA:
                return JsonResponse(
                    {"ok": False, "error": "No existe ocupacion activa para forzar alta."},
                    status=400,
                )

            paciente_prev = asig_actual.paciente
            asig_actual.estado = AsignacionCamaPaciente.Estado.VACIA
            asig_actual.paciente = None
            asig_actual.fecha_fin = timezone.now()
            asig_actual.usuario_cierre = request.user
            asig_actual.save()

            HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=AsignacionCamaPaciente.Estado.OCUPADA,
                estado_nuevo=AsignacionCamaPaciente.Estado.VACIA,
                paciente=None,
                usuario=request.user,
                observacion="Alta forzada desde mapeo",
            )

            if paciente_prev:
                MovimientoCama.objects.create(
                    tipo_movimiento="EGRESO",
                    cama_origen=cama,
                    cama_destino=cama,
                    paciente=paciente_prev,
                    usuario=request.user,
                    observacion="Alta forzada durante mapeo",
                )

            _registrar_detalle_mapeo(
                usuario=request.user,
                cama=cama,
                asignacion=asig_actual,
                tipo_accion=DetalleMapeoCama.TipoAccion.ALTA,
                hubo_cambio=True,
                observacion=observacion or "Sistema ocupado, cama vacia (alta forzada).",
                sesion_mapeo=sesion,
            )
            return JsonResponse({"ok": True, "mensaje": "Alta forzada aplicada. Cama liberada."})

    return JsonResponse({"ok": False, "error": "No se pudo procesar la accion solicitada."}, status=400)


# ---------------------------------------------------------------------------
# Sincronización de camas desde el listado de ingresos (solo superusuarios)
# ---------------------------------------------------------------------------
@require_POST
def sincronizar_camas_superadmin(request):
    """
    Endpoint exclusivo para superusuarios.
    Recorre los ingresos activos con cama asignada y crea el registro
    AsignacionCamaPaciente faltante mediante MapeoCamasService.

    POST /mapeo-camas/api/sincronizar-camas/
    Respuesta JSON:
      { "success": true, "sincronizados": N, "omitidos": N, "errores": [...] }
    """
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Acceso denegado."}, status=403)

    ingresos = list(
        Ingreso.objects.filter(
            estado=1,
            fecha_egreso__isnull=True,
            cama_id__isnull=False,
            paciente_id__isnull=False,
        ).values("id", "cama_id", "paciente_id")
    )

    ocupadas = set(
        AsignacionCamaPaciente.objects.filter(
            estado=AsignacionCamaPaciente.Estado.OCUPADA
        ).values_list("cama_id", flat=True)
    )

    sincronizados = 0
    omitidos = 0
    errores = []

    for ingreso in ingresos:
        cama_id = ingreso["cama_id"]
        paciente_id = ingreso["paciente_id"]
        ingreso_id = ingreso["id"]

        if cama_id in ocupadas:
            omitidos += 1
            continue

        try:
            MapeoCamasService.sincronizar_cama_con_ingreso(
                cama_id=cama_id,
                paciente_id=paciente_id,
                usuario=request.user,
            )
            ocupadas.add(cama_id)
            sincronizados += 1
        except Exception as exc:
            errores.append({"ingreso_id": ingreso_id, "error": str(exc)})

    return JsonResponse(
        {
            "success": True,
            "sincronizados": sincronizados,
            "omitidos": omitidos,
            "errores": errores,
        }
    )
