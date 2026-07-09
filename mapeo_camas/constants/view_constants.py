"""Constantes usadas por vistas de mapeo_camas."""

# 2026-06-09: centraliza catálogos inline de acciones/estados para reducir acoplamiento en vistas.
ACCIONES_MAPEO_VALIDAS = (
    "CONFIRMAR",
    "CONFIRMAR_ALTA",
    "CANCELAR_PREALTA",
    "CAMBIO_TRASLADO",
    "ASIGNACION",
    "ALTA_FORZADA",
)

ACCIONES_MAPEO_PERMITIDAS_ROL_RESTRINGIDO = (
    "CONFIRMAR",
    "CAMBIO_TRASLADO",
    "CONFIRMAR_ALTA",
    "ALTA_FORZADA",
)

ESTADOS_OCUPADA_PREALTA = ("OCUPADA", "PRE_ALTA")
# [2026-07-08] FUERA_SERVICIO permitido para rol INTENTOS_CAMBIO en edición directa
ESTADOS_EDICION_DIRECTA_ROL_RESTRINGIDO = ("PRE_ALTA", "VACIA", "FUERA_SERVICIO")
ESTADOS_MANTIENEN_INGRESO_SIN_NUEVO = ("PRE_ALTA", "ALTA")

# 2026-06-09: observaciones operativas centralizadas para correccion de reasignacion en mapeo.
OBS_REASIGNACION_SIN_ORIGEN_HISTORIAL = (
    "Paciente observado no encontrado en otra cama durante reasignacion; cama liberada a VACIA"
)
OBS_REASIGNACION_SIN_ORIGEN_DETALLE = (
    "No se encontro al paciente en otra cama; se corrige cama a VACIA"
)

# 2026-06-09: discrepancia fisica detectada durante mapeo (sin alta ni traslado).
OBS_AJUSTE_MAPEO_SIN_ALTA = (
    "Actualizacion de cama en mapeo por discrepancia fisica (sin alta)"
)

# 2026-06-22: observaciones específicas para transición de ingreso a OCUPADA.
OBS_INGRESO_DESDE_CONSULTA_EXTERNA_A_OCUPADA = (
    "Ingreso: cambio de CONSULTA_EXTERNA a OCUPADA"
)
OBS_INGRESO_DESDE_PREALTA_A_OCUPADA = (
    "Ingreso: cambio de PRE_ALTA a OCUPADA"
)

# [2026-06-26 SCOPE] Neonatologia se maneja como alcance aislado dentro de Pediatria.
MAPEO_CAMAS_SERVICIO_PEDIATRIA_ID = 300
MAPEO_CAMAS_SALA_NEONATOLOGIA_ID = 360
MAPEO_CAMAS_SERVICIO_VIRTUAL_NEONATOLOGIA_ID = 300360
MAPEO_CAMAS_SERVICIO_VIRTUAL_NEONATOLOGIA_NOMBRE = "NEONATOLOGIA"
