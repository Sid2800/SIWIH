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


# ============ OPCIONES REUTILIZABLES ============
OPCIONES = {
    'MBRM': ['Muy Bueno', 'Bueno', 'Regular', 'Malo', 'N/A'],
    'SINO_NA': ['Sí', 'No', 'N/A'],
    'SINO': ['Sí', 'No'],
    'PAGO': ['Pago', 'No Pago', 'Donación'],
    'MEDS': ['Todos', 'Algunos', 'Ninguno', 'N/A'],
    'CLARIDAD': ['Muy Claro', 'Claro', 'Poco Claro', 'No Recibí Instrucciones', 'N/A'],
}


# ============ DEFINICIÓN DE PREGUNTAS ============
# Cada item es un dict con:
#   codigo   : identificador del campo (p1, p2, tipoPago, ...)
#   tipo     : 'radio' (numerada, cuenta consolidado) | 'radio_simple' (no cuenta,
#              p. ej. filtros) | 'texto' (respuesta abierta, no cuenta)
#   numero   : nº de la pregunta (solo en 'radio' numeradas)
#   texto    : enunciado
#   opciones : clave de OPCIONES (para radios)
#   nota     : ayuda opcional bajo el enunciado
#
# ORDEN y textos tomados del PDF oficial "ENCUESTAS EMERGENCIA 2026".
EMERGENCIA_PREGUNTAS = [
    {'codigo': 'p1', 'tipo': 'radio', 'numero': 1, 'opciones': 'MBRM',
     'texto': '¿Cómo califica la oportunidad con que fue atendido en la emergencia?'},
    {'codigo': 'p2', 'tipo': 'radio', 'numero': 2, 'opciones': 'MBRM',
     'texto': '¿Cómo considera el tiempo de espera desde que fue clasificado en TRIAJE hasta que fue atendido por el médico?'},
    {'codigo': 'p3', 'tipo': 'radio', 'numero': 3, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad, confianza y seguridad del personal que le brindó la atención?'},
    {'codigo': 'p4', 'tipo': 'radio', 'numero': 4, 'opciones': 'MBRM',
     'texto': '¿Cómo fue la información suministrada por el personal tratante?'},
    {'codigo': 'p5', 'tipo': 'radio', 'numero': 5, 'opciones': 'MBRM',
     'texto': '¿Considera que le resolvieron su problema/estado de salud?'},
    {'codigo': 'p6', 'tipo': 'radio', 'numero': 6, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal MÉDICO?'},
    {'codigo': 'p7', 'tipo': 'radio', 'numero': 7, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ENFERMERÍA?'},
    {'codigo': 'p8', 'tipo': 'radio', 'numero': 8, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ADMISIÓN Y ARCHIVO?'},
    {'codigo': 'p9', 'tipo': 'radio', 'numero': 9, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de VIGILANCIA?'},
    {'codigo': 'p10', 'tipo': 'radio', 'numero': 10, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la amabilidad e interés del personal de RAYOS X? (Si aplica)'},
    {'codigo': 'p11', 'tipo': 'radio', 'numero': 11, 'opciones': 'MBRM',
     'texto': '¿Cómo califica la presentación del personal de Emergencia?'},
    {'codigo': 'p12', 'tipo': 'radio', 'numero': 12, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la limpieza de los sanitarios y pasillos de la emergencia?'},
    {'codigo': 'p13', 'tipo': 'radio', 'numero': 13, 'opciones': 'PAGO',
     'texto': '¿Realizó algún pago por la atención recibida?'},
    {'codigo': 'tipoPago', 'tipo': 'texto',
     'texto': 'Si la respuesta es Pago, especifique el tipo de pago que realizó:'},
    {'codigo': 'p14', 'tipo': 'radio', 'numero': 14, 'opciones': 'SINO_NA',
     'texto': '¿Los equipos médicos utilizados para su atención se encontraban en buen estado?'},
    {'codigo': 'p15', 'tipo': 'radio', 'numero': 15, 'opciones': 'SINO_NA',
     'texto': '¿Fueron suficientes los insumos (materiales) utilizados para su atención?'},
    {'codigo': 'meds', 'tipo': 'radio_simple', 'opciones': 'SINO',
     'texto': '¿Le indicaron medicamentos? (Si la respuesta es "No", pasar a la pregunta 19)'},
    {'codigo': 'p16', 'tipo': 'radio', 'numero': 16, 'opciones': 'MEDS',
     'texto': '¿Le dieron en la farmacia los medicamentos que le indicaron?'},
    {'codigo': 'p17', 'tipo': 'radio', 'numero': 17, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció el tiempo de espera para recibir sus medicamentos en farmacia?'},
    {'codigo': 'tiempoFarmacia', 'tipo': 'texto',
     'texto': 'Si contestó Regular o Malo, ¿cuánto tiempo estimado?'},
    {'codigo': 'p18', 'tipo': 'radio', 'numero': 18, 'opciones': 'CLARIDAD',
     'texto': '¿Qué tan claras fueron las instrucciones que le proporcionó el personal de farmacia sobre cómo tomar sus medicamentos?'},
    {'codigo': 'p19', 'tipo': 'radio', 'numero': 19, 'opciones': 'SINO',
     'texto': '¿Recomendaría nuestro hospital?'},
    {'codigo': 'explicacion', 'tipo': 'texto',
     'texto': 'Si la respuesta es No, explique por qué:'},
    {'codigo': 'observacion', 'tipo': 'texto',
     'texto': 'OBSERVACIÓN: en caso de respuestas insatisfechas, anote el número de pregunta y el comentario.'},
]

SECCIONES_EMERGENCIA = {
    'Tiempo': [2, 17],
    'Personal': [1, 3, 4, 6, 7, 8, 9, 10, 11, 18],
    'Infraestructura_Insumos': [12, 14, 15],
    'Procesos': [5, 13, 16],
    'Recomendacion': [19],
}


# ============ REGISTRO DE ENCUESTAS ============
# Un solo lugar del que se alimentan el formulario, el guardado y los reportes.
ENCUESTAS = {
    'EMER': {
        'servicio': 'EMER',
        'nombre': 'Emergencia',
        'subservicios': ['Emergencia'],
        'pide_tipo_encuestado': True,   # Paciente/Familiar
        'pide_identidad': True,
        'programadas': 34,
        'consolidado': True,            # entra al consolidado mensual
        'secciones': SECCIONES_EMERGENCIA,
        'preguntas': EMERGENCIA_PREGUNTAS,
    },
}


def definicion(servicio):
    """Devuelve la definición de una encuesta por su código de servicio."""
    return ENCUESTAS.get(servicio)


def opciones_de(item):
    """Lista de opciones de un item de pregunta (o [] si no es de opción)."""
    return OPCIONES.get(item.get('opciones'), []) if item.get('opciones') else []
