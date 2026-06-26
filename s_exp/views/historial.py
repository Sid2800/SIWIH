"""
historial.py - Vista e APIs del historial de solicitudes.

Parte del paquete s_exp.views (antes views.py monolitico).
"""



from django.http import JsonResponse
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET

from django.db.models import Count, Q

from s_exp.models import SolicitudPrestamo, ExpedienteEstadoLog


from .comunes import (
    SExpAdminMixin,
    _es_exp_admin,
    _fmt_local,
)


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


# ============================================
# HISTORIAL DE SOLICITUDES (Admin)
# ============================================

class HistorialSolicitudesView(SExpAdminMixin, TemplateView):
    template_name = 's_exp/historial_solicitudes.html'


@require_GET
def historial_solicitudes_api(request):
    """Lista todas las solicitudes (historico) con paginación server-side."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 25))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        qs = SolicitudPrestamo.objects.select_related(
            'usuario', 'estado_flujo', 'motivo'
        ).annotate(cant_exp=Count('detalles'))

        if estado_filtro:
            # estado_filtro es el CÓDIGO de texto que envía el frontend.
            qs = qs.filter(estado_flujo__codigo=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(usuario__username__icontains=search_value) |
                Q(usuario__first_name__icontains=search_value) |
                Q(usuario__last_name__icontains=search_value) |
                Q(id__icontains=search_value) |
                Q(motivo__nombre__icontains=search_value)
            )

        total_records = SolicitudPrestamo.objects.count()
        filtered_records = qs.count()
        solicitudes = qs.order_by('-fecha_creacion')[start:start + length]

        data = []
        for s in solicitudes:
            numeros = list(
                s.detalles.values_list('expediente_prestamo__expediente__numero', flat=True)
            )
            # Eventos resumen (incompleta, devuelto fuera de tiempo).
            # Comparamos por id usando id_de() (cacheado, sin query extra), ya
            # que estado_flujo_id/estado_id son enteros (PK de los catálogos).
            from s_exp.models import EstadoSolicitud, EstadoPrestamo
            evento = None
            prestamo = s.prestamos.first()
            if s.estado_flujo_id == EstadoSolicitud.id_de('SOL_INCOMPLETA'):
                faltantes = s.detalles.filter(devuelto=False).count()
                evento = f"⚠️ Incompleta: {faltantes} expediente(s) sin devolver"
            elif prestamo and prestamo.estado_id == EstadoPrestamo.id_de('DevueltoVencido'):
                evento = "🕒 Devuelto fuera del tiempo acordado"
            elif s.estado_flujo_id == EstadoSolicitud.id_de('SOL_FINALIZADA'):
                evento = "✅ Finalizada correctamente"

            from s_exp.services.datos_solicitud import DatosSolicitud
            data.append({
                "id": s.id,
                "usuario": DatosSolicitud.usuario_username(s),
                "usuario_nombre": DatosSolicitud.usuario_nombre_completo(s),
                "fecha_creacion": _fmt_local(s.fecha_creacion),
                "estado_flujo": DatosSolicitud.estado_codigo(s),
                "estado_flujo_nombre": DatosSolicitud.estado_nombre(s),
                "motivo": DatosSolicitud.motivo_nombre(s),
                "area_destino": DatosSolicitud.unidad_nombre(s),
                "expedientes": numeros,
                "evento_resumen": evento,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })
    except Exception as e:
        log_error(f"Error en historial_solicitudes_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def historial_solicitud_detalle_api(request, solicitud_id):
    """Retorna el detalle completo de una solicitud para el modal del historial."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        s = SolicitudPrestamo.objects.select_related(
            'usuario', 'estado_flujo', 'motivo', 'servicio_unidad'
        ).get(id=solicitud_id)

        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        # Expedientes con estado físico actual (nombre del paciente vía FK)
        expedientes_data = []
        for d in s.detalles.select_related(
            'expediente_prestamo__expediente', 'expediente_prestamo__estado', 'paciente'
        ):
            ep = d.expediente_prestamo
            expedientes_data.append({
                "numero": DatosDetalleSolicitud.numero_expediente(d),
                "paciente": DatosDetalleSolicitud.paciente_nombre_completo(d),
                "estado_fisico": ep.estado.nombre if ep.estado else "—",
                "devuelto": d.devuelto,
            })

        # Logs de cambios de estado de expedientes en esta solicitud
        logs = ExpedienteEstadoLog.objects.filter(
            solicitud=s
        ).select_related('usuario', 'estado_anterior', 'estado_nuevo').order_by('fecha')

        logs_data = [{
            "fecha": _fmt_local(l.fecha),
            "accion": f"Exp #{l.expediente_id}: {l.estado_anterior.nombre if l.estado_anterior else '—'} → {l.estado_nuevo.nombre}",
            "usuario": l.usuario.username,
            "observacion": l.observacion or "",
        } for l in logs]

        prestamo = s.prestamos.first()
        # estado del prestamo: traducir id->codigo para el frontend.
        from s_exp.models import EstadoPrestamo
        return JsonResponse({"data": {
            "id": s.id,
            "usuario": DatosSolicitud.usuario_username(s),
            "usuario_nombre": DatosSolicitud.usuario_nombre_completo(s),
            "fecha_creacion": _fmt_local(s.fecha_creacion),
            "estado_flujo": DatosSolicitud.estado_codigo(s),
            "estado_flujo_nombre": DatosSolicitud.estado_nombre(s),
            "motivo": DatosSolicitud.motivo_nombre(s),
            "area_destino": DatosSolicitud.unidad_nombre(s),
            "expedientes": expedientes_data,
            "logs": logs_data,
            "prestamo": {"id": prestamo.id, "estado": EstadoPrestamo.codigo_de(prestamo.estado_id)} if prestamo else None,
        }})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)
    except Exception as e:
        log_error(f"Error en historial_solicitud_detalle_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
