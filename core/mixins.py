from django.contrib.auth.mixins import LoginRequiredMixin
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

      # Verificar si tiene al menos un PerfilUnidad que coincida con los requerimientos
      tiene_permiso = PerfilUnidad.objects.filter(
         usuario=request.user,
         rol__in=self.required_roles,
         unidad__nombre_unidad__in=self.required_unidades
      ).exists()

      if not tiene_permiso:
         return redirect('acceso_denegado')

      return super().dispatch(request, *args, **kwargs)