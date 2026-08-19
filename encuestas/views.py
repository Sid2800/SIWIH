"""
Vistas del módulo de Encuestas (UAU).

Fase 1: acceso e inicio (encabezado + elegir servicio).
Fase 2: formulario genérico por servicio (se alimenta de encuestas.catalogos) y
guardado con calificación por puntos. Solo la UAU ve el módulo; cada usuario ve
sus encuestas y el personal `is_staff` (supervisión) las ve todas.
"""
import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST
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
    filas = []
    numerados_puntajes = []
    for item in definicion['preguntas']:
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
            cuenta_consolidado=es_numerada,
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

    from datetime import datetime
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
