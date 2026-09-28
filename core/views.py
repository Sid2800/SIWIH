from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from core.forms import CustomLoginForm
from core.mixins import UnidadRolRequiredMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.http import Http404, HttpResponse, HttpResponseNotModified
from core.constants import permisos
from core.services.usuario_service import UsuarioService
from core.services.server_image.media_service import MediaService
from core.services.server_image.auth_service import ImageServerAuthError
from core.services.server_image.request_service import RequestService

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


      user = form.get_user()
      url = UsuarioService.obtener_url_imagen_usuario(
         user=user
      )

      self.request.session["url_imagen_usuario"] = url


      return super().form_valid(form)


@login_required
async def media_equipo_proxy(request, ruta_archivo):
   """Sirve fotos de equipos usando la sesion y el host del SIWIH principal.

   Es asincrona porque es la vista que mas se repite del modulo y lo unico que
   hace es esperar: una ficha con seis fotografias son seis descargas contra
   SIWIH Images. Servida de forma sincrona, cada espera ocupa un hilo del pool
   del servidor mientras no llega la respuesta, y tres personas abriendo
   fichas a la vez bastaban para dejar al resto en cola. Asi las esperas no
   ocupan hilo y el limite lo pone la red, no el servidor.

   Necesita un servidor ASGI: con Daphne se ejecuta tal cual. Bajo WSGI
   Django la envolveria en su propio bucle y seguiria funcionando, solo que
   sin la ventaja.
   """
   try:
      archivo = await RequestService.obtener_archivo_media_equipo_async(
         f"EQUIPOS/{ruta_archivo}"
      )
   except ValueError as exc:
      raise Http404("Imagen de equipo no valida") from exc
   except (RuntimeError, ImageServerAuthError):
      # El navegador recibe un estado temporal sin revelar la direccion ni
      # detalles internos del servidor de imagenes.
      return HttpResponse(status=503)

   # El nombre del archivo es un uuid: el contenido de una ruta nunca cambia,
   # asi que si el navegador ya la tiene no hace falta volver a bajarla.
   etag = archivo.get("etag")

   if etag and request.headers.get("If-None-Match") == etag:
      return HttpResponseNotModified()

   response = HttpResponse(
      archivo["contenido"],
      content_type=archivo["content_type"],
   )
   response["Cache-Control"] = "private, max-age=300"
   response["X-Content-Type-Options"] = "nosniff"

   if etag:
      response["ETag"] = etag

   return response
