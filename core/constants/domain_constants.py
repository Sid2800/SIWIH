from enum import Enum


# Institución principal del sistema
HEAC_INSTITUCION_ID = 65

# ============================================================================
# ExpedienteUbicacion
# IDs fijos del catálogo de ubicaciones físicas del expediente.
# Estos registros se crean durante la instalación inicial del sistema y son
# utilizados para validar y actualizar la ubicación actual del expediente.
# ============================================================================
EXP_UBICA_ADMISION_ID = 1
"""Ubicación física: Admisión."""

EXP_UBICA_ESTADISTICA_ID = 32
"""Ubicación física: Estadística (digitación posterior al egreso)."""

# ============================================================================
# ExpedientePrestamoEstado
# IDs fijos del catálogo de estados de préstamo de expedientes.
# Utilizados para determinar la disponibilidad del expediente.
# ============================================================================
PRESTAMO_ESTADO_ACTIVO_ID = 3 # id prestado en pretamod de la app prestamis
APARTADO_ESTADO_ACTIVO_ID = 2 # id prestado en pretamod de la app prestamis
DISPONIBLE_ESTADO_ACTIVO_ID = 1 # id prestado en pretamod de la app prestamis






class MotivoEstadoExpediente:
    """
    Motivos que explican el estado físico actual del expediente.
    """

    RESGUARDO = "RESGUARDO"
    HOSPITALIZACION = "HOSPITALIZACIÓN"
    DIGITALIZACION = "DIGITALIZACIÓN"
    ATENCION_AMBULATORIA = "ATENCIÓN AMBULATORIA"
    PRESTAMO = "PRÉSTAMO"
    APARTADO = "APARTADO"
    NO_LOCALIZADO = "NO LOCALIZADO"


class UnidadID:
    ADMI = 1
    RX = 2
    UAU = 3
    SALA = 4

class AccionEstudio(str, Enum):
    KEEP = "KEEP"
    DELETE = "DELETE"

class UsoUnidadC(str, Enum):
    GENERAL = "general"
    DEFUNCION = "defuncion"
    OBITO = "obito"

class LogApp:
    GENERAL = "general"
    PACIENTE = "paciente"
    INGRESOS = "ingresos"
    # [2026-06-26 LOG] Canal dedicado para trazas del flujo de mapeo de camas.
    MAPEO_CAMAS = "mapeo_camas"
    RX = "rx"
    REFERENCIAS = "referencias"
    REPORTE = "reportes"
    AUTH = "auth"
    TOKEN = "token"
    MEDIA = "media"
    REPLICACION = "replicacion"
    EXPEDIENTE = "expediente"
    ATENCION = "atencion"
    AGENDA = "agenda"
    
    S_EXP = "s_exp"          # Solicitud/Préstamo de Expedientes
    EGRESOS = "egresos"      # Censo de egresos hospitalarios

class EstadoTemporalPeriodo(str, Enum):
    FUTURO = "FUTURO"
    EN_EJECUCION = "EN_EJECUCION"
    FINALIZADO = "FINALIZADO"

class AccionImpactoPeriodoLaboral(str, Enum):
    FRAGMENTACION_PERIODO = "FRAGMENTACION_PERIODO"
    REDUCCION_FINAL = "REDUCCION_FINAL"
    REDUCCION_INICIAL = "REDUCCION_INICIAL"
    ABSORSION_PERIODO = "ABSORSION_PERIODO"

class TipoCambioFechaPeriodo:
    SIN_CAMBIO = "SIN_CAMBIO"
    AMPLIACION = "AMPLIACION"
    REDUCCION = "REDUCCION"
"""
# Salas excluidas para reportes / lógica clínica
SALAS_EXCLUIDAS = [
    714,  # aislado covid
    200,  # aislado covid
    512,  # aislado gine (se consigna como Gine)
    114,  # aislado medicina
    206,
    308,
    310,  # cirugía pediátrica
    201,  # medicina hombres/mujeres juntos
    711,  # puerperio adolescente normal
    708,  # puerperio normal
    713,  # puerperio quirúrgico
    706,  # puerperio quirúrgico patológico
    709,  # puerperio vaginal patológico
    712,  # séptico aislado
    707,  # amenaza de aborto
    705,  # embarazo patológico
]

# Servicios auxiliares externos
SERVICIOS_AUX_EXTERNOS = [
    3,  # CESAMO
    4   # otros hospitales
]
"""

# Indicadores de edad
INDICADOR_DIAS = "2"
INDICADOR_MESES = "3"
INDICADOR_ANIOS = "4"

# Rango edad fértil
EDAD_FERTIL_MIN = 10
EDAD_FERTIL_MAX = 49

GENERO_FEMENINO = "M"



