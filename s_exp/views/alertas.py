"""
alertas.py - APIs de notificaciones en tiempo real (polling) y alertas de usuario.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt


from s_exp.models import SolicitudPrestamo, Prestamo, LogHistorico


logger = logging.getLogger("s_exp")


# ============================================
# APIs - Alertas
# ============================================

@require_GET
def changes_check_api(request):
    """
    Endpoint ULTRA LIGERO usado por el polling inteligente del frontend.

    Devuelve los timestamps del último cambio en cada sección del módulo s_exp.
    El frontend compara estos timestamps con los últimos vistos y solo
    recarga las tablas si hubo un cambio real (preserva el estado de UI
    como tarjetas expandidas, scroll, etc).

    Es deliberadamente ligero: solo hace agregaciones MAX(timestamp) sin
    devolver datos grandes. Se llama cada 3-5s pero su carga es mínima.
    """
    # Validación de seguridad: solo usuarios autenticados (sin sesión = sin polling)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    from django.db.models import Max
    from s_exp.models import LogHistorico, SolicitudPrestamo, Prestamo, Devolucion

    # GRANULARIDAD POR TIPO DE ACCIÓN:
    # Cada sección (pantalla del admin) solo se notifica de los eventos que
    # le incumben directamente. Esto evita que el admin reciba un banner en
    # "Gestión Solicitudes" cuando lo que cambió es una devolución, etc.
    user = request.user

    # ----- Eventos por sección (vía LogHistorico) -----
    # Gestión Solicitudes (admin) → nuevas solicitudes creadas por usuarios
    gestion_acciones = ['SOLICITUD_CREADA']

    # Control de Devoluciones (admin) → usuario pide devolver expedientes
    devoluciones_acciones = ['SOLICITUD_DEVOLUCION_INICIADA']

    # Monitoreo Préstamos (admin) → préstamos entregados/devueltos por OTROS admins
    # (no tiene un tipo de log "de usuario", solo cambios de estado por admins)
    monitoreo_acciones = ['PRESTAMO_ENTREGADO', 'DEVOLUCION_PROCESADA']

    # Mis Solicitudes (usuario) → cualquier cambio en sus propias solicitudes
    # hecho por un admin (aprobada, lista, etc).
    mis_solic_acciones = [
        'SOLICITUD_APROBADA', 'SOLICITUD_RECHAZADA', 'SOLICITUD_LISTA',
        'PRESTAMO_ENTREGADO', 'DEVOLUCION_PROCESADA',
    ]

    def _max_log(acciones, excluir_self=True):
        """MAX(timestamp) de logs filtrados por tipo. Opcional: excluir al user actual."""
        qs = LogHistorico.objects.filter(accion__in=acciones)
        if excluir_self:
            qs = qs.exclude(usuario=user)
        return qs.aggregate(ts=Max('timestamp'))['ts']

    # Gestión y Devoluciones: NO excluir al usuario (acciones de "usuario"
    # siempre deben notificar al admin, incluso si admin = solicitante en pruebas).
    gestion_ts = _max_log(gestion_acciones, excluir_self=False)
    devoluciones_ts = _max_log(devoluciones_acciones, excluir_self=False)

    # Monitoreo: SÍ excluir al usuario (acciones admin no deben auto-notificarse)
    monitoreo_ts = _max_log(monitoreo_acciones, excluir_self=True)

    # Mis Solicitudes: estos son cambios sobre las solicitudes del usuario.
    # No excluir nada (necesita ver TODO cambio que afecte sus solicitudes).
    mis_solic_ts = _max_log(mis_solic_acciones, excluir_self=False)

    # Global: cualquier log (excluyendo los del propio usuario para no spam)
    global_ts = LogHistorico.objects.exclude(usuario=user).aggregate(ts=Max('timestamp'))['ts']

    def _iso(dt):
        return dt.isoformat() if dt else ''

    return JsonResponse({
        # Fallback general (para Dashboard / Reportes)
        'global': _iso(global_ts),

        # Cada sección solo recibe sus eventos específicos:
        'solicitudes': _iso(gestion_ts),       # Gestión Solicitudes (admin)
        'mis_solicitudes': _iso(mis_solic_ts), # Mis Solicitudes (usuario)
        'prestamos': _iso(monitoreo_ts),       # Monitoreo
        'devoluciones': _iso(devoluciones_ts), # Control de Devoluciones
    })


@require_GET
def alertas_usuario_api(request):
    """Retorna alertas para el usuario actual."""
    if not request.user.is_authenticated:
        return JsonResponse({"alertas": []})

    try:
        alertas = []

        # Alertas para solicitantes: préstamos a punto de vencer
        prestamos_usuario = Prestamo.objects.filter(
            solicitud__usuario=request.user,
            estado='Entregado'
        )

        for p in prestamos_usuario:
            if p.esta_vencido:
                alertas.append({
                    "tipo": "danger",
                    "titulo": "Préstamo Vencido",
                    "mensaje": f"El préstamo #{p.id} ha superado el límite de tiempo. Devuelva los expedientes de inmediato.",
                    "prestamo_id": p.id,
                })
                continue

            # Minutos restantes para alertas de 10 / 5 min
            min_restantes = None
            if p.fecha_limite:
                min_restantes = int((p.fecha_limite - timezone.now()).total_seconds() // 60)

            if min_restantes is not None and 0 < min_restantes <= 5:
                alertas.append({
                    "tipo": "danger",
                    "titulo": "¡5 minutos para vencer!",
                    "mensaje": f"El préstamo #{p.id} vence en {min_restantes} minuto(s). Devuelva los expedientes ahora.",
                    "prestamo_id": p.id,
                    "sticky": True,
                })
            elif min_restantes is not None and 5 < min_restantes <= 10:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "10 minutos para vencer",
                    "mensaje": f"El préstamo #{p.id} vence en {min_restantes} minuto(s). Prepare la devolución.",
                    "prestamo_id": p.id,
                })
            elif p.porcentaje_tiempo_usado >= 90:
                alertas.append({
                    "tipo": "warning",
                    "titulo": "Préstamo por Vencer",
                    "mensaje": f"El préstamo #{p.id} está próximo a vencer. Considere devolver los expedientes.",
                    "prestamo_id": p.id,
                })

        # Alertas de Vencimiento Recurrentes (Sticky cada 5 min)
        prestamos_vencidos = Prestamo.objects.filter(
            solicitud__usuario=request.user,
            estado='Vencido'
        )
        ahora = timezone.now()
        for p in prestamos_vencidos:
            reaparecer = False
            if not p.alerta_vencimiento_leida_at:
                reaparecer = True
            else:
                diferencia = ahora - p.alerta_vencimiento_leida_at
                if diferencia.total_seconds() > 300:  # 5 min
                    reaparecer = True
            
            if reaparecer:
                alertas.append({
                    "tipo": "danger",
                    "titulo": "¡PRÉSTAMO VENCIDO!",
                    "mensaje": f"El préstamo #{p.id} está vencido. Por favor devuelva los expedientes.",
                    "prestamo_id": p.id,
                    "sticky": True,
                    "tipo_alerta": "vencimiento"
                })

        # Solicitudes aprobadas listas para retirar (Persistentes hasta que el usuario las acepte)
        solicitudes_aprobadas = SolicitudPrestamo.objects.filter(
            usuario=request.user,
            estado_flujo_id='SOL_LISTO_RECOGER',
            notificado_listo=False
        )
        for s in solicitudes_aprobadas:
            alertas.append({
                "tipo": "success",
                "titulo": "¡Listo para recoger!",
                "mensaje": "Sus expedientes ya estan listos para recoger.",
                "solicitud_id": s.id,
                "sticky": True
            })

        # Solicitudes rechazadas recientes
        solicitudes_rechazadas = SolicitudPrestamo.objects.filter(

            usuario=request.user,
            estado_flujo_id='SOL_RECHAZADA'
        ).order_by('-fecha_creacion')[:5]
        for s in solicitudes_rechazadas:
            try:
                motivo = s.prestamo.motivo_rechazo or "Sin motivo especificado"
            except Prestamo.DoesNotExist:
                motivo = "Sin motivo especificado"
            alertas.append({
                "tipo": "danger",
                "titulo": "Solicitud Rechazada",
                "mensaje": f"Su solicitud #{s.id} fue rechazada. Motivo: {motivo}",
                "solicitud_id": s.id,
            })

        return JsonResponse({"alertas": alertas})

    except Exception as e:
        logger.error(f"Error en alertas_usuario_api: {e}", exc_info=True)
        return JsonResponse({"alertas": []})


@csrf_exempt
@require_POST
def marcar_notificacion_leida_api(request):
    """Marca una notificación de 'Listo para recoger' como leída por el usuario."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        import json
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')

        if not solicitud_id:
            return JsonResponse({"error": "Falta ID de solicitud"}, status=400)

        solicitud = SolicitudPrestamo.objects.get(id=solicitud_id, usuario=request.user)
        solicitud.notificado_listo = True
        solicitud.save()

        return JsonResponse({"success": True})

    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_notificacion_leida_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno"}, status=500)


@csrf_exempt
@require_POST
def marcar_vencimiento_leido_api(request):
    """Marca una alerta de vencimiento como aceptada temporalmente (5 min)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    try:
        import json
        body = json.loads(request.body)
        prestamo_id = body.get('prestamo_id')

        if not prestamo_id:
            return JsonResponse({"error": "Falta ID de préstamo"}, status=400)

        prestamo = Prestamo.objects.get(id=prestamo_id, solicitud__usuario=request.user)
        prestamo.alerta_vencimiento_leida_at = timezone.now()
        prestamo.save()

        return JsonResponse({"success": True})

    except Prestamo.DoesNotExist:
        return JsonResponse({"error": "Préstamo no encontrado"}, status=404)
    except Exception as e:
        logger.error(f"Error en marcar_vencimiento_leido_api: {e}", exc_info=True)
        return JsonResponse({"error": "Error interno"}, status=500)
