from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime

def validar_fecha(fecha, anio_minimo=2000, permitir_futuro=False, permitir_pasado=True):
    # Convertir a datetime si es date
    if isinstance(fecha, date) and not isinstance(fecha, datetime):
        fecha_dt = datetime.combine(fecha, datetime.min.time())
    else:
        fecha_dt = fecha

    hoy = timezone.localdate()

    if not permitir_futuro and fecha_dt.date() > hoy:
        raise ValidationError(
            "La fecha no puede ser mayor que la fecha actual."
        )

    if not permitir_pasado and fecha_dt.date() < hoy:
        raise ValidationError(
            "La fecha no puede ser menor que la fecha actual."
        )
    
    if fecha_dt.year < anio_minimo:
        raise ValidationError(f"La fecha no puede ser menor al año {anio_minimo}.")


def validar_rango_fechas(
        fecha_inicio,
        fecha_final,
        permitir_fin_igual_inicio=False
    ):
        # Validar relación entre fechas
        if permitir_fin_igual_inicio:

            if fecha_final < fecha_inicio:
                raise ValidationError(
                    "La fecha final no puede ser menor "
                    "que la fecha inicial."
                )

        else:

            if fecha_final <= fecha_inicio:
                raise ValidationError(
                    "La fecha final debe ser mayor "
                    "que la fecha inicial."
                )


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


def validar_horario(hora_inicio, hora_fin):

    try:
        hora_inicio = datetime.strptime(
            hora_inicio,
            "%H:%M"
        ).time()

        hora_fin = datetime.strptime(
            hora_fin,
            "%H:%M"
        ).time()

    except (ValueError, TypeError):
        raise ValidationError(
            "Formato de hora inválido."
        )

    if hora_fin <= hora_inicio:
        raise ValidationError(
            "La hora final debe ser mayor que la hora inicial."
        )

    return hora_inicio, hora_fin
