from django.contrib.auth.models import User
from usuario.models import PerfilUnidad
from core.constants.domain_constants import UnidadID
from core.constants.choices_constants import AlcanceUsuario, RolUsuario


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
            rol=RolUsuario.DIRECTIVO
        ).exists()

    @staticmethod
    def es_admin_global(user):
        return user.perfilunidad_set.filter(
            alcance=AlcanceUsuario.GLOBAL,
            rol='admin'
        ).exists()
    

    @staticmethod
    def obtener_botones_paciente(usuario):

        if usuario.is_superuser or UsuarioService.es_admin_global(usuario):
            return ["todos"]

        perfiles = PerfilUnidad.objects.select_related("servicio_unidad").filter(usuario=usuario)
        botones = {"editar_paciente"}  

        if any(
                p.rol == RolUsuario.DIRECTIVO and p.alcance == AlcanceUsuario.GLOBAL
                for p in perfiles
            ):
            return list(botones)

        for perfil in perfiles:
            if perfil.rol == RolUsuario.VISITANTE:
                continue

            unidad_id = perfil.servicio_unidad.id

            if unidad_id == UnidadID.ADMISION:
                botones.update([
                    "crear_paciente",
                    "crear_ingreso",
                    "crear_atencion"
                ])

            elif unidad_id == UnidadID.IMAGENOLOGIA:
                botones.add("crear_evaluacionrx")

            elif unidad_id == UnidadID.REFERENCIA:
                botones.add("crear_referencia")

        return list(botones)