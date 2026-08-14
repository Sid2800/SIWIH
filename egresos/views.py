"""
Vistas del módulo de Egresos.

Fase 2: pantalla de CAPTURA. Estadística ve los ingresos aún abiertos (solo
tienen fecha de ingreso) y toma los expedientes disponibles para llenar sus
egresos. Aquí va, por ahora, la API que ALIMENTA ese listado (solo lectura; no
modifica el módulo Ingreso).
"""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_GET

from ingreso.models import Ingreso
from expediente.models import PacienteAsignacion
from s_exp.models import (
    ExpedientePrestamo, SolicitudExpedienteDetalle,
    EstadoSolicitud, EstadoExpedienteFisico,
)

from egresos.services.permisos import puede_acceder_egresos

from core.utils.utilidades_logging import log_error
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
