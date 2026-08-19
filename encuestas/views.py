"""
Vistas del módulo de Encuestas (UAU).

Fase 1: acceso e inicio (encabezado + elegir servicio).
Fase 2: formulario genérico por servicio (se alimenta de encuestas.catalogos) y
guardado con calificación por puntos. Solo la UAU ve el módulo; cada usuario ve
sus encuestas y el personal `is_staff` (supervisión) las ve todas.
"""
import json
from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from core.mixins import UnidadRolRequiredMixin
from usuario.permisos import verificar_permisos_usuario
from core.constants.permisos import (
    ENCUESTAS_VISUALIZACION_ROLES, ENCUESTAS_VISUALIZACION_UNIDADES,
)
from core.utils.utilidades_logging import log_error, log_info
from core.constants.domain_constants import LogApp

from encuestas.models import Encuesta, EncuestaRespuesta
from encuestas import catalogos


# =============================================================================
# Acceso
# =============================================================================
def _tiene_permiso_encuestas(user):
    return verificar_permisos_usuario(
        user, ENCUESTAS_VISUALIZACION_ROLES, ENCUESTAS_VISUALIZACION_UNIDADES
    )


def _ve_todas_las_encuestas(user):
    """Cada usuario ve lo suyo; el personal is_staff (supervisión) ve todo."""
    return bool(user.is_superuser or user.is_staff)


# =============================================================================
# Inicio
# =============================================================================
class EncuestasInicioView(UnidadRolRequiredMixin, TemplateView):
    """Inicio del módulo: encabezado + selección del servicio a encuestar."""
    template_name = 'encuestas/inicio.html'
    required_roles = ENCUESTAS_VISUALIZACION_ROLES
    required_unidades = ENCUESTAS_VISUALIZACION_UNIDADES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['servicios'] = Encuesta.SERVICIOS
        return ctx


# =============================================================================
# Formulario de una encuesta (genérico, según definición del servicio)
# =============================================================================
class EncuestaFormView(UnidadRolRequiredMixin, TemplateView):
    """Formulario de una encuesta; las preguntas salen de encuestas.catalogos."""
    template_name = 'encuestas/encuesta_form.html'
    required_roles = ENCUESTAS_VISUALIZACION_ROLES
    required_unidades = ENCUESTAS_VISUALIZACION_UNIDADES

    def dispatch(self, request, *args, **kwargs):
        self.definicion = catalogos.definicion(kwargs.get('servicio'))
        if not self.definicion:
            return redirect('encuestas_inicio')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        d = self.definicion
        # Resolver opciones de cada pregunta para pintarlas en la plantilla.
        preguntas = []
        for item in d['preguntas']:
            preguntas.append({**item, 'lista_opciones': catalogos.opciones_de(item)})
        ctx['servicio'] = d['servicio']
        ctx['nombre_servicio'] = d['nombre']
        ctx['subservicios'] = d.get('subservicios') or []
        ctx['pide_tipo_encuestado'] = d.get('pide_tipo_encuestado', False)
        ctx['pide_identidad'] = d.get('pide_identidad', False)
        ctx['preguntas'] = preguntas
        return ctx


# =============================================================================
# Guardado + calificación
# =============================================================================
def _calificar_y_guardar_respuestas(encuesta, definicion, respuestas):
    """
    Crea las respuestas de una encuesta y devuelve el % de satisfacción.

    Solo las preguntas 'radio' numeradas cuentan para el consolidado: se les
    calcula el puntaje (100/85/70/55) con la tabla del catálogo. El % de
    satisfacción de la encuesta es (puntos 100 y 85) / (nº numeradas * 100).
    """
    entra_consolidado = definicion.get('consolidado', True)
    filas = []
    numerados_puntajes = []
    for item in definicion['preguntas']:
        if item.get('tipo') == 'seccion':
            continue
        valor = (respuestas.get(item['codigo']) or '').strip()
        if not valor:
            continue
        es_numerada = item.get('tipo') == 'radio' and item.get('numero') is not None
        puntaje = catalogos.puntaje_de(valor) if es_numerada else None
        if es_numerada:
            numerados_puntajes.append(puntaje)
        filas.append(EncuestaRespuesta(
            encuesta=encuesta,
            codigo=item['codigo'],
            numero=item.get('numero'),
            texto_pregunta=item.get('texto', '')[:300],
            respuesta=valor[:200],
            puntaje=puntaje,
            # Solo cuenta para el consolidado mensual si la encuesta lo integra
            # (Usuario Externo NO) y la pregunta es numerada.
            cuenta_consolidado=bool(es_numerada and entra_consolidado),
        ))
    EncuestaRespuesta.objects.bulk_create(filas)

    if numerados_puntajes:
        total = len(numerados_puntajes) * 100
        satisf = sum(p for p in numerados_puntajes if p in (100, 85))
        return round(satisf / total * 100, 2)
    return None


@csrf_protect
@require_POST
def guardar_encuesta_api(request):
    """Guarda una encuesta con sus respuestas y calcula su % de satisfacción."""
    if not _tiene_permiso_encuestas(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    servicio = body.get('servicio')
    definicion = catalogos.definicion(servicio)
    if not definicion:
        return JsonResponse({"error": "Servicio de encuesta no válido"}, status=400)

    try:
        fecha = datetime.strptime((body.get('fecha') or '').strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({"error": "La fecha de la encuesta es obligatoria"}, status=400)

    respuestas = body.get('respuestas') or {}
    if not isinstance(respuestas, dict):
        return JsonResponse({"error": "Respuestas inválidas"}, status=400)

    try:
        with transaction.atomic():
            encuesta = Encuesta.objects.create(
                servicio=servicio,
                subservicio=(body.get('subservicio') or '').strip() or None,
                fecha=fecha,
                tipo_encuestado=(body.get('tipo_encuestado') or '').strip() or None,
                identidad=(body.get('identidad') or '').strip() or None,
                comentario=(body.get('comentario') or '').strip() or None,
                creado_por=request.user,
            )
            porcentaje = _calificar_y_guardar_respuestas(encuesta, definicion, respuestas)
            encuesta.porcentaje_satisfaccion = porcentaje
            encuesta.save(update_fields=['porcentaje_satisfaccion'])

        log_info(
            f"Encuesta #{encuesta.id} ({servicio}) guardada por {request.user.username} "
            f"— satisf {porcentaje}%", app=LogApp.ENCUESTAS,
        )
        return JsonResponse({
            "success": True,
            "encuesta_id": encuesta.id,
            "porcentaje_satisfaccion": float(porcentaje) if porcentaje is not None else None,
        })
    except Exception as e:
        log_error(f"Error en guardar_encuesta_api: {e}", app=LogApp.ENCUESTAS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# =============================================================================
# Lista de encuestas ingresadas (cada usuario las suyas; is_staff todas)
# =============================================================================
class MisEncuestasView(UnidadRolRequiredMixin, TemplateView):
    """Lista de encuestas ingresadas por el usuario (o todas, si es staff)."""
    template_name = 'encuestas/lista.html'
    required_roles = ENCUESTAS_VISUALIZACION_ROLES
    required_unidades = ENCUESTAS_VISUALIZACION_UNIDADES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['servicios'] = Encuesta.SERVICIOS
        ctx['ve_todas'] = _ve_todas_las_encuestas(self.request.user)
        return ctx


@require_GET
def mis_encuestas_api(request):
    """
    Devuelve las encuestas visibles para el usuario. Cada usuario ve las suyas;
    el personal is_staff (supervisión) ve todas. Filtros: servicio, desde, hasta.
    """
    if not _tiene_permiso_encuestas(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        qs = Encuesta.objects.select_related('creado_por').order_by('-fecha', '-id')
        if not _ve_todas_las_encuestas(request.user):
            qs = qs.filter(creado_por=request.user)

        servicio = (request.GET.get('servicio') or '').strip()
        if servicio:
            qs = qs.filter(servicio=servicio)

        def _fecha(v):
            try:
                return datetime.strptime((v or '').strip(), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return None
        desde, hasta = _fecha(request.GET.get('desde')), _fecha(request.GET.get('hasta'))
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)

        display = dict(Encuesta.SERVICIOS)
        data = [{
            "id": e.id,
            "servicio": e.servicio,
            "servicio_nombre": display.get(e.servicio, e.servicio),
            "subservicio": e.subservicio or '',
            "fecha": e.fecha.isoformat(),
            "porcentaje": (float(e.porcentaje_satisfaccion)
                           if e.porcentaje_satisfaccion is not None else None),
            "encuestador": (e.creado_por.get_full_name() or e.creado_por.username),
        } for e in qs[:500]]

        return JsonResponse({"data": data, "total": len(data)})
    except Exception as e:
        log_error(f"Error en mis_encuestas_api: {e}", app=LogApp.ENCUESTAS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def detalle_encuesta_api(request, encuesta_id):
    """Detalle (solo lectura) de una encuesta: sus respuestas. Dueño o staff."""
    if not _tiene_permiso_encuestas(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    encuesta = get_object_or_404(
        Encuesta.objects.select_related('creado_por'), id=encuesta_id
    )
    if encuesta.creado_por_id != request.user.id and not _ve_todas_las_encuestas(request.user):
        return JsonResponse({"error": "No puede ver esta encuesta"}, status=403)

    display = dict(Encuesta.SERVICIOS)
    respuestas = [{
        "codigo": r.codigo,
        "numero": r.numero,
        "texto": r.texto_pregunta or '',
        "respuesta": r.respuesta or '',
        "puntaje": r.puntaje,
    } for r in encuesta.respuestas.all().order_by('numero', 'codigo')]

    return JsonResponse({
        "id": encuesta.id,
        "servicio": encuesta.servicio,
        "servicio_nombre": display.get(encuesta.servicio, encuesta.servicio),
        "subservicio": encuesta.subservicio or '',
        "fecha": encuesta.fecha.isoformat(),
        "tipo_encuestado": encuesta.tipo_encuestado or '',
        "identidad": encuesta.identidad or '',
        "porcentaje": (float(encuesta.porcentaje_satisfaccion)
                       if encuesta.porcentaje_satisfaccion is not None else None),
        "encuestador": (encuesta.creado_por.get_full_name() or encuesta.creado_por.username),
        "respuestas": respuestas,
    })
