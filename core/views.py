from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.contrib.auth.views import LoginView
from core.forms import CustomLoginForm
from core.mixins import UnidadRolRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from core.constants import permisos
from core.services.usuario_service import UsuarioService
from core.services.server_image.media_service import MediaService

# Create your views here.
class HomePageView(TemplateView):
   template_name = "core/home.html"


class samplePageView(TemplateView):
   template_name = "core/sample.html"

class MantenimientoView(UnidadRolRequiredMixin, TemplateView):
   template_name = "core/mantenimiento.html"
   required_roles = permisos.CORE_EDITOR_ROLES
   required_unidades = permisos.CORE_EDITOR_UNIDADES

   def get_context_data(self,**kwargs):
      context = super().get_context_data(**kwargs)
      usuarios = UsuarioService.obtener_usuarios_activos()
      usu,_ = MediaService.obtener_imagenes_usuarios(usuarios)
      context['usuarios'] = usu

      return context


class CustomLoginView(LoginView):
   form_class = CustomLoginForm
   template_name = "core/login.html"

   def form_valid(self, form):
      # Guardar la zona seleccionada en la sesión
      zona = form.cleaned_data.get('zona')
      self.request.session['zona_codigo'] = zona.codigo
      self.request.session['zona_nombre_zona'] = zona.nombre_zona
      return super().form_valid(form)   
