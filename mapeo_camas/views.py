# 2026-05-29: views.py reorganizado en módulos (refactor E). Este archivo es
# una FACHADA que reexporta todos los símbolos públicos para preservar la
# compatibilidad con mapeo_camas/urls.py y cualquier import externo.
# Para tocar lógica concreta, edita el módulo correspondiente:
#   - _constants.py        : constantes de configuración
#   - _helpers.py          : helpers de formateo y resolución
#   - _sesion.py           : helpers de sesión + auditoría (historial/detalle)
#   - _permisos.py         : helpers de permisos + límite de intentos
#   - views_admin.py       : sincronización masiva y diagnóstico de permisos
#   - views_mapa.py        : mapa de camas + edición directa
#   - views_mapeo.py       : ciclo de sesión de mapeo
#   - views_historiales.py : historiales de auditoría
#   - views_dashboard.py   : dashboard operativo

from .views_admin import *  # noqa: F401,F403
from .views_dashboard import *  # noqa: F401,F403
from .views_historiales import *  # noqa: F401,F403
from .views_mapa import *  # noqa: F401,F403
from .views_mapeo import *  # noqa: F401,F403
