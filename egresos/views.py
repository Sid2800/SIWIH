"""
Vistas del módulo de Egresos.

Fase 2: pantalla de CAPTURA. Estadística ve los ingresos aún abiertos (solo
tienen fecha de ingreso) y toma los expedientes disponibles para llenar sus
egresos. Aquí va, por ahora, la API que ALIMENTA ese listado (solo lectura; no
modifica el módulo Ingreso).
"""
import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from ingreso.models import Ingreso
from expediente.models import PacienteAsignacion, Expediente
from s_exp.models import (
    ExpedientePrestamo, SolicitudExpedienteDetalle,
    EstadoSolicitud, EstadoExpedienteFisico,
)

from egresos.models import LoteEgreso, LoteEgresoDetalle
from egresos.services.permisos import puede_acceder_egresos
from egresos.services.movimiento import mover_a_estadistica

from core.utils.utilidades_logging import log_error, log_info
from core.constants.domain_constants import LogApp


# =============================================================================
# MIXIN de acceso (mismo criterio que el servicio de permisos)
# =============================================================================
class EgresosAccesoMixin(LoginRequiredMixin):
    """Solo Estadística y staff pueden entrar a las pantallas de Egresos."""
    def dispatch(self, request, *args, **kwargs):
        if not puede_acceder_egresos(request.user):
            return redirect('acceso_denegado')
        return super().dispatch(request, *args, **kwargs)


class CapturaEgresosView(EgresosAccesoMixin, TemplateView):
    """Pantalla donde Estadística captura expedientes desde los ingresos."""
    template_name = 'egresos/captura.html'


# =============================================================================
# Helpers de disponibilidad (reutilizan el criterio de s_exp)
# =============================================================================
def _expedientes_no_disponibles():
    """
    IDs de expedientes que NO se pueden tomar, con el mismo criterio de s_exp:
      - los que están en cualquier estado físico distinto de DISPONIBLE, y
      - los que participan en una solicitud de préstamo activa (aprobados y sin
        devolver).
    Se calcula en 2 consultas (sin N+1) para clasificar el listado completo.
    """
    no_disp = set(
        ExpedientePrestamo.objects
        .exclude(estado_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'))
        .values_list('expediente_id', flat=True)
    )
    en_proceso = set(
        SolicitudExpedienteDetalle.objects.filter(
            solicitud__estado_flujo_id__in=EstadoSolicitud.ids_de([
                'SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
                'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA',
            ]),
            devuelto=False, aprobado=True,
        ).values_list('expediente_prestamo__expediente_id', flat=True)
    )
    return no_disp | en_proceso


@require_GET
def ingresos_para_egreso_api(request):
    """
    Lista los ingresos ABIERTOS (solo fecha de ingreso, sin egreso) para que
    Estadística tome sus expedientes.

    Devuelve por ingreso: paciente (identidad y nombre), fecha de ingreso, área
    (sala/servicio del ingreso), número de expediente y si está DISPONIBLE para
    capturar. No modifica nada del módulo Ingreso (solo lectura).
    """
    if not puede_acceder_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from s_exp.services.datos_solicitud import DatosPaciente

        ingresos = (
            Ingreso.objects
            .filter(fecha_egreso__isnull=True, paciente__isnull=False)
            .select_related('paciente', 'sala', 'sala__servicio')
            .order_by('-fecha_ingreso')
        )

        # Expediente de cada paciente (uno solo, el vigente), en bloque para no
        # disparar una consulta por fila.
        paciente_ids = list(ingresos.values_list('paciente_id', flat=True))
        exp_por_paciente = {}
        for asig in (PacienteAsignacion.objects
                     .filter(paciente_id__in=paciente_ids)
                     .select_related('expediente')
                     .order_by('-estado')):
            # order_by('-estado') deja la asignación vigente primero; nos quedamos
            # con la primera vista por paciente.
            exp_por_paciente.setdefault(asig.paciente_id, asig.expediente)

        no_disponibles = _expedientes_no_disponibles()

        data = []
        for ing in ingresos:
            pac = ing.paciente
            exp = exp_por_paciente.get(pac.id)
            disponible = bool(exp) and exp.id not in no_disponibles
            data.append({
                "ingreso_id": ing.id,
                "paciente_id": pac.id,
                "identidad": DatosPaciente.dni(pac),
                "nombre": DatosPaciente.nombre_completo(pac),
                "fecha_ingreso": ing.fecha_ingreso.date().isoformat() if ing.fecha_ingreso else '',
                "area_ingreso": str(ing.sala) if ing.sala_id else '',
                "expediente_id": exp.id if exp else None,
                "numero_expediente": exp.numero if exp else None,
                "disponible": disponible,
            })

        return JsonResponse({"data": data, "total": len(data)})

    except Exception as e:
        log_error(f"Error en ingresos_para_egreso_api: {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def crear_lote_captura_api(request):
    """
    Estadística captura los expedientes seleccionados: crea un LOTE con sus
    detalles y marca cada expediente como "prestado a Estadística" (se ubica en
    Estadística y deja de estar disponible para otros).

    Solo se aceptan expedientes DISPONIBLES; la disponibilidad se revalida aquí
    (no se confía en lo que mandó el navegador). Todo va en una transacción: o se
    capturan todos o ninguno.
    """
    if not puede_acceder_egresos(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    # El front manda parejas expediente/paciente de las filas elegidas.
    seleccion = body.get('seleccion') or []
    observaciones = (body.get('observaciones') or '').strip()

    expediente_ids = [s.get('expediente_id') for s in seleccion if s.get('expediente_id')]
    if not expediente_ids:
        return JsonResponse({"error": "Seleccione al menos un expediente"}, status=400)

    # Revalidación de disponibilidad en el servidor.
    no_disponibles = _expedientes_no_disponibles()
    validos = [eid for eid in expediente_ids if eid not in no_disponibles]
    if not validos:
        return JsonResponse(
            {"error": "Los expedientes seleccionados ya no están disponibles"}, status=400
        )

    # paciente por expediente (según lo que mandó el front, para no re-resolver).
    paciente_por_exp = {
        s['expediente_id']: s.get('paciente_id')
        for s in seleccion if s.get('expediente_id')
    }

    try:
        expedientes = {e.id: e for e in Expediente.objects.filter(id__in=validos)}

        with transaction.atomic():
            lote = LoteEgreso.objects.create(
                usuario_estadistica=request.user,
                observaciones=observaciones or None,
            )
            for eid in validos:
                exp = expedientes.get(eid)
                if not exp:
                    continue
                LoteEgresoDetalle.objects.create(
                    lote=lote,
                    expediente=exp,
                    paciente_id=paciente_por_exp.get(eid),
                    estado=LoteEgresoDetalle.PRESTADO,
                )
                # Marca el expediente como prestado a Estadística.
                mover_a_estadistica(exp, request.user)

        log_info(
            f"Lote de egresos #{lote.id}: {len(validos)} expediente(s) capturados por "
            f"{request.user.username}", app=LogApp.EGRESOS
        )
        return JsonResponse({"success": True, "lote_id": lote.id, "capturados": len(validos)})

    except Exception as e:
        log_error(f"Error en crear_lote_captura_api: {e}", app=LogApp.EGRESOS)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
