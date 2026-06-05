"""
solicitudes.py - APIs del ciclo de vida de las solicitudes de expedientes.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import json
import logging
from datetime import timedelta

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect

from django.db.models import Count, Q

from s_exp.models import MotivoSolicitud, ExpedientePrestamo, SolicitudPrestamo, SolicitudExpedienteDetalle, Prestamo, ExpedienteEstadoLog
from expediente.models import Expediente, PacienteAsignacion


from .comunes import (
    _es_exp_admin,
    _es_exp_solicitante,
    _fmt_local,
    _get_servicio_unidad_from_rrhh,
    _registrar_log,
)


from s_exp.models import EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo, EstadoDevolucion


logger = logging.getLogger("s_exp")


# ============================================
# APIs ADMIN - Gestión de Solicitudes
# ============================================

@require_GET
def listar_solicitudes_api(request):
    """
    API para alimentar el DataTable de gestión de solicitudes (Admin).
    Soporta filtrado por estado y búsqueda server-side.
    """
    """Lista solicitudes para el admin (DataTables server-side)."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        draw = int(request.GET.get('draw', 0))
        start = int(request.GET.get('start', 0))
        length = int(request.GET.get('length', 20))
        search_value = request.GET.get('search[value]', '').strip()
        estado_filtro = request.GET.get('estado', '')

        # Optimizamos joins para reducir queries N+1: traemos en una sola consulta
        # todas las relaciones necesarias para construir la respuesta.
        qs = SolicitudPrestamo.objects.select_related(
            'usuario', 'servicio_unidad', 'motivo', 'estado_flujo'
        ).annotate(cant_expedientes=Count('detalles'))

        if estado_filtro:
            qs = qs.filter(estado_flujo__codigo=estado_filtro)

        if search_value:
            qs = qs.filter(
                Q(usuario__username__icontains=search_value) |
                Q(motivo__nombre__icontains=search_value) |
                Q(id__icontains=search_value)
            )

        total_records = SolicitudPrestamo.objects.count()
        filtered_records = qs.count()

        solicitudes = qs.order_by('-fecha_creacion')[start:start + length]

        # Importamos los servicios de acceso a datos.
        # Toda la lectura de DNI/nombre/etc. pasa por aquí, NO se accede a
        # campos snapshot deprecados directamente.
        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        data = []
        for s in solicitudes:
            # Cada detalle se enriquece con datos vivos del paciente/expediente
            detalles_info = []
            for d in s.detalles.select_related(
                'expediente_prestamo__expediente', 'paciente'
            ):
                info = DatosDetalleSolicitud.enriquecer(d)
                detalles_info.append(info)

            prestamo_id = None
            try:
                prestamo_id = s.prestamo.id
            except Exception:
                prestamo_id = None

            # Construimos el dict de respuesta usando los servicios
            data.append({
                "id": s.id,
                "prestamo_id": prestamo_id,
                "usuario": DatosSolicitud.usuario_username(s),
                "usuario_nombre": DatosSolicitud.usuario_nombre_completo(s),
                "fecha_creacion": _fmt_local(s.fecha_creacion),
                "estado_flujo": DatosSolicitud.estado_codigo(s),
                "estado_flujo_nombre": DatosSolicitud.estado_nombre(s),
                "motivo": DatosSolicitud.motivo_nombre(s),
                "observaciones": s.observaciones or "",
                # 'unidad' reemplaza tanto area_destino como servicio_unidad antiguos
                "unidad": DatosSolicitud.unidad_nombre(s),
                "unidad_id": DatosSolicitud.unidad_id(s),
                # Mantenemos 'area_destino' como alias para compatibilidad con
                # frontend existente que aún lee ese key (se removerá luego).
                "area_destino": DatosSolicitud.unidad_nombre(s),
                "cant_expedientes": s.cant_expedientes,
                "expedientes": detalles_info,
                "tiempo_sugerido_horas": s.tiempo_sugerido_horas,
            })

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": data,
        })
    except Exception as e:
        logger.error(f"Error en listar_solicitudes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def aprobar_solicitud_api(request):
    """
    Aprueba una solicitud y crea el préstamo.
    Soporta decisiones individuales por expediente (aprobado/rechazado).
    Si todos los expedientes son rechazados, la solicitud pasa a SOL_RECHAZADA.
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    tiempo_limite = body.get('tiempo_limite_horas', 24)
    es_minutos = body.get('es_minutos', False)
    expedientes_decisiones = body.get('expedientes_decisiones', [])

    if int(tiempo_limite) < 1:
        return JsonResponse({"error": "El tiempo debe ser mayor a 0"}, status=400)

    # Validar tope de 72 horas cuando no es modo minutos (el frontend ya convierte días a horas)
    if not es_minutos and int(tiempo_limite) > 72:
        return JsonResponse({"error": "El tiempo máximo de préstamo es 72 horas (3 días)"}, status=400)

    # Mapa de decisiones: {detalle_id: {aprobado, observaciones}}
    mapa_decisiones = {}
    for d in expedientes_decisiones:
        det_id = d.get('detalle_id')
        if det_id is None:
            continue
        aprobado = d.get('aprobado', True)
        mapa_decisiones[det_id] = {
            'aprobado': aprobado,
            'observaciones': (d.get('observaciones') or '').strip(),
        }

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo__codigo='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        detalles = list(solicitud.detalles.select_related('expediente_prestamo__expediente'))

        # Verificar que los expedientes aprobados estén disponibles
        for d in detalles:
            info = mapa_decisiones.get(d.id, {'aprobado': True, 'observaciones': ''})
            if info['aprobado'] and d.expediente_prestamo.estado_id == EstadoExpedienteFisico.id_de('EXP_PRESTADO'):
                return JsonResponse({
                    "error": f"El expediente #{d.expediente_prestamo.expediente.numero} ya no está disponible"
                }, status=400)

        # Aplicar decisiones por expediente
        aprobados = []
        rechazados = []
        for d in detalles:
            info = mapa_decisiones.get(d.id, {'aprobado': True, 'observaciones': ''})
            d.aprobado = info['aprobado']
            # Guardar SIEMPRE las observaciones (tanto aprobados como rechazados pueden tenerlas)
            d.motivo_rechazo_individual = info['observaciones'] or None
            if info['aprobado']:
                aprobados.append(d)
            else:
                rechazados.append(d)
            d.save()

        # Texto motivo general: usamos las primeras observaciones de rechazados (para Prestamo.motivo_rechazo si aplica)
        motivo_rechazo_general = " | ".join(
            f"#{d.expediente_prestamo.expediente.numero}: {d.motivo_rechazo_individual}"
            for d in rechazados if d.motivo_rechazo_individual
        )

        todos_rechazados = len(aprobados) == 0

        if todos_rechazados:
            # Rechazar toda la solicitud
            solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_RECHAZADA')
            solicitud.save()

            for d in rechazados:
                ep = d.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
                ep.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion=f"Liberado: todos los expedientes rechazados. Motivo: {motivo_rechazo_general}"
                )

            Prestamo.objects.create(
                solicitud=solicitud,
                admin_aprobador=request.user,
                motivo_rechazo=motivo_rechazo_general,
                estado_id=EstadoPrestamo.id_de('Cerrado')
            )

            _registrar_log(
                request.user, 'SOLICITUD_RECHAZADA',
                f'Solicitud #{solicitud.id} rechazada (todos los expedientes rechazados individualmente). Motivo: {motivo_rechazo_general}',
                'SolicitudPrestamo', solicitud.id
            )
            return JsonResponse({"success": True, "todos_rechazados": True})

        # Al menos un expediente aprobado: continuar con la solicitud
        solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_APROBADA_ORGANIZANDO')
        solicitud.save()

        # Aprobados → EXP_APARTADO
        for d in aprobados:
            if d.expediente_prestamo.estado_id != EstadoExpedienteFisico.id_de('EXP_APARTADO'):
                estado_ant = d.expediente_prestamo.estado
                d.expediente_prestamo.estado_id = EstadoExpedienteFisico.id_de('EXP_APARTADO')
                d.expediente_prestamo.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=d.expediente_prestamo.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_APARTADO'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Apartado al aprobar solicitud"
                )

        # Rechazados → EXP_DISPONIBLE
        for d in rechazados:
            ep = d.expediente_prestamo
            estado_ant = ep.estado
            ep.estado_id = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
            ep.save()
            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=estado_ant,
                estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'),
                usuario=request.user,
                solicitud=solicitud,
                observacion=f"No se prestará en esta solicitud. Motivo: {motivo_rechazo_general}"
            )

        prestamo = Prestamo.objects.create(
            solicitud=solicitud,
            admin_aprobador=request.user,
            tiempo_limite_horas=int(tiempo_limite),
            es_minutos=es_minutos,
            estado_id=EstadoPrestamo.id_de('Activo')
        )

        detalle_rechazo = f" ({len(rechazados)} expediente(s) rechazado(s))" if rechazados else ""
        _registrar_log(
            request.user, 'SOLICITUD_APROBADA',
            f'Solicitud #{solicitud.id} aprobada{detalle_rechazo}. En proceso de organización.',
            'Prestamo', prestamo.id
        )

        logger.info(f"Solicitud #{solicitud.id} aprobada por {request.user.username}")
        return JsonResponse({"success": True, "todos_rechazados": False, "prestamo_id": prestamo.id})

    except Exception as e:
        logger.error(f"Error en aprobar_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def expedientes_revision_api(request, solicitud_id):
    """Retorna los expedientes APROBADOS de una solicitud en revisión (estado SOL_APROBADA_ORGANIZANDO)."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        solicitud = SolicitudPrestamo.objects.get(
            id=solicitud_id, estado_flujo__codigo='SOL_APROBADA_ORGANIZANDO'
        )
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en revisión"}, status=404)

    from s_exp.services.datos_solicitud import DatosDetalleSolicitud

    expedientes = []
    for d in solicitud.detalles.select_related(
        'expediente_prestamo__expediente', 'paciente'
    ).filter(aprobado=True):
        expedientes.append({
            "detalle_id": d.id,
            "numero": DatosDetalleSolicitud.numero_expediente(d),
            "paciente_id": DatosDetalleSolicitud.paciente_id(d),
            "paciente_nombre": DatosDetalleSolicitud.paciente_nombre_completo(d),
            "paciente_identidad": DatosDetalleSolicitud.paciente_dni(d),
        })
    return JsonResponse({"expedientes": expedientes})


@require_GET
def expedientes_solicitud_api(request, solicitud_id):
    """Retorna los expedientes de una solicitud pendiente para el modal de aprobación."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo__codigo='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        # Importamos los servicios — sin acceso directo a snapshots
        from s_exp.services.datos_solicitud import DatosDetalleSolicitud

        expedientes = []
        for d in solicitud.detalles.select_related(
            'expediente_prestamo__expediente', 'paciente'
        ):
            expedientes.append({
                "detalle_id": d.id,
                "numero": DatosDetalleSolicitud.numero_expediente(d),
                "paciente_id": DatosDetalleSolicitud.paciente_id(d),
                "paciente_nombre": DatosDetalleSolicitud.paciente_nombre_completo(d),
                "paciente_identidad": DatosDetalleSolicitud.paciente_dni(d),
                "estado_fisico": EstadoExpedienteFisico.codigo_de(d.expediente_prestamo.estado_id),
            })
        return JsonResponse({
            "expedientes": expedientes,
            "tiempo_sugerido_horas": solicitud.tiempo_sugerido_horas,
            "motivo": solicitud.motivo.nombre if solicitud.motivo_id else "",
        })
    except Exception as e:
        logger.error(f"Error en expedientes_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@require_GET
def imprimir_solicitud_pdf(request, solicitud_id):
    """Genera y descarga el PDF de una solicitud (aprobada/organizando/listo/prestamo/devolucion/finalizada)."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    estados_permitidos = {
        'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
        'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION',
        'SOL_FINALIZADA', 'SOL_INCOMPLETA',
    }
    try:
        solicitud = SolicitudPrestamo.objects.select_related(
            'usuario', 'motivo', 'prestamo', 'prestamo__admin_aprobador'
        ).get(id=solicitud_id)
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)

    if EstadoSolicitud.codigo_de(solicitud.estado_flujo_id) not in estados_permitidos:
        return JsonResponse({"error": "La solicitud no está en un estado imprimible"}, status=400)

    try:
        from s_exp.services.pdf_solicitud_service import generar_pdf_solicitud
        # Pasamos el admin actual como respaldo de la firma de entrega cuando
        # la solicitud aún no tiene admin_aprobador (organizando/sin préstamo).
        pdf_bytes = generar_pdf_solicitud(solicitud, admin_actual=request.user)
    except Exception as e:
        logger.error(f"Error generando PDF solicitud {solicitud_id}: {e}", exc_info=True)
        return JsonResponse({"error": "Error al generar el PDF"}, status=500)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    tz = timezone.get_current_timezone()
    ts = timezone.now().astimezone(tz).strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'inline; filename="solicitud_{solicitud.id}_{ts}.pdf"'
    return response


@csrf_protect
@csrf_protect
@require_POST
def revisar_entrega_api(request):
    """
    Revisión de Entrega — el admin verifica físicamente cada expediente antes de marcar listo.
    Permite desmarcar expedientes que no se encontraron físicamente y registrar comentario por expediente.
    Los desmarcados pasan a EXP_DISPONIBLE y quedan con aprobado=False + motivo_rechazo_individual.
    No cambia el estado de la solicitud (sigue en SOL_APROBADA_ORGANIZANDO).
    """
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    decisiones = body.get('decisiones', [])

    try:
        solicitud = SolicitudPrestamo.objects.get(
            id=solicitud_id, estado_flujo__codigo='SOL_APROBADA_ORGANIZANDO'
        )
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en revisión"}, status=404)

    try:
        mapa = {d.get('detalle_id'): d for d in decisiones if d.get('detalle_id') is not None}
        cambios = 0
        for d in solicitud.detalles.select_related('expediente_prestamo__expediente'):
            info = mapa.get(d.id)
            if info is None:
                continue
            encontrado = bool(info.get('encontrado', True))
            comentario = (info.get('comentario') or '').strip()

            if not encontrado and d.aprobado:
                # Marcado como no encontrado físicamente
                d.aprobado = False
                d.motivo_rechazo_individual = comentario or 'No encontrado físicamente'
                d.save()

                ep = d.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
                ep.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion=f"Revisión de entrega: {d.motivo_rechazo_individual}"
                )
                cambios += 1
            elif encontrado and comentario and comentario != (d.motivo_rechazo_individual or ''):
                # Sólo actualizar comentario sin cambiar aprobación
                d.motivo_rechazo_individual = comentario
                d.save()
                cambios += 1

        # Si todos los expedientes quedaron rechazados, cerrar la solicitud
        aprobados_restantes = solicitud.detalles.filter(aprobado=True).count()
        if aprobados_restantes == 0:
            solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_RECHAZADA')
            solicitud.save()
            try:
                p = solicitud.prestamo
                p.estado_id = EstadoPrestamo.id_de('Cerrado')
                p.save()
            except Exception:
                pass

        _registrar_log(
            request.user, 'REVISION_ENTREGA',
            f'Revisión de entrega para solicitud #{solicitud.id}: {cambios} cambio(s).',
            'SolicitudPrestamo', solicitud.id
        )
        return JsonResponse({
            "success": True,
            "cambios": cambios,
            "todos_rechazados": aprobados_restantes == 0,
        })
    except Exception as e:
        logger.error(f"Error en revisar_entrega_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def marcar_listo_recojer_api(request):
    """Admin marca que los expedientes ya están organizados físicamente y listos en ventanilla."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')

        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo__codigo='SOL_APROBADA_ORGANIZANDO')
        # Validar que al menos un expediente siga aprobado
        if solicitud.detalles.filter(aprobado=True).count() == 0:
            return JsonResponse({"error": "No hay expedientes aprobados para entregar"}, status=400)
        solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_LISTO_RECOGER')
        solicitud.notificado_listo = False  # Reset para que el sistema dispare la alerta al usuario
        solicitud.save()

        _registrar_log(
            request.user, 'SOLICITUD_LISTA',
            f'Solicitud #{solicitud.id} marcada como lista para recoger.',
            'SolicitudPrestamo', solicitud.id
        )

        return JsonResponse({"success": True})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en proceso de organización"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_listo_recojer_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def rechazar_solicitud_api(request):
    """
    Rechaza una solicitud de préstamo pendiente.
    Libera automáticamente los expedientes que estaban apartados (EXP_APARTADO -> EXP_DISPONIBLE).
    
    Body JSON:
        solicitud_id (int): ID de la solicitud a rechazar.
        motivo (str): Razón del rechazo.
    """
    """Rechaza una solicitud con motivo obligatorio."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    solicitud_id = body.get('solicitud_id')
    motivo_rechazo = body.get('motivo_rechazo', '').strip()

    if not motivo_rechazo:
        return JsonResponse({"error": "El motivo de rechazo es obligatorio"}, status=400)

    try:
        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, estado_flujo__codigo='SOL_PENDIENTE')
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o ya procesada"}, status=404)

    try:
        solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_RECHAZADA')
        solicitud.save()

        # Liberar expedientes: volver a ponerlos disponibles
        for detalle in solicitud.detalles.select_related('expediente_prestamo'):
            ep = detalle.expediente_prestamo
            estado_anterior = ep.estado
            ep.estado_id = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
            ep.save()

            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=estado_anterior,
                estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'),
                usuario=request.user,
                solicitud=solicitud,
                observacion=f"Expediente liberado por rechazo de solicitud. Motivo: {motivo_rechazo}"
            )

        Prestamo.objects.create(
            solicitud=solicitud,
            admin_aprobador=request.user,
            motivo_rechazo=motivo_rechazo,
            estado_id=EstadoPrestamo.id_de('Cerrado')
        )

        _registrar_log(
            request.user, 'SOLICITUD_RECHAZADA',
            f'Solicitud #{solicitud.id} rechazada. Motivo: {motivo_rechazo}',
            'SolicitudPrestamo', solicitud.id
        )

        logger.info(f"Solicitud #{solicitud.id} rechazada por {request.user.username}")
        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"Error en rechazar_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def crear_solicitud_api(request):
    """
    Crea una nueva solicitud de préstamo iniciada por un usuario del sistema.
    Verifica la disponibilidad física de los expedientes antes de permitir la creación.
    Asigna automáticamente la unidad de servicio del usuario desde su registro en RRHH.
    """
    if not _es_exp_solicitante(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    expediente_ids = body.get('expedientes', [])  # lista de expediente IDs (de tabla Expediente)
    motivo_id = body.get('motivo_id')
    observaciones = body.get('observaciones', '').strip()
    tiempo_sugerido_horas = body.get('tiempo_sugerido_horas')

    if not expediente_ids:
        return JsonResponse({"error": "Debe seleccionar al menos un expediente"}, status=400)
    if not motivo_id:
        return JsonResponse({"error": "El motivo es obligatorio"}, status=400)

    # Validar tiempo sugerido (opcional). Mismo día: max horas hasta 4 PM. Días posteriores: max 72h.
    if tiempo_sugerido_horas is not None:
        try:
            tiempo_sugerido_horas = int(tiempo_sugerido_horas)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Tiempo sugerido inválido"}, status=400)
        if tiempo_sugerido_horas < 1:
            return JsonResponse({"error": "El tiempo sugerido debe ser mayor a 0"}, status=400)
        if tiempo_sugerido_horas > 72:
            return JsonResponse({"error": "El tiempo sugerido no puede superar 72 horas"}, status=400)

    # Validar motivo
    try:
        motivo = MotivoSolicitud.objects.get(id=motivo_id, activo=True)
    except MotivoSolicitud.DoesNotExist:
        return JsonResponse({"error": "Motivo no válido"}, status=400)

    # Obtener unidad de servicio desde RRHH (fuente principal)
    servicio_unidad, es_registrado_rrhh = _get_servicio_unidad_from_rrhh(request.user)
    if not es_registrado_rrhh:
        return JsonResponse({
            "error": "El usuario no está registrado en el sistema RRHH (Recursos Humanos). Contacte al administrador."
        }, status=403)

    # Nota: ya no calculamos area_destino como texto. La unidad queda referenciada
    # por FK en `servicio_unidad`. Para mostrar el nombre, los servicios consultan
    # en vivo (ver s_exp/services/datos_solicitud.py → DatosSolicitud.unidad_nombre).

    try:

        # Verificar que existan y no estén prestados o en proceso
        prestados = set(
            ExpedientePrestamo.objects.filter(estado__codigo='EXP_PRESTADO')
            .values_list('expediente_id', flat=True)
        )
        en_proceso = set(
            SolicitudExpedienteDetalle.objects.filter(
                solicitud__estado_flujo__codigo__in=['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO'],
                aprobado=True,
            ).values_list('expediente_prestamo__expediente_id', flat=True)
        )
        expedientes_prestados_ids = prestados | en_proceso

        expedientes = Expediente.objects.filter(id__in=expediente_ids)
        if expedientes.count() != len(expediente_ids):
            return JsonResponse({"error": "Algunos expedientes no fueron encontrados"}, status=400)

        for exp in expedientes:
            if exp.id in expedientes_prestados_ids:
                return JsonResponse({
                    "error": f"El expediente #{exp.numero} ya no está disponible"
                }, status=400)

        # Crear solicitud (sin snapshots de texto; solo referencia FK)
        solicitud = SolicitudPrestamo.objects.create(
            usuario=request.user,
            motivo=motivo,
            estado_flujo_id=EstadoSolicitud.id_de('SOL_PENDIENTE'),
            observaciones=observaciones or None,
            servicio_unidad=servicio_unidad,  # ubicación del solicitante (FK a servicio.Unidad)
            tiempo_sugerido_horas=tiempo_sugerido_horas,
        )

        # Crear detalles guardando SOLO el paciente_id (FK).
        # Los datos del paciente (DNI/nombre) se consultan en vivo cuando se
        # muestran, usando DatosDetalleSolicitud.
        for exp in expedientes:
            # Obtener o crear ExpedientePrestamo (estado físico actual)
            ep, created_ep = ExpedientePrestamo.objects.get_or_create(
                expediente=exp,
                defaults={'estado_id': EstadoExpedienteFisico.id_de('EXP_APARTADO')}
            )
            if not created_ep:
                estado_anterior = ep.estado
                ep.estado_id = EstadoExpedienteFisico.id_de('EXP_APARTADO')
                ep.save()
                ExpedienteEstadoLog.objects.create(
                    expediente=exp,
                    estado_anterior=estado_anterior,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_APARTADO'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Expediente apartado por solicitud"
                )
            else:
                ExpedienteEstadoLog.objects.create(
                    expediente=exp,
                    estado_anterior=None,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_APARTADO'),
                    usuario=request.user,
                    solicitud=solicitud
                )

            # Buscar el paciente asignado AL MOMENTO de la solicitud.
            # Si después el expediente se reasigna a otro paciente, esta
            # solicitud conserva el paciente original via FK.
            asig = PacienteAsignacion.objects.filter(
                expediente=exp, estado='1'
            ).select_related('paciente').first()
            paciente_actual = asig.paciente if asig else None

            SolicitudExpedienteDetalle.objects.create(
                solicitud=solicitud,
                expediente_prestamo=ep,
                paciente=paciente_actual,  # FK al paciente (no snapshot)
            )

        _registrar_log(
            request.user, 'SOLICITUD_CREADA',
            f'Solicitud #{solicitud.id} creada con {expedientes.count()} expedientes.',
            'SolicitudPrestamo', solicitud.id
        )

        logger.info(f"Solicitud #{solicitud.id} creada por {request.user.username}")
        return JsonResponse({
            "success": True,
            "solicitud_id": solicitud.id,
            "mensaje": f"Solicitud #{solicitud.id} creada exitosamente con {expedientes.count()} expediente(s)."
        })

    except Exception as e:
        logger.error(f"Error en crear_solicitud_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# ============================================
# APIs USUARIO - Seguimiento
# ============================================

@require_GET
def mis_solicitudes_api(request):
    """
    Lista las solicitudes del usuario actual con filtros opcionales de fecha.
    
    Query Params:
        filtro (str): 'hoy', 'semana', 'mes', 'rango' o '' para todas.
        fecha_inicio (str): Fecha inicio en formato YYYY-MM-DD (aplica con filtro='rango').
        fecha_fin (str): Fecha fin en formato YYYY-MM-DD (aplica con filtro='rango').
    """
    if not _es_exp_solicitante(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        qs = SolicitudPrestamo.objects.filter(
            usuario=request.user
        ).select_related('servicio_unidad').order_by('-fecha_creacion')

        # --- Aplicar filtros de fecha (mismo patrón que reportes del módulo) ---
        filtro = request.GET.get('filtro', '').strip()
        from datetime import date as date_type
        hoy = date_type.today()

        if filtro == 'hoy':
            qs = qs.filter(
                fecha_creacion__gte=str(hoy),
                fecha_creacion__lte=str(hoy) + ' 23:59:59'
            )
        elif filtro == 'semana':
            inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
            fin_semana = inicio_semana + timedelta(days=6)        # Domingo
            qs = qs.filter(
                fecha_creacion__gte=str(inicio_semana),
                fecha_creacion__lte=str(fin_semana) + ' 23:59:59'
            )
        elif filtro == 'mes':
            import calendar
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            inicio_mes = str(hoy.replace(day=1))
            fin_mes = str(hoy.replace(day=ultimo_dia))
            qs = qs.filter(
                fecha_creacion__gte=inicio_mes,
                fecha_creacion__lte=fin_mes + ' 23:59:59'
            )
        elif filtro == 'rango':
            fecha_inicio_str = request.GET.get('fecha_inicio', '').strip()
            fecha_fin_str = request.GET.get('fecha_fin', '').strip()
            if fecha_inicio_str:
                qs = qs.filter(fecha_creacion__gte=fecha_inicio_str)
            if fecha_fin_str:
                qs = qs.filter(fecha_creacion__lte=fecha_fin_str + ' 23:59:59')
        # Si filtro está vacío retorna todas las solicitudes
        data = []
        for s in qs:
            # Importamos los servicios para acceso unificado a datos
            from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

            # Cada detalle se enriquece desde el FK paciente (no desde snapshots)
            detalles_info = []
            for d in s.detalles.select_related(
                'expediente_prestamo__expediente', 'paciente'
            ):
                detalles_info.append(DatosDetalleSolicitud.enriquecer(d))

            prestamo_info = None
            try:
                p = s.prestamo
                prestamo_info = {
                    "id": p.id,
                    "estado": EstadoPrestamo.codigo_de(p.estado_id),
                    "fecha_entrega": _fmt_local(p.fecha_entrega) or None,
                    "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                    "tiempo_restante_segundos": p.tiempo_restante_segundos,
                    "porcentaje_tiempo_usado": p.porcentaje_tiempo_usado,
                    "esta_vencido": p.esta_vencido,
                    "motivo_rechazo": p.motivo_rechazo or "",
                    "comentarios": p.comentarios or "",
                }
            except Prestamo.DoesNotExist:
                pass

            data.append({
                "id": s.id,
                "fecha_creacion": _fmt_local(s.fecha_creacion),
                "estado_flujo": DatosSolicitud.estado_codigo(s),
                "estado_flujo_nombre": DatosSolicitud.estado_nombre(s),
                "motivo": DatosSolicitud.motivo_nombre(s),
                "observaciones": s.observaciones or "",
                "unidad": DatosSolicitud.unidad_nombre(s),
                "unidad_id": DatosSolicitud.unidad_id(s),
                # Alias para retrocompatibilidad con frontend actual
                "area_destino": DatosSolicitud.unidad_nombre(s),
                "expedientes": detalles_info,
                "cant_expedientes": len(detalles_info),
                "prestamo": prestamo_info,
            })

        return JsonResponse({"data": data})

    except Exception as e:
        logger.error(f"Error en mis_solicitudes_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
