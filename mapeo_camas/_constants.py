# 2026-05-29: extraído de mapeo_camas/views.py en refactor E (split)
"""
Constantes de configuración operativa del flujo de mapeo de camas.

- MAX_CAMBIOS_CAMA: número máximo de movimientos permitidos por sala dentro
  de la ventana temporal, para usuarios que no son superadmin.
- VENTANA_LIMITE_CAMBIOS_SALA_HORAS: tamaño de la ventana de tiempo (horas)
  usada para contabilizar los cambios manuales y resetear el conteo.
- VENTANA_ALTAS_RECIENTES_HORAS: ventana para considerar altas recientes en
  el buscador de pacientes del mapa.
- OBSERVACION_*: textos fijos grabados en el historial; también se usan como
  criterio de filtrado al contar cambios por sala.
"""

MAX_CAMBIOS_CAMA = 5
VENTANA_LIMITE_CAMBIOS_SALA_HORAS = 24
VENTANA_ALTAS_RECIENTES_HORAS = 24

OBSERVACION_CAMBIO_MANUAL_MAPA = "Cambio manual desde mapa"
OBSERVACION_CAMBIO_MANUAL_MAPA_DETALLE = "Cambio manual desde mapa (detalle)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA = "Movimiento de paciente entre camas (mapa)"
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_DETALLE = "Movimiento de paciente entre camas (mapa detalle)"
OBSERVACION_CAMBIO_TRASLADO_MAPEO = "Cambio/traslado desde mapeo"
# Observacion para traslados de superadmin: queda registrado pero NO cuenta
# en _contar_cambios_manual_por_sala, por lo que no descuenta del límite.
OBSERVACION_MOVIMIENTO_PACIENTE_MAPA_SUPERADMIN = "Movimiento de paciente entre camas (superadmin)"
OBSERVACION_SESION_SIN_OBSERVACIONES = "Sin observaciones"

DETALLE_PAGE_SIZE_DEFAULT = 50
DETALLE_PAGE_SIZE_MAX = 200
