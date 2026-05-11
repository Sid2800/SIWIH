from core.services.server_image.media_service import MediaService
from core.services.usuario_service import UsuarioService



def usuario_imagen(request):

    if not request.user.is_authenticated:
        return {}

    return {
        "usuario_imagen_url":
            request.session.get("url_imagen_usuario")
    }