"""
Definiciones fijas de las encuestas (formatos del Ministerio / UAU).

De momento contiene la tabla de PUNTAJES y utilidades de calificación, tomadas
del script original `procesarencuestas.py`. Las definiciones de preguntas por
servicio (enunciado, opciones, número y sección) se agregan por fase, siguiendo
el ORDEN de los PDF oficiales.
"""

# ============ PUNTAJES POR RESPUESTA ============
# Solo las preguntas NUMERADAS cuentan para el consolidado. El puntaje se asigna
# por el texto de la respuesta (normalizado a mayúsculas y sin acentos triviales).
PUNTAJES = {
    'MUY BUENO': 100, 'BUENO': 85, 'REGULAR': 70, 'MALO': 55,
    'SI': 100, 'NO': 55, 'SÍ': 100,
    'TODOS': 100, 'ALGUNOS': 85, 'NINGUNO': 55,
    'PAGO': 55, 'NO PAGO': 100,
    'N/A': 100, 'NO APLICA': 100,
    'MUY CLARO': 100, 'CLARO': 85, 'POCO CLARO': 70,
    'NO RECIBI': 55, 'NO RECIBÍ': 55,
    'NO RECIBI INSTRUCCIONES': 55, 'NO RECIBÍ INSTRUCCIONES': 55,
    'DONACIÓN': 100, 'DONACION': 100,
}

ABREVIATURAS = {
    'MUY BUENO': 'MB', 'BUENO': 'B', 'REGULAR': 'R', 'MALO': 'M',
    'SI': 'Si', 'NO': 'No', 'SÍ': 'Si',
    'TODOS': 'T', 'ALGUNOS': 'A', 'NINGUNO': 'N',
    'PAGO': 'P', 'NO PAGO': 'NP',
    'N/A': 'N/A', 'NO APLICA': 'N/A',
    'MUY CLARO': 'MC', 'CLARO': 'C', 'POCO CLARO': 'PC',
    'NO RECIBI': 'NR', 'NO RECIBÍ': 'NR',
    'NO RECIBI INSTRUCCIONES': 'NR', 'NO RECIBÍ INSTRUCCIONES': 'NR',
    'DONACIÓN': 'D', 'DONACION': 'D',
}


def normalizar(respuesta):
    """Normaliza una respuesta: recorta y trata 'No Aplica' como 'N/A'."""
    if respuesta is None:
        return 'N/A'
    r = str(respuesta).strip()
    return 'N/A' if r.upper() == 'NO APLICA' else r


def puntaje_de(respuesta):
    """Puntaje de una respuesta (100/85/70/55...). Por defecto 100 (N/A)."""
    return PUNTAJES.get(normalizar(respuesta).upper(), 100)


def abreviatura_de(respuesta):
    """Abreviatura de una respuesta para los reportes."""
    return ABREVIATURAS.get(normalizar(respuesta).upper(), str(respuesta))
