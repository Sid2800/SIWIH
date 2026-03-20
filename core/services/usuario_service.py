from django.contrib.auth.models import User
from usuario.models import PerfilUnidad
from core.constants.domain_constants import UnidadID
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
        perfiles = PerfilUnidad.objects.filter(usuario=usuario).values_list('unidad_id', flat=True)
        return int(unidad_id) in perfiles
    

    
    @staticmethod
    def obtener_tabs_usuario(usuario):
        tabs = {
            "ingresos": False,
            "atenciones": False,
            "radiologia": False,
        }

        activo = None

        # Superuser y rectivos ve todo
        if usuario.is_superuser or UsuarioService.pertenece_unidad(usuario, UnidadID.DIRECTIVOS) or UsuarioService.pertenece_unidad(usuario, UnidadID.SALA):
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