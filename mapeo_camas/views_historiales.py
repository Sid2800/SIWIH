# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Vistas e historiales de auditoría: listado y detalle (sesiones de mapeo,
historial por cama y movimientos)."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from core.constants.permisos import (
    MAPEO_CAMAS_HISTORIALES_ROLES,
    MAPEO_CAMAS_HISTORIALES_UNIDADES,
)
from core.mixins import UnidadRolRequiredMixin
from servicio.models import Cama

from mapeo_camas.models import (
    DetalleMapeoCama,
    HistorialEstadoCama,
    MapeoSesionCama,
    MapeoSesionServicio,
    MovimientoCama,
)

from ._constants import DETALLE_PAGE_SIZE_DEFAULT, DETALLE_PAGE_SIZE_MAX
from ._helpers import (
    _hora_local_iso,
    _nombre_cama,
    _nombre_usuario,
    _observacion_codigo,
    _paciente_payload,
    _parse_fecha_filtro,
    _ubicacion_desde_cama,
)
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
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Historiales de Camas"
        context["subtitulo"] = "Consulta de historial, movimientos y mapeos"
        return context


class MapeoCamasHistorialDetalleView(UnidadRolRequiredMixin, TemplateView):
    template_name = "mapeo_camas/historiales_detalle.html"
    required_roles = MAPEO_CAMAS_HISTORIALES_ROLES
    required_unidades = MAPEO_CAMAS_HISTORIALES_UNIDADES

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
    if not _tiene_permiso_historiales(request.user):
        return JsonResponse({"ok": False, "error": "Acceso denegado."}, status=403)

    tipo = (request.GET.get("tipo") or "mapeo").strip().lower()
    cama_id = (request.GET.get("cama_id") or "").strip()
    fecha_inicio = _parse_fecha_filtro(request.GET.get("fecha_inicio"), fin_del_dia=False)
    fecha_fin = _parse_fecha_filtro(request.GET.get("fecha_fin"), fin_del_dia=True)

    if tipo not in {"mapeo", "historial", "movimiento"}:
        return JsonResponse({"ok": False, "error": "Tipo de historial no valido."}, status=400)

    if tipo == "mapeo":
        sesiones = MapeoSesionCama.objects.select_related("usuario").prefetch_related(
            Prefetch(
                "servicios_incluidos",
                queryset=MapeoSesionServicio.objects.select_related("servicio").order_by("servicio__nombre_servicio"),
                to_attr="servicios_prefetch",
            )
        ).order_by("-fecha_inicio")
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
            nombres_servicios = [
                ss.servicio.nombre_servicio
                for ss in getattr(sesion, "servicios_prefetch", [])
                if ss.servicio_id
            ]
            results.append(
                {
                    "id": sesion.id,
                    "referencia": f"Sesion {sesion.id}",
                    "tipo": "MAPEO",
                    "estado": sesion.estado.codigo if hasattr(sesion.estado, "codigo") else str(sesion.estado),
                    "fecha_principal": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_inicio": _hora_local_iso(sesion.fecha_inicio),
                    "fecha_fin": _hora_local_iso(sesion.fecha_fin),
                    "usuario": _nombre_usuario(sesion.usuario),
                    "detalle_1": f"Camas procesadas: {sesion.total_camas}",
                    "detalle_2": f"Cambios detectados: {sesion.total_cambios}",
                    "detalle_3": f"Registros detalle: {sesion.total_detalles}",
                    "servicios": nombres_servicios,
                }
            )
        return JsonResponse({"ok": True, "results": results})

    if tipo == "historial":
        historial_qs = HistorialEstadoCama.objects.select_related(
            "cama__sala__servicio", "cama__cubiculo", "ingreso__paciente", "usuario"
        )
        if fecha_inicio:
            historial_qs = historial_qs.filter(fecha_hora__gte=fecha_inicio)
        if fecha_fin:
            historial_qs = historial_qs.filter(fecha_hora__lte=fecha_fin)
        if cama_id:
            historial_qs = historial_qs.filter(cama_id=cama_id)

        latest_id_por_cama = (
            historial_qs.filter(cama_id=OuterRef("cama_id"))
            .order_by("-fecha_hora", "-id")
            .values("id")[:1]
        )

        eventos_por_cama = {
            str(item["cama_id"]): item["total"]
            for item in historial_qs.values("cama_id").annotate(total=Count("id"))
        }

        ultimos_eventos = (
            historial_qs.filter(id=Subquery(latest_id_por_cama))
            .order_by("-fecha_hora", "-id")[:300]
        )

        results = []
        for item in ultimos_eventos:
            total_eventos = eventos_por_cama.get(str(item.cama_id), 0)
            paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
            results.append(
                {
                    "id": item.cama_id,
                    "referencia": f"Cama {_nombre_cama(item.cama)}",
                    "tipo": "HISTORIAL",
                    "estado": item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo),
                    "fecha_principal": _hora_local_iso(item.fecha_hora),
                    "fecha_inicio": _hora_local_iso(item.fecha_hora),
                    "fecha_fin": "",
                    "usuario": _nombre_usuario(item.usuario),
                    "detalle_1": f"Cama: {_nombre_cama(item.cama)}",
                    "detalle_2": f"Ultimo cambio: {(getattr(item.estado_anterior, 'codigo', item.estado_anterior) or 'SIN_ESTADO')} -> {getattr(item.estado_nuevo, 'codigo', item.estado_nuevo)}",
                    "detalle_3": f"Eventos: {total_eventos} | " + (
                        f"Paciente: {paciente['nombre']}" if paciente else "Paciente: Sin paciente"
                    ),
                }
            )
        return JsonResponse({"ok": True, "results": results})

    # [2026-05-05 FEATURE] Agrupa movimientos por cama.
    movimientos = (
        MovimientoCama.objects.select_related(
            "cama_origen__sala__servicio",
            "cama_origen__cubiculo",
            "cama_destino__sala__servicio",
            "cama_destino__cubiculo",
            "ingreso__paciente",
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

    camas_map = {}
    for mov in movimientos[:500]:
        for cama in [mov.cama_origen, mov.cama_destino]:
            key = str(cama.pk)
            if key not in camas_map:
                camas_map[key] = {"cama": cama, "ultimo": mov, "total": 0}
            camas_map[key]["total"] += 1

    camas_ordenadas = sorted(
        camas_map.values(),
        key=lambda x: x["ultimo"].fecha_hora,
        reverse=True,
    )[:300]

    results = []
    for registro in camas_ordenadas:
        cama = registro["cama"]
        ultimo = registro["ultimo"]
        total = registro["total"]
        paciente = _paciente_payload(ultimo.ingreso.paciente if ultimo.ingreso_id else None, ingreso_id=ultimo.ingreso_id)
        results.append(
            {
                "id": cama.pk,
                "referencia": f"Cama {_nombre_cama(cama)}",
                "tipo": "MOVIMIENTO",
                "estado": f"{total} movimiento(s)",
                "fecha_principal": _hora_local_iso(ultimo.fecha_hora),
                "fecha_inicio": _hora_local_iso(ultimo.fecha_hora),
                "fecha_fin": "",
                "usuario": _nombre_usuario(ultimo.usuario),
                "detalle_1": f"Cama: {_nombre_cama(cama)}",
                "detalle_2": f"Total movimientos: {total}",
                "detalle_3": f"Ultimo paciente: {paciente['nombre']}" if paciente else "Sin paciente",
            }
        )
    return JsonResponse({"ok": True, "results": results})


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

    if not registro_id:
        return JsonResponse({"ok": False, "error": "Debe indicar id."}, status=400)

    if tipo == "mapeo":
        sesion = MapeoSesionCama.objects.filter(pk=registro_id).first()
        if not sesion:
            return JsonResponse({"ok": False, "error": "Sesion no encontrada."}, status=404)

        detalles = (
            DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
            .select_related("cama__sala__servicio", "cama__cubiculo__sala__servicio", "ingreso_actual__paciente", "usuario", "estado_actual", "tipo_accion")
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "fecha_hora")
        )

        detalles_list = list(detalles)
        ultimo_estado_por_cama = {}
        tipo_accion_display_map = {}

        for item in detalles_list:
            estado_actual_codigo = item.estado_actual.codigo if item.estado_actual else ""
            estado_anterior_codigo = ultimo_estado_por_cama.get(item.cama_id, None)

            if estado_anterior_codigo is None:
                tipo_accion_display = "Confirmación"
            else:
                tipo_accion_display = f"{estado_anterior_codigo} \u2192 {estado_actual_codigo}"

            tipo_accion_display_map[(item.cama_id, item.fecha_hora.isoformat())] = tipo_accion_display
            ultimo_estado_por_cama[item.cama_id] = estado_actual_codigo

        detalles_list_ordenados = sorted(detalles_list, key=lambda x: x.fecha_hora, reverse=True)

        cards = []
        servicios_map = {}
        camas_vistas_estructura = set()

        for item in detalles_list_ordenados:
            paciente = _paciente_payload(item.ingreso_actual.paciente if item.ingreso_actual_id else None, ingreso_id=item.ingreso_actual_id)
            cama_numero = _nombre_cama(item.cama)
            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre,
                    "cubiculos": {},
                    "camas_directas": [],
                }

            tipo_accion_display = tipo_accion_display_map.get((item.cama_id, item.fecha_hora.isoformat()), "Confirmación")

            cama_item = {
                "numero_cama": cama_numero,
                "estado": item.estado_actual.codigo if item.estado_actual else "",
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": tipo_accion_display,
                "hubo_cambio": bool(item.hubo_cambio),
                "fue_validada": bool(item.fue_validada),
                "observacion": _observacion_codigo(item.observacion),
            }

            clave_cama = (servicio_nombre, sala_nombre, cubiculo_nombre, cama_numero)
            if clave_cama not in camas_vistas_estructura:
                camas_vistas_estructura.add(clave_cama)
                if cubiculo_nombre == "SIN_CUBICULO":
                    servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
                else:
                    cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                    if cubiculo_nombre not in cubiculos_map:
                        cubiculos_map[cubiculo_nombre] = {
                            "nombre": cubiculo_nombre,
                            "camas": [],
                        }
                    cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

            cards.append(
                {
                    "titulo": f"Cama {item.cama_id}",
                    "subtitulo": tipo_accion_display,
                    "estado": item.estado_actual.codigo if item.estado_actual else "",
                    "paciente": paciente["nombre"] if paciente else "Sin paciente",
                    "usuario": _nombre_usuario(item.usuario),
                    "fecha": _hora_local_iso(item.fecha_hora),
                    "detalle_1": f"Ubicacion: {_ubicacion_desde_cama(item.cama)}",
                    "detalle_2": f"Validada: {'SI' if item.fue_validada else 'NO'}",
                    "detalle_3": f"Hubo cambio: {'SI' if item.hubo_cambio else 'NO'}",
                    "observacion": _observacion_codigo(item.observacion),
                }
            )

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                cubiculos_data = list(sala_data["cubiculos"].values())
                salas_data.append(
                    {
                        "nombre": sala_data["nombre"],
                        "cubiculos": cubiculos_data,
                        "camas_directas": sala_data["camas_directas"],
                    }
                )
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        servicios_sesion = [
            ss.servicio.nombre_servicio
            for ss in MapeoSesionServicio.objects.select_related("servicio")
            .filter(sesion_mapeo=sesion)
            .order_by("servicio__nombre_servicio")
        ]

        return JsonResponse(
            {
                "ok": True,
                "cards": cards,
                "estructura": estructura,
                "servicios_sesion": servicios_sesion,
                "sesion_observacion": sesion.observacion_texto if sesion.observacion_texto else None,
                "paginacion": {
                    "page": 1,
                    "page_size": page_size,
                    "total_items": len(cards),
                    "total_pages": 1,
                },
            }
        )

    if tipo == "historial":
        timeline_qs = (
            HistorialEstadoCama.objects.select_related(
                "cama__sala__servicio", "cama__cubiculo__sala__servicio",
                "estado_anterior", "estado_nuevo", "ingreso__paciente", "usuario",
            )
            .filter(cama_id=registro_id)
            .order_by("cama__sala__nombre_sala", "cama__cubiculo__numero", "cama__numero_cama", "-fecha_hora")
        )
        total_items = timeline_qs.count()
        if total_items == 0:
            return JsonResponse({"ok": False, "error": "Historial no encontrado para esta cama."}, status=404)

        total_pages = max(1, (total_items + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        inicio = (page - 1) * page_size
        timeline_page = timeline_qs[inicio:inicio + page_size]

        servicios_map = {}
        for item in timeline_page:
            paciente = _paciente_payload(item.ingreso.paciente if item.ingreso_id else None, ingreso_id=item.ingreso_id)
            estado_nuevo_codigo = item.estado_nuevo.codigo if hasattr(item.estado_nuevo, "codigo") else str(item.estado_nuevo)
            estado_anterior_codigo = (
                item.estado_anterior.codigo if hasattr(item.estado_anterior, "codigo") else str(item.estado_anterior)
            ) if item.estado_anterior else "SIN_ESTADO"

            cubiculo_obj = getattr(item.cama, "cubiculo", None)
            sala_real = (cubiculo_obj.sala if cubiculo_obj else None) or getattr(item.cama, "sala", None)
            servicio_nombre = getattr(getattr(sala_real, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
            sala_nombre = getattr(sala_real, "nombre_sala", "") or "SIN_SALA"
            cubiculo_nombre = (f"#{cubiculo_obj.numero} {cubiculo_obj.nombre_cubiculo}") if cubiculo_obj else "SIN_CUBICULO"

            if servicio_nombre not in servicios_map:
                servicios_map[servicio_nombre] = {"nombre": servicio_nombre, "salas": {}}
            if sala_nombre not in servicios_map[servicio_nombre]["salas"]:
                servicios_map[servicio_nombre]["salas"][sala_nombre] = {
                    "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                }

            cama_item = {
                "numero_cama": _nombre_cama(item.cama),
                "estado": estado_nuevo_codigo,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(item.usuario),
                "fecha": _hora_local_iso(item.fecha_hora),
                "tipo_accion": f"{estado_anterior_codigo} \u2192 {estado_nuevo_codigo}",
                "observacion": _observacion_codigo(item.observacion),
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        estructura = []
        for servicio_data in servicios_map.values():
            salas_data = []
            for sala_data in servicio_data["salas"].values():
                salas_data.append({
                    "nombre": sala_data["nombre"],
                    "cubiculos": list(sala_data["cubiculos"].values()),
                    "camas_directas": sala_data["camas_directas"],
                })
            estructura.append({"nombre": servicio_data["nombre"], "salas": salas_data})

        return JsonResponse(
            {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }
        )

    if tipo == "movimiento":
        movimientos_qs = (
            MovimientoCama.objects.select_related(
                "cama_origen__sala__servicio", "cama_origen__cubiculo__sala__servicio",
                "cama_destino__sala__servicio", "cama_destino__cubiculo__sala__servicio",
                "ingreso__paciente", "usuario",
            )
            .filter(Q(cama_origen_id=registro_id) | Q(cama_destino_id=registro_id))
            .order_by("-fecha_hora")
        )
        total_items = movimientos_qs.count()
        if total_items == 0:
            return JsonResponse({"ok": False, "error": "No se encontraron movimientos para esta cama."}, status=404)

        total_pages = max(1, (total_items + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        inicio = (page - 1) * page_size
        movimientos_page = movimientos_qs[inicio:inicio + page_size]

        primer_mov = movimientos_qs.first()
        cama_ref = (
            primer_mov.cama_origen
            if str(primer_mov.cama_origen_id) == str(registro_id)
            else primer_mov.cama_destino
        )

        cubiculo_obj_ref = getattr(cama_ref, "cubiculo", None)
        sala_real_ref = (cubiculo_obj_ref.sala if cubiculo_obj_ref else None) or getattr(cama_ref, "sala", None)
        servicio_nombre = getattr(getattr(sala_real_ref, "servicio", None), "nombre_servicio", "") or "SIN_SERVICIO"
        sala_nombre = getattr(sala_real_ref, "nombre_sala", "") or "SIN_SALA"
        cubiculo_nombre = (f"#{cubiculo_obj_ref.numero} {cubiculo_obj_ref.nombre_cubiculo}") if cubiculo_obj_ref else "SIN_CUBICULO"

        servicios_map = {
            servicio_nombre: {
                "nombre": servicio_nombre,
                "salas": {
                    sala_nombre: {
                        "nombre": sala_nombre, "cubiculos": {}, "camas_directas": [],
                    }
                },
            }
        }

        for mov in movimientos_page:
            paciente = _paciente_payload(mov.ingreso.paciente if mov.ingreso_id else None, ingreso_id=mov.ingreso_id)
            tipo_mov = mov.tipo_movimiento.codigo if hasattr(mov.tipo_movimiento, "codigo") else str(mov.tipo_movimiento)
            es_origen = str(mov.cama_origen_id) == str(registro_id)
            otra_cama = mov.cama_destino if es_origen else mov.cama_origen
            rol = f"SALIDA \u2192 Cama {_nombre_cama(otra_cama)}" if es_origen else f"ENTRADA \u2190 Cama {_nombre_cama(otra_cama)}"

            cama_item = {
                "numero_cama": _nombre_cama(cama_ref),
                "estado": tipo_mov,
                "paciente": paciente["nombre"] if paciente else "Sin paciente",
                "dni": paciente["dni"] if paciente else "",
                "usuario": _nombre_usuario(mov.usuario),
                "fecha": _hora_local_iso(mov.fecha_hora),
                "tipo_accion": rol,
                "observacion": _observacion_codigo(mov.observacion),
            }

            if cubiculo_nombre == "SIN_CUBICULO":
                servicios_map[servicio_nombre]["salas"][sala_nombre]["camas_directas"].append(cama_item)
            else:
                cubiculos_map = servicios_map[servicio_nombre]["salas"][sala_nombre]["cubiculos"]
                if cubiculo_nombre not in cubiculos_map:
                    cubiculos_map[cubiculo_nombre] = {"nombre": cubiculo_nombre, "camas": []}
                cubiculos_map[cubiculo_nombre]["camas"].append(cama_item)

        salas_data = []
        for sala_data in servicios_map[servicio_nombre]["salas"].values():
            salas_data.append({
                "nombre": sala_data["nombre"],
                "cubiculos": list(sala_data["cubiculos"].values()),
                "camas_directas": sala_data["camas_directas"],
            })
        estructura = [{"nombre": servicio_nombre, "salas": salas_data}]

        return JsonResponse(
            {
                "ok": True,
                "cards": [],
                "estructura": estructura,
                "paginacion": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                },
            }
        )

    return JsonResponse({"ok": False, "error": "Tipo no soportado."}, status=400)
