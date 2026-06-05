"""
prestamos.py - APIs de monitoreo y entrega de prestamos.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import json
import logging
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect

from django.db.models import Q

from s_exp.models import Prestamo, ExpedienteEstadoLog


from .comunes import (
    _es_exp_admin,
    _fmt_local,
    _registrar_log,
    _set_localizacion_por_solicitud,
)


from s_exp.models import EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo, EstadoDevolucion


logger = logging.getLogger("s_exp")


# ============================================
# APIs ADMIN - Monitoreo de Préstamos
# ============================================

@require_GET
def prestamos_activos_api(request):
    """Lista préstamos activos/entregados para monitoreo con DataTables server-side."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 10))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        qs = Prestamo.objects.select_related(
            'solicitud__usuario', 'solicitud__motivo', 'solicitud__servicio_unidad'
        ).filter(
            estado__codigo__in=['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido']
        )

        if estado_filtro:
            qs = qs.filter(estado=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(solicitud__usuario__username__icontains=search_value) |
                Q(id__icontains=search_value) |
                Q(solicitud__usuario__first_name__icontains=search_value) |
                Q(solicitud__usuario__last_name__icontains=search_value)
            )

        total_records = Prestamo.objects.filter(
            estado__codigo__in=['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido']
        ).count()
        filtered_records = qs.count()

        prestamos = qs.order_by('-fecha_aprobacion')[start:start + length]

        data = []
        for p in prestamos:
            numeros = list(
                p.solicitud.detalles.select_related('expediente_prestamo__expediente')
                .filter(aprobado=True)
                .values_list('expediente_prestamo__expediente__numero', flat=True)
            )

            # Usamos los servicios para evitar acceso directo a snapshots
            from s_exp.services.datos_solicitud import DatosSolicitud
            data.append({
                "id": p.id,
                "solicitud_id": p.solicitud.id,
                "usuario": DatosSolicitud.usuario_username(p.solicitud),
                "usuario_nombre": DatosSolicitud.usuario_nombre_completo(p.solicitud),
                # 'area_destino' es alias retrocompat — el valor viene de la unidad FK
                "area_destino": DatosSolicitud.unidad_nombre(p.solicitud),
                "unidad": DatosSolicitud.unidad_nombre(p.solicitud),
                "unidad_id": DatosSolicitud.unidad_id(p.solicitud),
                "motivo": DatosSolicitud.motivo_nombre(p.solicitud),
                "estado": EstadoPrestamo.codigo_de(p.estado_id),
                "fecha_aprobacion": _fmt_local(p.fecha_aprobacion),
                "fecha_entrega": _fmt_local(p.fecha_entrega) or None,
                "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                "tiempo_limite_horas": p.tiempo_limite_horas,
                "tiempo_restante_segundos": p.tiempo_restante_segundos,
                "porcentaje_tiempo_usado": p.porcentaje_tiempo_usado,
                "esta_vencido": p.esta_vencido,
                "expedientes": numeros,
                "cant_expedientes": len(numeros),
                "solicitud_estado_flujo": EstadoSolicitud.codigo_de(p.solicitud.estado_flujo_id),
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data
        })

    except Exception as e:
        logger.error(f"Error en prestamos_activos_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def marcar_entregado_api(request):
    """Marca un préstamo como entregado e inicia el cronómetro."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    prestamo_id = body.get('prestamo_id')

    try:
        prestamo = Prestamo.objects.get(id=prestamo_id, estado__codigo='Activo')
        if prestamo.solicitud.estado_flujo_id != EstadoSolicitud.id_de('SOL_LISTO_RECOGER'):
             return JsonResponse({"error": "La solicitud debe estar marcada como 'Listo para recoger' antes de entregar."}, status=400)
    except Prestamo.DoesNotExist:
        return JsonResponse({"error": "Préstamo no encontrado o no está en estado Activo"}, status=404)

    try:
        ahora = timezone.now()
        prestamo.fecha_entrega = ahora

        # Lógica de vencimiento flexible (Pruebas vs Producción)
        if prestamo.es_minutos:
            # Si el préstamo se configuró en minutos (para pruebas)
            prestamo.fecha_limite = ahora + timedelta(minutes=prestamo.tiempo_limite_horas)
        else:
            # Configuración estándar en horas
            prestamo.fecha_limite = ahora + timedelta(hours=prestamo.tiempo_limite_horas)

        prestamo.estado_id = EstadoPrestamo.id_de('Entregado')
        prestamo.save()

        prestamo.solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_EN_PRESTAMO')
        prestamo.solicitud.save()

        # Resolver UNA sola vez la ubicación destino del préstamo (Opción A):
        # el expediente se mueve a la unidad del SOLICITANTE (catálogo nuevo).
        from expediente.services.ubicaciones import CatalogoUbicaciones
        ubicacion_destino = None
        try:
            ubicacion_destino = CatalogoUbicaciones.ubicacion_del_solicitante(prestamo.solicitud)
        except Exception as _e:
            logger.warning(f"No se pudo resolver ubicacion del solicitante: {_e}")

        # Solo marcar como prestados los expedientes aprobados
        for d in prestamo.solicitud.detalles.select_related('expediente_prestamo__expediente').filter(aprobado=True):
            estado_anterior = d.expediente_prestamo.estado
            d.expediente_prestamo.estado_id = EstadoExpedienteFisico.id_de('EXP_PRESTADO')

            # NUEVO: registrar la ubicación actual via FK al catálogo unificado.
            if ubicacion_destino is not None:
                d.expediente_prestamo.ubicacion = ubicacion_destino

            d.expediente_prestamo.save()

            # Actualizar la ubicación del expediente:
            #  - NUEVO: expediente.ubicacion (FK catálogo unificado) = ubicacion_destino
            #  - LEGACY: expediente.localizacion (texto) sincronizado en la transición
            try:
                _set_localizacion_por_solicitud(
                    d.expediente_prestamo.expediente,
                    prestamo.solicitud,
                    request.user,
                    ubicacion_obj=ubicacion_destino,
                )
            except Exception as _e:
                logger.warning(f"No se pudo actualizar ubicacion/localizacion al entregar: {_e}")

            ExpedienteEstadoLog.objects.create(
                expediente=d.expediente_prestamo.expediente,
                estado_anterior=estado_anterior,
                estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_PRESTADO'),
                usuario=request.user,
                solicitud=prestamo.solicitud
            )

        _registrar_log(
            request.user, 'PRESTAMO_ENTREGADO',
            f'Préstamo #{prestamo.id} entregado. Cronómetro iniciado: {prestamo.tiempo_limite_horas}h.',
            'Prestamo', prestamo.id
        )

        logger.info(f"Préstamo #{prestamo.id} entregado por {request.user.username}")
        return JsonResponse({
            "success": True,
            "fecha_entrega": _fmt_local(ahora),  # 12h local
            "fecha_limite": prestamo.fecha_limite.isoformat(),
        })

    except Exception as e:
        logger.error(f"Error en marcar_entregado_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
