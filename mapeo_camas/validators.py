# 2026-06-04: validadores de request para flujos POST de mapeo_camas.

from django.core.exceptions import ValidationError

from core.validators.main_validator import validar_entero_positivo


def validar_ids_movimiento(cama_origen_id, cama_destino_id):
    """Valida IDs de origen/destino y evita movimientos hacia la misma cama."""
    cama_origen_id = validar_entero_positivo(cama_origen_id, "cama_origen_id")
    cama_destino_id = validar_entero_positivo(cama_destino_id, "cama_destino_id")
    if cama_origen_id == cama_destino_id:
        raise ValidationError("La cama destino debe ser diferente a la cama origen.")
    return cama_origen_id, cama_destino_id


def validar_cama_id(cama_id, nombre_campo="cama_id"):
    """Valida que cama_id sea entero positivo para requests POST."""
    return validar_entero_positivo(cama_id, nombre_campo)


def validar_accion_mapeo(accion, acciones_validas):
    """Valida que la accion solicitada pertenezca al catálogo permitido."""
    if accion not in acciones_validas:
        raise ValidationError("Accion de mapeo no valida.")
    return accion


def validar_servicios_ids_mapeo(servicio_ids):
    """Valida y normaliza servicio_ids para iniciar sesión de mapeo."""
    # 2026-06-09: prioriza validación en validators (con core.validators) antes de consultas ORM.
    if not isinstance(servicio_ids, list):
        raise ValidationError("Debe indicar una lista valida de servicios.")

    servicios_ids_normalizados = []
    for servicio_id in servicio_ids:
        servicios_ids_normalizados.append(validar_entero_positivo(servicio_id, "servicio_id"))

    servicios_ids_normalizados = sorted(set(servicios_ids_normalizados))
    if not servicios_ids_normalizados:
        raise ValidationError("Debe seleccionar al menos un servicio para iniciar el mapeo.")
    return servicios_ids_normalizados


def validar_id_opcional(valor, nombre_campo):
    """Valida ID opcional; retorna None cuando no viene en el request."""
    if valor in (None, ""):
        return None
    return validar_entero_positivo(valor, nombre_campo)


def validar_ingreso_requerido_para_ocupada(estado_codigo, ingreso_id):
    """En estado OCUPADA se exige ingreso_id explícito."""
    if estado_codigo == "OCUPADA" and not ingreso_id:
        raise ValidationError("Para asignar una cama OCUPADA debe indicar el ingreso.")
    return ingreso_id


def validar_transicion_vacia_a_prealta(estado_anterior_codigo, estado_codigo):
    """Bloquea transición inválida VACIA -> PRE_ALTA antes de persistir."""
    if estado_anterior_codigo == "VACIA" and estado_codigo == "PRE_ALTA":
        raise ValidationError(
            "Una cama vacia no puede pasar a pre-alta. Debe iniciarse como ocupada o permanecer vacia."
        )
