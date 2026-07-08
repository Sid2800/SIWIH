"""
Utilidades de formateo (módulo s_exp).
=============================================================================

Formateo de fecha/hora en la zona horaria local del sistema.

IMPORTANTE sobre zona horaria:
  - La BD guarda en UTC (USE_TZ=True), igual que TODOS los módulos del sistema.
  - La conversión a hora local (America/Tegucigalpa, UTC-6) se hace SOLO al
    mostrar, con timezone.localtime(), idéntico a core/utils/utilidades_fechas.
"""
from django.utils import timezone


def fmt_local(dt, formato="%d/%m/%Y %H:%M"):
    """
    Formatea un datetime convirtiéndolo a la zona horaria local (UTC-6) en
    formato de 24 horas.

    Args:
        dt: datetime aware (o None).
        formato: patrón strftime (por defecto 24h: "%d/%m/%Y %H:%M").

    Returns:
        str: fecha/hora local formateada, o '' si dt es None.
    """
    if not dt:
        return ''
    # Si es aware, convertir a la zona local; si es naive, asumir que ya es local
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime(formato).strip()
