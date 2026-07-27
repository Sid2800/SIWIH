# Solo las rutas, sin la IP
BUSCAR_ARCHIVOS = "/api_images/buscar/"
BUSCAR_IMAGENES_USUARIO = "/api_images/buscar_imagenes_usuarios/"
SUBIR_IMAGEN = "/api_images/subir_imagen/"
# Endpoints exclusivos para las fotografias asociadas al inventario de equipos.
SUBIR_IMAGEN_DISPOSITIVO = "/api_images/equipos/subir/"
BUSCAR_IMAGENES_DISPOSITIVO = "/api_images/equipos/{dispositivo_id}/imagenes/"
# La ficha firmada es una constancia legal separada de las seis fotografias.
SUBIR_FICHA_BAJA_DISPOSITIVO = "/api_images/equipos/bajas/subir/"
BUSCAR_FICHA_BAJA_DISPOSITIVO = (
    "/api_images/equipos/{dispositivo_id}/baja/ficha/"
)


SUBIR_IMAGEN_USUARIO = "/api_images/subir_imagen_usuario/"
DESACTIVAR_IMAGEN = "/api_images/desactivar/"
DESACTIVAR_IMAGEN_BATCH = "/api_images/desactivar-batch/"
MIGRAR_IMAGENES_EXTERNO_INTERNO = "/api_images/migrar-imagenes-externo-a-interno/"




OBTENER_TOKEN = "/api_images/api/token/"
ESTADISTICAS = "/api_images/stats/"




