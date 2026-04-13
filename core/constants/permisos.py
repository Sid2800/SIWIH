

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
ATENCION_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
ATENCION_VISUALIZACION_UNIDADES = ["Admision","Sala"]


# -----------------------------
# PERMISOS APP EXPEDIENTE
# -----------------------------

# Acceso de solo visualización (listar, obtener modo lectura)
EXPEDIENTE_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
EXPEDIENTE_VISUALIZACION_UNIDADES = ["Admision"]


# -----------------------------
# PERMISOS APP IMAGENOLOGIA
# -----------------------------

# Acceso de edición (Add, Inactivar)
IMAGENOLOGIA_EDITOR_ROLES = ["admin", "digitador"]
IMAGENOLOGIA_EDITOR_UNIDADES = ["Imagenologia"]

# Acceso de solo visualización / edición parcial (Edit, Listar)
IMAGENOLOGIA_VISUALIZACION_ROLES = ["admin", "digitador", "directivo","visitante"]
IMAGENOLOGIA_VISUALIZACION_UNIDADES = ["Imagenologia", "DIRECTIVOS","Sala"]


# -----------------------------
# PERMISOS APP INGRESO
# -----------------------------

# Acceso de edición
INGRESO_EDITOR_ROLES = ["admin", "digitador"]
INGRESO_EDITOR_UNIDADES = ["Admision"]

# Acceso de visualización / auditoría
INGRESO_VISUALIZACION_ROLES = ["admin", "digitador", "directivo", "visitante"]
INGRESO_VISUALIZACION_UNIDADES = ["Admision","Sala"]


# -----------------------------
# PERMISOS APP PACINETE
# -----------------------------


# Permisos Paciente
PACIENTE_EDITOR_ROLES = ['admin', 'digitador']
PACIENTE_EDITOR_UNIDADES = ['Admision']

PACIENTE_VISUALIZACION_ROLES = ['admin', 'digitador', 'directivo','visitante']
PACIENTE_VISUALIZACION_UNIDADES = ['Admision', 'Imagenologia','Sala']

PACIENTE_DISPENSACION_ROLES = ['admin', 'directivo']
PACIENTE_DISPENSACION_UNIDADES = ['Admision', 'Imagenologia']


# -----------------------------
# PERMISOS APP REFERECINA
# -----------------------------
REFERENCIA_EDITOR_ROLES = ['admin', 'digitador']
REFERENCIA_EDITOR_UNIDADES = ['Referencia']


# Acceso de solo visualización / edición parcial (Edit, Listar)
REFERENCIA_VISUALIZACION_ROLES = ["admin", "digitador", "auditor"]
REFERENCIA_VISUALIZACION_UNIDADES = ["Referencia", "DIRECTIVOS"]


# -----------------------------
# PERMISOS APP S_EXP
# -----------------------------

# Acceso de administración (aprobar, rechazar, monitorear, devoluciones, reportes)
S_EXP_ADMIN_ROLES = ['exp_admin', 'admin']
S_EXP_ADMIN_UNIDADES = ['Admision', 'DIRECTIVOS']

# Acceso de usuario solicitante (buscar, solicitar, seguimiento)
S_EXP_USUARIO_ROLES = ['exp_admin', 'exp_solicitante', 'admin']
S_EXP_USUARIO_UNIDADES = ['Admision', 'DIRECTIVOS', 'Sala', 'Imagenologia', 'Referencia']
