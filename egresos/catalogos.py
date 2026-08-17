"""
Listas fijas del formulario HC-13 (Hoja de Hospitalización).

Son opciones cerradas del formato impreso (no catálogos de BD). Se usan para el
autocompletado de "Causa de accidente o violencia" y "Lugar de accidente o
violencia", y como leyenda de "Condición de egreso" y "Razón de egreso" (donde
el usuario escribe el número) y "Personal que atendió el parto".

OJO: 'Condición de egreso' y 'Razón de egreso' se transcribieron de la imagen
y conviene que el usuario confirme las etiquetas exactas; cambiarlas aquí es
suficiente (no afecta el modelo).
"""

# Causa de accidente o violencia (autocompletado; texto libre permitido).
CAUSAS_ACCIDENTE = [
    "Otro motorizado",
    "Otro transporte",
    "Máquina",
    "Caída",
    "Incendio o explosión",
    "Fenómeno natural",
    "Accidente de agresión",
    "Intento de suicidio",
    "Exposición a sustancias nocivas",
    "Descarga eléctrica",
    "Contacto por agente físico (mano, calor)",
    "Otros",
]

# Lugar de accidente o violencia (autocompletado; texto libre permitido).
LUGARES_ACCIDENTE = [
    "Trabajo",
    "Vivienda",
    "Centro de estudios",
    "Recreación",
    "Deporte o diversión",
    "Vía pública",
    "Desconocido",
    "Otros",
]

# Condición de egreso: se muestra la leyenda y el usuario escribe el número.
CONDICIONES_EGRESO = {
    1: "Igual",
    2: "Mejorado(a)",
    3: "Curado(a)",
    4: "Fallecido < 48 horas",
    5: "Fallecido > 48 horas",
}

# Razón de egreso: leyenda + número.
RAZONES_EGRESO = {
    1: "Alta por mejoría",
    2: "Alta exigida / retiro voluntario",
    3: "Referido / trasladado",
    4: "Fallecido",
    5: "Fuga",
}

# Personal que atendió el parto (selección múltiple).
PERSONAL_PARTO = [
    "Estudiante",
    "Médico general",
    "Médico especialista",
    "Residente",
    "Auxiliar de enfermería",
    "Enfermero profesional",
    "Empírica / partera",
    "Extrahospitalario",
]
