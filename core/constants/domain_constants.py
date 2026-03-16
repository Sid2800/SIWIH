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