from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime

def validar_informe(informe, permitidos):
    try:
        informe = int(informe)
        if informe in permitidos:
            return informe
    except:
        pass
    raise ValueError("El informe especificado no es válido.")