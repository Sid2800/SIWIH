# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""Helpers de sesión de mapeo y persistencia de auditoría (historial/detalle)."""

import json

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from mapeo_camas.models import (
    DetalleMapeoCama,
    EstadoMapeo,
    HistorialEstadoCama,
    MapeoSesionCama,
    get_observacion_mapeo,
)

from ._helpers import get_estado_mapeo, _resolver_ingreso_operativo

# [2026-06-26 SCOPE] Prefijo técnico para serializar alcance de sesión sin migración adicional.
_SCOPE_PREFIX = "__MAPEO_SCOPE__="

def _cancelar_sesion_mapeo_sin_sesion_django(sesion):
    """[2026-06-22] Cancela una sesion de mapeo cuyo usuario ya no tiene sesion Django activa."""
    if not sesion:
        return None

    with transaction.atomic():
        sesion.estado = get_estado_mapeo("CANCELADO", "ESTADO_SESION")
        sesion.fecha_fin = timezone.now()
        sesion.observacion_texto = "Cancelacion automatica por cierre de sesion Django"
        sesion.save(update_fields=["estado", "fecha_fin", "observacion_texto"])
    return sesion


def _usuarios_con_sesion_django_activa(usuario_ids):
    """[2026-06-22] Resuelve qué usuarios aún tienen al menos una sesión Django vigente."""
    if not usuario_ids:
        return set()

    usuarios_objetivo = {str(usuario_id) for usuario_id in usuario_ids if usuario_id is not None}
    usuarios_activos = set()

    sesiones = Session.objects.filter(expire_date__gt=timezone.now()).only("session_key", "session_data", "expire_date")
    for sesion in sesiones.iterator():
        try:
            data = sesion.get_decoded()
        except Exception:
            continue

        usuario_id = str(data.get("_auth_user_id") or "")
        if usuario_id in usuarios_objetivo:
            usuarios_activos.add(usuario_id)
            if usuarios_activos == usuarios_objetivo:
                break

    return usuarios_activos


def _cerrar_sesiones_mapeo_sin_sesion_django(qs=None):
    """[2026-06-22] Depura sesiones EN_PROGRESO cuyo usuario ya perdió la sesión Django."""
    sesiones_qs = qs or MapeoSesionCama.objects.filter(
        estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
        fecha_fin__isnull=True,
    )
    sesiones = list(sesiones_qs.select_related("usuario"))
    if not sesiones:
        return []

    usuarios_activos = _usuarios_con_sesion_django_activa([sesion.usuario_id for sesion in sesiones])
    sesiones_canceladas = []
    for sesion in sesiones:
        if str(sesion.usuario_id) in usuarios_activos:
            continue
        _cancelar_sesion_mapeo_sin_sesion_django(sesion)
        sesiones_canceladas.append(sesion.id)

    return sesiones_canceladas

# [2026-05-07] Helper para obtener sesión de mapeo activa del usuario
def _obtener_sesion_mapeo_activa(usuario):
    """Retorna la sesion EN_PROGRESO activa mas reciente del usuario."""
    sesion = (
        MapeoSesionCama.objects.filter(
            usuario=usuario,
            estado=get_estado_mapeo("EN_PROGRESO", "ESTADO_SESION"),
            fecha_fin__isnull=True,
        )
        .order_by("-fecha_inicio")
        .first()
    )

    if sesion:
        sesiones_activas = _usuarios_con_sesion_django_activa([sesion.usuario_id])
        if str(sesion.usuario_id) not in sesiones_activas:
            _cancelar_sesion_mapeo_sin_sesion_django(sesion)
            return None

    if not sesion:
        return None

    return sesion


# [2026-05-07] Helper para obtener IDs de servicios en sesión de mapeo
def _obtener_servicios_ids_sesion(sesion):
    """Retorna los ids de servicio incluidos en la sesion de mapeo."""
    if not sesion:
        return []
    return list(
        sesion.servicios_incluidos.order_by("servicio_id").values_list("servicio_id", flat=True)
    )


def _obtener_salas_ids_sesion(sesion):
    """Retorna ids de sala restringidos en la sesion (si aplica)."""
    if not sesion:
        return []

    # [2026-06-26 SCOPE] Reusa observacion_texto como metadato estructurado de alcance.
    texto = (getattr(sesion, "observacion_texto", "") or "").strip()
    if not texto.startswith(_SCOPE_PREFIX):
        return []

    payload_raw = texto[len(_SCOPE_PREFIX):]
    try:
        payload = json.loads(payload_raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    sala_ids = payload.get("sala_ids") or []
    if not isinstance(sala_ids, list):
        return []

    resultado = []
    for sala_id in sala_ids:
        try:
            sala_id_int = int(sala_id)
        except (TypeError, ValueError):
            continue
        if sala_id_int > 0:
            resultado.append(sala_id_int)
    return sorted(set(resultado))


def _guardar_scope_sesion(sesion, *, sala_ids=None):
    """Guarda alcance técnico de sala en la sesión activa de mapeo."""
    sala_ids = sorted(set(int(s) for s in (sala_ids or []) if int(s) > 0))
    if not sala_ids:
        return

    # [2026-06-26 SCOPE] JSON compacto para minimizar escritura y facilitar parseo.
    scope = json.dumps({"sala_ids": sala_ids}, separators=(",", ":"))
    sesion.observacion_texto = f"{_SCOPE_PREFIX}{scope}"
    sesion.save(update_fields=["observacion_texto"])


# [2026-05-07] Helper para registrar detalle de mapeo (auditoría)
def _registrar_detalle_mapeo(
    *,
    usuario,
    cama,
    asignacion,
    tipo_accion,
    hubo_cambio,
    observacion="",
    fue_validada=True,
    sesion_mapeo=None,
):
    """Guarda el detalle por cama en tiempo real dentro de la sesion activa."""
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    if not sesion:
        return None

    # [2026-05-04 AUDIT] Bug Fix: Convertir string de tipo_accion a objeto FK EstadoMapeo.
    # tipo_accion puede ser un string (codigo) o un objeto EstadoMapeo.
    # codigo es unique en la tabla, por lo que no se necesita filtrar por categoria.
    if isinstance(tipo_accion, str):
        tipo_accion = EstadoMapeo.objects.get(codigo=tipo_accion)

    observacion_catalogada = get_observacion_mapeo(observacion)

    # [2026-05-21] Si la misma cama vuelve a pasar por la misma sesion,
    # se conserva un solo registro y se actualiza su ultimo estado.
    # 2026-06-01: asegura atomic en creación/actualización de detalle de mapeo.
    with transaction.atomic():
        detalle, _ = DetalleMapeoCama.objects.update_or_create(
            sesion_mapeo=sesion,
            cama=cama,
            defaults={
                "fue_validada": fue_validada,
                "hubo_cambio": hubo_cambio,
                "estado_actual": asignacion.estado if asignacion else None,
                "ingreso_actual": asignacion.ingreso if asignacion else None,
                "tipo_accion": tipo_accion,
                "usuario": usuario,
                "observacion": observacion_catalogada,
                "fecha_hora": timezone.now(),
            },
        )
    return detalle


def _registrar_historial_mapeo(
    *,
    cama,
    estado_anterior,
    estado_nuevo,
    ingreso,
    usuario,
    observacion,
    sesion_mapeo=None,
    forzar_nuevo=False,
):
    """Registra historial de cama; en mapeo activo actualiza el último registro de la sesión.

    [2026-06-11] `forzar_nuevo=True` evita la fusion con el ultimo historial de la sesion
    (necesario para cierres intermedios en reasignaciones, p.ej. liberar a VACIA
    antes de registrar la nueva ocupacion en OCUPADA).
    """
    sesion = sesion_mapeo or _obtener_sesion_mapeo_activa(usuario)
    observacion_catalogada = get_observacion_mapeo(observacion)

    if not sesion or forzar_nuevo:
        # 2026-06-01: asegura atomic en creación de historial cuando no hay sesión activa.
        with transaction.atomic():
            return HistorialEstadoCama.objects.create(
                cama=cama,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                ingreso=ingreso,
                usuario=usuario,
                observacion=observacion_catalogada,
            )

    # [2026-05-21] Durante la sesión de mapeo se conserva un solo historial por cama.
    historial = (
        HistorialEstadoCama.objects.filter(
            cama=cama,
            usuario=usuario,
            fecha_hora__gte=sesion.fecha_inicio,
        )
        .order_by("-fecha_hora", "-id")
        .first()
    )

    # 2026-06-01: asegura atomic en actualización/creación del historial de sesión.
    with transaction.atomic():
        if historial:
            historial.estado_anterior = estado_anterior
            historial.estado_nuevo = estado_nuevo
            historial.ingreso = ingreso
            historial.observacion = observacion_catalogada
            historial.fecha_hora = timezone.now()
            historial.save(
                update_fields=[
                    "estado_anterior",
                    "estado_nuevo",
                    "ingreso",
                    "observacion",
                    "fecha_hora",
                ]
            )
            return historial

        return HistorialEstadoCama.objects.create(
            cama=cama,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            ingreso=ingreso,
            usuario=usuario,
            observacion=observacion_catalogada,
        )


# [2026-05-21] Helper de consistencia entre mapeo de camas e ingreso activo.
def _sincronizar_cama_en_ingreso_activo(*, ingreso_id=None, cama_id=None):
    """Alinea la cama del ingreso operativo con el estado resultante del mapeo."""
    ingreso_activo = _resolver_ingreso_operativo(ingreso_id=ingreso_id)
    if not ingreso_activo:
        return None

    if ingreso_activo.cama_id == cama_id:
        return ingreso_activo

    # [2026-05-21] Regla de consistencia: cada cambio de cama en mapeo
    # debe reflejarse en el ingreso activo del paciente.
    # 2026-06-01: asegura atomic en actualización de cama del ingreso activo.
    with transaction.atomic():
        ingreso_activo.cama_id = cama_id
        ingreso_activo.save(update_fields=["cama"])
    return ingreso_activo


# [2026-05-07] Helper para obtener IDs de camas mapeadas en sesión
def _camas_mapeadas_sesion(sesion):
    """Retorna ids de camas ya mapeadas en la sesion."""
    if not sesion:
        return []
    return list(
        DetalleMapeoCama.objects.filter(sesion_mapeo=sesion)
        .values_list("cama__numero_cama", flat=True)
        .distinct()
    )
