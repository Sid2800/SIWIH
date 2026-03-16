

# -----------------------------
# PERMISOS APP CORE
# -----------------------------

# Acceso de edición (por ejemplo mantenimiento del sistema)
CORE_EDITOR_ROLES = ["admin"]
CORE_EDITOR_UNIDADES = ["Admision"]



# -----------------------------
# PERMISOS APP ATENCION
# -----------------------------

# Acceso de edición (guardar, registrar, recepcion)
ATENCION_EDITOR_ROLES = ["admin", "digitador"]
ATENCION_EDITOR_UNIDADES = ["Admision"]

# Acceso de solo visualización (listar, obtener modo lectura)
ATENCION_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "auditor"]
ATENCION_VISUALIZACION_UNIDADES = ["Admision","DIRECTIVOS","Sala"]


# -----------------------------
# PERMISOS APP EXPEDIENTE
# -----------------------------

# Acceso de solo visualización (listar, obtener modo lectura)
EXPEDIENTE_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "auditor"]
EXPEDIENTE_VISUALIZACION_UNIDADES = ["Admision","DIRECTIVOS"]


# -----------------------------
# PERMISOS APP IMAGENOLOGIA
# -----------------------------

# Acceso de edición (Add, Inactivar)
IMAGENOLOGIA_EDITOR_ROLES = ["admin", "digitador"]
IMAGENOLOGIA_EDITOR_UNIDADES = ["Imagenologia"]

# Acceso de solo visualización / edición parcial (Edit, Listar)
IMAGENOLOGIA_VISUALIZACION_ROLES = ["admin", "digitador", "auditor","visitante"]
IMAGENOLOGIA_VISUALIZACION_UNIDADES = ["Imagenologia", "DIRECTIVOS","Sala"]


# -----------------------------
# PERMISOS APP INGRESO
# -----------------------------

# Acceso de edición
INGRESO_EDITOR_ROLES = ["admin", "digitador"]
INGRESO_EDITOR_UNIDADES = ["Admision"]

# Acceso de visualización / auditoría
INGRESO_VISUALIZACION_ROLES = ["admin", "digitador", "auditor","visitante"]
INGRESO_VISUALIZACION_UNIDADES = ["Admision", "DIRECTIVOS","Sala"]


# -----------------------------
# PERMISOS APP PACINETE
# -----------------------------


# Permisos Paciente
PACIENTE_EDITOR_ROLES = ['admin', 'digitador']
PACIENTE_EDITOR_UNIDADES = ['Admision']

PACIENTE_VISUALIZACION_ROLES = ['admin', 'digitador', 'auditor','visitante']
PACIENTE_VISUALIZACION_UNIDADES = ['Admision', 'Imagenologia', 'DIRECTIVOS','Sala']

PACIENTE_DISPENSACION_ROLES = ['admin', 'auditor']
PACIENTE_DISPENSACION_UNIDADES = ['Admision', 'Imagenologia', 'DIRECTIVOS']


# -----------------------------
# PERMISOS APP REFERECINA
# -----------------------------
REFERENCIA_EDITOR_ROLES = ['admin', 'digitador']
REFERENCIA_EDITOR_UNIDADES = ['Referencia']


# Acceso de solo visualización / edición parcial (Edit, Listar)
REFERENCIA_VISUALIZACION_ROLES = ["admin", "digitador", "auditor"]
REFERENCIA_VISUALIZACION_UNIDADES = ["Referencia", "DIRECTIVOS"]