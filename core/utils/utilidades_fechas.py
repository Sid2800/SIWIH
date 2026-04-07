from datetime import datetime, timedelta, date, time
from django.core.exceptions import ValidationError
from core.validators.fecha_validator import validar_fecha
from core.constants.domain_constants import INDICADOR_ANIOS, INDICADOR_DIAS, INDICADOR_MESES 
import platform
import locale
from django.utils import timezone
import calendar

MESES_ES = [
        "",  # índice 0 no se usa
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


@staticmethod
def mes_nombre(numero_mes, upper=False):
        """
        Retorna el nombre del mes en español según el número.
        Ejemplo: 3 -> 'Marzo'
        Si upper=True -> 'MARZO'
        """
        try:
            nombre = MESES_ES[int(numero_mes)]
        except (ValueError, IndexError):
            return ""

        return nombre.upper() if upper else nombre


def configurar_locale():
    """Configura el locale dependiendo del sistema operativo."""
    try:
        if platform.system() == "Windows":
            locale.setlocale(locale.LC_TIME, "Spanish_Spain.1252")
        else:
            locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
    except locale.Error:
        # Evita fallos en servidores sin locale español configurado
        pass


def calcular_edad_texto(fecha_nacimiento):
    hoy = datetime.now()
    # Si viene como date, convertir a datetime
    if isinstance(fecha_nacimiento, date):
        fecha_nac = datetime(fecha_nacimiento.year, fecha_nacimiento.month, fecha_nacimiento.day)
    else:
        fecha_nac = datetime.strptime(fecha_nacimiento, "%Y-%m-%d")

    anios = hoy.year - fecha_nac.year
    meses = hoy.month - fecha_nac.month
    dias = hoy.day - fecha_nac.day

    if dias < 0:
        # primer día del mes actual
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)

        dias += ultimo_dia_mes_anterior.day
        meses -= 1

    if meses < 0:
        anios -= 1
        meses += 12

    partes = []
    if anios > 0:
        partes.append(f"{anios} {'año' if anios == 1 else 'años'}")
    if meses > 0:
        partes.append(f"{meses} {'mes' if meses == 1 else 'meses'}")
    if dias > 0:
        partes.append(f"{dias} {'día' if dias == 1 else 'días'}")

    return ", ".join(partes) if partes else "0 días"


def obtener_edad_con_indicador(fecha_nacimiento):
    hoy = datetime.now()
    fecha_nac = datetime.strptime(fecha_nacimiento, "%Y-%m-%d")
    
    if hoy.date() == fecha_nac.date():
        return "1", "1"
    # Inicializar diferencias
    anios = hoy.year - fecha_nac.year
    meses = hoy.month - fecha_nac.month
    dias = hoy.day - fecha_nac.day
    
    # Ajuste de días negativos
    if dias < 0:
        # primer día del mes actual
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        dias += ultimo_dia_mes_anterior.day
        meses -= 1

    # Ajuste de meses negativos
    if meses < 0:
        anios -= 1
        meses += 12

    # Construir el resultado como string
    if anios > 0:
        numero = anios
        indicador=INDICADOR_ANIOS
    elif meses > 0:
        numero = meses
        indicador=INDICADOR_MESES
    elif dias > 0:
        numero = dias
        indicador=INDICADOR_DIAS
    return str(numero), str(indicador)


def formatear_fecha2(fecha, formato='%d %b %y - %H:%M'):
    if fecha:
        configurar_locale()
        return timezone.localtime(fecha).strftime(formato)
    return ""


def formatear_fecha(fecha):
    if not fecha:
        return ""

    configurar_locale()

    try:
        if isinstance(fecha, datetime):
            local_dt = timezone.localtime(fecha)
        else:
            local_dt = timezone.localtime(datetime.fromisoformat(fecha))

        return local_dt.strftime("%A %d de %B del %Y, %H:%M").encode('utf-8').decode('utf-8')
    except (ValueError, TypeError):
        return "Fecha inválida"


def formatear_hora(fecha):
    if not fecha:
        return ""

    configurar_locale()

    try:
        if isinstance(fecha, datetime):
            local_dt = timezone.localtime(fecha)
        else:
            local_dt = timezone.localtime(datetime.fromisoformat(fecha))
        return local_dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return "Hora inválida"


def formatear_fecha_simple(fecha):
    if isinstance(fecha, (datetime, date)):
        configurar_locale()
        return fecha.strftime("%d %B de %Y")
    raise ValueError("La fecha proporcionada no es válida.")


def formatear_fecha_dd_mm_yyyy_hh_mm(fecha):
    if not fecha:
        return ""

    configurar_locale()

    try:
        if isinstance(fecha, datetime):
            local_dt = timezone.localtime(fecha)
        else:
            local_dt = timezone.localtime(datetime.fromisoformat(fecha))

        return local_dt.strftime("%d/%m/%Y-%H:%M")
    except (ValueError, TypeError):
        return "Fecha inválida"


def formatear_fecha_dd_mm_yyyy(fecha, usar_timezone=True):
    if not fecha:
        return ""

    configurar_locale()

    try:
        if isinstance(fecha, datetime):
            dt = fecha
        elif isinstance(fecha, date):
            dt = datetime.combine(fecha, time.min)
        elif isinstance(fecha, str):
            try:
                d = date.fromisoformat(fecha)
                dt = datetime.combine(d, time.min)
            except ValueError:
                dt = datetime.fromisoformat(fecha)
        else:
            return "Fecha inválida"

        if usar_timezone:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            dt = timezone.localtime(dt)

        return dt.strftime("%d/%m/%Y")

    except Exception:
        return "Fecha inválida"



def generar_rango_mes(mes: int, anio: int):
    """
    Devuelve el rango de fechas timezone-aware para un mes específico.
    Retorna (inicio, fin):
        - inicio: 1 del mes a las 00:00:00
        - fin: último día del mes a las 23:59:59.999999
    """

    if not (1 <= mes <= 12):
        raise ValueError("El mes debe estar entre 1 y 12.")

    # Primer día del mes
    fecha_ini_date = date(anio, mes, 1)

    # Último día del mes
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_fin_date = date(anio, mes, ultimo_dia)

    # Convertir ambos a datetime aware
    fecha_ini = timezone.make_aware(datetime.combine(fecha_ini_date, time.min))
    fecha_fin = timezone.make_aware(datetime.combine(fecha_fin_date, time.max))

    return fecha_ini, fecha_fin


def convertir_rango_fechas(fecha_ini_str: str, fecha_fin_str: str):
    """
    Convierte dos strings 'YYYY-MM-DD' a un rango de fechas timezone-aware.
    Realiza validaciones: formato, fecha futura, fecha inicial > final.
    """

    try:
        # Convertir los strings a date
        fecha_ini_date = datetime.strptime(fecha_ini_str, "%Y-%m-%d").date()
        fecha_fin_date = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()

        # Reutilizar  validador
        validar_fecha(fecha_ini_date)
        validar_fecha(fecha_fin_date)

    except ValidationError as e:
        # Convertir ValidationError → ValueError para las vistas API
        raise ValueError(str(e))
    except ValueError:
        # Error de formato YYYY-MM-DD
        raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD.")

    if fecha_ini_date > fecha_fin_date:
        raise ValueError("La fecha inicial no puede ser mayor que la fecha final.")

    hoy = timezone.localdate()
    if fecha_fin_date > hoy:
        raise ValueError("La fecha final no puede ser mayor que la fecha actual.")

    # Convertir a datetime aware
    fecha_ini = timezone.make_aware(datetime.combine(fecha_ini_date, time.min))
    fecha_fin = timezone.make_aware(datetime.combine(fecha_fin_date, time.max))

    return fecha_ini, fecha_fin


def filtro_rango_fecha(campo, inicio, fin):
    """
    Devuelve un diccionario dinámico para filtros Django:
    { "campo__range": (inicio, fin) }
    """
    return {f"{campo}__range": (inicio, fin)}