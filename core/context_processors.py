from core.services.server_image.media_service import MediaService
from core.services.usuario_service import UsuarioService



def usuario_imagen(request):
    if not request.user.is_authenticated:
        return {}

    usuarios = [{"id": request.user.id}]
    imagenes ,_ = MediaService.obtener_imagenes_usuarios(usuarios)

    url = imagenes[0].get("url_imagen") if imagenes else None

    return {
        "usuario_imagen_url": url
    }