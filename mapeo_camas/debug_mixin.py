"""
Script de debugging para investigar por qué UnidadRolRequiredMixin rechaza acceso.
Se ejecuta dentro de mapeo_camas sin modificar core/mixins.py.

Uso:
    python manage.py shell < mapeo_camas/debug_mixin.py
    # Luego copiar y pegar en la shell de Django
"""

import os
import django

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SIWI.settings")
django.setup()

from django.contrib.auth.models import User
from usuario.models import PerfilUnidad, AlcanceUsuario
from core.constants.permisos import (
    MAPEO_CAMAS_MAPEAR_ROLES,
    MAPEO_CAMAS_MAPEAR_UNIDADES,
)

# Usuario a debuggear
usuario_username = "ffffffffffffffffff"

try:
    usuario = User.objects.get(username=usuario_username)
except User.DoesNotExist:
    print(f"❌ Usuario {usuario_username} no existe")
    exit(1)

print(f"\n{'='*60}")
print(f"DEBUGGING: {usuario_username}")
print(f"{'='*60}")

# 1. Información básica
print(f"\n[1] Información del usuario:")
print(f"    - Username: {usuario.username}")
print(f"    - Email: {usuario.email}")
print(f"    - is_superuser: {usuario.is_superuser}")
print(f"    - is_staff: {usuario.is_staff}")

# 2. Permisos requeridos para mapeo_camas mapa
print(f"\n[2] Permisos REQUERIDOS para acceder a /mapeo-camas/:")
print(f"    - Roles: {MAPEO_CAMAS_MAPEAR_ROLES}")
print(f"    - Unidades: {MAPEO_CAMAS_MAPEAR_UNIDADES}")

# 3. Verificación SUPERUSUARIO
print(f"\n[3] Verificación SUPERUSUARIO:")
if usuario.is_superuser:
    print(f"    ✅ Es superusuario → ACCESO PERMITIDO")
else:
    print(f"    ❌ No es superusuario → continuar verificación")

# 4. Verificación GLOBAL
print(f"\n[4] Verificación GLOBAL:")
global_check = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_MAPEAR_ROLES,
    alcance=AlcanceUsuario.GLOBAL
)
print(f"    - Perfiles GLOBAL: {global_check.count()}")
for perfil in global_check:
    print(f"      • {perfil.rol} en {perfil.servicio_unidad.nombre_corto_unidad}")

if global_check.exists():
    print(f"    ✅ Tiene alcance GLOBAL → ACCESO PERMITIDO")
else:
    print(f"    ❌ No tiene alcance GLOBAL → continuar verificación")

# 5. Verificación UNIDAD
print(f"\n[5] Verificación UNIDAD:")
unidad_perfiles = PerfilUnidad.objects.filter(
    usuario=usuario,
    alcance=AlcanceUsuario.UNIDAD
)
print(f"    - Total de perfiles UNIDAD: {unidad_perfiles.count()}")
for perfil in unidad_perfiles:
    print(f"      • Rol: {perfil.rol} | Unidad: {perfil.servicio_unidad.nombre_corto_unidad}")

# 5a. Verificar si el rol está en los requeridos
print(f"\n[5a] Filtro por ROL REQUERIDO ({MAPEO_CAMAS_MAPEAR_ROLES}):")
perfiles_rol = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_MAPEAR_ROLES,
    alcance=AlcanceUsuario.UNIDAD
)
print(f"    - Perfiles con rol requerido: {perfiles_rol.count()}")
for perfil in perfiles_rol:
    print(f"      • Rol: {perfil.rol} | Unidad: {perfil.servicio_unidad.nombre_corto_unidad}")

# 5b. Verificar si la unidad está en las requeridas
print(f"\n[5b] Filtro por UNIDAD REQUERIDA ({MAPEO_CAMAS_MAPEAR_UNIDADES}):")
perfiles_unidad = PerfilUnidad.objects.filter(
    usuario=usuario,
    alcance=AlcanceUsuario.UNIDAD,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_MAPEAR_UNIDADES
)
print(f"    - Perfiles con unidad requerida: {perfiles_unidad.count()}")
for perfil in perfiles_unidad:
    print(f"      • Rol: {perfil.rol} | Unidad: {perfil.servicio_unidad.nombre_corto_unidad}")

# 5c. Verificación FINAL (ambas condiciones)
print(f"\n[5c] Verificación FINAL (ROL + UNIDAD):")
final_check = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_MAPEAR_ROLES,
    alcance=AlcanceUsuario.UNIDAD,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_MAPEAR_UNIDADES
)
print(f"    - Perfiles que cumplen AMBAS condiciones: {final_check.count()}")
for perfil in final_check:
    print(f"      • Rol: {perfil.rol} | Unidad: {perfil.servicio_unidad.nombre_corto_unidad}")

if final_check.exists():
    print(f"    ✅ ACCESO PERMITIDO → El usuario DEBERÍA poder acceder")
else:
    print(f"    ❌ ACCESO RECHAZADO → El usuario NO puede acceder")

# 6. CONCLUSIÓN
print(f"\n{'='*60}")
print(f"CONCLUSIÓN:")
print(f"{'='*60}")
if usuario.is_superuser:
    print(f"✅ Usuario DEBERÍA tener acceso (es superusuario)")
elif global_check.exists():
    print(f"✅ Usuario DEBERÍA tener acceso (alcance GLOBAL)")
elif final_check.exists():
    print(f"✅ Usuario DEBERÍA tener acceso (alcance UNIDAD con rol/unidad correctos)")
else:
    print(f"❌ Usuario NO puede tener acceso (falla todas las verificaciones)")
    print(f"\nProblemas posibles:")
    if not unidad_perfiles.exists():
        print(f"   1. No tiene NINGÚN PerfilUnidad asignado")
    elif not perfiles_rol.exists():
        print(f"   2. Su rol NO está en: {MAPEO_CAMAS_MAPEAR_ROLES}")
    elif not perfiles_unidad.exists():
        print(f"   3. Su unidad NO está en: {MAPEO_CAMAS_MAPEAR_UNIDADES}")
    else:
        print(f"   4. Error desconocido (consultar logs)")

print(f"\n")
