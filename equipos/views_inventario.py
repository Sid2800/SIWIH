# Alta, consulta, edicion y fotografias de los equipos: el nucleo del
# inventario. Incluye el listado, la busqueda y el detalle.


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.services.server_image.media_service import MediaService
from .forms import DispositivoCreateForm, ImagenDispositivoForm
from .models import (
    AreaGestora,
    AsignacionDispositivo,
    Dispositivo,
    EstadoDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    TipoDispositivo,
)
from .decorators import exige_editar_equipos, exige_ver_equipos
from .permisos import puede_visualizar_equipos
from .services.garantia_service import calcular_estado_garantia
from .view_helpers import (
    _obtener_asignacion_actual,
    _obtener_baja_dispositivo,
    _obtener_contexto_imagenes_dispositivo,
    _obtener_orden_trabajo_baja,
    registrar_errores_vista,
)
from .view_constants import (
    CSS_CRITICIDAD_DISPOSITIVO,
    CSS_ESTADO_DISPOSITIVO,
    CSS_ESTADO_GARANTIA,
    ETIQUETAS_ESTADO_DISPOSITIVO,
)


CAMPOS_UNICOS_DISPOSITIVO = {
    "numero_serie": "Ya existe un equipo con este número de serie.",
    "inventario_bienes_nacionales": (
        "Ya existe un equipo con este inventario de bienes nacionales."
    ),
    "inventario_numero_ficha": (
        "Ya existe un equipo con este número de ficha."
    ),
}


def _asignar_error_de_duplicado(form, error):
    """Convierte un choque al guardar en un error legible del formulario.

    Llegan por dos caminos. El modelo revalida en save(), asi que un duplicado
    aparece como ValidationError con sus campos ya identificados. Si el choque
    ocurre entre esa comprobacion y la insercion, lo detecta la base y llega
    como IntegrityError, del que solo se puede leer el nombre de la columna en
    el mensaje del motor.

    En ambos casos se responde con el formulario y su error. Cuando no se
    reconoce el campo se deja un aviso general en lugar de callar: es preferible
    decir que no se guardo a insinuar que si.
    """
    if isinstance(error, ValidationError):
        for campo, mensajes in getattr(error, "message_dict", {}).items():
            for mensaje in mensajes:
                form.add_error(
                    campo if campo in form.fields else None, mensaje
                )
        if form.errors:
            return
    else:
        detalle = str(error)
        for campo, mensaje in CAMPOS_UNICOS_DISPOSITIVO.items():
            if campo in detalle:
                form.add_error(campo, mensaje)
                return

    form.add_error(
        None,
        "No se pudo guardar el equipo porque otro registro usa los mismos "
        "datos. Revise el número de serie y los inventarios.",
    )


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
        dispositivo = None
        try:
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
        except (IntegrityError, ValidationError) as error:
            # El formulario ya comprueba los duplicados, pero entre esa consulta
            # y la insercion se sube la foto al servidor de imagenes, que tarda.
            # Si el usuario vuelve a enviar en ese rato, la segunda peticion ya
            # habia pasado la validacion y choca aqui contra el UNIQUE.
            # La restriccion de base es la ultima linea de defensa y no debe
            # llegarle al usuario como pagina de error.
            _asignar_error_de_duplicado(form, error)

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
        if dispositivo is not None:
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
        "procedencia",
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
    # Los registros recientes encabezan listado y busqueda. El id resuelve
    # empates si varios equipos comparten la misma fecha de creacion.
    return dispositivos.order_by(
        "-fecha_creado",
        "-pk",
    ).distinct()


def _preparar_dispositivos_para_tabla(dispositivos):
    # Agrega atributos temporales a cada objeto para simplificar el template.
    for dispositivo in dispositivos:
        dispositivo.asignacion_actual = (
            dispositivo.asignacion_activa_lista[0]
            if dispositivo.asignacion_activa_lista
            else None
        )
        dispositivo.estado_css = CSS_ESTADO_DISPOSITIVO.get(
            dispositivo.estado, ""
        )
        dispositivo.estado_etiqueta = ETIQUETAS_ESTADO_DISPOSITIVO.get(
            dispositivo.estado,
            dispositivo.get_estado_display(),
        )
        dispositivo.criticidad_css = CSS_CRITICIDAD_DISPOSITIVO.get(
            dispositivo.criticidad, ""
        )


@exige_ver_equipos
@registrar_errores_vista("Error en listado de equipos")
def listado_dispositivos(request):
    # Vista principal de inventario. Lee filtros GET, aplica consultas,
    # pagina resultados y renderiza la tabla.
    consulta = request.GET.get("q", "").strip()
    filtro_estado = request.GET.get("estado", "").strip()
    filtro_tipo = request.GET.get("tipo", "").strip()
    filtro_marca = request.GET.get("marca", "").strip()
    filtro_modelo = request.GET.get("modelo", "").strip()
    filtro_area_gestora = request.GET.get("area_gestora", "").strip()

    dispositivos = _aplicar_busqueda_dispositivos(
        _obtener_dispositivos_base(),
        consulta,
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
                "estado": filtro_estado,
                "tipo": filtro_tipo,
                "marca": filtro_marca,
                "modelo": filtro_modelo,
                "area_gestora": filtro_area_gestora,
            },
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
            "procedencia",
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
            "estado_css": CSS_ESTADO_DISPOSITIVO.get(dispositivo.estado, ""),
            "criticidad_css": CSS_CRITICIDAD_DISPOSITIVO.get(
                dispositivo.criticidad, ""
            ),
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
            "procedencia",
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
