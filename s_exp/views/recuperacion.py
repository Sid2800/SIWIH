"""
recuperacion.py - Recuperación de expedientes de URGENCIA (módulo s_exp).

Parte del paquete s_exp.views.

¿Para qué existe?
----------------
Admisión necesita a veces un expediente que YA está prestado, por una
emergencia o un asunto urgente. Este flujo permite exigirlo de inmediato:
se selecciona el expediente sin importar a quién se le prestó y, al confirmar,
el expediente se devuelve a ADMISIÓN saltándose el protocolo normal (no espera
a que el usuario lo devuelva ni a la auditoría de devolución).

Efecto sobre la solicitud del usuario que lo tenía:
  - Ese expediente termina su proceso y vuelve a ADMISIÓN.
  - Los demás expedientes de esa solicitud SIGUEN prestados.
  - Solo si no queda ningún expediente pendiente, la solicitud se finaliza.

Al usuario que lo tenía se le avisa con una alerta (ver alertas.py), que se
genera a partir de recuperado_admision / recuperacion_leida.

Permisos: exclusivo de Admisión (puede_recuperar_expedientes), no de cualquier
admin del módulo.
"""

import json

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect

from s_exp.models import (
    SolicitudExpedienteDetalle, ExpedienteEstadoLog,
    EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo,
)
from s_exp.services.permisos import puede_recuperar_expedientes

from .comunes import _fmt_local, _registrar_log, _set_ubicacion_admision

from core.utils.utilidades_logging import log_info, log_warning, log_error
from core.constants.domain_constants import LogApp


# Estados de solicitud POSTERIORES a la entrega: son los únicos en los que el
# expediente ya salió del archivo y, por tanto, hay algo que exigir.
# Se excluyen a propósito SOL_APROBADA_ORGANIZANDO y SOL_LISTO_RECOGER: ahí el
# expediente está APARTADO (reservado) pero sigue físicamente en el archivo, así
# que no tiene sentido "recuperarlo" de nadie.
ESTADOS_ENTREGADA = [
    'SOL_EN_PRESTAMO',
    'SOL_EN_DEVOLUCION',
    'SOL_INCOMPLETA',
]


def _ids_estados_entregada():
    """
    Traduce los códigos de arriba a sus ids ENTEROS.

    Se filtra por id y no por `estado_flujo__codigo__in=[...]`: esa forma obliga a
    un JOIN contra el catálogo y a comparar texto en cada fila. Con los ids el
    filtro es un IN sobre la FK (columna indexada, entero) y no toca el catálogo.
    EstadoSolicitud.id_de() cachea el mapeo código->id, así que la resolución no
    cuesta consultas extra.
    """
    return [EstadoSolicitud.id_de(codigo) for codigo in ESTADOS_ENTREGADA]


def _filtros_recuperable():
    """
    Condiciones que debe cumplir un expediente para poder exigirse.

    El criterio decisivo es el ESTADO FÍSICO = EXP_PRESTADO: solo se recupera lo
    que de verdad está entregado (fuera del archivo). Eso deja fuera por sí solo
    lo APARTADO y lo PENDIENTE DE PRÉSTAMO, que nunca salieron. El estado de la
    solicitud se mantiene como filtro adicional de coherencia.
    """
    return {
        'solicitud__estado_flujo_id__in': _ids_estados_entregada(),
        'expediente_prestamo__estado_id': EstadoExpedienteFisico.id_de('EXP_PRESTADO'),
        'aprobado': True,      # solo lo que sí se prestó
        'devuelto': False,     # lo ya devuelto no se recupera
    }


@require_GET
def expedientes_recuperables_api(request):
    """
    Lista los expedientes ENTREGADOS que se pueden exigir.

    Solo aparecen los que están físicamente fuera del archivo (EXP_PRESTADO).
    Los apartados/reservados y los pendientes de entrega quedan fuera: siguen en
    el archivo, así que no hay nada que recuperarle a nadie.

    Solo devuelve los datos que necesita la pantalla: número de solicitud,
    expediente, identidad, nombre, fecha de solicitud, fecha de entrega, a quién
    se prestó y a qué área.

    Rendimiento: un solo queryset con select_related; sin N+1 dentro del loop.
    """
    if not puede_recuperar_expedientes(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        from s_exp.services.datos_solicitud import DatosDetalleSolicitud, DatosSolicitud

        qs = SolicitudExpedienteDetalle.objects.select_related(
            'solicitud__usuario', 'solicitud__servicio_unidad', 'solicitud__estado_flujo',
            'expediente_prestamo__expediente', 'paciente',
        ).filter(
            **_filtros_recuperable()
        ).order_by('-solicitud__fecha_creacion')

        data = []
        for d in qs:
            s = d.solicitud
            data.append({
                "detalle_id": d.id,
                "solicitud_id": s.id,
                "numero": DatosDetalleSolicitud.numero_expediente(d),
                "paciente_identidad": DatosDetalleSolicitud.paciente_dni(d),
                "paciente_nombre": DatosDetalleSolicitud.paciente_nombre_completo(d),
                "fecha_solicitud": _fmt_local(s.fecha_creacion),
                # Hora en que se entregó ESE expediente (puede diferir del resto:
                # un préstamo pendiente se entrega después que el resto).
                "fecha_entrega": _fmt_local(d.fecha_entrega) if d.fecha_entrega else '',
                "prestado_a": DatosSolicitud.usuario_nombre_completo(s),
                "area": DatosSolicitud.unidad_nombre(s),
            })

        return JsonResponse({"data": data, "total": len(data)})

    except Exception as e:
        log_error(f"Error en expedientes_recuperables_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)


@csrf_protect
@require_POST
def recuperar_expedientes_api(request):
    """
    Fuerza la devolución inmediata a ADMISIÓN de los expedientes seleccionados.

    Equivale a "como si solo ese expediente hubiera sido devuelto": se marca
    devuelto, se sella su fecha y el expediente vuelve a ADMISIÓN y a estado
    DISPONIBLE, sin pasar por la auditoría de devolución.

    Cierre de la solicitud (según lo definido):
      - Si tras recuperar no queda NINGÚN expediente pendiente -> se finaliza.
      - Si quedan, la solicitud sigue activa y los demás siguen prestados.

    Todo en una transacción: o se recuperan todos los seleccionados o ninguno.
    """
    if not puede_recuperar_expedientes(request.user):
        return JsonResponse({"error": "Sin permisos"}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Datos inválidos"}, status=400)

    detalle_ids = body.get('detalle_ids') or []
    observaciones = (body.get('observaciones') or '').strip()

    if not detalle_ids:
        return JsonResponse({"error": "Seleccione al menos un expediente"}, status=400)

    try:
        detalles = list(
            SolicitudExpedienteDetalle.objects.select_related(
                'solicitud', 'expediente_prestamo__expediente'
            ).filter(
                id__in=detalle_ids,
                # Mismas condiciones que el listado: se revalida en el POST para
                # que no se pueda recuperar algo que ya no está entregado.
                **_filtros_recuperable()
            )
        )
        if not detalles:
            return JsonResponse(
                {"error": "Los expedientes seleccionados ya no están disponibles para recuperar"},
                status=400
            )

        # Ubicación ADMISION: se resuelve UNA vez fuera del loop (no cambia).
        from expediente.services.ubicaciones import CatalogoUbicaciones
        ubicacion_admision = None
        try:
            ubicacion_admision = CatalogoUbicaciones.ubicacion_admision()
        except Exception as _e:
            log_warning(f"No se pudo resolver ubicacion ADMISION: {_e}", app=LogApp.S_EXP)

        ahora = timezone.now()
        id_disponible = EstadoExpedienteFisico.id_de('EXP_DISPONIBLE')
        solicitudes_tocadas = set()

        with transaction.atomic():
            for d in detalles:
                ep = d.expediente_prestamo
                estado_ant = ep.estado

                # 1) El detalle queda devuelto, marcado como recuperación forzada.
                d.devuelto = True
                d.fecha_devolucion = ahora
                d.recuperado_admision = True
                d.motivo_recuperacion = observaciones or 'Requerido de urgencia por Admisión'
                d.recuperacion_leida = False  # dispara la alerta al usuario
                d.save()

                # 2) El expediente físico vuelve a estar disponible en ADMISIÓN.
                ep.estado_id = id_disponible
                if ubicacion_admision is not None:
                    ep.ubicacion = ubicacion_admision
                ep.save()
                try:
                    _set_ubicacion_admision(ep.expediente, request.user,
                                            ubicacion_obj=ubicacion_admision)
                except Exception as _e:
                    log_warning(f"No se pudo regresar a ADMISION al recuperar: {_e}",
                                app=LogApp.S_EXP)

                ExpedienteEstadoLog.objects.create(
                    expediente=ep.expediente,
                    estado_anterior=estado_ant,
                    estado_nuevo_id=id_disponible,
                    usuario=request.user,
                    solicitud=d.solicitud,
                    observacion=f"Recuperado de urgencia por Admisión: {d.motivo_recuperacion}",
                )
                solicitudes_tocadas.add(d.solicitud_id)

            # 3) Cerrar SOLO las solicitudes que ya no tengan pendientes.
            #    Si quedan expedientes fuera, la solicitud sigue activa y los
            #    demás continúan prestados.
            finalizadas = []
            for sol_id in solicitudes_tocadas:
                from s_exp.models import SolicitudPrestamo
                solicitud = SolicitudPrestamo.objects.get(id=sol_id)
                quedan = solicitud.detalles.filter(aprobado=True, devuelto=False).count()
                if quedan == 0:
                    solicitud.estado_flujo_id = EstadoSolicitud.id_de('SOL_FINALIZADA')
                    solicitud.save()
                    try:
                        p = solicitud.prestamo
                        p.estado_id = EstadoPrestamo.id_de('Cerrado')
                        p.fecha_devolucion_real = ahora
                        p.save()
                    except Exception:
                        pass
                    finalizadas.append(sol_id)

        _registrar_log(
            request.user, 'EXPEDIENTES_RECUPERADOS',
            f'{len(detalles)} expediente(s) recuperado(s) de urgencia por Admisión. '
            f'Solicitudes afectadas: {sorted(solicitudes_tocadas)}. '
            f'Finalizadas: {finalizadas or "ninguna"}. Motivo: {observaciones or "—"}',
            'SolicitudPrestamo', detalles[0].solicitud_id
        )
        log_info(
            f"Recuperación de urgencia: {len(detalles)} expediente(s) por {request.user.username}",
            app=LogApp.S_EXP
        )

        return JsonResponse({
            "success": True,
            "recuperados": len(detalles),
            "solicitudes_finalizadas": finalizadas,
        })

    except Exception as e:
        log_error(f"Error en recuperar_expedientes_api: {e}", app=LogApp.S_EXP)
        return JsonResponse({"error": "Error interno del servidor"}, status=500)
