# ============================================================================
# CONFIGURACIÓN CENTRAL DE PERMISOS
# ============================================================================
#
# El sistema SIWIh utiliza un esquema de autorización basado en dos criterios:
#
# 1. Rol del usuario
#    Determina el nivel funcional que posee dentro del sistema.
#
#       - admin       : Acceso administrativo completo.
#       - digitador   : Usuario operativo con permisos de edición.
#       - visitante   : Usuario de solo consulta.
#       - directivo   : Usuario con acceso global de consulta y supervisión.
#
#
# 2. Unidad del usuario
#    Determina el área organizacional a la que pertenece el empleado.
#    Se utilizan los nombres cortos registrados en ServicioUnidad.
#
#       ADMI  -> Admisión
#       ENF   -> Enfermería
#       RX    -> Imagenología
#       UAU   -> Unidad de Atención al Usuario
#       FARM  -> Farmacia
#       LAB   -> Laboratorio
#       RRHH  -> Talento Humano
#       CAL   -> Calidad
#       DIR   -> Dirección
#       EPI   -> Epidemiología
#
#
# Para que un usuario pueda ejecutar una acción normalmente debe cumplir:
#
#     • Tener uno de los roles permitidos.
#     • Pertenecer a una de las unidades autorizadas.
#
# Algunas excepciones utilizan ROLES_GLOBALES para otorgar acceso
# independientemente de la unidad asignada.
#
# Todas las constantes de este archivo son consumidas por el sistema
# de autorización mediante los decoradores y validadores de permisos.
# ============================================================================


# =============================================================================
# MODELO DE PERSONAL Y AUTORIZACIÓN DEL SISTEMA SIWIH
# =============================================================================
#
# El sistema SIWIH separa la información del empleado de la autorización de
# acceso al sistema. Esta separación permite representar correctamente la
# estructura organizacional del hospital y asignar permisos de manera flexible.
#
# 1. EMPLEADO
#    Representa a la persona (identidad, nombres, contacto, usuario, etc.).
#    No define permisos ni el acceso al sistema.
#
# 2. PERSONAL DE SALUD / PERSONAL NO CLÍNICO
#    Describe la relación laboral del empleado con el hospital.
#    Define aspectos como:
#       - Tipo de personal.
#       - Servicio o unidad a la que pertenece.
#       - Especialidad (cuando aplica).
#
#    Esta información responde a la pregunta:
#       ¿Qué es el empleado y dónde desempeña sus funciones?
#
# 3. PERFIL DE USUARIO
#    Define la autorización dentro del sistema SIWIH.
#    Es independiente de la información laboral del empleado y establece:
#
#       - Rol del sistema.
#       - Unidad de trabajo dentro de SIWIH.
#
#    Esta información responde a la pregunta:
#       ¿Qué puede hacer el usuario dentro del sistema?
#
# IMPORTANTE:
# La unidad asignada en el PerfilUsuario puede ser diferente a la unidad
# organizacional del empleado. Esto permite contemplar escenarios como:
#
#   • Personal que realiza funciones administrativas.
#   • Personal asignado temporalmente a otra área.
#   • Usuarios con responsabilidades distintas a su cargo institucional.
#
# Asimismo, los usuarios con roles de alcance global (por ejemplo: admin o
# directivo) no deben tener una unidad asignada en su PerfilUsuario (NULL),
# ya que sus permisos aplican sobre todas las unidades del hospital.
#
# Esta separación garantiza un modelo flexible, escalable y alineado con la
# organización real del Hospital Dr. Enrique Aguilar Cerrato.
# =============================================================================

TODAS_LAS_UNIDADES = [
      "ADMI",
      "ENF",
      "RX",
      "UAU",
      "FARM",
      "LAB",
      "RRHH",
      "CAL",
      "DIR",
      "EPI",
      "EST",
      "GCL",
      "TS",
   ]




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
ATENCION_EDITOR_UNIDADES = ["ADMI"]# Admisión

# Acceso de solo visualización (listar, obtener modo lectura)
ATENCION_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
ATENCION_VISUALIZACION_UNIDADES = [
   "ADMI",  # Admisión
   "ENF",   # Enfermería
   "LAB",   # Laboratorio
   "DIR",   # Dirección
   "EPI",   # Epidemiología
   "EST",   # Estadistica
   "UAU",
   "GCL",   #gestion clinica / medicos 
   "TS",
]


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
IMAGENOLOGIA_VISUALIZACION_UNIDADES = [
   "RX",    # Personal de Imagenología
   "ENF",   # Enfermería
   "LAB",   # Laboratorio (consulta clínica)
   "GCL",   #gestion clinica / medicos 

]


# -----------------------------
# PERMISOS APP INGRESO
# -----------------------------

# Acceso de edición
INGRESO_EDITOR_ROLES = ["admin", "digitador"]
INGRESO_EDITOR_UNIDADES = ["ADMI"]

# Acceso de visualización / auditoría
INGRESO_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
INGRESO_VISUALIZACION_UNIDADES = [
   "ADMI",  # Admisión
   "ENF",   # Enfermería
   "LAB",   # Laboratorio
   "DIR",   # DirecciónPACIENTE_VISUALIZACION_UNIDADES = TODAS_LAS_UNIDADES
   "EPI",   # Epidemiología
   "EST",   # Estadistica
   "UAU",
   "GCL",   #gestion clinica / medicos 
   "TS",    #trabajo social 
 

]


# -----------------------------
# PERMISOS APP PACINETE
# -----------------------------


# Permisos Paciente

# Acceso de edición
PACIENTE_EDITOR_ROLES = ["admin", "digitador"]
PACIENTE_EDITOR_UNIDADES = ["ADMI"]

# Acceso de visualización / auditoría
PACIENTE_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
PACIENTE_VISUALIZACION_UNIDADES = TODAS_LAS_UNIDADES


# Acceso a dispensaciones (consulta SALMI)
PACIENTE_DISPENSACION_ROLES = ["admin", "directivo"]
PACIENTE_DISPENSACION_UNIDADES = ["ADMI", "RX"]


PACIENTE_HISTORIAL_ROLES = ["admin", "digitador", "directivo",]
PACIENTE_HISTORIAL_UNIDADES = [
   "ADMI",  # Admisión
   "ENF",   # Enfermería
   "RX",    # Imagenología
   "LAB",   # Laboratorio
   "FARM",  # Farmacia
   "EST",   # Estadistica
   "UAU",
   "GCL",   #gestion clinica / medicos 
   "TS",    #trabajo social 

]


# -----------------------------
# PERMISOS APP REFERECINA
# -----------------------------
REFERENCIA_EDITOR_ROLES = ['admin', 'digitador']
REFERENCIA_EDITOR_UNIDADES = ['UAU']


# Acceso de solo visualización / edición parcial (Edit, Listar)
REFERENCIA_VISUALIZACION_ROLES = ["admin", "digitador", "directivo"]
REFERENCIA_VISUALIZACION_UNIDADES = ["UAU", "CAL", "EST"]



# -----------------------------
# PERMISOS APP REPORTES
# -----------------------------

# Acceso de visualización / generación de reportes
REPORTES_ROLES = [
   "admin",
   "digitador",
   "visitante",
   "directivo",
]

REPORTES_UNIDADES = [
   "ADMI",  # Admisión
   "ENF",   # Enfermería
   "RX",    # Imagenología
   "UAU",   # Unidad de Atención al Usuario
   "FARM",  # Farmacia
   "LAB",   # Laboratorio
   "RRHH",  # Talento Humano
   "CAL",   # Calidad
   "DIR",   # Dirección
   "EPI",   # Epidemiología
   "EST",   # Estadística
   "GCL",   #gestion clinica / medicos 
   "TS",    #trabajo social 

]


# ============================================================================
# ROLES GLOBALES
# ============================================================================
#
# Los roles definidos aquí tienen alcance institucional.
# Cuando un usuario posee uno de estos roles, el sistema puede omitir
# la validación de la unidad según la operación correspondiente.
#
# Ejemplo:
# Un usuario con rol "directivo" puede consultar información de todas
# las unidades autorizadas para consulta sin pertenecer a cada una de ellas.
#
#
# IMPORTANTE:
# Los usuarios con roles de alcance global NO deben tener una unidad asignada.
# La unidad debe permanecer en NULL, ya que estos roles tienen autorización
# institucional y sus permisos aplican sobre todas las unidades del hospital.
# Si se asigna una unidad a un usuario con alcance global, esta no será tomada
# como referencia para la autorización y puede generar configuraciones
# inconsistentes.
# ============================================================================

# los usauro de alcance gglbal pueden ser

ROLES_GLOBALES = ['directivo', 'admin']




# -----------------------------
# PERMISOS APP S_EXP    solo estan declarados no se usan
# -----------------------------

# Acceso de administración (aprobar, rechazar, monitorear, devoluciones, reportes)
S_EXP_ADMIN_ROLES = ['admin']
S_EXP_ADMIN_UNIDADES = ['ADMI']

# Acceso de usuario solicitante (buscar, solicitar, seguimiento)
S_EXP_SOLICITANTE_ROLES = ['admin', 'digitador', 'directivo']
S_EXP_SOLICITANTE_UNIDADES = [
   "ADMI",  # Admisión
   "DIR",   # Dirección
   "RX",    # Imagenología
   "UAU",   # Unidad de Atención al Usuario
   "ENF",   # Enfermería
   "FARM",  # Farmacia
   "LAB",   # Laboratorio
   "CAL",   # Calidad
   "EPI",   # Epidemiología
   "EST",   # Estadística
   "GCL",   #gestion clinica / medicos 
   "TS",    #trabajo social 

]
# remapeir todo los usaurios visitante admision a sus repectivos unidades 
# por ejemplo los usaurios de estadistica
# correjir SAla a enfermeria  los uaurios de unidad sala serian unioda enfermeria 
# correjir el texto de usaurio en menu para todos los usauiros no depender user si no de empleado. 
# incluso hacer un bloqueo mexin para los usuriuos sin empleado  y personal no clinico


# -----------------------------
# PERMISOS APP MAPEO_CAMAS
# -----------------------------

# [2026-06-22] Acceso de solo visualización al template del mapa de camas.
MAPEO_CAMAS_VISUALIZACION_ROLES = ["admin", "digitador", "visitante", "directivo"]
MAPEO_CAMAS_VISUALIZACION_UNIDADES = ["ADMI", 'ENF']

# [2026-05-18] Acceso para entrar y ejecutar flujo de mapeo.
MAPEO_CAMAS_MAPEAR_ROLES = ["admin", "digitador",]
MAPEO_CAMAS_MAPEAR_UNIDADES = ["ADMI"]

# [2026-05-18] Acceso para cambios manuales en el mapa (edición directa).
MAPEO_CAMAS_CAMBIOS_ROLES = []
MAPEO_CAMAS_CAMBIOS_UNIDADES = ["ADMI"]

# [2026-06-11] Ajuste operativo: el limite de intentos aplica.
MAPEO_CAMAS_INTENTOS_CAMBIO_ROLES = []
MAPEO_CAMAS_INTENTOS_CAMBIO_UNIDADES = ["ADMI"]

# Acceso de auditoría (historiales, detalle de historial)
# [2026-05-11] Visitante habilitado para visualizar templates de historial.
MAPEO_CAMAS_HISTORIALES_ROLES = []
MAPEO_CAMAS_HISTORIALES_UNIDADES = ["ADMI"]

# [2026-05-28] Acceso al dashboard operativo de KPIs/gráficas en tiempo real.
MAPEO_CAMAS_DASHBOARD_ROLES = []
MAPEO_CAMAS_DASHBOARD_UNIDADES = ["ADMI"]


# -----------------------------
# PERMISOS APP EQUIPOS
# -----------------------------
# EQ es una unidad de autorizacion, no un area fisica del hospital: agrupa a
# quienes mantienen el inventario. Un digitador solo entra si tiene un
# PerfilUnidad en EQ; admin y directivo pasan por su alcance GLOBAL.
#
# is_staff no concede acceso a este modulo. Solo cuentan rol mas unidad, o
# ser superusuario: is_staff abre el admin de Django, que es otra cosa.
#
# Las cuatro capacidades van separadas aunque hoy tres compartan roles. Asi
# se puede estrechar una sin tocar las demas: por ejemplo dejar la baja solo
# en manos de admin sin quitarle al tecnico el registro diario.

# Consultar el inventario sin modificarlo. Es donde llega el directivo.
EQUIPOS_VISUALIZACION_ROLES = ["admin", "digitador", "directivo"]
EQUIPOS_VISUALIZACION_UNIDADES = ["EQ"]

# Registrar y editar equipos, cambiar ubicacion o responsable, subir fotos.
EQUIPOS_EDICION_ROLES = ["admin", "digitador"]
EQUIPOS_EDICION_UNIDADES = ["EQ"]

# Mantener los catalogos de tipos, marcas y modelos.
EQUIPOS_CATALOGO_ROLES = ["admin", "digitador"]
EQUIPOS_CATALOGO_UNIDADES = ["EQ"]

# Tramitar la baja. Va aparte de la edicion porque no tiene vuelta atras:
# crea el registro, deja el equipo dado de baja y bloquea su edicion.
EQUIPOS_BAJA_ROLES = ["admin", "digitador"]
EQUIPOS_BAJA_UNIDADES = ["EQ"]
