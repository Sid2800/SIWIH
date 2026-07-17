"""
prestamos.py - APIs de monitoreo y entrega de prestamos.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import json
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


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


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
            estado_id__in=EstadoPrestamo.ids_de(['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido'])
        )

        if estado_filtro:
            # estado_filtro es el CÓDIGO que envían los botones del front.
            # Se traduce a id (id_de_seguro devuelve None si no existe) para
            # filtrar por la FK entera en vez de hacer JOIN y comparar texto.
            # Si el código no existe, no se devuelve nada: mismo resultado que
            # antes con un valor invalido, pero sin lanzar error.
            _id_estado = EstadoPrestamo.id_de_seguro(estado_filtro)
            qs = qs.filter(estado_id=_id_estado) if _id_estado else qs.none()

        if search_value:
            qs = qs.filter(
                Q(solicitud__usuario__username__icontains=search_value) |
                Q(id__icontains=search_value) |
                Q(solicitud__usuario__first_name__icontains=search_value) |
                Q(solicitud__usuario__last_name__icontains=search_value)
            )

        total_records = Prestamo.objects.filter(
            estado_id__in=EstadoPrestamo.ids_de(['Activo', 'Entregado', 'Vencido', 'DevolucionParcial', 'DevueltoVencido'])
        ).count()
        filtered_records = qs.count()

        prestamos = qs.order_by('-fecha_aprobacion')[start:start + length]

        data = []
        for p in prestamos:
            # Detalles ENRIQUECIDOS (no solo el número): el monitoreo necesita el
            # estado de cada expediente (devuelto / pendiente / fuera de tiempo /
            # préstamo pendiente) para poder colorear cada tag. Antes se enviaba
            # solo values_list(numero), por eso todos salían sin color.
            from s_exp.services.datos_solicitud import DatosSolicitud, DatosDetalleSolicitud
            numeros = [
                DatosDetalleSolicitud.enriquecer(d)
                for d in p.solicitud.detalles.select_related(
                    'expediente_prestamo__expediente', 'paciente'
                ).filter(aprobado=True)
            ]
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
        log_error(f"Error en prestamos_activos_api: {e}", app=LogApp.S_EXP)
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
        prestamo = Prestamo.objects.get(id=prestamo_id, estado_id=EstadoPrestamo.id_de('Activo'))
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
            log_warning(f"No se pudo resolver ubicacion del solicitante: {_e}", app=LogApp.S_EXP)

        # Solo marcar como prestados los expedientes aprobados.
        # Se EXCLUYEN los marcados como "préstamo pendiente" (prestamo_pendiente=True):
        # esos se encontraron pero no se entregan ahora, así que conservan su estado
        # EXP_PENDIENTE_PRESTAMO (reservados) aunque el resto de la solicitud ya se
        # haya entregado. Se liberan luego con "Entregar pendientes" o "Cancelar pendientes".
        for d in prestamo.solicitud.detalles.select_related(
            'expediente_prestamo__expediente'
        ).filter(aprobado=True, prestamo_pendiente=False):
            estado_anterior = d.expediente_prestamo.estado
            d.expediente_prestamo.estado_id = EstadoExpedienteFisico.id_de('EXP_PRESTADO')

            # Hora de entrega POR expediente (los pendientes se sellarán luego,
            # cuando se ejecute "Entregar pendientes").
            d.fecha_entrega = ahora
            d.save(update_fields=['fecha_entrega'])

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
                log_warning(f"No se pudo actualizar ubicacion/localizacion al entregar: {_e}", app=LogApp.S_EXP)

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

        log_info(f"Préstamo #{prestamo.id} entregado por {request.user.username}", app=LogApp.S_EXP)
        return JsonResponse({
            "success": True,
            "fecha_entrega": _fmt_local(ahora),  # 12h local
            "fecha_limite": prestamo.fecha_limite.isoformat(),
        })

    except Exception as e:
        log_error(f"Error en marcar_entregado_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================================================
# APIs ADMIN - Préstamos PENDIENTES (estado EXP_PENDIENTE_PRESTAMO)
# ----------------------------------------------------------------------------
# Origen del flujo: en la "Revisión de Entrega" el admin marca un expediente
# como "préstamo pendiente" (lo encontró, pero no se entrega todavía). Ese
# expediente queda RESERVADO y NO se entrega junto con el resto de la solicitud
# (marcar_entregado_api lo excluye). Queda pendiente indefinidamente hasta que
# el admin ejecute una de estas dos acciones:
#   - entregar_pendientes_api  -> pasa a EXP_PRESTADO (se entrega de verdad).
#   - cancelar_pendientes_api  -> pasa a EXP_DISPONIBLE (se libera, no se presta).
# Los botones de ambas acciones solo aparecen una vez entregada la solicitud.
# ============================================================================

def _resolver_pendientes(request, accion):
    """
    Helper común de "Entregar pendientes" / "Cancelar pendientes".

    Ambas acciones recorren los mismos detalles (prestamo_pendiente=True) y solo
    difieren en el estado destino y los efectos, por eso comparten el cuerpo:

      - accion='entregar': EXP_PRESTADO + se mueve la ubicación a la unidad del
        solicitante (igual que la entrega normal). El expediente queda prestado.
      - accion='cancelar':  EXP_DISPONIBLE + el detalle queda aprobado=False con
        su motivo, de modo que el PDF lo muestre como NO PRESTADO y el
        expediente vuelva a estar disponible para otros. Exige un comentario
        que JUSTIFIQUE la cancelación (ver abajo).

    Todo va dentro de una transacción: o se resuelven todos los pendientes de la
    solicitud o no se toca ninguno (evita dejar expedientes a medio liberar).
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    # Opcional: lista de detalle_id concretos. Si no viene, se resuelven todos
    # los pendientes de la solicitud.
    detalle_ids = body.get('detalle_ids') or None
    # Justificación de la CANCELACIÓN. Es un comentario NUEVO y distinto de
    # detalle.comentario_pendiente: aquel explicaba por qué el expediente quedó
    # pendiente; este explica por qué finalmente NO se presta. Por eso es
    # obligatorio al cancelar (al entregar no aplica: el pendiente se cumple).
    comentario = (body.get('comentario') or '').strip()
    if accion == 'cancelar' and not comentario:
        return JsonResponse(
            {"error": "Debe justificar la cancelación con un comentario."}, status=400
        )

    from django.db import transaction
    from s_exp.models import SolicitudPrestamo

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id)
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)

    qs = solicitud.detalles.select_related('expediente_prestamo__expediente').filter(
        prestamo_pendiente=True, aprobado=True
    )
    if detalle_ids:
        qs = qs.filter(id__in=detalle_ids)

    pendientes = list(qs)
    if not pendientes:
        return JsonResponse({"error": "No hay préstamos pendientes por resolver"}, status=400)

    # Para 'entregar' se necesita la ubicación destino (unidad del solicitante),
    # se resuelve UNA sola vez fuera del loop para no repetir consultas.
    ubicacion_destino = None
    if accion == 'entregar':
        from expediente.services.ubicaciones import CatalogoUbicaciones
        try:
            ubicacion_destino = CatalogoUbicaciones.ubicacion_del_solicitante(solicitud)
        except Exception as _e:
            log_warning(f"No se pudo resolver ubicacion del solicitante: {_e}", app=LogApp.S_EXP)

    estado_destino = (
        EstadoExpedienteFisico.id_de('EXP_PRESTADO') if accion == 'entregar'
        else EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
    )

    ahora = timezone.now()

    with transaction.atomic():
        for d in pendientes:
            ep = d.expediente_prestamo
            estado_ant = ep.estado
            ep.estado_id = estado_destino

            if accion == 'entregar':
                # Se entrega de verdad: el expediente viaja a la unidad solicitante.
                # Se sella SU hora de entrega (distinta a la del resto de la
                # solicitud, que se entregó antes).
                d.fecha_entrega = ahora
                if ubicacion_destino is not None:
                    ep.ubicacion = ubicacion_destino
                ep.save()
                try:
                    _set_localizacion_por_solicitud(
                        ep.expediente, solicitud, request.user,
                        ubicacion_obj=ubicacion_destino,
                    )
                except Exception as _e:
                    log_warning(f"No se pudo actualizar ubicacion al entregar pendiente: {_e}",
                                app=LogApp.S_EXP)
                observacion = f"Préstamo pendiente entregado: {d.comentario_pendiente or ''}".strip()
            else:
                # Se cancela: el expediente vuelve a estar disponible y el detalle
                # queda como NO prestado, con la JUSTIFICACIÓN de la cancelación
                # (no con el comentario del pendiente) para el PDF/historial.
                ep.save()
                d.aprobado = False
                d.motivo_rechazo_individual = comentario
                # En la bitácora se conservan AMBOS motivos: por qué había quedado
                # pendiente y por qué se canceló. Así no se pierde el contexto al
                # limpiar comentario_pendiente más abajo.
                motivo_previo = d.comentario_pendiente or '—'
                observacion = (
                    f"Préstamo pendiente cancelado: {comentario} "
                    f"(quedó pendiente por: {motivo_previo})"
                )

            # En ambos casos deja de estar pendiente.
            d.prestamo_pendiente = False
            d.comentario_pendiente = None
            d.save()

            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=estado_ant,
                estado_nuevo_id=estado_destino,
                usuario=request.user,
                solicitud=solicitud,
                observacion=observacion,
            )

    _registrar_log(
        request.user,
        'PRESTAMO_PENDIENTE_ENTREGADO' if accion == 'entregar' else 'PRESTAMO_PENDIENTE_CANCELADO',
        f'{len(pendientes)} préstamo(s) pendiente(s) '
        f'{"entregado(s)" if accion == "entregar" else "cancelado(s)"} '
        f'en la solicitud #{solicitud.id}.'
        + (f' Motivo: {comentario}' if accion == 'cancelar' else ''),
        'SolicitudPrestamo', solicitud.id
    )
    return JsonResponse({"success": True, "resueltos": len(pendientes)})


@csrf_protect
@require_POST
def entregar_pendientes_api(request):
    """Entrega los expedientes que quedaron como 'préstamo pendiente'."""
    try:
        return _resolver_pendientes(request, 'entregar')
    except Exception as e:
        log_error(f"Error en entregar_pendientes_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def cancelar_pendientes_api(request):
    """Cancela los 'préstamos pendientes': libera los expedientes (quedan disponibles)."""
    try:
        return _resolver_pendientes(request, 'cancelar')
    except Exception as e:
        log_error(f"Error en cancelar_pendientes_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
