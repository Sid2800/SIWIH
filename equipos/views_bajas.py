# Tramite de baja de un equipo y su ficha firmada, con la orden de
# trabajo que reserva el correlativo.


from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from core.services.server_image.media_service import MediaService
from .forms import BajaDispositivoForm
from .models import Dispositivo, EstadoDispositivo, OrdenTrabajoBajaDispositivo
from .decorators import exige_baja_equipos
from .services.ficha_baja_pdf_service import FichaBajaPdfService
from .view_helpers import (
    _obtener_asignacion_actual,
    _obtener_baja_dispositivo,
    _obtener_contexto_imagenes_dispositivo,
    _obtener_orden_trabajo_baja,
    registrar_errores_vista,
)


def _obtener_o_crear_orden_trabajo_baja(dispositivo, usuario):
    # Bloquear la fila del equipo serializa dos intentos simultáneos y evita
    # que ambos técnicos reserven una orden diferente.
    with transaction.atomic():
        dispositivo_bloqueado = (
            Dispositivo.objects
            .select_for_update()
            .get(pk=dispositivo.pk)
        )
        orden, _ = OrdenTrabajoBajaDispositivo.objects.get_or_create(
            dispositivo=dispositivo_bloqueado,
            defaults={"creado_por": usuario},
        )
    return orden


@exige_baja_equipos
@registrar_errores_vista("Error en tramite de baja de equipo")
def tramite_baja_dispositivo(request, dispositivo_id):
    # No existe un estado pendiente. La baja se crea solamente cuando el
    # servidor de imagenes confirma que recibio la ficha firmada.
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
    orden_trabajo_baja = _obtener_orden_trabajo_baja(dispositivo)
    asignacion_actual = _obtener_asignacion_actual(dispositivo)

    if _obtener_baja_dispositivo(dispositivo):
        messages.warning(request, "Este equipo ya tiene un registro de baja.")
        return redirect("detalle_dispositivo_equipos", dispositivo_id=dispositivo.id)

    form = BajaDispositivoForm(
        request.POST or None,
        request.FILES or None,
    )

    formulario_valido = request.method == "POST" and form.is_valid()
    if request.method == "POST" and not asignacion_actual:
        form.add_error(
            None,
            "El equipo no tiene una asignación activa. Debe asignar un "
            "empleado antes de tramitar la baja.",
        )
        formulario_valido = False

    if formulario_valido and not orden_trabajo_baja:
        form.add_error(
            None,
            "Primero debe generar la ficha PDF para reservar el número "
            "de orden de trabajo.",
        )
        formulario_valido = False

    if formulario_valido:
        resultado_ficha = MediaService.subir_ficha_baja_dispositivo(
            dispositivo.id,
            form.cleaned_data["ficha_firmada"],
            request.user,
        )
        ficha = resultado_ficha.get("ficha") or {}
        ficha_uuid = ficha.get("uuid")

        if not resultado_ficha.get("ok") or not ficha_uuid:
            form.add_error(
                "ficha_firmada",
                "No se pudo guardar la ficha firmada. "
                "El equipo no fue dado de baja.",
            )
        else:
            # La escritura local se agrupa para que el historial y el estado
            # nunca queden separados dentro de la base principal.
            with transaction.atomic():
                dispositivo_bloqueado = (
                    Dispositivo.objects
                    .select_for_update()
                    .get(pk=dispositivo.pk)
                )
                baja = form.save(commit=False)
                baja.dispositivo = dispositivo_bloqueado
                # La fecha real pertenece a la confirmacion definitiva, no a
                # la preparacion previa de la ficha.
                baja.fecha_baja = timezone.localdate()
                baja.registrado_por = request.user
                baja.ficha_firmada_uuid = ficha_uuid
                baja.save()

                # Algunos equipos historicos no tienen todos los campos que
                # hoy exige Dispositivo.full_clean(). Actualizar solo estas
                # columnas permite cerrar su baja sin revalidar toda la ficha.
                Dispositivo.objects.filter(
                    pk=dispositivo_bloqueado.pk
                ).update(
                    estado=EstadoDispositivo.DADO_DE_BAJA,
                    modificado_por=request.user,
                    fecha_modificado=timezone.now(),
                )

            messages.success(
                request,
                f"Equipo {dispositivo.codigo} dado de baja correctamente.",
            )
            return redirect(
                "detalle_dispositivo_equipos",
                dispositivo_id=dispositivo.id,
            )

    # La cabecera reutiliza la misma foto GENERAL que la ficha de detalle. Si
    # SIWIH Images no responde, el tramite sigue disponible con su icono local.
    contexto_imagenes = _obtener_contexto_imagenes_dispositivo(dispositivo.id)

    return render(
        request,
        "equipos/tramite_baja_dispositivo_equipos.html",
        {
            "form": form,
            "dispositivo": dispositivo,
            "asignacion_actual": asignacion_actual,
            "url_regresar": reverse(
                "detalle_dispositivo_equipos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
            "url_ficha_baja": reverse(
                "ficha_baja_dispositivo_equipos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
            "orden_trabajo_baja": orden_trabajo_baja,
            "fecha_baja_automatica": timezone.localdate(),
            "imagen_general": contexto_imagenes["imagen_general"],
        },
    )


@exige_baja_equipos
@registrar_errores_vista("Error al generar ficha de baja de equipo")
@require_http_methods(["GET", "POST"])
def ficha_baja_dispositivo_pdf(request, dispositivo_id):
    # La ficha es una previsualizacion: no crea BajaDispositivo ni modifica el
    # estado. Si la baja ya existe, reutiliza sus datos guardados.
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related(
            "tipo",
            "marca",
            "modelo",
            "area_gestora",
            "color",
            "baja",
            "orden_trabajo_baja",
        ),
        pk=dispositivo_id,
    )
    baja_dispositivo = _obtener_baja_dispositivo(dispositivo)
    asignacion_actual = _obtener_asignacion_actual(dispositivo)

    if baja_dispositivo:
        motivo = baja_dispositivo.motivo
        habitacion_estancia = baja_dispositivo.habitacion_estancia
    elif request.method == "POST":
        # El PDF se genera antes de tener la fotografia firmada.
        form = BajaDispositivoForm(request.POST, requiere_ficha=False)
        if not form.is_valid():
            # El boton de la ficha abre pestaña nueva, asi que una respuesta de
            # texto plano dejaba una pestaña en blanco con la cadena cruda. El
            # formulario ya valida en cliente; esto es solo la red de seguridad.
            return HttpResponseBadRequest(
                "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
                "<title>Datos incompletos</title></head>"
                "<body style='font-family:system-ui,sans-serif;padding:2.5rem;"
                "line-height:1.6;color:#7f1d1d'>"
                "<h1 style='font-size:1.25rem;margin:0 0 .75rem'>"
                "Faltan datos para generar la ficha</h1>"
                "<p style='margin:0 0 .5rem;color:#333'>Complete el motivo antes de "
                "generar la ficha.</p>"
                "<p style='margin:0;color:#333'>Puede cerrar esta pestaña y "
                "volver al trámite.</p>"
                "</body></html>",
                content_type="text/html; charset=utf-8",
            )
        motivo = form.cleaned_data["motivo"]
        habitacion_estancia = form.cleaned_data["habitacion_estancia"]
    else:
        motivo = ""
        habitacion_estancia = ""

    if request.method == "POST" and not asignacion_actual:
        return HttpResponseBadRequest(
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<title>Equipo sin asignación</title></head>"
            "<body style='font-family:system-ui,sans-serif;padding:2.5rem;"
            "line-height:1.6;color:#7f1d1d'>"
            "<h1 style='font-size:1.25rem;margin:0 0 .75rem'>"
            "El equipo no tiene una asignación activa</h1>"
            "<p style='margin:0;color:#333'>Asigne un empleado al equipo "
            "antes de generar la ficha de baja.</p>"
            "</body></html>",
            content_type="text/html; charset=utf-8",
        )

    # Solo reservan correlativo el POST con datos validos (el usuario esta
    # generando la ficha de verdad) y la reimpresion de una baja ya registrada.
    # Un GET es previsualizacion en blanco: abrir la URL a mano, un crawler o
    # el preview de un enlace no deben quemar un numero de orden.
    if baja_dispositivo or request.method == "POST":
        orden_trabajo = _obtener_o_crear_orden_trabajo_baja(
            dispositivo,
            request.user,
        )
    else:
        orden_trabajo = _obtener_orden_trabajo_baja(dispositivo)

    if orden_trabajo and orden_trabajo.fecha_creado:
        fecha_orden_trabajo = timezone.localtime(
            orden_trabajo.fecha_creado
        ).date()
    elif baja_dispositivo:
        # Compatibilidad con bajas antiguas que no tengan orden reservada.
        fecha_orden_trabajo = baja_dispositivo.fecha_baja
    else:
        fecha_orden_trabajo = timezone.localdate()

    return FichaBajaPdfService.generar(
        dispositivo=dispositivo,
        asignacion=asignacion_actual,
        usuario=request.user,
        fecha_orden_trabajo=fecha_orden_trabajo,
        motivo=motivo,
        habitacion_estancia=habitacion_estancia,
        numero_orden_trabajo=(
            orden_trabajo.numero_orden if orden_trabajo else "SIN ASIGNAR"
        ),
    )
