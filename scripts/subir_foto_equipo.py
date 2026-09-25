"""Sube la foto GENERAL de un equipo ya registrado a SIWIH Images.

El flujo normal convierte la imagen a WebP en el navegador, asi que un equipo
creado desde un script o importado de otro sistema se queda sin fotografia.
Este comando cubre ese hueco: convierte el archivo y lo envia con el mismo
servicio que usa el formulario, de modo que pasa por las mismas validaciones y
queda registrado con el mismo formato.

    python scripts/subir_foto_equipo.py <id_equipo> <ruta_imagen> [tipo]

El tipo por defecto es GENERAL. Los demas (INVENTARIO, PLACA_SERIE,
ESTADO_FISICO, ACCESORIOS, OTRA) se pasan como tercer argumento.
"""

import io
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SIWI.settings")
django.setup()

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from core.services.server_image.media_service import MediaService
from equipos.models import Dispositivo


# Mismo limite que aplica el servidor de imagenes antes de aceptar el archivo.
LADO_MAXIMO = 2000


def convertir_a_webp(ruta):
    """Devuelve el archivo listo para subir, en WebP y con el nombre esperado.

    Se aplana sobre blanco porque el WebP con transparencia se ve mal sobre el
    fondo claro de la ficha, y muchos PNG de catalogo vienen con fondo
    transparente.
    """
    with Image.open(ruta) as imagen:
        if imagen.mode in ("RGBA", "LA", "P"):
            imagen = imagen.convert("RGBA")
            fondo = Image.new("RGB", imagen.size, (255, 255, 255))
            fondo.paste(imagen, mask=imagen.split()[-1])
            imagen = fondo
        else:
            imagen = imagen.convert("RGB")

        imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)

        memoria = io.BytesIO()
        imagen.save(memoria, format="WEBP", quality=85, method=6)

    contenido = memoria.getvalue()
    nombre = os.path.splitext(os.path.basename(ruta))[0]

    return SimpleUploadedFile(
        f"{nombre}.webp",
        contenido,
        content_type="image/webp",
    )


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    dispositivo_id = int(sys.argv[1])
    ruta = sys.argv[2]
    tipo_imagen = sys.argv[3].upper() if len(sys.argv) > 3 else "GENERAL"

    equipo = Dispositivo.objects.get(pk=dispositivo_id)
    usuario = equipo.creado_por or User.objects.filter(is_superuser=True).first()
    archivo = convertir_a_webp(ruta)

    print(f"Equipo {equipo.codigo} - {equipo.tipo}")
    print(f"Archivo {archivo.name} ({archivo.size / 1024:.0f} KB) como {tipo_imagen}")

    resultado = MediaService.subir_imagen_dispositivo(
        dispositivo_id=equipo.pk,
        archivo=archivo,
        tipo_imagen=tipo_imagen,
        usuario=usuario,
    )

    if not resultado.get("ok"):
        print(f"\nNo se pudo subir: {resultado.get('error')}")
        return 1

    imagen = resultado["imagen"]
    print(f"\nSubida correctamente\n  uuid {imagen['uuid']}\n  url  {imagen['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
