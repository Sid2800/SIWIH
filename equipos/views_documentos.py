# Documentos que genera el modulo: la ficha de activo fijo en PDF y la
# pantalla imprimible del codigo QR.


import base64
from io import BytesIO
import qrcode
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .models import Dispositivo
from .decorators import exige_ver_equipos
from .services.ficha_activo_fijo_pdf_service import FichaActivoFijoPdfService
from .view_helpers import _obtener_asignacion_actual, registrar_errores_vista


@exige_ver_equipos
@registrar_errores_vista("Error al generar ficha de activo fijo")
@require_http_methods(["GET"])
def ficha_activo_fijo_pdf(request, dispositivo_id):
    # Es una vista dinamica: consulta la ficha vigente y no crea registros.
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related(
            "tipo",
            "marca",
            "modelo",
            "area_gestora",
            "color",
            "color_secundario",
            "procedencia",
        ),
        pk=dispositivo_id,
    )
    asignacion_actual = _obtener_asignacion_actual(dispositivo)

    return FichaActivoFijoPdfService.generar(
        dispositivo=dispositivo,
        asignacion=asignacion_actual,
        usuario=request.user,
    )


def _generar_qr_data_uri(valor):
    # Genera la imagen QR en memoria y la devuelve como data URI para el template.
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(valor)
    qr.make(fit=True)

    imagen = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    return f"data:image/png;base64,{qr_base64}"


def _construir_url_qr_equipo(request, dispositivo_id):
    # En produccion puede usarse EQUIPOS_QR_BASE_URL para que el QR apunte al
    # dominio/IP estable. Si no existe, Django arma la URL desde la peticion.
    ruta_detalle = reverse(
        "detalle_dispositivo_equipos",
        kwargs={"dispositivo_id": dispositivo_id},
    )
    base_url = getattr(settings, "EQUIPOS_QR_BASE_URL", "").strip()

    if base_url:
        return f"{base_url.rstrip('/')}{ruta_detalle}"

    return request.build_absolute_uri(ruta_detalle)


@exige_ver_equipos
@registrar_errores_vista("Error al generar QR de equipo")
def qr_dispositivo(request, dispositivo_id):
    # Pantalla imprimible: el QR contiene la URL de detalle del equipo.
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related(
            "tipo",
            "marca",
            "modelo",
            "area_gestora",
            "color",
        ),
        pk=dispositivo_id,
    )
    detalle_url = _construir_url_qr_equipo(request, dispositivo.id)

    return render(
        request,
        "equipos/qr_dispositivo_equipos.html",
        {
            "dispositivo": dispositivo,
            "detalle_url": detalle_url,
            "qr_data_uri": _generar_qr_data_uri(detalle_url),
        },
    )
