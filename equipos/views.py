import base64
import logging
from functools import wraps
from io import BytesIO
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from core.constants.choices_constants import EstadoRegistro
from core.services.server_image.media_service import MediaService
from rrhh.models import Empleado

from .forms import (
    BajaDispositivoForm,
    DispositivoCreateForm,
    RetornoGarantiaForm,
    SalidaGarantiaForm,
    ImagenDispositivoForm,
    MarcaCatalogoForm,
    ModeloCatalogoForm,
    TipoCatalogoForm,
    TIPOS_IMAGEN_DISPOSITIVO,
)
from .models import (
    AreaGestora,
    DIAS_AVISO_GARANTIA,
    AsignacionDispositivo,
    BajaDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    EstadoDispositivo,
    EstadoGarantiaDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    OrdenTrabajoBajaDispositivo,
    PausaGarantia,
    TipoDispositivo,
)
from .decorators import (
    exige_baja_equipos,
    exige_catalogo_equipos,
    exige_editar_equipos,
    exige_formularios_equipos_json,
    exige_ver_equipos,
)
from .permisos import puede_editar_equipos, puede_visualizar_equipos
from .services.garantia_service import calcular_estado_garantia, puede_pausarse
from .services.ficha_baja_pdf_service import FichaBajaPdfService
from .services.ficha_activo_fijo_pdf_service import FichaActivoFijoPdfService


logger = logging.getLogger("siwi")
LOG_EXTRA = {"app": "equipos"}
ICONOS_TIPO_IMAGEN = {
    "GENERAL": "bi bi-camera",
    "INVENTARIO": "bi bi-upc-scan",
    "PLACA_SERIE": "bi bi-card-text",
    "ESTADO_FISICO": "bi bi-shield-check",
    "ACCESORIOS": "bi bi-plug",
    "OTRA": "bi bi-image",
}

# Reutiliza los colores de estado del modulo para no inventar una paleta nueva.
CSS_ESTADO_GARANTIA = {
    EstadoGarantiaDispositivo.VIGENTE: "equipos-estado--operativo",
    EstadoGarantiaDispositivo.POR_VENCER: "equipos-estado--media",
    EstadoGarantiaDispositivo.VENCIDA: "equipos-estado--alta",
    EstadoGarantiaDispositivo.PAUSADA: "equipos-estado--repuesto",
    EstadoGarantiaDispositivo.SIN_GARANTIA: "equipos-estado--inactivo",
}


def _registrar_error_vista(mensaje, request, **contexto):
    # Los logs del modulo registran solo errores tecnicos. No guardan exitos ni
    # valores del formulario para evitar ruido y datos sensibles innecesarios.
    usuario = getattr(getattr(request, "user", None), "username", "") or "anonimo"
    detalles = {
        "usuario": usuario,
        "metodo": getattr(request, "method", ""),
        "ruta": getattr(request, "path", ""),
        **contexto,
    }
    contexto_log = " ".join(
        f"{clave}={valor}"
        for clave, valor in detalles.items()
        if valor not in (None, "")
    )
    logger.exception("%s | %s", mensaje, contexto_log, extra=LOG_EXTRA)


def registrar_errores_vista(mensaje):
    def decorador(vista):
        @wraps(vista)
        def wrapper(request, *args, **kwargs):
            try:
                return vista(request, *args, **kwargs)
            except Http404:
                raise
            except Exception:
                _registrar_error_vista(mensaje, request, **kwargs)
                raise

        return wrapper

    return decorador


@exige_ver_equipos
def inicio(request):
    # Pantalla de entrada del modulo. Solo renderiza el menu interno de Equipos.
    return render(
        request,
        'equipos/equipos_inicio.html'
    )


@exige_editar_equipos
@registrar_errores_vista("Error al registrar equipo")
def registrar_dispositivo(request):
    # GET: muestra formulario vacio.
    # POST valido: crea equipo, asignacion y foto GENERAL. Si SIWIH Images no
    # confirma la foto, la transaccion local se revierte y no queda un equipo
    # incompleto en el inventario.
    form = DispositivoCreateForm(
        request.POST or None,
        request.FILES or None,
    )

    if request.method == "POST" and form.is_valid():
        registro_completo = False
        with transaction.atomic():
            dispositivo = form.save(commit=False)
            dispositivo.creado_por = request.user
            dispositivo.modificado_por = request.user
            dispositivo.save()

            _crear_asignacion_dispositivo(
                dispositivo,
                form,
                request.user,
                "Asignación inicial del equipo.",
            )

            foto_general = form.cleaned_data["foto_general"]
            foto_general.seek(0)
            resultado_media = MediaService.subir_imagen_dispositivo(
                dispositivo_id=dispositivo.id,
                archivo=foto_general,
                tipo_imagen="GENERAL",
                usuario=request.user,
            )

            if resultado_media.get("ok"):
                registro_completo = True
            else:
                # El error tecnico ya queda en el log de MediaService. Al
                # usuario se le muestra un mensaje estable sin datos internos.
                transaction.set_rollback(True)
                form.add_error(
                    "foto_general",
                    "No se pudo guardar la foto. Intente nuevamente.",
                )

        if registro_completo:
            messages.success(
                request,
                f"Equipo {dispositivo.codigo} registrado correctamente.",
            )
            return redirect(
                "detalle_dispositivo_equipos",
                dispositivo_id=dispositivo.id,
            )

        # La instancia conserva su PK en memoria aunque la base haya hecho
        # rollback; se restablece para que el formulario siga siendo de alta.
        dispositivo.pk = None
        dispositivo._state.adding = True

    return render(
        request,
        "equipos/registrar_dispositivo_equipos.html",
        {
            "form": form,
            "titulo_pagina": "Registrar equipo",
            "titulo_formulario": "Registrar equipo",
            "icono_formulario": "bi bi-clipboard2-plus",
            "texto_boton_guardar": "Guardar equipo",
            "url_regresar": reverse("inicio_equipos"),
            "texto_regresar": "Equipos",
            "estado_label": "Estado inicial *",
        },
    )


def _obtener_asignacion_actual(dispositivo):
    # La asignacion activa es la que no tiene fecha_fin.
    return dispositivo.asignaciones.filter(
        fecha_fin__isnull=True
    ).select_related(
        "area_clinica__servicio",
        "unidad_no_clinica",
        "responsable",
    ).first()
def _obtener_baja_dispositivo(dispositivo):
    # Evita repetir try/except cada vez que necesitamos saber si el equipo
    # ya tiene baja administrativa.
    try:
        return dispositivo.baja
    except BajaDispositivo.DoesNotExist:
        return None


def _obtener_orden_trabajo_baja(dispositivo):
    try:
        return dispositivo.orden_trabajo_baja
    except OrdenTrabajoBajaDispositivo.DoesNotExist:
        return None


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


def _crear_asignacion_dispositivo(dispositivo, form, usuario, observaciones):
    # Crea una fila en el historial de asignaciones con los datos ya validados
    # por DispositivoCreateForm.clean().
    return AsignacionDispositivo.objects.create(
        dispositivo=dispositivo,
        area_clinica=form.cleaned_data.get("area_clinica"),
        unidad_no_clinica=form.cleaned_data.get("unidad_no_clinica"),
        responsable=form.cleaned_data["responsable"],
        observaciones=observaciones,
        creado_por=usuario,
        modificado_por=usuario,
    )


def _datos_asignacion_cambiaron(asignacion_actual, form):
    # Si ubicacion o responsable no cambiaron, editar el equipo no crea una
    # asignacion duplicada.
    if not asignacion_actual:
        return True

    area_clinica = form.cleaned_data.get("area_clinica")
    unidad_no_clinica = form.cleaned_data.get("unidad_no_clinica")
    responsable = form.cleaned_data["responsable"]

    return (
        asignacion_actual.area_clinica_id != getattr(area_clinica, "pk", None)
        or asignacion_actual.unidad_no_clinica_id
        != getattr(unidad_no_clinica, "pk", None)
        or asignacion_actual.responsable_id != responsable.pk
    )


def _actualizar_asignacion_dispositivo(dispositivo, form, usuario, asignacion_actual):
    # Cuando cambia la asignacion, cerramos la anterior y abrimos una nueva.
    # Asi queda historial sin perder quien tuvo el equipo antes.
    if not _datos_asignacion_cambiaron(asignacion_actual, form):
        return asignacion_actual

    if asignacion_actual:
        asignacion_actual.fecha_fin = timezone.now()
        asignacion_actual.modificado_por = usuario
        asignacion_actual.save()

    return _crear_asignacion_dispositivo(
        dispositivo,
        form,
        usuario,
        "Asignación actualizada desde edición del equipo.",
    )


def _obtener_opciones_area_listado():
    # Construye opciones de filtro solo con areas que tienen equipos asignados.
    opciones = []
    vistos = set()
    asignaciones = AsignacionDispositivo.objects.filter(
        fecha_fin__isnull=True
    ).select_related(
        "area_clinica__servicio",
        "unidad_no_clinica",
    ).order_by(
        "area_clinica__nombre_area_atencion",
        "unidad_no_clinica__nombre_unidad",
    )

    for asignacion in asignaciones:
        if asignacion.area_clinica_id:
            valor = f"clinica:{asignacion.area_clinica_id}"
            etiqueta = f"Clínica - {asignacion.area_clinica}"
        elif asignacion.unidad_no_clinica_id:
            valor = f"no_clinica:{asignacion.unidad_no_clinica_id}"
            etiqueta = f"No clínica - {asignacion.unidad_no_clinica}"
        else:
            continue

        if valor in vistos:
            continue

        vistos.add(valor)
        opciones.append({"value": valor, "label": etiqueta})

    return opciones


def _parametro_entero(valor):
    # Convierte parametros GET a enteros seguros antes de filtrar.
    if valor and valor.isdigit():
        return int(valor)
    return None


def _prefetch_asignacion_activa():
    # Prefetch evita consultar la asignacion activa una vez por cada fila de tabla.
    return Prefetch(
        "asignaciones",
        queryset=AsignacionDispositivo.objects.filter(
            fecha_fin__isnull=True
        ).select_related(
            "area_clinica__servicio",
            "unidad_no_clinica",
            "responsable",
        ),
        to_attr="asignacion_activa_lista",
    )


def _obtener_dispositivos_base():
    # Query base compartida por listado y busqueda.
    return Dispositivo.objects.select_related(
        "tipo",
        "marca",
        "modelo",
        "area_gestora",
        "color",
    ).prefetch_related(_prefetch_asignacion_activa())


def _aplicar_busqueda_dispositivos(dispositivos, consulta):
    # Busqueda base por identificadores y catalogos principales.
    if not consulta:
        return dispositivos

    filtro_busqueda = (
        Q(tipo__nombre__icontains=consulta)
        | Q(marca__nombre__icontains=consulta)
        | Q(color__nombre__icontains=consulta)
        | Q(inventario_bienes_nacionales__icontains=consulta)
        | Q(inventario_numero_ficha__icontains=consulta)
    )

    codigo_numerico = "".join(caracter for caracter in consulta if caracter.isdigit())

    if codigo_numerico:
        filtro_busqueda |= Q(pk=int(codigo_numerico))

    return dispositivos.filter(filtro_busqueda)


def _ordenar_dispositivos(dispositivos):
    # Orden estable para que paginacion/listados no cambien entre consultas.
    return dispositivos.order_by(
        "tipo__nombre",
        "marca__nombre",
        "modelo__nombre",
        "area_gestora__nombre",
        "color__nombre",
        "numero_serie",
    ).distinct()


def _preparar_dispositivos_para_tabla(dispositivos):
    # Agrega atributos temporales a cada objeto para simplificar el template.
    estado_css = {
        EstadoDispositivo.OPERATIVO: "equipos-estado--operativo",
        EstadoDispositivo.EN_MANTENIMIENTO: "equipos-estado--media",
        EstadoDispositivo.FUERA_DE_SERVICIO: "equipos-estado--alta",
        EstadoDispositivo.DADO_DE_BAJA: "equipos-estado--inactivo",
        EstadoDispositivo.REPUESTO_PENDIENTE: "equipos-estado--repuesto",
    }
    criticidad_css = {
        CriticidadDispositivo.BAJA: "equipos-estado--operativo",
        CriticidadDispositivo.MEDIA: "equipos-estado--media",
        CriticidadDispositivo.ALTA: "equipos-estado--alta",
    }

    estado_etiqueta = {
        EstadoDispositivo.OPERATIVO: "Oper.",
        EstadoDispositivo.EN_MANTENIMIENTO: "Mant.",
        EstadoDispositivo.FUERA_DE_SERVICIO: "F. serv.",
        EstadoDispositivo.DADO_DE_BAJA: "Baja",
        EstadoDispositivo.REPUESTO_PENDIENTE: "Rep.",
    }
    for dispositivo in dispositivos:
        dispositivo.asignacion_actual = (
            dispositivo.asignacion_activa_lista[0]
            if dispositivo.asignacion_activa_lista
            else None
        )
        dispositivo.estado_css = estado_css.get(dispositivo.estado, "")
        dispositivo.estado_etiqueta = estado_etiqueta.get(
            dispositivo.estado,
            dispositivo.get_estado_display(),
        )
        dispositivo.criticidad_css = criticidad_css.get(dispositivo.criticidad, "")


@exige_ver_equipos
@registrar_errores_vista("Error en listado de equipos")
def listado_dispositivos(request):
    # Vista principal de inventario. Lee filtros GET, aplica consultas,
    # pagina resultados y renderiza la tabla.
    consulta = request.GET.get("q", "").strip()
    filtro_area = request.GET.get("area", "").strip()
    filtro_estado = request.GET.get("estado", "").strip()
    filtro_tipo = request.GET.get("tipo", "").strip()
    filtro_marca = request.GET.get("marca", "").strip()
    filtro_modelo = request.GET.get("modelo", "").strip()
    filtro_area_gestora = request.GET.get("area_gestora", "").strip()

    dispositivos = _aplicar_busqueda_dispositivos(
        _obtener_dispositivos_base(),
        consulta,
    )

    if filtro_area.startswith("clinica:"):
        area_id = _parametro_entero(filtro_area.removeprefix("clinica:"))
        if area_id:
            dispositivos = dispositivos.filter(
                asignaciones__fecha_fin__isnull=True,
                asignaciones__area_clinica_id=area_id,
            )
    elif filtro_area.startswith("no_clinica:"):
        unidad_id = _parametro_entero(filtro_area.removeprefix("no_clinica:"))
        if unidad_id:
            dispositivos = dispositivos.filter(
                asignaciones__fecha_fin__isnull=True,
                asignaciones__unidad_no_clinica_id=unidad_id,
            )

    estado_id = _parametro_entero(filtro_estado)
    if estado_id:
        dispositivos = dispositivos.filter(estado=estado_id)
    else:
        dispositivos = dispositivos.exclude(estado=EstadoDispositivo.DADO_DE_BAJA)


    tipo_id = _parametro_entero(filtro_tipo)
    if tipo_id:
        dispositivos = dispositivos.filter(tipo_id=tipo_id)

    marca_id = _parametro_entero(filtro_marca)
    if marca_id:
        dispositivos = dispositivos.filter(marca_id=marca_id)

    modelo_id = _parametro_entero(filtro_modelo)
    if modelo_id:
        dispositivos = dispositivos.filter(modelo_id=modelo_id)

    area_gestora_id = _parametro_entero(filtro_area_gestora)
    if area_gestora_id:
        dispositivos = dispositivos.filter(area_gestora_id=area_gestora_id)


    dispositivos = _ordenar_dispositivos(dispositivos)
    paginador = Paginator(dispositivos, 10)
    page_obj = paginador.get_page(request.GET.get("page"))
    _preparar_dispositivos_para_tabla(page_obj.object_list)

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        'equipos/listado_dispositivos_equipos.html',
        {
            "dispositivos": page_obj.object_list,
            "page_obj": page_obj,
            "rango_paginas": paginador.get_elided_page_range(
                page_obj.number,
                on_each_side=1,
                on_ends=1,
            ),
            "total_dispositivos": paginador.count,
            "querystring": query_params.urlencode(),
            "filtros": {
                "q": consulta,
                "area": filtro_area,
                "estado": filtro_estado,
                "tipo": filtro_tipo,
                "marca": filtro_marca,
                "modelo": filtro_modelo,
                "area_gestora": filtro_area_gestora,
            },
            "area_choices": _obtener_opciones_area_listado(),
            "estado_choices": [
                {"value": str(valor), "label": etiqueta}
                for valor, etiqueta in EstadoDispositivo.choices
            ],
            "tipo_choices": TipoDispositivo.objects.filter(activo=True).order_by(
                "nombre"
            ),
            "marca_choices": MarcaDispositivo.objects.filter(activo=True).order_by(
                "nombre"
            ),
            "modelo_choices": ModeloDispositivo.objects.filter(activo=True).order_by(
                "nombre"
            ),
            "area_gestora_choices": AreaGestora.objects.filter(activo=True).order_by(
                "nombre"
            ),
        },
    )


def _obtener_contexto_imagenes_dispositivo(dispositivo_id):
    # Ordena la respuesta remota según las seis categorías acordadas. La base
    # principal conserva solo el id del equipo; no duplica rutas de archivos.
    imagenes, media_server_offline = (
        MediaService.obtener_imagenes_dispositivo(dispositivo_id)
    )
    imagenes_por_tipo = {
        imagen.get("tipo_imagen"): imagen
        for imagen in imagenes
        if imagen.get("tipo_imagen")
    }
    imagenes_slots = [
        {
            "tipo": tipo,
            "etiqueta": etiqueta,
            "icono": ICONOS_TIPO_IMAGEN[tipo],
            "imagen": imagenes_por_tipo.get(tipo),
        }
        for tipo, etiqueta in TIPOS_IMAGEN_DISPOSITIVO
    ]
    tipos_ocupados = {
        slot["tipo"] for slot in imagenes_slots if slot["imagen"]
    }

    return {
        "imagen_general": imagenes_por_tipo.get("GENERAL"),
        "imagenes_slots": imagenes_slots,
        "cantidad_imagenes": len(tipos_ocupados),
        "tipos_imagen_ocupados": tipos_ocupados,
        "tipos_imagen_disponibles": (
            not media_server_offline
            and len(tipos_ocupados) < len(TIPOS_IMAGEN_DISPOSITIVO)
        ),
        "media_server_offline": media_server_offline,
    }


def _contexto_detalle_reducido(dispositivo):
    """Lista blanca de lo que ve quien no pertenece a Equipos.

    Se enumera campo por campo a proposito. Si manana el formulario crece
    (proveedor, procedencia, lo que sea), el campo nuevo no aparece aqui salvo
    que alguien lo agregue con intencion. Al reves se filtraria solo.

    Queda fuera todo lo administrativo: costo de adquisicion, inventario de
    bienes nacionales, numero de ficha, constancia firmada, garantia, quien lo
    registro y los datos de baja.
    """
    asignacion = _obtener_asignacion_actual(dispositivo)
    imagenes, _ = MediaService.obtener_imagenes_dispositivo(dispositivo.id)
    imagen_general = next(
        (img for img in imagenes if img.get("tipo_imagen") == "GENERAL"), None
    )

    return {
        "dispositivo": dispositivo,
        "asignacion_actual": asignacion,
        "imagen_general": imagen_general,
    }


@login_required
@registrar_errores_vista("Error al abrir detalle de equipo")
def detalle_dispositivo(request, dispositivo_id):
    # Unico detalle del equipo, con dos caras. Es la URL que llevan los codigos
    # QR pegados a los aparatos, asi que cualquiera del hospital debe poder
    # abrirla: el tecnico ve la ficha completa y el resto una version reducida
    # para identificar el equipo y saber a quien avisar.
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related(
            "tipo",
            "marca",
            "modelo",
            "area_gestora",
            "color",
            "baja__registrado_por",
            "orden_trabajo_baja__creado_por",
        ),
        pk=dispositivo_id,
    )

    if not puede_visualizar_equipos(request.user):
        return render(
            request,
            "equipos/detalle_dispositivo_reducido_equipos.html",
            _contexto_detalle_reducido(dispositivo),
        )

    asignacion_actual = _obtener_asignacion_actual(dispositivo)
    baja_dispositivo = _obtener_baja_dispositivo(dispositivo)
    orden_trabajo_baja = _obtener_orden_trabajo_baja(dispositivo)
    # La ficha sigue disponible aunque el servidor de imagenes no responda.
    contexto_imagenes = _obtener_contexto_imagenes_dispositivo(dispositivo.id)
    ficha_baja_firmada = None
    ficha_baja_server_offline = False
    if baja_dispositivo:
        # La constancia legal se consulta aparte de las seis fotos del equipo.
        (
            ficha_baja_firmada,
            ficha_baja_server_offline,
        ) = MediaService.obtener_ficha_baja_dispositivo(dispositivo.id)
    estado_css = {
        EstadoDispositivo.OPERATIVO: "equipos-estado--operativo",
        EstadoDispositivo.EN_MANTENIMIENTO: "equipos-estado--media",
        EstadoDispositivo.FUERA_DE_SERVICIO: "equipos-estado--alta",
        EstadoDispositivo.DADO_DE_BAJA: "equipos-estado--inactivo",
        EstadoDispositivo.REPUESTO_PENDIENTE: "equipos-estado--repuesto",
    }
    criticidad_css = {
        CriticidadDispositivo.BAJA: "equipos-estado--operativo",
        CriticidadDispositivo.MEDIA: "equipos-estado--media",
        CriticidadDispositivo.ALTA: "equipos-estado--alta",
    }
    # La ficha solo informa de la garantia. Pausar y reanudar se maneja desde
    # Garantias, asi que aqui no viaja nada para operar.
    pausas = list(dispositivo.pausas_garantia.all())
    garantia = calcular_estado_garantia(dispositivo, pausas=pausas)

    return render(
        request,
        'equipos/detalle_dispositivo_equipos.html',
        {
            "dispositivo": dispositivo,
            "asignacion_actual": asignacion_actual,
            "baja_dispositivo": baja_dispositivo,
            "orden_trabajo_baja": orden_trabajo_baja,
            "ficha_baja_firmada": ficha_baja_firmada,
            "ficha_baja_server_offline": ficha_baja_server_offline,
            "estado_css": estado_css.get(dispositivo.estado, ""),
            "criticidad_css": criticidad_css.get(dispositivo.criticidad, ""),
            "garantia": garantia,
            "garantia_css": CSS_ESTADO_GARANTIA.get(garantia.estado, ""),
            "pausas": pausas,
            **contexto_imagenes,
        }
    )

@exige_editar_equipos
@registrar_errores_vista("Error al editar equipo")
def editar_dispositivo(request, dispositivo_id):
    # Reutiliza DispositivoCreateForm y el template de registro.
    # Si el equipo esta dado de baja, se bloquea la edicion.
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

    if (
        _obtener_baja_dispositivo(dispositivo)
        or dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA
    ):
        messages.warning(
            request,
            "El equipo ya fue dado de baja y no puede editarse desde esta vista.",
        )
        return redirect("detalle_dispositivo_equipos", dispositivo_id=dispositivo.id)

    asignacion_actual = _obtener_asignacion_actual(dispositivo)
    form = DispositivoCreateForm(
        request.POST or None,
        request.FILES or None,
        instance=dispositivo,
        asignacion_actual=asignacion_actual,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            dispositivo = form.save(commit=False)
            dispositivo.modificado_por = request.user
            dispositivo.save()

            _actualizar_asignacion_dispositivo(
                dispositivo,
                form,
                request.user,
                asignacion_actual,
            )

        messages.success(
            request,
            f"Equipo {dispositivo.codigo} actualizado correctamente.",
        )
        return redirect("detalle_dispositivo_equipos", dispositivo_id=dispositivo.id)

    contexto_imagenes = _obtener_contexto_imagenes_dispositivo(dispositivo.id)
    imagen_form = ImagenDispositivoForm(
        tipos_ocupados=contexto_imagenes["tipos_imagen_ocupados"],
    )

    return render(
        request,
        "equipos/registrar_dispositivo_equipos.html",
        {
            "form": form,
            "dispositivo": dispositivo,
            "titulo_pagina": f"Editar {dispositivo.codigo}",
            "titulo_formulario": "Editar equipo",
            "icono_formulario": "bi bi-pencil-square",
            "texto_boton_guardar": "Actualizar equipo",
            "url_regresar": reverse("listado_dispositivos_equipos"),
            "estado_label": "Estado *",
            "texto_regresar": "Listado de equipos",
            "imagen_form": imagen_form,
            "url_agregar_imagen": reverse(
                "agregar_imagen_dispositivo_equipos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
            **contexto_imagenes,
        },
    )


@exige_editar_equipos
@registrar_errores_vista("Error al agregar fotografía de equipo")
@require_POST
def agregar_imagen_dispositivo(request, dispositivo_id):
    # La fotografía se envía por separado para que un fallo de SIWIH Images no
    # deshaga ni mezcle cambios del formulario de datos del equipo.
    dispositivo = get_object_or_404(Dispositivo, pk=dispositivo_id)
    url_edicion = reverse(
        "editar_dispositivo_equipos",
        kwargs={"dispositivo_id": dispositivo.id},
    )

    if (
        _obtener_baja_dispositivo(dispositivo)
        or dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA
    ):
        messages.warning(
            request,
            "El equipo dado de baja no admite nuevas fotografías.",
        )
        return redirect("detalle_dispositivo_equipos", dispositivo_id=dispositivo.id)

    contexto_imagenes = _obtener_contexto_imagenes_dispositivo(dispositivo.id)
    if contexto_imagenes["media_server_offline"]:
        messages.error(
            request,
            "El servidor de imágenes no está disponible. Intente nuevamente.",
        )
        return redirect(url_edicion)

    if not contexto_imagenes["tipos_imagen_disponibles"]:
        messages.info(request, "El equipo ya tiene sus seis fotografías.")
        return redirect(url_edicion)

    form = ImagenDispositivoForm(
        request.POST,
        request.FILES,
        tipos_ocupados=contexto_imagenes["tipos_imagen_ocupados"],
    )
    if not form.is_valid():
        primer_error = next(
            (
                str(error)
                for errores in form.errors.values()
                for error in errores
            ),
            "Revise la fotografía seleccionada.",
        )
        messages.error(request, primer_error)
        return redirect(url_edicion)

    archivo = form.cleaned_data["archivo"]
    archivo.seek(0)
    resultado_media = MediaService.subir_imagen_dispositivo(
        dispositivo_id=dispositivo.id,
        archivo=archivo,
        tipo_imagen=form.cleaned_data["tipo_imagen"],
        usuario=request.user,
    )

    if resultado_media.get("ok"):
        messages.success(request, "Fotografía agregada correctamente.")
    else:
        messages.error(
            request,
            "No se pudo guardar la fotografía. Intente nuevamente.",
        )

    return redirect(url_edicion)


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
@exige_ver_equipos
@registrar_errores_vista("Error en busqueda de equipos")
def buscar_dispositivo(request):
    # Busqueda rapida. Muestra resultados cuando hay texto o filtro de gestoria.
    consulta = request.GET.get("q", "").strip()
    filtro_area_gestora = request.GET.get("area_gestora", "").strip()
    dispositivos = Dispositivo.objects.none()
    page_obj = None
    rango_paginas = []
    total_dispositivos = 0

    if consulta or filtro_area_gestora:
        dispositivos = _aplicar_busqueda_dispositivos(
            _obtener_dispositivos_base(),
            consulta,
        )

        area_gestora_id = _parametro_entero(filtro_area_gestora)
        if area_gestora_id:
            dispositivos = dispositivos.filter(area_gestora_id=area_gestora_id)

        dispositivos = _ordenar_dispositivos(dispositivos)
        paginador = Paginator(dispositivos, 10)
        page_obj = paginador.get_page(request.GET.get("page"))
        _preparar_dispositivos_para_tabla(page_obj.object_list)
        rango_paginas = paginador.get_elided_page_range(
            page_obj.number,
            on_each_side=1,
            on_ends=1,
        )
        total_dispositivos = paginador.count

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        'equipos/buscar_dispositivo_equipos.html',
        {
            "consulta": consulta,
            "dispositivos": page_obj.object_list if page_obj else [],
            "page_obj": page_obj,
            "rango_paginas": rango_paginas,
            "total_dispositivos": total_dispositivos,
            "querystring": query_params.urlencode(),
            "filtros": {
                "area_gestora": filtro_area_gestora,
            },
            "area_gestora_choices": AreaGestora.objects.filter(activo=True).order_by(
                "nombre"
            ),
        },
    )


TAMANO_PAGINA_AUTOCOMPLETADO = 20


def _respuesta_select2(pagina):
    """Formato que Select2 espera para paginar por scroll infinito."""
    return JsonResponse({
        "results": pagina["resultados"],
        "pagination": {"more": pagina["hay_mas"]},
    })


def _paginar_autocompletado(queryset, request, construir):
    # Select2 envia ?page=N al llegar al final de la lista. Se pide un elemento
    # de mas para saber si queda otra pagina sin contar el total, que en
    # catalogos grandes seria una consulta cara e inutil.
    try:
        pagina = max(int(request.GET.get("page", 1)), 1)
    except (TypeError, ValueError):
        pagina = 1

    inicio = (pagina - 1) * TAMANO_PAGINA_AUTOCOMPLETADO
    fin = inicio + TAMANO_PAGINA_AUTOCOMPLETADO
    registros = list(queryset[inicio:fin + 1])
    hay_mas = len(registros) > TAMANO_PAGINA_AUTOCOMPLETADO

    return {
        "resultados": [construir(r) for r in registros[:TAMANO_PAGINA_AUTOCOMPLETADO]],
        "hay_mas": hay_mas,
    }


@exige_formularios_equipos_json
@login_required
@registrar_errores_vista("Error al buscar tipos de equipo")
def buscar_tipos(request):
    # Alimenta el Select2 de tipo. Mismo patron que marcas: sin texto devuelve
    # las primeras para poder abrir y elegir con el raton sin escribir nada.
    consulta = request.GET.get("q", "").strip()
    tipos = TipoDispositivo.objects.filter(activo=True)

    if consulta:
        tipos = tipos.filter(nombre__icontains=consulta)

    pagina = _paginar_autocompletado(
        tipos.order_by("nombre"),
        request,
        lambda tipo: {"id": tipo.id, "text": tipo.nombre},
    )
    return _respuesta_select2(pagina)


@exige_formularios_equipos_json
@login_required
@registrar_errores_vista("Error al buscar marcas de equipo")
def buscar_marcas(request):
    # Alimenta el Select2 de marca. Sin texto devuelve las primeras marcas para
    # que el usuario pueda abrir y elegir con el raton sin escribir nada.
    consulta = request.GET.get("q", "").strip()
    marcas = MarcaDispositivo.objects.filter(activo=True)

    if consulta:
        marcas = marcas.filter(nombre__icontains=consulta)

    pagina = _paginar_autocompletado(
        marcas.order_by("nombre"),
        request,
        lambda marca: {"id": marca.id, "text": marca.nombre},
    )
    return _respuesta_select2(pagina)


@exige_formularios_equipos_json
@login_required
@registrar_errores_vista("Error al buscar modelos de equipo")
def buscar_modelos(request):
    # Solo devuelve modelos activos de la marca pedida. La marca es obligatoria:
    # sin ella no hay lista que mostrar, y devolver el catalogo entero
    # permitiria elegir un modelo de otro fabricante.
    marca_id = (request.GET.get("marca_id") or "").strip()

    if not marca_id.isdigit():
        return JsonResponse(
            {"results": [], "pagination": {"more": False},
             "error": "Debe indicar la marca."},
            status=400,
        )

    consulta = request.GET.get("q", "").strip()
    modelos = ModeloDispositivo.objects.filter(
        marca_id=int(marca_id),
        activo=True,
        marca__activo=True,
    ).select_related("marca")

    if consulta:
        modelos = modelos.filter(nombre__icontains=consulta)

    pagina = _paginar_autocompletado(
        modelos.order_by("nombre"),
        request,
        lambda modelo: {"id": modelo.id, "text": modelo.nombre},
    )
    return _respuesta_select2(pagina)


@exige_formularios_equipos_json
@registrar_errores_vista("Error al buscar empleados para equipos")
def buscar_empleados(request):
    # Endpoint AJAX usado por Select2 en el formulario de registro/edicion.
    # Devuelve JSON con maximo 10 empleados activos.
    consulta = request.GET.get("q", "").strip()
    empleados = Empleado.objects.filter(estado=EstadoRegistro.ACTIVO)

    if not consulta:
        return JsonResponse({"results": []})

    for termino in consulta.split():
        filtro = (
            Q(dni__icontains=termino)
            | Q(primer_nombre__icontains=termino)
            | Q(segundo_nombre__icontains=termino)
            | Q(primer_apellido__icontains=termino)
            | Q(segundo_apellido__icontains=termino)

        )

        empleados = empleados.filter(filtro)

    resultados = [
        {
            # Select2 necesita la PK como valor interno, pero no se muestra ni
            # se utiliza como criterio de búsqueda.
            "id": empleado.id,
            "text": f"{empleado.dni} - {empleado.nombre_completo}",
        }
        for empleado in empleados.order_by(
            "primer_nombre",
            "primer_apellido",
            "dni",
        )[:10]
    ]

    return JsonResponse({"results": resultados})



# =====================================================================
# Catalogo de marcas y modelos
# ---------------------------------------------------------------------
# Unico lugar donde se dan de alta marcas y modelos. El formulario de
# equipos solo permite elegir entre los ya existentes, para que un error
# de tecleo durante un registro no genere catalogos duplicados.
# =====================================================================


def _marca_seleccionada(request):
    # La marca elegida viaja por querystring para que la pantalla se pueda
    # compartir y recargar sin perder el contexto.
    marca_id = (request.GET.get("marca") or "").strip()

    if not marca_id.isdigit():
        return None

    return MarcaDispositivo.objects.filter(pk=int(marca_id)).first()


def _tipo_en_edicion(request):
    # El tipo que se esta editando viaja por querystring, igual que la marca
    # seleccionada, para que recargar la pantalla no pierda el contexto.
    tipo_id = (request.GET.get("tipo") or "").strip()

    if not tipo_id.isdigit():
        return None

    return TipoDispositivo.objects.filter(pk=int(tipo_id)).first()


def _url_catalogo(marca=None, tipo=None):
    # Marca y tipo son secciones independientes de la misma pantalla, asi que
    # se conservan ambas para no perder una al operar sobre la otra.
    url = reverse("catalogo_marcas_equipos")
    partes = []

    if marca:
        partes.append(f"marca={marca.pk}")
    if tipo:
        partes.append(f"tipo={tipo.pk}")

    return f"{url}?{'&'.join(partes)}" if partes else url


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error en catalogo de marcas y modelos")
def catalogo_marcas_modelos(request):
    marca = _marca_seleccionada(request)
    tipo_editado = _tipo_en_edicion(request)

    # Se muestran activas e inactivas: desactivar no es esconder, y desde aqui
    # se reactiva. El contador ayuda a detectar marcas vacias.
    marcas = MarcaDispositivo.objects.annotate(
        total_modelos=Count("modelos"),
        total_equipos=Count("dispositivos", distinct=True),
    ).order_by("-activo", "nombre")

    modelos = []
    if marca:
        modelos = (
            ModeloDispositivo.objects.filter(marca=marca)
            .annotate(total_equipos=Count("dispositivos"))
            .select_related("marca")
            .order_by("-activo", "nombre")
        )

    # Los tipos comparten pantalla con marcas y modelos porque son el mismo
    # tipo de tarea: mantener los catalogos que alimentan el formulario.
    tipos = TipoDispositivo.objects.annotate(
        total_equipos=Count("dispositivos"),
    ).order_by("-activo", "nombre")

    return render(
        request,
        "equipos/catalogo_marcas_equipos.html",
        {
            "marcas": marcas,
            "marca_seleccionada": marca,
            "modelos": modelos,
            "tipos": tipos,
            "tipo_editado": tipo_editado,
            "form_marca": MarcaCatalogoForm(),
            "form_modelo": ModeloCatalogoForm(marca=marca) if marca else None,
            # El mismo formulario sirve para alta y edicion; lo unico que
            # cambia es si se le pasa la instancia que se esta editando.
            "form_tipo": TipoCatalogoForm(instance=tipo_editado),
            "url_regresar": reverse("inicio_equipos"),
        },
    )


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar marca")
@require_POST
def agregar_marca_catalogo(request):
    form = MarcaCatalogoForm(request.POST)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos de la marca.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo())

    marca = form.save()
    messages.success(request, f"Marca {marca.nombre} agregada correctamente.")
    # Se deja seleccionada para poder cargarle modelos de inmediato.
    return redirect(_url_catalogo(marca))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar modelo")
@require_POST
def agregar_modelo_catalogo(request, marca_id):
    marca = get_object_or_404(MarcaDispositivo, pk=marca_id)
    form = ModeloCatalogoForm(request.POST, marca=marca)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos del modelo.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo(marca))

    modelo = form.save()
    messages.success(
        request,
        f"Modelo {modelo.nombre} agregado a {marca.nombre}.",
    )
    return redirect(_url_catalogo(marca))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al cambiar estado de marca")
@require_POST
def cambiar_estado_marca(request, marca_id):
    # No se elimina: una marca puede estar referenciada por equipos y por sus
    # propios modelos, y borrarla perderia historico. Desactivar la saca de los
    # selectores sin tocar lo ya registrado.
    marca = get_object_or_404(MarcaDispositivo, pk=marca_id)
    marca.activo = not marca.activo
    marca.save(update_fields=["activo"])

    messages.success(
        request,
        f"Marca {marca.nombre} {'reactivada' if marca.activo else 'desactivada'}.",
    )
    return redirect(_url_catalogo(marca))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar tipo de equipo")
@require_POST
def agregar_tipo_catalogo(request):
    form = TipoCatalogoForm(request.POST)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos del tipo de equipo.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo())

    tipo = form.save()
    messages.success(request, f"Tipo {tipo.nombre} agregado correctamente.")
    return redirect(_url_catalogo())


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al editar tipo de equipo")
@require_POST
def editar_tipo_catalogo(request, tipo_id):
    # Editar el nombre no rompe los equipos que ya lo usan: apuntan por id, no
    # por texto. Sirve para corregir erratas sin duplicar el catalogo.
    tipo = get_object_or_404(TipoDispositivo, pk=tipo_id)
    form = TipoCatalogoForm(request.POST, instance=tipo)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos del tipo de equipo.",
        )
        messages.error(request, primer_error)
        # Se vuelve al modo edicion para que el usuario corrija sin repetir
        # el camino desde la lista.
        return redirect(_url_catalogo(tipo=tipo))

    tipo = form.save()
    messages.success(request, f"Tipo {tipo.nombre} actualizado correctamente.")
    return redirect(_url_catalogo())


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al cambiar estado de tipo de equipo")
@require_POST
def cambiar_estado_tipo(request, tipo_id):
    # No se elimina: Dispositivo.tipo es PROTECT y borrarlo perderia el
    # historico. Desactivar lo saca del formulario de registro sin tocar los
    # equipos que ya lo tienen.
    tipo = get_object_or_404(TipoDispositivo, pk=tipo_id)
    tipo.activo = not tipo.activo
    tipo.save(update_fields=["activo"])

    messages.success(
        request,
        f"Tipo {tipo.nombre} {'reactivado' if tipo.activo else 'desactivado'}.",
    )
    return redirect(_url_catalogo())


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al cambiar estado de modelo")
@require_POST
def cambiar_estado_modelo(request, modelo_id):
    modelo = get_object_or_404(
        ModeloDispositivo.objects.select_related("marca"), pk=modelo_id
    )
    modelo.activo = not modelo.activo
    modelo.save(update_fields=["activo"])

    messages.success(
        request,
        f"Modelo {modelo.nombre} {'reactivado' if modelo.activo else 'desactivado'}.",
    )
    return redirect(_url_catalogo(modelo.marca))


@exige_ver_equipos
@registrar_errores_vista("Error en el panel de garantías")
def panel_garantias(request):
    """Que equipos siguen cubiertos y cuales estan a punto de dejar de estarlo.

    Abre mostrando lo accionable (por vencer y pausados) porque es la pregunta
    que trae aqui a la gente: que puedo reclamarle todavia al proveedor. El
    resto se consulta con el filtro.

    Solo pide permiso de visualizacion: la jefatura entra a ver que vence sin
    poder tocar nada. Registrar salidas y retornos exige permiso de edicion y
    se hace desde la ficha del equipo.
    """
    filtro = request.GET.get("estado", "").strip()

    # Los equipos dados de baja no entran: su garantia dejo de importar.
    dispositivos = (
        Dispositivo.objects.exclude(estado=EstadoDispositivo.DADO_DE_BAJA)
        .select_related("tipo", "marca", "modelo")
        .prefetch_related("pausas_garantia")
    )

    filas = []
    conteo = {estado.value: 0 for estado in EstadoGarantiaDispositivo}

    for dispositivo in dispositivos:
        estado = calcular_estado_garantia(
            dispositivo,
            pausas=list(dispositivo.pausas_garantia.all()),
        )
        conteo[estado.estado] += 1
        filas.append((dispositivo, estado))

    if filtro in conteo:
        filas = [par for par in filas if par[1].estado == filtro]
    else:
        # Vista por defecto: lo que requiere una decision.
        filtro = ""
        filas = [
            par
            for par in filas
            if par[1].estado
            in (
                EstadoGarantiaDispositivo.POR_VENCER,
                EstadoGarantiaDispositivo.PAUSADA,
            )
        ]

    # Lo mas urgente primero; sin garantia al final.
    filas.sort(
        key=lambda par: (
            par[1].dias_restantes is None,
            par[1].dias_restantes if par[1].dias_restantes is not None else 0,
        )
    )

    equipos = []
    for dispositivo, estado in filas:
        dispositivo.garantia = estado
        dispositivo.garantia_css = CSS_ESTADO_GARANTIA.get(estado.estado, "")
        equipos.append(dispositivo)

    # Las plantillas de Django no indexan diccionarios, asi que el conteo de
    # cada estado se resuelve aqui.
    pestanas = [
        {
            "valor": valor,
            "etiqueta": etiqueta,
            "conteo": conteo.get(valor, 0),
            "activa": filtro == valor,
        }
        for valor, etiqueta in EstadoGarantiaDispositivo.choices
    ]

    return render(
        request,
        "equipos/panel_garantias_equipos.html",
        {
            "equipos": equipos,
            "filtro": filtro,
            "pestanas": pestanas,
            "atencion": (
                conteo.get(EstadoGarantiaDispositivo.POR_VENCER, 0)
                + conteo.get(EstadoGarantiaDispositivo.PAUSADA, 0)
            ),
            "dias_aviso": DIAS_AVISO_GARANTIA,
        },
    )


def _contexto_gestion_garantia(dispositivo, formulario, pausa_abierta):
    """Contexto comun de la pantalla de salida y retorno."""
    pausas = list(dispositivo.pausas_garantia.all())
    garantia = calcular_estado_garantia(dispositivo, pausas=pausas)

    if pausa_abierta:
        url_envio = reverse(
            "registrar_retorno_garantia_equipos", args=[dispositivo.id]
        )
    else:
        url_envio = reverse(
            "registrar_salida_garantia_equipos", args=[dispositivo.id]
        )

    return {
        "dispositivo": dispositivo,
        "form": formulario,
        "garantia": garantia,
        "garantia_css": CSS_ESTADO_GARANTIA.get(garantia.estado, ""),
        "hoy": timezone.localdate(),
        "pausa_abierta": pausa_abierta,
        "pausas": pausas,
        "titulo": f"Garantía de {dispositivo.codigo}",
        "url_envio": url_envio,
    }


@exige_ver_equipos
@registrar_errores_vista("Error al abrir la garantía del equipo")
def gestionar_garantia(request, dispositivo_id):
    """La pantalla de garantia de un equipo: estado, historial y operacion.

    Es el destino unico desde el menu de acciones del listado, desde el panel
    de garantias y desde la ficha. Siempre muestra la situacion, aunque no
    haya nada que hacer: si el equipo no tiene garantia o ya vencio, se dice
    y punto, en vez de rebotar al usuario a otra pantalla.

    Verla solo exige permiso de consulta, para que la jefatura pueda llegar
    desde el panel. Pausar y reanudar exigen permiso de edicion, y de eso se
    encargan las vistas que reciben el formulario.
    """
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related("tipo", "marca", "modelo"),
        pk=dispositivo_id,
    )
    pausa = dispositivo.pausas_garantia.filter(fecha_retorno__isnull=True).first()
    permitido, motivo_sin_pausa = puede_pausarse(dispositivo)

    # El formulario solo se arma para quien puede usarlo y cuando hay algo que
    # registrar: reanudar si esta fuera, pausar si se puede pausar.
    formulario = None
    if puede_editar_equipos(request.user):
        if pausa is not None:
            formulario = RetornoGarantiaForm(pausa=pausa)
        elif permitido:
            formulario = SalidaGarantiaForm(dispositivo=dispositivo)

    contexto = _contexto_gestion_garantia(dispositivo, formulario, pausa)
    contexto["motivo_sin_pausa"] = "" if pausa else motivo_sin_pausa

    return render(
        request, "equipos/gestionar_garantia_equipos.html", contexto
    )


@exige_editar_equipos
@registrar_errores_vista("Error al registrar la salida del equipo")
def registrar_salida_garantia(request, dispositivo_id):
    """Anota que el equipo salio a reparacion y su garantia deja de correr."""
    dispositivo = get_object_or_404(Dispositivo, pk=dispositivo_id)
    # Se vuelve a la pantalla de garantia del equipo: alli se ve el
    # resultado del movimiento. La ficha ya no interviene en garantias.
    destino = redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    permitido, motivo = puede_pausarse(dispositivo)
    if not permitido:
        messages.error(request, motivo)
        return destino

    if request.method != "POST":
        return redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    formulario = SalidaGarantiaForm(request.POST, dispositivo=dispositivo)

    if not formulario.is_valid():
        # Se vuelve a pintar la pantalla con lo escrito y el error al lado del
        # campo, en lugar de redirigir y perder lo que el tecnico habia puesto.
        return render(
            request,
            "equipos/gestionar_garantia_equipos.html",
            _contexto_gestion_garantia(dispositivo, formulario, None),
        )

    # La fecha la pone el servidor: la pausa se anota el dia que se ejecuta.
    PausaGarantia.objects.create(
        dispositivo=dispositivo,
        fecha_salida=timezone.localdate(),
        motivo=formulario.cleaned_data["motivo"],
        registrado_por=request.user,
    )
    messages.success(
        request,
        f"Salida registrada. La garantía de {dispositivo.codigo} queda pausada.",
    )
    return destino


@exige_editar_equipos
@registrar_errores_vista("Error al registrar el retorno del equipo")
def registrar_retorno_garantia(request, dispositivo_id):
    """Cierra la pausa y suma al vencimiento los dias que estuvo fuera."""
    dispositivo = get_object_or_404(Dispositivo, pk=dispositivo_id)
    # Se vuelve a la pantalla de garantia del equipo: alli se ve el
    # resultado del movimiento. La ficha ya no interviene en garantias.
    destino = redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    pausa = dispositivo.pausas_garantia.filter(fecha_retorno__isnull=True).first()

    if pausa is None:
        messages.error(request, "El equipo no tiene ninguna salida pendiente.")
        return destino

    if request.method != "POST":
        return redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    formulario = RetornoGarantiaForm(request.POST, pausa=pausa)

    if not formulario.is_valid():
        return render(
            request,
            "equipos/gestionar_garantia_equipos.html",
            _contexto_gestion_garantia(dispositivo, formulario, pausa),
        )

    pausa.fecha_retorno = timezone.localdate()
    pausa.observaciones_retorno = formulario.cleaned_data[
        "observaciones_retorno"
    ]
    pausa.save()

    messages.success(
        request,
        f"Retorno registrado. Se sumaron {pausa.dias} día"
        f"{'s' if pausa.dias != 1 else ''} a la garantía de {dispositivo.codigo}.",
    )
    return destino
