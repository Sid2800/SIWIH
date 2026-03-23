from enum import Enum, IntEnum


TIPOS_IMAGEN_PERMITIDOS = [
    "image/webp"
]

MAX_TAMANO_IMAGEN_MB = 15


class AccionImagen(str, Enum):
    STAY = "STAY"
    SYNC = "SYNC"
    DELETE = "DELETE"


class TipoPaciente(IntEnum):
    INTERNO = 1
    EXTERNO = 2

class AppValida(str, Enum):
    RX = "RX"
    REFERENCIA = "REFERENCIA"


class OrigenValido(str, Enum):
    EVALUACIONRXDETALLE = "EVALUACIONRXDETALLE"
    REFERENCIA = "REFERENCIA"
    RESPUESTA = "RESPUESTA"