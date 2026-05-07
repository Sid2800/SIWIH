

# -----------------------------
# PERMISOS APP CORE
# -----------------------------

# Acceso de edición (por ejemplo mantenimiento del sistema)
CORE_EDITOR_ROLES = ["admin"]
CORE_EDITOR_UNIDADES = ["ADMI"]

# -----------------------------
# PERMISOS APP ATENCION
# -----------------------------

# Acceso de edición (guardar, registrar, recepcion)
ATENCION_EDITOR_ROLES = ["admin", "digitador"]
ATENCION_EDITOR_UNIDADES = ["ADMI"]

# Acceso de solo visualización (listar, obtener modo lectura)
ATENCION_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
ATENCION_VISUALIZACION_UNIDADES = ["ADMI","SALA"]


# -----------------------------
# PERMISOS APP EXPEDIENTE
# -----------------------------

# Acceso de solo visualización (listar, obtener modo lectura)
EXPEDIENTE_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
EXPEDIENTE_VISUALIZACION_UNIDADES = ["ADMI"]


# -----------------------------
# PERMISOS APP IMAGENOLOGIA
# -----------------------------

# Acceso de edición (Add, Inactivar)
IMAGENOLOGIA_EDITOR_ROLES = ["admin", "digitador"]
IMAGENOLOGIA_EDITOR_UNIDADES = ["RX"]

# Acceso de solo visualización / edición parcial (Edit, Listar)
IMAGENOLOGIA_VISUALIZACION_ROLES = ["admin", "digitador", "directivo","visitante"]
IMAGENOLOGIA_VISUALIZACION_UNIDADES = ["RX","SALA"]


# -----------------------------
# PERMISOS APP INGRESO
# -----------------------------

# Acceso de edición
INGRESO_EDITOR_ROLES = ["admin", "digitador"]
INGRESO_EDITOR_UNIDADES = ["ADMI"]

# Acceso de visualización / auditoría
INGRESO_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
INGRESO_VISUALIZACION_UNIDADES = ["ADMI","SALA"]


# -----------------------------
# PERMISOS APP PACINETE
# -----------------------------


# Permisos Paciente
PACIENTE_EDITOR_ROLES = ['admin', 'digitador']
PACIENTE_EDITOR_UNIDADES = ['ADMI']

PACIENTE_VISUALIZACION_ROLES = ['admin', 'digitador','visitante', 'directivo']
PACIENTE_VISUALIZACION_UNIDADES = ['ADMI', 'RX','SALA']

PACIENTE_DISPENSACION_ROLES = ['admin', 'directivo']
PACIENTE_DISPENSACION_UNIDADES = ['ADMI', 'RX']


# -----------------------------
# PERMISOS APP REFERECINA
# -----------------------------
REFERENCIA_EDITOR_ROLES = ['admin', 'digitador']
REFERENCIA_EDITOR_UNIDADES = ['UAU']


# Acceso de solo visualización / edición parcial (Edit, Listar)
REFERENCIA_VISUALIZACION_ROLES = ["admin", "digitador", "directivo"]
REFERENCIA_VISUALIZACION_UNIDADES = ["UAU"]




# los usauro de alcance gglbal pueden ser 

ROLES_GLOBALES = ['directivo', 'admin']