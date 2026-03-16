from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime

def validar_fecha(fecha, anio_minimo=2000, permitir_futuro=False):
    # Convertir a datetime si es date
    if isinstance(fecha, date) and not isinstance(fecha, datetime):
        fecha_dt = datetime.combine(fecha, datetime.min.time())
    else:
        fecha_dt = fecha

    if not permitir_futuro and fecha_dt.date() > timezone.localdate():
        raise ValidationError("La fecha no puede ser mayor que la fecha actual.")
    
    if fecha_dt.year < anio_minimo:
        raise ValidationError(f"La fecha no puede ser menor al año {anio_minimo}.")


def validar_anio(anio):
    anio_actual = date.today().year
    try:
        anio = int(anio)
        if 2000 <= anio <= anio_actual:
            return anio
    except:
        pass
    raise ValueError(f"El año debe estar entre 2000 y {anio_actual}.")


def validar_mes(mes):
    try:
        mes = int(mes)
        if 1 <= mes <= 12:
            return mes
    except:
        pass
    raise ValueError("El mes debe estar entre 1 y 12.")