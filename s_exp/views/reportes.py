"""
reportes.py - APIs de datos de reportes y exportacion (delegan en servicios).

Parte del paquete s_exp.views (antes views.py monolitico).
"""


from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from django.db.models import Count, F, Q

from s_exp.models import (
    SolicitudPrestamo, SolicitudExpedienteDetalle, Prestamo,
    EstadoSolicitud, EstadoPrestamo,
)


# Servicio de exportacion de reportes (Excel/PDF). Se importa con alias para
# mantener las vistas delgadas sin chocar con los nombres publicos de las vistas.
from s_exp.services.reporte_export_service import (
    exportar_reporte_excel as _reporte_export_excel,
    exportar_reporte_pdf as _reporte_export_pdf,
)


from .comunes import (
    _es_exp_admin,
    _fmt_local,
)


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


# ============================================
# APIs - Reportes

# Techo de las tablas de detalle (rechazos, morosidad, inconsistencias). Los
# totales del resumen no se cortan; estas listas sí, y la respuesta dice
# cuántas hay para que la pantalla pueda avisarlo.
LIMITE_FILAS_REPORTE = 200

@require_GET
def reportes_data_api(request):
    """Retorna datos completos para los reportes con filtros de fecha.
    Cuenta solicitudes reales (SolicitudPrestamo) en el período seleccionado.
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')

        # Convertir a datetimes tz-aware para evitar RuntimeWarning
        from datetime import datetime, time as _dtime
        dt_ini = dt_fin = None
        if fecha_inicio:
            try:
                dt_ini = timezone.make_aware(
                    datetime.combine(datetime.strptime(fecha_inicio, '%Y-%m-%d').date(), _dtime.min)
                )
            except (ValueError, TypeError):
                dt_ini = None
        if fecha_fin:
            try:
                dt_fin = timezone.make_aware(
                    datetime.combine(datetime.strptime(fecha_fin, '%Y-%m-%d').date(), _dtime.max)
                )
            except (ValueError, TypeError):
                dt_fin = None

        # Filtros base sobre SolicitudPrestamo.fecha_creacion
        sol_filtros = {}
        if dt_ini:
            sol_filtros['fecha_creacion__gte'] = dt_ini
        if dt_fin:
            sol_filtros['fecha_creacion__lte'] = dt_fin

        qs_solicitudes = SolicitudPrestamo.objects.filter(**sol_filtros)

        # --- RESUMEN GENERAL ---
        total_solicitudes = qs_solicitudes.count()
        total_expedientes_solicitados = SolicitudExpedienteDetalle.objects.filter(
            solicitud__in=qs_solicitudes
        ).count()
        total_aprobadas = qs_solicitudes.filter(
            estado_flujo_id__in=EstadoSolicitud.ids_de([
                'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
                'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION',
                'SOL_FINALIZADA', 'SOL_INCOMPLETA',
            ])
        ).count()
        total_rechazadas = qs_solicitudes.filter(
            estado_flujo_id=EstadoSolicitud.id_de('SOL_RECHAZADA')
        ).count()
        total_pendientes = qs_solicitudes.filter(
            estado_flujo_id=EstadoSolicitud.id_de('SOL_PENDIENTE')
        ).count()

        # --- DEMANDA POR ÁREA ---
        # La unidad ahora es relacional (servicio_unidad FK). Agrupamos por el
        # nombre de la unidad consultado en vivo, en lugar del antiguo texto
        # area_destino (eliminado en el refactor relacional).
        # 'total' = nº de solicitudes; 'expedientes' = nº de expedientes pedidos
        # (detalles). Al agrupar y unir con 'detalles', cada solicitud aparece una
        # vez por cada expediente, por eso el conteo de solicitudes va con
        # distinct=True (si no, quedaría inflado); el de detalles sí es directo.
        demanda_area = list(
            qs_solicitudes.values(
                area_destino=F('servicio_unidad__nombre_unidad')
            ).annotate(
                total=Count('id', distinct=True),
                expedientes=Count('detalles')
            ).order_by('-total')
        )

        # --- MOTIVOS DE USO ---
        motivos = list(
            qs_solicitudes.values(nombre=F('motivo__nombre')).annotate(
                total=Count('id', distinct=True),
                expedientes=Count('detalles')
            ).order_by('-total')[:10]
        )

        # --- EXPEDIENTE MÁS SOLICITADO ---
        expedientes_top = list(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__in=qs_solicitudes
            ).values(
                numero=F('expediente_prestamo__expediente__numero')
            ).annotate(
                total=Count('id')
            ).order_by('-total')[:10]
        )

        # --- USUARIOS CON MÁS SOLICITUDES ---
        usuarios_top = list(
            qs_solicitudes.values(
                username=F('usuario__username'),
                nombre_completo=F('usuario__first_name'),
            ).annotate(
                total=Count('id')
            ).order_by('-total')[:10]
        )
        # Construir nombre completo
        for u in usuarios_top:
            u['nombre'] = u.pop('nombre_completo', '') or u['username']

        # --- RECHAZOS CON DETALLE ---
        rechazos_qs = qs_solicitudes.filter(
            estado_flujo_id=EstadoSolicitud.id_de('SOL_RECHAZADA')
        )
        rechazos_total = rechazos_qs.count()
        # select_related de 'prestamo' (inverso uno-a-uno): antes era una
        # consulta por rechazo.
        rechazos = []
        for s in rechazos_qs.select_related('usuario', 'prestamo')[:LIMITE_FILAS_REPORTE]:
            try:
                motivo_r = s.prestamo.motivo_rechazo or ""
            except Prestamo.DoesNotExist:
                motivo_r = ""
            rechazos.append({
                "solicitud_id": s.id,
                "usuario": s.usuario.username,
                "fecha": _fmt_local(s.fecha_creacion),
                "motivo_rechazo": motivo_r,
            })

        # --- MOROSIDAD (préstamos vencidos activos) ---
        ahora = timezone.now()
        filtros_prestamo = {}
        if dt_ini:
            filtros_prestamo['fecha_aprobacion__gte'] = dt_ini
        if dt_fin:
            filtros_prestamo['fecha_aprobacion__lte'] = dt_fin

        morosos = Prestamo.objects.filter(
            estado_id__in=EstadoPrestamo.ids_de(['Entregado', 'Vencido']),
            fecha_limite__lt=ahora,
            **filtros_prestamo
        ).select_related('solicitud__usuario', 'solicitud__servicio_unidad')
        morosidad_total = morosos.count()
        morosos = morosos.order_by('fecha_limite')[:LIMITE_FILAS_REPORTE]

        from s_exp.services.datos_solicitud import DatosSolicitud
        morosidad = []
        for p in morosos:
            morosidad.append({
                "prestamo_id": p.id,
                "usuario": DatosSolicitud.usuario_username(p.solicitud),
                # 'area' viene de la FK unidad (deprecado area_destino texto)
                "area": DatosSolicitud.unidad_nombre(p.solicitud),
                "fecha_limite": _fmt_local(p.fecha_limite),
                "dias_vencido": (ahora - p.fecha_limite).days if p.fecha_limite else 0,
            })

        # --- INCONSISTENCIAS (devoluciones parciales) ---
        # Se cuenta sobre el estado real de cada expediente. Antes se sumaba
        # cantidad_recibida de todas las Devolucion, pero cada una guarda el
        # acumulado de su auditoría: dos tandas de 1 y 2 sumaban 3 y el reporte
        # decía "0 faltantes" cuando faltaba uno. Y el total contaba también
        # los expedientes no aprobados, que nunca salieron del archivo.
        parciales = Prestamo.objects.filter(
            estado_id=EstadoPrestamo.id_de('DevolucionParcial'),
            **filtros_prestamo
        )
        inconsistencias_total = parciales.count()
        parciales = parciales.select_related('solicitud__usuario').annotate(
            n_aprobados=Count('solicitud__detalles', filter=Q(solicitud__detalles__aprobado=True)),
            n_devueltos=Count('solicitud__detalles', filter=Q(
                solicitud__detalles__aprobado=True, solicitud__detalles__devuelto=True
            )),
        ).order_by('id')[:LIMITE_FILAS_REPORTE]

        inconsistencias = []
        for p in parciales:
            total_exp = p.n_aprobados
            devueltos = p.n_devueltos
            inconsistencias.append({
                "prestamo_id": p.id,
                "usuario": p.solicitud.usuario.username,
                "total_expedientes": total_exp,
                "devueltos": devueltos,
                "faltantes": total_exp - devueltos,
            })

        return JsonResponse({
            "resumen": {
                "total_solicitudes": total_solicitudes,
                "total_expedientes": total_expedientes_solicitados,
                "aprobadas": total_aprobadas,
                "rechazadas": total_rechazadas,
                "pendientes": total_pendientes,
            },
            "demanda_area": demanda_area,
            "motivos": motivos,
            "expedientes_top": expedientes_top,
            "usuarios_top": usuarios_top,
            "rechazos": rechazos,
            "morosidad": morosidad,
            "inconsistencias": inconsistencias,
            "rechazos_total": rechazos_total,
            "morosidad_total": morosidad_total,
            "inconsistencias_total": inconsistencias_total,
        })

    except Exception as e:
        log_error(f"Error en reportes_data_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# EXPORTACION DE REPORTES
# --------------------------------------------
# La logica pesada de armado de Excel/PDF vive en
# s_exp.services.reporte_export_service. Aqui solo quedan vistas delgadas
# que delegan en el servicio (urls.py sigue apuntando a estos nombres).
# ============================================
def exportar_reporte_excel(request):
    """Vista delgada: delega en el servicio de exportacion (Excel)."""
    return _reporte_export_excel(request)


def exportar_reporte_pdf(request):
    """Vista delgada: delega en el servicio de exportacion (PDF)."""
    return _reporte_export_pdf(request)
