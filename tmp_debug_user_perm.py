import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","SIWI.settings")
import django
django.setup()

from django.contrib.auth.models import User
from usuario.models import PerfilUnidad, AlcanceUsuario
from core.constants.permisos import MAPEO_CAMAS_VISUALIZACION_ROLES, MAPEO_CAMAS_VISUALIZACION_UNIDADES

username = "ffffffffffffffffff"
print("username:", username)
print("roles req:", MAPEO_CAMAS_VISUALIZACION_ROLES)
print("unidades req:", MAPEO_CAMAS_VISUALIZACION_UNIDADES)

try:
    u = User.objects.get(username=username)
except User.DoesNotExist:
    print("ERROR: usuario no existe")
    raise SystemExit(0)

print("user.id:", u.id)
print("is_active:", u.is_active)
print("is_superuser:", u.is_superuser)
print("is_staff:", u.is_staff)

qs_all = PerfilUnidad.objects.filter(usuario=u).select_related("servicio_unidad")
print("perfiles total:", qs_all.count())
for p in qs_all:
    unidad = getattr(p.servicio_unidad, "nombre_corto_unidad", None)
    print(" -", {"rol": p.rol, "alcance": p.alcance, "alcance_label": p.get_alcance_display(), "unidad": unidad, "unidad_repr": str(p.servicio_unidad)})

q_global = PerfilUnidad.objects.filter(
    usuario=u,
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    alcance=AlcanceUsuario.GLOBAL,
)

q_unidad = PerfilUnidad.objects.filter(
    usuario=u,
    rol__in=MAPEO_CAMAS_VISUALIZACION_ROLES,
    alcance=AlcanceUsuario.UNIDAD,
    servicio_unidad__nombre_corto_unidad__in=MAPEO_CAMAS_VISUALIZACION_UNIDADES,
)

print("match GLOBAL:", q_global.exists(), "count=", q_global.count())
print("match UNIDAD:", q_unidad.exists(), "count=", q_unidad.count())

# posibles desajustes de texto
qs_similar = PerfilUnidad.objects.filter(usuario=u, alcance=AlcanceUsuario.UNIDAD).values_list("rol", "servicio_unidad__nombre_corto_unidad")
print("pares rol/unidad del usuario:", list(qs_similar))
print("roles normalizados usuario:", sorted({(r or "").strip().lower() for r,_ in qs_similar}))
print("roles normalizados req:", sorted({(r or "").strip().lower() for r in MAPEO_CAMAS_VISUALIZACION_ROLES}))
print("unidades normalizadas usuario:", sorted({(un or "").strip().upper() for _,un in qs_similar}))
print("unidades normalizadas req:", sorted({(un or "").strip().upper() for un in MAPEO_CAMAS_VISUALIZACION_UNIDADES}))
