import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from django.contrib.auth import get_user_model
from usuario.models import PerfilUnidad
from core.constants.choices_constants import AlcanceUsuario
from core.constants.permisos import (
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)

User = get_user_model()
username = "ffffffffffffffffff"

try:
    usuario = User.objects.get(username=username)
except User.DoesNotExist:
    print(f"❌ Usuario '{username}' no encontrado")
    exit(1)

print(f"\n{'='*60}")
print(f"VALIDACIÓN EXACTA DEL MIXIN")
print(f"{'='*60}\n")

print(f"Usuario: {usuario.username}")
print(f"required_roles = {MAPEO_CAMAS_VISUALIZACION_ROLES}")
print(f"required_unidades = {MAPEO_CAMAS_VISUALIZACION_UNIDADES}\n")

# Prueba 1: Superusuario
print(f"1. ¿Es superusuario? {usuario.is_superuser}")

# Prueba 2: Alcance GLOBAL
print(f"\n2. Búsqueda GLOBAL:")
print(f"   AlcanceUsuario.GLOBAL = {AlcanceUsuario.GLOBAL}")
resultado_global = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    alcance=AlcanceUsuario.GLOBAL
)
print(f"   Resultados: {resultado_global.count()}")

# Prueba 3: Alcance UNIDAD
print(f"\n3. Búsqueda UNIDAD:")
print(f"   AlcanceUsuario.UNIDAD = {AlcanceUsuario.UNIDAD}")

perfiles_unidad = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    alcance=AlcanceUsuario.UNIDAD
)
print(f"   Resultados con rol correcto: {perfiles_unidad.count()}")

for perfil in perfiles_unidad:
    print(f"     - Rol: {perfil.rol}")
    print(f"       Unidad: {perfil.servicio_unidad}")
    print(f"       nombre_corto_unidad: {perfil.servicio_unidad.nombre_corto_unidad}")

# Prueba 4: Búsqueda completa (lo que hace el mixin)
print(f"\n4. BÚSQUEDA COMPLETA DEL MIXIN (lo que debería permitir acceso):")
resultado_final = PerfilUnidad.objects.filter(
    usuario=usuario,
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    alcance=AlcanceUsuario.UNIDAD,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_VISUALIZACION_UNIDADES
)
print(f"   Resultados: {resultado_final.count()}")
if resultado_final.exists():
    print(f"   ✅ ACCESO PERMITIDO por el mixin")
else:
    print(f"   ❌ ACCESO DENEGADO por el mixin")
    print(f"\n   Debugging:")
    
    # Verificar si existe la unidad
    print(f"   ¿Existe la unidad '{MAPEO_CAMAS_VISUALIZACION_UNIDADES[0]}'?")
    from servicio.models import Unidad
    unidades = Unidad.objects.filter(nombre_corto_unidad__in=MAPEO_CAMAS_VISUALIZACION_UNIDADES)
    print(f"   Unidades encontradas: {unidades.count()}")
    for u in unidades:
        print(f"     - {u.nombre_unidad} ({u.nombre_corto_unidad})")

print(f"\n{'='*60}\n")
