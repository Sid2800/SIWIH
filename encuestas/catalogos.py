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
    'CLARIDAD4': ['Muy Claro', 'Claro', 'Poco Claro', 'N/A'],
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


# ---------------------------------------------------------------------------
# CONSULTA EXTERNA (21 preguntas numeradas). Orden del PDF oficial.
# ---------------------------------------------------------------------------
CONSULTA_EXTERNA_PREGUNTAS = [
    {'codigo': 'p1', 'tipo': 'radio', 'numero': 1, 'opciones': 'MBRM',
     'texto': '¿Cómo considera el tiempo de espera para su cita programada en consulta externa?'},
    {'codigo': 'p2', 'tipo': 'radio', 'numero': 2, 'opciones': 'MBRM',
     'texto': '¿Cómo considera el tiempo que esperó desde que llegó hasta que fue atendido por el médico en la consulta?'},
    {'codigo': 'p3', 'tipo': 'radio', 'numero': 3, 'opciones': 'SINO_NA',
     'texto': '¿El profesional que le brindó la consulta le explicó con palabras claras su estado de salud?'},
    {'codigo': 'p4', 'tipo': 'radio', 'numero': 4, 'opciones': 'SINO_NA',
     'texto': '¿Considera usted que le resolvieron su problema/estado de salud?'},
    {'codigo': 'p5', 'tipo': 'radio', 'numero': 5, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ENFERMERÍA?'},
    {'codigo': 'p6', 'tipo': 'radio', 'numero': 6, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal MÉDICO?'},
    {'codigo': 'p7', 'tipo': 'radio', 'numero': 7, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ADMISIÓN Y ARCHIVO?'},
    {'codigo': 'p8', 'tipo': 'radio', 'numero': 8, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de LABORATORIO?'},
    {'codigo': 'p9', 'tipo': 'radio', 'numero': 9, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la amabilidad e interés del personal de RAYOS X? (Si aplica)'},
    {'codigo': 'p10', 'tipo': 'radio', 'numero': 10, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la amabilidad e interés del personal de VIGILANCIA?'},
    {'codigo': 'p11', 'tipo': 'radio', 'numero': 11, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la ayuda que le brindó el personal de la Unidad de ATENCIÓN AL USUARIO?'},
    {'codigo': 'p12', 'tipo': 'radio', 'numero': 12, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la limpieza de los pasillos de la consulta externa y del consultorio?'},
    {'codigo': 'p13', 'tipo': 'radio', 'numero': 13, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció las instalaciones del hospital?'},
    {'codigo': 'p14', 'tipo': 'radio', 'numero': 14, 'opciones': 'SINO_NA',
     'texto': '¿Los equipos médicos utilizados para su atención se encontraban en buen estado?'},
    {'codigo': 'p15', 'tipo': 'radio', 'numero': 15, 'opciones': 'SINO_NA',
     'texto': '¿Fueron suficientes los insumos (materiales) utilizados para su atención?'},
    {'codigo': 'meds', 'tipo': 'radio_simple', 'opciones': 'SINO',
     'texto': '¿Le indicaron medicamentos? (Si la respuesta es "No", pasar a la pregunta 19)'},
    {'codigo': 'p16', 'tipo': 'radio', 'numero': 16, 'opciones': 'MEDS',
     'texto': '¿Le dieron en la farmacia los medicamentos que le indicaron?'},
    {'codigo': 'recuerdaNoBrindados', 'tipo': 'texto',
     'texto': '¿Recuerda cuáles no le brindaron?'},
    {'codigo': 'p17', 'tipo': 'radio', 'numero': 17, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció el tiempo de espera para recibir sus medicamentos en farmacia?'},
    {'codigo': 'tiempoFarmacia', 'tipo': 'texto',
     'texto': 'Si contestó Regular o Malo, ¿cuánto tiempo estimado?'},
    {'codigo': 'p18', 'tipo': 'radio', 'numero': 18, 'opciones': 'CLARIDAD',
     'texto': '¿Qué tan claras fueron las instrucciones que le proporcionó el personal de farmacia sobre cómo tomar sus medicamentos?'},
    {'codigo': 'p19', 'tipo': 'radio', 'numero': 19, 'opciones': 'PAGO',
     'texto': '¿Realizó algún pago por la atención recibida?'},
    {'codigo': 'tipoPago', 'tipo': 'texto',
     'texto': 'Si fue Pago, especifique el tipo de pago:'},
    {'codigo': 'p20', 'tipo': 'radio', 'numero': 20, 'opciones': 'SINO',
     'texto': '¿Después de la consulta, inmediatamente le dieron su cita?'},
    {'codigo': 'citaExplicacion', 'tipo': 'texto',
     'texto': 'Si respondió No, especifique:'},
    {'codigo': 'p21', 'tipo': 'radio', 'numero': 21, 'opciones': 'SINO',
     'texto': '¿Recomendaría nuestro hospital?'},
    {'codigo': 'explicacion', 'tipo': 'texto',
     'texto': 'Si respondió No, explique por qué:'},
    {'codigo': 'comentarios', 'tipo': 'texto', 'texto': 'Comentarios:'},
]

SECCIONES_CONSULTA_EXTERNA = {
    'Tiempo': [1, 2, 17],
    'Personal': [3, 5, 6, 7, 8, 9, 10, 11, 18],
    'Infraestructura_Insumos': [12, 13, 14, 15],
    'Procesos': [4, 16, 19, 20],
    'Recomendacion': [21],
}

SUBSERVICIOS_CONSULTA_EXTERNA = [
    'Pediatría', 'Cirugía', 'Psicología', 'Odontología',
    'Medicina Interna', 'Medicina General', 'Planificación Familiar',
]


# ---------------------------------------------------------------------------
# HOSPITALIZACIÓN (26 preguntas numeradas). Orden del PDF oficial.
# ---------------------------------------------------------------------------
HOSPITALIZACION_PREGUNTAS = [
    {'codigo': 'p1', 'tipo': 'radio', 'numero': 1, 'opciones': 'MBRM',
     'texto': '¿Cómo le parecieron las instalaciones de la unidad del hospital?'},
    {'codigo': 'p2', 'tipo': 'radio', 'numero': 2, 'opciones': 'SINO_NA',
     'texto': '¿Cuándo ingresó, le informaron las reglas de la sala de hospitalización?'},
    {'codigo': 'p3', 'tipo': 'radio', 'numero': 3, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la limpieza e higiene de la habitación y sanitarios?'},
    {'codigo': 'p4', 'tipo': 'radio', 'numero': 4, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la ropa y otros insumos (materiales) para su aseo diario?'},
    {'codigo': 'p5', 'tipo': 'radio', 'numero': 5, 'opciones': 'SINO_NA',
     'texto': '¿Le informaron sobre las pruebas o procedimientos que le realizaron?'},
    {'codigo': 'p6', 'tipo': 'radio', 'numero': 6, 'opciones': 'SINO_NA',
     'texto': '¿Cuándo se le examinó respetaron su privacidad?'},
    {'codigo': 'p7', 'tipo': 'radio', 'numero': 7, 'opciones': 'SINO_NA',
     'texto': '¿El personal de salud le informaba diariamente sobre su enfermedad o estado de salud?'},
    {'codigo': 'p8', 'tipo': 'radio', 'numero': 8, 'opciones': 'SINO_NA',
     'texto': '¿Le orientaron claramente sobre lo que tiene que hacer al salir del hospital?'},
    {'codigo': 'p9', 'tipo': 'radio', 'numero': 9, 'opciones': 'PAGO',
     'texto': '¿Realizó algún pago o donación por la atención recibida?'},
    {'codigo': 'tipoPago', 'tipo': 'texto', 'texto': 'Si fue Pago, especifique:'},
    {'codigo': 'p10', 'tipo': 'radio', 'numero': 10, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ENFERMERÍA?'},
    {'codigo': 'p11', 'tipo': 'radio', 'numero': 11, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal MÉDICO?'},
    {'codigo': 'p12', 'tipo': 'radio', 'numero': 12, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad e interés del personal de ADMISIÓN Y ARCHIVO?'},
    {'codigo': 'p13', 'tipo': 'radio', 'numero': 13, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la amabilidad e interés del personal de RAYOS X?'},
    {'codigo': 'p14', 'tipo': 'radio', 'numero': 14, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció la amabilidad e interés del personal de VIGILANCIA?'},
    {'codigo': 'p15', 'tipo': 'radio', 'numero': 15, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad del personal que le brindó los alimentos?'},
    {'codigo': 'p16', 'tipo': 'radio', 'numero': 16, 'opciones': 'MBRM',
     'texto': '¿Cómo considera la amabilidad del personal de LABORATORIO? (Si aplica)'},
    {'codigo': 'meds', 'tipo': 'radio_simple', 'opciones': 'SINO',
     'texto': '¿Le dieron medicamentos? (Si la respuesta es "No", pasar a la pregunta 20)'},
    {'codigo': 'p17', 'tipo': 'radio', 'numero': 17, 'opciones': 'MEDS',
     'texto': '¿Le dieron en la farmacia los medicamentos que le indicaron?'},
    {'codigo': 'p18', 'tipo': 'radio', 'numero': 18, 'opciones': 'MBRM',
     'texto': '¿Cómo le pareció el tiempo de espera para recibir sus medicamentos en farmacia?'},
    {'codigo': 'p19', 'tipo': 'radio', 'numero': 19, 'opciones': 'CLARIDAD',
     'texto': '¿Qué tan claras fueron las instrucciones que le proporcionó el personal de farmacia sobre cómo tomar sus medicamentos?'},
    {'codigo': 'p20', 'tipo': 'radio', 'numero': 20, 'opciones': 'SINO',
     'texto': '¿Recomendaría nuestro hospital?'},
    {'codigo': 'seccion_operado', 'tipo': 'seccion',
     'texto': 'En caso de haber sido operado'},
    {'codigo': 'p21', 'tipo': 'radio', 'numero': 21, 'opciones': 'SINO_NA',
     'texto': '¿Firmó usted el documento de "consentimiento informado" para ser operado?'},
    {'codigo': 'p22', 'tipo': 'radio', 'numero': 22, 'opciones': 'SINO_NA',
     'texto': '¿Le explicó el médico el procedimiento quirúrgico que le iban a hacer?'},
    {'codigo': 'seccion_obstetricia', 'tipo': 'seccion',
     'texto': 'Las siguientes preguntas son exclusivas de Obstetricia'},
    {'codigo': 'p23', 'tipo': 'radio', 'numero': 23, 'opciones': 'CLARIDAD4',
     'texto': '¿Qué tan claras fueron las explicaciones que recibió sobre los cuidados que debe seguir en casa, tanto para usted como para su recién nacido?'},
    {'codigo': 'p24', 'tipo': 'radio', 'numero': 24, 'opciones': 'SINO_NA',
     'texto': '¿Le informaron sobre las señales de peligro que debe vigilar en el posparto, tanto para usted como para el recién nacido?'},
    {'codigo': 'p25', 'tipo': 'radio', 'numero': 25, 'opciones': 'SINO_NA',
     'texto': '¿Durante su estadía en Labor y Parto y Obstetricia recibió información y apoyo con la lactancia materna?'},
    {'codigo': 'p26', 'tipo': 'radio', 'numero': 26, 'opciones': 'SINO_NA',
     'texto': '¿Recibió información sobre los diferentes métodos para planificar o espaciar sus embarazos?'},
    {'codigo': 'observacion', 'tipo': 'texto',
     'texto': 'OBSERVACIÓN: en caso de respuestas insatisfechas, anote el número de pregunta y el comentario.'},
]

SECCIONES_HOSPITALIZACION = {
    'Tiempo': [18],
    'Personal': [2, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26],
    'Infraestructura_Insumos': [1, 3, 4],
    'Procesos': [9, 19, 20],
    'Recomendacion': [20],
}

SUBSERVICIOS_HOSPITALIZACION = [
    'Obstetricia', 'Medicina Hombre', 'Medicina Mujer', 'Ginecología',
    'Neonatología', 'Cirugía Hombre', 'Cirugía Mujer', 'Pediatría',
]

# Encuestas programadas por subservicio (metas mensuales).
PROGRAMADAS_HOSPITALIZACION = {
    'Obstetricia': 141, 'Medicina Hombre': 15, 'Medicina Mujer': 15,
    'Ginecología': 15, 'Neonatología': 18, 'Cirugía Hombre': 15,
    'Cirugía Mujer': 15, 'Pediatría': 34,
}


# ---------------------------------------------------------------------------
# USUARIO EXTERNO (obstetricia). NO entra al consolidado; puntajes por
# confirmar (Sí=100/No=55 por defecto). Orden del PDF oficial.
# ---------------------------------------------------------------------------
USUARIO_EXTERNO_PREGUNTAS = [
    {'codigo': 'causa', 'tipo': 'radio_simple',
     'opciones': None, 'opciones_lista': [
         'Parto Vaginal o Cesárea', 'Planificación Familiar',
         'Complicación Obstétrica', 'Complicación Neonatal'],
     'texto': 'Causa de la atención:'},
    {'codigo': 'p1a', 'tipo': 'radio', 'opciones': 'SINO_NA',
     'texto': '1A. A su llegada al hospital, ¿le atendieron de acuerdo a su condición? (Inmediatamente, en caso de emergencia. No aplica si la atención fue en la C.E.)'},
    {'codigo': 'p1b', 'tipo': 'radio', 'opciones': 'SINO_NA',
     'texto': '1B. A su llegada al hospital, ¿le atendieron de acuerdo a su condición? (Dentro de 30-60 minutos, si no había urgencias. No aplica si fue en la C.E.)'},
    {'codigo': 'p2', 'tipo': 'radio', 'numero': 2, 'opciones': 'SINO_NA',
     'texto': 'El personal que le atendió, ¿le explicó con palabras claras y fáciles de entender su estado de salud o la de su recién nacido?'},
    {'codigo': 'p3', 'tipo': 'radio', 'numero': 3, 'opciones': 'SINO_NA',
     'texto': 'El personal del hospital que le atendió, ¿le brindó un buen trato?'},
    {'codigo': 'p4', 'tipo': 'radio', 'numero': 4, 'opciones': 'SINO_NA',
     'texto': 'Durante la atención recibida, ¿se respetó su privacidad?'},
    {'codigo': 'p5', 'tipo': 'radio', 'numero': 5, 'opciones': 'SINO',
     'texto': 'Durante la atención recibida, ¿le parecieron cómodas las salas/áreas del hospital?'},
    {'codigo': 'p6', 'tipo': 'radio', 'numero': 6, 'opciones': 'SINO',
     'texto': '¿Estaban limpias las diferentes áreas/salas donde se brindó la atención?'},
    {'codigo': 'p7', 'tipo': 'radio', 'numero': 7, 'opciones': 'SINO_NA',
     'texto': 'Si le dieron indicaciones en una receta, ¿están escritas en forma clara para usted?'},
    {'codigo': 'p8', 'tipo': 'radio', 'numero': 8, 'opciones': 'SINO_NA',
     'texto': 'El personal que le atendió, ¿le explicó los cuidados a seguir en su casa, para usted o para su recién nacido?'},
    {'codigo': 'p9', 'tipo': 'radio', 'numero': 9, 'opciones': 'SINO_NA',
     'texto': '¿Le informaron sobre las señales de peligro que debe vigilar en el posparto, tanto para usted como para el recién nacido?'},
    {'codigo': 'p10', 'tipo': 'radio', 'numero': 10, 'opciones': 'SINO_NA',
     'texto': '¿La atención fue gratuita?'},
    {'codigo': 'p11', 'tipo': 'radio', 'numero': 11, 'opciones': 'SINO_NA',
     'texto': 'Si la atención fue por Planificación Familiar y se decidió por un método, ¿obtuvo el método que solicitó?'},
    {'codigo': 'p12', 'tipo': 'radio', 'numero': 12, 'opciones': 'SINO_NA',
     'texto': 'En términos generales, ¿usted siente que le resolvieron su problema de salud o el motivo de búsqueda de la atención?'},
    {'codigo': 'p13', 'tipo': 'radio', 'numero': 13, 'opciones': 'SINO_NA',
     'texto': 'En términos generales, ¿usted se siente satisfecha con la atención recibida?'},
    {'codigo': 'p14', 'tipo': 'radio', 'numero': 14, 'opciones': 'SINO_NA',
     'texto': '¿Recomendaría usted a otras personas acudir a este hospital?'},
    {'codigo': 'comentario', 'tipo': 'texto', 'texto': 'Comentario:'},
]


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
    'CE': {
        'servicio': 'CE',
        'nombre': 'Consulta Externa',
        'subservicios': SUBSERVICIOS_CONSULTA_EXTERNA,
        'pide_tipo_encuestado': True,
        'pide_identidad': True,
        'programadas': 34,
        'consolidado': True,
        'secciones': SECCIONES_CONSULTA_EXTERNA,
        'preguntas': CONSULTA_EXTERNA_PREGUNTAS,
    },
    'HOSP': {
        'servicio': 'HOSP',
        'nombre': 'Hospitalización',
        'subservicios': SUBSERVICIOS_HOSPITALIZACION,
        'pide_tipo_encuestado': True,
        'pide_identidad': True,
        'programadas': PROGRAMADAS_HOSPITALIZACION,
        'consolidado': True,
        'secciones': SECCIONES_HOSPITALIZACION,
        'preguntas': HOSPITALIZACION_PREGUNTAS,
    },
    'EXT': {
        'servicio': 'EXT',
        'nombre': 'Usuario Externo',
        'subservicios': [],
        'pide_tipo_encuestado': False,
        'pide_identidad': False,
        'programadas': None,
        'consolidado': False,           # NO entra al consolidado
        'secciones': {},
        'preguntas': USUARIO_EXTERNO_PREGUNTAS,
    },
}


def definicion(servicio):
    """Devuelve la definición de una encuesta por su código de servicio."""
    return ENCUESTAS.get(servicio)


def opciones_de(item):
    """Lista de opciones de un item de pregunta (o [] si no es de opción)."""
    if item.get('opciones_lista'):
        return item['opciones_lista']
    return OPCIONES.get(item.get('opciones'), []) if item.get('opciones') else []
