"""
devoluciones.py - APIs de gestion y procesamiento de devoluciones.

Parte del paquete s_exp.views (antes views.py monolitico).
"""


import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect


from s_exp.models import SolicitudPrestamo, SolicitudExpedienteDetalle, Prestamo, Devolucion, ExpedienteEstadoLog


from .comunes import (
    _es_exp_admin,
    _registrar_log,
    _set_ubicacion_admision,
)


from s_exp.models import EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo, EstadoDevolucion


from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


# ============================================
# APIs ADMIN - Control de Devoluciones
# ============================================

@require_GET
def prestamos_para_devolucion_api(request):
    """Lista préstamos que están pendientes de devolución."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        # Mostrar solicitudes marcadas para devolución O con devoluciones incompletas pendientes
        qs = Prestamo.objects.select_related('solicitud__usuario').filter(
            solicitud__estado_flujo__codigo='SOL_EN_DEVOLUCION',
            estado__codigo__in=['Entregado', 'Vencido', 'DevolucionParcial']
        ).order_by('fecha_limite')

        # Importamos los servicios — acceso unificado a datos del detalle
        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        data = []
        for p in qs:
            detalles = []
            # Mostrar TODOS los expedientes aprobados (devueltos y pendientes)
            for d in p.solicitud.detalles.select_related(
                'expediente_prestamo__expediente', 'expediente_prestamo__estado', 'paciente'
            ).filter(aprobado=True):
                estado_fisico_id = EstadoExpedienteFisico.codigo_de(d.expediente_prestamo.estado_id)
                # Estado de devolución para el front:
                #   - 'pendiente'  : aún no devuelto
                #   - 'devuelto'   : devuelto correctamente (EXP_DISPONIBLE)
                #   - 'perdido'    : marcado como perdido (EXP_PERDIDO)
                if not d.devuelto:
                    estado_devolucion = 'pendiente'
                elif estado_fisico_id == 'EXP_PERDIDO':
                    estado_devolucion = 'perdido'
                else:
                    estado_devolucion = 'devuelto'

                detalles.append({
                    "id": d.id,
                    "numero": DatosDetalleSolicitud.numero_expediente(d),
                    "estado_fisico": d.expediente_prestamo.estado.nombre,
                    "estado_devolucion": estado_devolucion,
                    "devuelto": bool(d.devuelto),
                    "paciente_id": DatosDetalleSolicitud.paciente_id(d),
                    "paciente_identidad": DatosDetalleSolicitud.paciente_dni(d),
                    "paciente_nombre": DatosDetalleSolicitud.paciente_nombre_completo(d),
                    "comentario_devolucion": d.comentario_devolucion or '',
                    # Decisión que dejó el USUARIO al iniciar la devolución. El
                    # front del admin la usa para precargar el radio:
                    #   True  -> "Recibido" ; False -> "No Recibido" (+ comentario)
                    #   None  -> sin decisión previa (comportamiento anterior)
                    "usuario_solicita_devolver": d.usuario_solicita_devolver,
                    "comentario_usuario_devolucion": d.comentario_usuario_devolucion or '',
                })

            data.append({
                "id": p.id,
                "solicitud_id": p.solicitud.id,
                "usuario": DatosSolicitud.usuario_username(p.solicitud),
                "usuario_nombre": DatosSolicitud.usuario_nombre_completo(p.solicitud),
                "unidad": DatosSolicitud.unidad_nombre(p.solicitud),
                "estado": EstadoPrestamo.codigo_de(p.estado_id),
                "detalles_expedientes": detalles,
                "cant_expedientes": p.solicitud.detalles.filter(aprobado=True).count(),
                "cant_devueltos": p.solicitud.detalles.filter(aprobado=True, devuelto=True).count(),
                "fecha_limite": p.fecha_limite.isoformat() if p.fecha_limite else None,
                "esta_vencido": p.esta_vencido,
            })

        return JsonResponse({"data": data})

    except Exception as e:
        log_error(f"Error en prestamos_para_devolucion_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


# Comentario por defecto para los expedientes que el usuario NO devuelve en una
# devolución parcial (editable por el usuario en el modal).
COMENTARIO_TODAVIA_EN_USO = 'Todavía en uso'


@csrf_protect
@require_POST
def solicitar_devolucion_api(request):
    """
    El personal (usuario) inicia la devolución de los expedientes al archivo.

    Origen del flujo: botones "Devolución completa" / "Devolución parcial" de la
    pantalla "Mis Solicitudes" del usuario. En ambos casos la solicitud pasa a
    SOL_EN_DEVOLUCION y queda a la espera de la auditoría física del admin; lo
    que cambia es la DECISIÓN por expediente que el usuario deja registrada para
    que el admin la vea precargada:

      body = {
        "solicitud_id": int,
        "tipo": "completa" | "parcial",   # default "completa"
        "decisiones": [                    # solo en "parcial"
            {"detalle_id": int, "devolver": bool, "comentario": str}, ...
        ]
      }

    - completa: TODOS los expedientes aprobados y aún no devueltos se marcan
      usuario_solicita_devolver=True (el admin los verá pre-marcados "Recibido").
    - parcial: cada expediente toma la decisión del usuario. Los que NO se
      devuelven guardan comentario_usuario_devolucion ("Todavía en uso" por
      defecto, editable) y el admin los verá pre-marcados "No Recibido".

    Rendimiento: una sola escritura por rama (update masivo en completa,
    bulk_update en parcial) dentro de una transacción atómica, para no dejar la
    solicitud en un estado a medias si algo falla.
    """
    if not request.user.is_authenticated:
         return JsonResponse({"error": "No autenticado"}, status=401)

    from django.db import transaction

    try:
        body = json.loads(request.body)
        solicitud_id = body.get('solicitud_id')
        tipo = (body.get('tipo') or 'completa').lower()
        decisiones = body.get('decisiones', []) or []

        # El usuario puede devolver si está en préstamo o si fue incompleta (quedan pendientes)
        solicitud = SolicitudPrestamo.objects.get(
            id=solicitud_id,
            usuario=request.user,
            estado_flujo__codigo__in=['SOL_EN_PRESTAMO', 'SOL_INCOMPLETA']
        )

        with transaction.atomic():
            if tipo == 'parcial':
                # Mapa detalle_id -> decisión, restringido a detalles de ESTA
                # solicitud que sigan aprobados y sin devolver (lo demás se ignora).
                decisiones_por_id = {}
                for dec in decisiones:
                    try:
                        did = int(dec.get('detalle_id'))
                    except (TypeError, ValueError):
                        continue
                    decisiones_por_id[did] = dec

                pendientes = list(solicitud.detalles.filter(
                    aprobado=True, devuelto=False, id__in=decisiones_por_id.keys()
                ))
                for d in pendientes:
                    dec = decisiones_por_id[d.id]
                    quiere = bool(dec.get('devolver'))
                    d.usuario_solicita_devolver = quiere
                    if quiere:
                        d.comentario_usuario_devolucion = None
                    else:
                        d.comentario_usuario_devolucion = (
                            (dec.get('comentario') or '').strip() or COMENTARIO_TODAVIA_EN_USO
                        )
                if pendientes:
                    SolicitudExpedienteDetalle.objects.bulk_update(
                        pendientes,
                        ['usuario_solicita_devolver', 'comentario_usuario_devolucion']
                    )
            else:
                # Completa: todos los pendientes -> el usuario quiere devolverlos.
                solicitud.detalles.filter(aprobado=True, devuelto=False).update(
                    usuario_solicita_devolver=True,
                    comentario_usuario_devolucion=None
                )

            solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_EN_DEVOLUCION')
            solicitud.save()

            _registrar_log(
                request.user, 'SOLICITUD_DEVOLUCION_INICIADA',
                f'Usuario inició devolución ({tipo}) de la solicitud #{solicitud.id}.',
                'SolicitudPrestamo', solicitud.id
            )

        return JsonResponse({"success": True})
    except SolicitudPrestamo.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada o no está en préstamo"}, status=404)
    except Exception as e:
        log_error(f"Error en solicitar_devolucion_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def procesar_devolucion_api(request):
    """Admin audita los expedientes recibidos. Marca cuáles llegaron y cuáles se perdieron."""
    if not _es_exp_admin(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
        prestamo_id = body.get('prestamo_id')
        detalles_recibidos = body.get('detalles_recibidos', [])
        detalles_perdidos = body.get('detalles_perdidos', [])
        detalles_no_recibidos = body.get('detalles_no_recibidos', [])
        # Comentarios por expediente: { detalle_id: "comentario" }
        comentarios_por_detalle = body.get('comentarios_por_detalle', {}) or {}
        notas = body.get('notas', '')

        def _comentario(det_id):
            v = comentarios_por_detalle.get(str(det_id)) or comentarios_por_detalle.get(det_id)
            return (v or '').strip() or None

        prestamo = Prestamo.objects.get(id=prestamo_id)
        solicitud = prestamo.solicitud

        # 1. Procesar los que llegaron (Disponibles)
        esta_vencido = prestamo.esta_vencido

        # Resolver UNA sola vez la ubicación ADMISION (catálogo nuevo).
        # Al devolver, el expediente regresa a ADMISION.
        from expediente.services.ubicaciones import CatalogoUbicaciones
        ubicacion_admision = None
        try:
            ubicacion_admision = CatalogoUbicaciones.ubicacion_admision()
        except Exception as _e:
            log_warning(f"No se pudo resolver ubicacion ADMISION: {_e}", app=LogApp.S_EXP)

        # Hora de ESTA auditoría: se sella en cada expediente recibido ahora.
        # Clave para las devoluciones parciales: cada tanda queda con su propia
        # fecha, así se sabe cuándo regresó realmente cada expediente.
        ahora_dev = timezone.now()

        for det_id in detalles_recibidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            if not detalle.devuelto:
                detalle.devuelto = True
                detalle.fecha_devolucion = ahora_dev
                if esta_vencido:
                    detalle.fuera_de_tiempo = True
                detalle.comentario_devolucion = _comentario(det_id)
                detalle.save()

                ep = detalle.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
                # NUEVO: regresar al catálogo unificado → ADMISION (FK por id)
                if ubicacion_admision is not None:
                    ep.ubicacion = ubicacion_admision
                ep.save()

                # Actualizar la ubicación del expediente a ADMISION:
                #  - NUEVO: expediente.ubicacion (FK catálogo) = ADMISION
                #  - LEGACY: expediente.localizacion (texto) sincronizado
                try:
                    _set_ubicacion_admision(ep.expediente, request.user, ubicacion_obj=ubicacion_admision)
                except Exception as _e:
                    log_warning(f"No se pudo regresar a ADMISION al devolver: {_e}", app=LogApp.S_EXP)

                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_DISPONIBLE'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Devuelto correctamente" + (" (Fuera de tiempo)" if esta_vencido else "")
                )

        # 2. Procesar los perdidos (Cuentan como procesados/cerrados para la solicitud)
        for det_id in detalles_perdidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            if not detalle.devuelto:
                detalle.devuelto = True  # Se marca como procesado
                # Fecha en que se cerró el expediente (aunque sea como perdido).
                detalle.fecha_devolucion = ahora_dev
                detalle.comentario_devolucion = _comentario(det_id) or 'Marcado como perdido'
                detalle.save()
                
                ep = detalle.expediente_prestamo
                estado_ant = ep.estado
                ep.estado_id = EstadoExpedienteFisico.id_de('EXP_PERDIDO')
                ep.save()
                
                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_PERDIDO'),
                    usuario=request.user,
                    solicitud=solicitud,
                    observacion="Marcado como perdido durante auditoría"
                )

        # 3. Procesar los NO recibidos (Siguen pendientes)
        for det_id in detalles_no_recibidos:
            detalle = SolicitudExpedienteDetalle.objects.get(id=det_id, solicitud=solicitud)
            ep = detalle.expediente_prestamo
            ExpedienteEstadoLog.objects.create(
                expediente=ep.expediente,
                estado_anterior=ep.estado,
                estado_nuevo_id=EstadoExpedienteFisico.id_de('EXP_PRESTADO'),
                usuario=request.user,
                solicitud=solicitud,
                observacion="Auditado como NO RECIBIDO (Sigue en préstamo)"
            )

        # 4. Determinar estado final de la solicitud (solo expedientes aprobados cuentan)
        total_exp = solicitud.detalles.filter(aprobado=True).count()
        devueltos_ahora = solicitud.detalles.filter(aprobado=True, devuelto=True).count()
        hay_no_recibidos = len(detalles_no_recibidos) > 0
        
        if devueltos_ahora >= total_exp and not hay_no_recibidos:
            # Todo procesado: ver si fue vencido
            if prestamo.esta_vencido:
                solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_FINALIZADA')
                prestamo.estado_id = EstadoPrestamo.id_de('DevueltoVencido')
            else:
                solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_FINALIZADA')
                prestamo.estado_id = EstadoPrestamo.id_de('Cerrado')
            prestamo.fecha_devolucion_real = timezone.now()
        else:
            # Faltan expedientes (no_recibidos pendientes)
            solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_INCOMPLETA')
            prestamo.estado_id = EstadoPrestamo.id_de('DevolucionParcial')
            
        solicitud.save()
        prestamo.save()

        # Registrar devolución parcial
        Devolucion.objects.create(
            prestamo=prestamo,
            cantidad_esperada=total_exp,
            cantidad_recibida=devueltos_ahora,
            # estado_id (FK al catálogo EstadoDevolucion). El código string es el PK.
            estado_id=EstadoDevolucion.id_de('Completa') if devueltos_ahora >= total_exp and not hay_no_recibidos else EstadoDevolucion.id_de('Incompleta'),
            notas_admin=notas
        )

        # Registrar log de auditoría — esto también dispara el changes-check
        # para que las pantallas conectadas (Mis Solicitudes, etc.) detecten
        # el cambio y se actualicen automáticamente.
        descripcion_log = (
            f"Auditoría de devolución del préstamo #{prestamo.id}: "
            f"{devueltos_ahora}/{total_exp} expedientes devueltos. "
            f"Estado solicitud: {EstadoSolicitud.codigo_de(solicitud.estado_flujo_id)}."
        )
        _registrar_log(
            request.user,
            'DEVOLUCION_PROCESADA',
            descripcion_log,
            'Prestamo', prestamo.id
        )

        return JsonResponse({"success": True, "estado": EstadoSolicitud.codigo_de(solicitud.estado_flujo_id)})

    except Exception as e:
        log_error(f"Error en procesar_devolucion_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
