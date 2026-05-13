#!/usr/bin/env python
"""
Script para debuggear permisos de un usuario específico.
Uso: python debug_permisos.py <username>
"""

import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SIWI.settings')
django.setup()

from django.contrib.auth import get_user_model
from usuario.models import PerfilUnidad
from core.constants.permisos import (
    MAPEO_CAMAS_VISUALIZACION_ROLES,
    MAPEO_CAMAS_VISUALIZACION_UNIDADES,
    MAPEO_CAMAS_EDITOR_ROLES,
    MAPEO_CAMAS_EDITOR_UNIDADES,
)

User = get_user_model()

if len(sys.argv) < 2:
    print("Uso: python debug_permisos.py <username>")
    sys.exit(1)

username = sys.argv[1]

try:
    usuario = User.objects.get(username=username)
except User.DoesNotExist:
    print(f"❌ Usuario '{username}' no encontrado")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"DEBUG DE PERMISOS: {usuario.username}")
print(f"{'='*60}\n")

print(f"Datos del usuario:")
print(f"  - ID: {usuario.id}")
print(f"  - Email: {usuario.email}")
print(f"  - Es superusuario: {usuario.is_superuser}")
print(f"  - Está activo: {usuario.is_active}\n")

# Obtener perfiles de unidad del usuario
perfiles = PerfilUnidad.objects.filter(usuario=usuario).select_related('servicio_unidad')

print(f"Perfiles de Unidad registrados: {perfiles.count()}")
for perfil in perfiles:
    unidad_nombre = perfil.servicio_unidad.nombre_unidad if perfil.servicio_unidad else "SIN UNIDAD"
    unidad_corto = perfil.servicio_unidad.nombre_corto_unidad if perfil.servicio_unidad else "N/A"
    alcance = perfil.get_alcance_display() if hasattr(perfil, 'get_alcance_display') else str(perfil.alcance)
    print(f"  - Rol: {perfil.rol} | Unidad: {unidad_nombre} ({unidad_corto}) | Alcance: {alcance}")

if not perfiles.exists():
    print(f"  ⚠️  No tiene perfiles de unidad asignados")

print(f"\n{'='*60}")
print(f"VALIDACIÓN DE ACCESO A MAPEO_CAMAS")
print(f"{'='*60}\n")

print(f"Requerimientos para VISUALIZACIÓN del mapa:")
print(f"  Roles requeridos: {MAPEO_CAMAS_VISUALIZACION_ROLES}")
print(f"  Unidades requeridas: {MAPEO_CAMAS_VISUALIZACION_UNIDADES}\n")

# Verificar visualización
tiene_rol_visualizacion = perfiles.filter(rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES).exists()
tiene_unidad_visualizacion = perfiles.filter(
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_VISUALIZACION_UNIDADES
).exists()

print(f"✓ Tiene rol válido para visualización: {tiene_rol_visualizacion}")
print(f"✓ Tiene unidad + rol válidos para visualización: {tiene_unidad_visualizacion}")

if usuario.is_superuser:
    print(f"\n✅ ACCESO PERMITIDO (superusuario)")
elif tiene_unidad_visualizacion:
    print(f"\n✅ ACCESO PERMITIDO")
else:
    print(f"\n❌ ACCESO DENEGADO")
    print(f"\nMotivo:")
    if not tiene_rol_visualizacion:
        print(f"  - No tiene ningún rol en {MAPEO_CAMAS_VISUALIZACION_ROLES}")
    if tiene_rol_visualizacion and not tiene_unidad_visualizacion:
        print(f"  - Tiene un rol válido pero no está en la unidad {MAPEO_CAMAS_VISUALIZACION_UNIDADES}")

print(f"\n{'='*60}")
print(f"Requerimientos para EDICIÓN del mapa:")
print(f"  Roles requeridos: {MAPEO_CAMAS_EDITOR_ROLES}")
print(f"  Unidades requeridas: {MAPEO_CAMAS_EDITOR_UNIDADES}\n")

tiene_rol_editor = perfiles.filter(rol__in=MAPEO_CAMAS_EDITOR_ROLES).exists()
tiene_unidad_editor = perfiles.filter(
    rol__in=MAPEO_CAMAS_EDITOR_ROLES,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_EDITOR_UNIDADES
).exists()

print(f"✓ Tiene rol válido para edición: {tiene_rol_editor}")
print(f"✓ Tiene unidad + rol válidos para edición: {tiene_unidad_editor}")

if usuario.is_superuser:
    print(f"\n✅ ACCESO PERMITIDO (superusuario)")
elif tiene_unidad_editor:
    print(f"\n✅ ACCESO PERMITIDO")
else:
    print(f"\n❌ ACCESO DENEGADO")
    print(f"\nMotivo:")
    if not tiene_rol_editor:
        print(f"  - No tiene ningún rol en {MAPEO_CAMAS_EDITOR_ROLES}")
    if tiene_rol_editor and not tiene_unidad_editor:
        print(f"  - Tiene un rol válido pero no está en la unidad {MAPEO_CAMAS_EDITOR_UNIDADES}")

print(f"\n{'='*60}\n")
