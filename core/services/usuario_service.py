from django.contrib.auth.models import User
from usuario.models import PerfilUnidad
from core.constants.domain_constants import UnidadID
from core.constants.choices_constants import AlcanceUsuario

from django.db import connections

class UsuarioService:
    def __init__(self, usuario=None):
        self.usuario = usuario

    @staticmethod
    def obtener_usuarios_activos():
        usuarios = User.objects.filter(is_active=True).values('id', 'username')
        return list(usuarios)

    @staticmethod
    def pertenece_unidad(usuario, unidad_id):
        perfiles = PerfilUnidad.objects.filter(usuario=usuario).values_list('servicio_unidad_id', flat=True)
        return int(unidad_id) in perfiles
    
    @staticmethod
    def es_global_roles(usuario, roles=None):
        if usuario.is_superuser:
            return True

        if not roles:
            return False

        return PerfilUnidad.objects.filter(
            usuario=usuario,
            rol__in=roles,
            alcance=AlcanceUsuario.GLOBAL
        ).exists()

    @staticmethod
    def obtener_tabs_usuario(usuario):
        tabs = {
            "ingresos": False,
            "atenciones": False,
            "radiologia": False,
        }

        activo = None
        # Superuser y rectivos ve todo
        if usuario.is_superuser or UsuarioService.es_directivo(usuario) or UsuarioService.es_admin_global(usuario) or UsuarioService.pertenece_unidad(usuario, UnidadID.SALA):
            for t in tabs.keys():
                tabs[t] = True
            activo = "ingresos"
            return tabs, activo

        # Usuarios por unidad
        if UsuarioService.pertenece_unidad(usuario, UnidadID.ADMISION):  # ADMISION
            tabs["ingresos"] = True
            tabs["atenciones"] = True
            if not activo:
                activo = "ingresos"

        if UsuarioService.pertenece_unidad(usuario, UnidadID.IMAGENOLOGIA):  # IMAGENOLOGÍA
            tabs["radiologia"] = True
            if not activo:
                activo = "radiologia"

        return tabs, activo
    
    @staticmethod
    def es_global(user):
        return user.perfilunidad_set.filter(
            alcance=AlcanceUsuario.GLOBAL
        ).exists()

    @staticmethod
    def es_directivo(user):
        return user.perfilunidad_set.filter(
            alcance=AlcanceUsuario.GLOBAL,
            rol='directivo'
        ).exists()

    @staticmethod
    def es_admin_global(user):
        return user.perfilunidad_set.filter(
            alcance=AlcanceUsuario.GLOBAL,
            rol='admin'
        ).exists()