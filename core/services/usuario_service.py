from django.contrib.auth.models import User
from usuario.models import PerfilUnidad
from core.constants.domain_constants import UnidadID
from core.constants.choices_constants import AlcanceUsuario, RolUsuario
from django.db.models import F
from django.db.models.functions import Coalesce
from core.services.server_image.media_service import MediaService
from django.db import connections

class UsuarioService:
    def __init__(self, usuario=None):
        self.usuario = usuario

    @staticmethod
    def obtener_usuarios_activos():
        usuarios = (
            User.objects
            .filter(is_active=True)
            .annotate(
                nombre=Coalesce(
                    F('empleado__primer_nombre'),
                    F('first_name')
                ),
                apellido=Coalesce(
                    F('empleado__primer_apellido'),
                    F('last_name')
                )
            )
            .order_by('username')
            .values('id', 'username', 'nombre', 'apellido')

        )

        return list(usuarios)

    
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
    def pertenece_unidades(usuario, unidades):
        """
        Verifica si el usuario pertenece a alguna de las unidades indicadas.

        Args:
            usuario: Usuario autenticado.
            unidades: Lista de nombres cortos de unidades
            (ej. PACIENTE_VISUALIZACION_UNIDADES).

        Returns:
            bool
        """

        if usuario.is_superuser:
            return True

        if UsuarioService.es_global(usuario):
            return True

        return PerfilUnidad.objects.filter(
            usuario=usuario,
            servicio_unidad__nombre_corto_unidad__in=unidades
        ).exists()



    @staticmethod
    def obtener_tabs_usuario(usuario):

        from core.constants.permisos import (
            PACIENTE_HISTORIAL_UNIDADES,
            IMAGENOLOGIA_VISUALIZACION_UNIDADES,
            S_EXP_SOLICITANTE_UNIDADES,
        )
                
        tabs = {
            "ingresos": False,
            "atenciones": False,
            "radiologia": False,
            "prestamos": False,
        }

        activo = None
        # Superuser y rectivos ve todo
        if usuario.is_superuser or UsuarioService.es_directivo(usuario) or UsuarioService.es_admin_global(usuario):
            for t in tabs.keys():
                tabs[t] = True
            activo = "ingresos"
            return tabs, activo

        # Usuarios por unidad 
        if UsuarioService.pertenece_unidades(usuario, PACIENTE_HISTORIAL_UNIDADES):  # ADMISION
            tabs["ingresos"] = True
            tabs["atenciones"] = True
            tabs["prestamos"] = True
            if not activo:
                activo = "ingresos"

        if UsuarioService.pertenece_unidades(usuario, IMAGENOLOGIA_VISUALIZACION_UNIDADES):# IMAGENOLOGÍA
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

            if unidad_id == UnidadID.ADMI:
                botones.update([
                    "crear_paciente",
                    "crear_ingreso",
                    "crear_atencion"
                ])

            elif unidad_id == UnidadID.RX:
                botones.add("crear_evaluacionrx")

            elif unidad_id == UnidadID.UAU:
                botones.add("crear_referencia")

        return list(botones)
    

    @staticmethod
    def obtener_url_imagen_usuario(user):

        try:

            usuarios = [{"id": user.id}]

            imagenes, _ = (
                MediaService.obtener_imagenes_usuarios(
                    usuarios
                )
            )

            return (
                imagenes[0].get("url_imagen")
                if imagenes else None
            )

        except Exception:
            return None