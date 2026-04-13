from enum import Enum


# Institución principal del sistema
HEAC_INSTITUCION_ID = 65

class UnidadID:
    ADMISION = 1
    IMAGENOLOGIA = 2
    REFERENCIA = 3
    SALA = 4

class AccionEstudio(str, Enum):
    KEEP = "KEEP"
    DELETE = "DELETE"

class UsoDependencia(str, Enum):
    GENERAL = "general"
    DEFUNCION = "defuncion"
    OBITO = "obito"

class LogApp:
    GENERAL = "general"
    PACIENTE = "paciente"
    INGRESOS = "ingresos"
    RX = "rx"
    REFERENCIAS = "referencias"
    REPORTE = "reportes"
    AUTH = "auth"
    TOKEN = "token"
    MEDIA = "media"
    REPLICACION = "replicacion"
    EXPEDIENTE = "expediente"
    ATENCION = "atencion"


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


# Indicadores de edad
INDICADOR_DIAS = "2"
INDICADOR_MESES = "3"
INDICADOR_ANIOS = "4"

# Rango edad fértil
EDAD_FERTIL_MIN = 10
EDAD_FERTIL_MAX = 49

GENERO_FEMENINO = "M"



