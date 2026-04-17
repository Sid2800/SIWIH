
from django.views.generic import View
from django.http import JsonResponse
from types import SimpleNamespace
from core.constants import permisos
from usuario.permisos import verificar_permisos_usuario
from core.services.referencia.referencia_service import ReferenciaService
from core.utils.utilidades_request import cargar_json
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.services.server_image.media_service import MediaService


# Create your views here.

class Procesar_imagen_usuario(View):

    def dispatch(self, request, *args, **kwargs):
        if not verificar_permisos_usuario(request.user, permisos.CORE_EDITOR_ROLES, permisos.CORE_EDITOR_UNIDADES):
            return JsonResponse({"guardo": False, "mensaje": "No tiene permisos para registrar/actualizar este registro"})
        return super().dispatch(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):

        usuario = request.user

        try:
            archivo = request.FILES.get("archivo")
            usuario_id = request.POST.get("usuario_id")

            resultado=MediaService.procesar_imagen_usuario(archivo,usuario_id)

            if resultado['ok']:
                return JsonResponse({
                    "guardo": resultado['ok'],
                    "url":resultado['url']
                })
            else:
                return JsonResponse({
                "guardo": False,
                "mensaje": "No se proceso la imagen"
                })
            

        except Exception:
            log_error(
                f"Error en subida imagen usuario {request.POST.get('usuario_id')}",
                app=LogApp.MEDIA
            )

            return JsonResponse({
                "guardo": False,
                "mensaje": "Error interno"
            })
