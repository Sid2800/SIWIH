from django.contrib.auth.mixins import LoginRequiredMixin
from core.constants.choices_constants import AlcanceUsuario 
from django.core.exceptions import PermissionDenied
from usuario.models import PerfilUnidad
from django.shortcuts import redirect

class UnidadRolRequiredMixin(LoginRequiredMixin):
   """
   Mixin para verificar si el usuario tiene al menos uno de los roles
   requeridos en una o más unidades especificadas.
   """
   required_roles = []     # Lista de roles, ej: ['admin', 'auditor']
   required_unidades = []  # Lista de nombres de unidad, ej: ['Admisión', 'Archivo']

   def dispatch(self, request, *args, **kwargs):
      # Superusuarios siempre tienen acceso
      if request.user.is_superuser:
         return super().dispatch(request, *args, **kwargs)

      #usuarios de manejo global 
      if PerfilUnidad.objects.filter(
         usuario=request.user,
         rol__in=self.required_roles,
         alcance=AlcanceUsuario.GLOBAL
      ).exists():
         return super().dispatch(request, *args, **kwargs)

      
      # Verificar si tiene al menos un PerfilUnidad que coincida con los requerimientos
      if PerfilUnidad.objects.filter(
         usuario=request.user,
         rol__in=self.required_roles,
         alcance=AlcanceUsuario.UNIDAD,
         servicio_unidad__nombre_unidad__in=self.required_unidades
      ).exists():
         return super().dispatch(request, *args, **kwargs)


      return redirect('acceso_denegado')
