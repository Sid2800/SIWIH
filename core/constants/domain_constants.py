from enum import Enum

# Institución principal del sistema
HEAC_INSTITUCION_ID = 65

class UnidadID:
    ADMISION = 1
    IMAGENOLOGIA = 2
    REFERENCIA = 3
    DIRECTIVOS = 4
    SALA = 7

class AccionEstudio(str, Enum):
    KEEP = "KEEP"
    DELETE = "DELETE"

class LogApp:
    GENERAL = "general"
    PACIENTES = "pacientes"
    INGRESOS = "ingresos"
    RX = "rx"
    REFERENCIAS = "referencias"
    REPORTES = "reportes"
    AUTH = "auth"
    TOKEN = "token"
    MEDIA = "media"

