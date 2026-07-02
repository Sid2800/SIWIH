import base64
import logging
from datetime import timedelta
from functools import wraps
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.constants.choices_constants import EstadoRegistro
from rrhh.models import Empleado

from .forms import (
    BajaDispositivoForm,
    DispositivoCreateForm,
    MantenimientoEquipoForm,
    RepuestoMantenimientoFormSet,
)
from .models import (
    AreaGestora,
    AsignacionDispositivo,
    BajaDispositivo,
    CriticidadDispositivo,
    Dispositivo,
    EstadoMantenimiento,
    EstadoDispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    TipoDispositivo,
)


logger = logging.getLogger("siwi")
LOG_EXTRA = {"app": "equipos_biomedicos"}


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


def inicio(request):
    # Pantalla de entrada del modulo. Solo renderiza el menu interno de Equipos.
    return render(
        request,
        'equipos_biomedicos/equipos_biomedicos_inicio.html'
    )


@registrar_errores_vista("Error al registrar equipo")
def registrar_dispositivo(request):
    # GET: muestra formulario vacio.
    # POST valido: crea el equipo y su asignacion inicial en una transaccion.
    form = DispositivoCreateForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
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

        messages.success(
            request,
            f"Equipo {dispositivo.codigo} registrado correctamente.",
        )
        return redirect("detalle_dispositivo_biomedicos", dispositivo_id=dispositivo.id)

    return render(
        request,
        "equipos_biomedicos/registrar_dispositivo_biomedicos.html",
        {
            "form": form,
            "titulo_pagina": "Registrar equipo",
            "titulo_formulario": "Registrar equipo",
            "icono_formulario": "bi bi-clipboard2-plus",
            "texto_boton_guardar": "Guardar equipo",
            "url_regresar": reverse("inicio_biomedicos"),
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
    # Busqueda flexible: tipo, marca, modelo, serie, inventarios o id numerico.
    if not consulta:
        return dispositivos

    filtro_busqueda = (
        Q(tipo__nombre__icontains=consulta)
        | Q(marca__nombre__icontains=consulta)
        | Q(modelo__nombre__icontains=consulta)
        | Q(area_gestora__nombre__icontains=consulta)
        | Q(color__nombre__icontains=consulta)
        | Q(numero_serie__icontains=consulta)
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
        EstadoDispositivo.OPERATIVO: "biomedicos-estado--operativo",
        EstadoDispositivo.EN_MANTENIMIENTO: "biomedicos-estado--media",
        EstadoDispositivo.FUERA_DE_SERVICIO: "biomedicos-estado--alta",
        EstadoDispositivo.DADO_DE_BAJA: "biomedicos-estado--inactivo",
    }
    criticidad_css = {
        CriticidadDispositivo.BAJA: "biomedicos-estado--operativo",
        CriticidadDispositivo.MEDIA: "biomedicos-estado--media",
        CriticidadDispositivo.ALTA: "biomedicos-estado--alta",
    }

    estado_etiqueta = {
        EstadoDispositivo.OPERATIVO: "Oper.",
        EstadoDispositivo.EN_MANTENIMIENTO: "Mant.",
        EstadoDispositivo.FUERA_DE_SERVICIO: "F. serv.",
        EstadoDispositivo.DADO_DE_BAJA: "Baja",
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
        dispositivo.garantia_estado, dispositivo.garantia_css = _obtener_estado_garantia(
            dispositivo
        )




def _obtener_mantenimientos_recientes(dispositivo, limite=5):
    return dispositivo.mantenimientos.select_related(
        "tecnico_responsable",
    ).prefetch_related(
        "repuestos_usados__repuesto",
    ).order_by(
        "-fecha_solicitud",
        "-fecha_creado",
    )[:limite]


def _sincronizar_estado_por_mantenimiento(dispositivo, mantenimiento, usuario):
    if dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA:
        return

    nuevo_estado = None
    if mantenimiento.estado == EstadoMantenimiento.EN_PROCESO:
        nuevo_estado = EstadoDispositivo.EN_MANTENIMIENTO
    elif mantenimiento.estado == EstadoMantenimiento.COMPLETADO:
        nuevo_estado = mantenimiento.estado_final_equipo

    if nuevo_estado and dispositivo.estado != nuevo_estado:
        Dispositivo.objects.filter(pk=dispositivo.pk).update(
            estado=nuevo_estado,
            modificado_por=usuario,
            fecha_modificado=timezone.now(),
        )
        dispositivo.estado = nuevo_estado


def _obtener_estado_garantia(dispositivo):
    # Calcula etiqueta visual de garantia sin guardarla en base de datos.
    if not dispositivo.fin_garantia:
        return "No indicada", "biomedicos-estado--inactivo"

    hoy = timezone.localdate()

    if dispositivo.fin_garantia < hoy:
        return "Vencida", "biomedicos-estado--alta"

    if dispositivo.fin_garantia <= hoy + timedelta(days=30):
        return "Vence pronto", "biomedicos-estado--media"

    return "Vigente", "biomedicos-estado--vigente"


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
        'equipos_biomedicos/listado_dispositivos_biomedicos.html',
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


@registrar_errores_vista("Error al abrir detalle de equipo")
def detalle_dispositivo(request, dispositivo_id):
    # Ficha solo lectura del equipo. El id llega desde la URL.
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related(
            "tipo",
            "marca",
            "modelo",
            "area_gestora",
            "color",
            "baja__registrado_por",
        ),
        pk=dispositivo_id,
    )
    asignacion_actual = _obtener_asignacion_actual(dispositivo)
    baja_dispositivo = _obtener_baja_dispositivo(dispositivo)
    mantenimientos_recientes = _obtener_mantenimientos_recientes(dispositivo)
    ultimo_mantenimiento = dispositivo.mantenimientos.filter(
        estado=EstadoMantenimiento.COMPLETADO,
    ).select_related(
        "tecnico_responsable",
    ).order_by(
        "-fecha_cierre",
        "-fecha_salida",
        "-fecha_solicitud",
        "-fecha_creado",
    ).first()
    mantenimiento_activo = dispositivo.mantenimientos.filter(
        estado=EstadoMantenimiento.EN_PROCESO,
    ).select_related(
        "tecnico_responsable",
    ).order_by(
        "-fecha_inicio",
        "-fecha_ingreso",
        "-fecha_solicitud",
        "-fecha_creado",
    ).first()

    return render(
        request,
        'equipos_biomedicos/detalle_dispositivo_biomedicos.html',
        {
            "dispositivo": dispositivo,
            "asignacion_actual": asignacion_actual,
            "baja_dispositivo": baja_dispositivo,
            "mantenimientos_recientes": mantenimientos_recientes,
            "ultimo_mantenimiento": ultimo_mantenimiento,
            "mantenimiento_activo": mantenimiento_activo,
        }
    )


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
        return redirect("detalle_dispositivo_biomedicos", dispositivo_id=dispositivo.id)

    asignacion_actual = _obtener_asignacion_actual(dispositivo)
    form = DispositivoCreateForm(
        request.POST or None,
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
        return redirect("detalle_dispositivo_biomedicos", dispositivo_id=dispositivo.id)

    return render(
        request,
        "equipos_biomedicos/registrar_dispositivo_biomedicos.html",
        {
            "form": form,
            "dispositivo": dispositivo,
            "titulo_pagina": f"Editar {dispositivo.codigo}",
            "titulo_formulario": "Editar equipo",
            "icono_formulario": "bi bi-pencil-square",
            "texto_boton_guardar": "Actualizar equipo",
            "url_baja": reverse(
                "dar_baja_dispositivo_biomedicos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
            "url_regresar": reverse(
                "detalle_dispositivo_biomedicos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
            "estado_label": "Estado *",
        },
    )


@registrar_errores_vista("Error al dar de baja equipo")
def dar_baja_dispositivo(request, dispositivo_id):
    # Crea BajaDispositivo y marca el equipo como DADO_DE_BAJA.
    # No elimina la ficha, por eso QR y detalle siguen funcionando.
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

    if _obtener_baja_dispositivo(dispositivo):
        messages.warning(request, "Este equipo ya tiene un registro de baja.")
        return redirect("detalle_dispositivo_biomedicos", dispositivo_id=dispositivo.id)

    form = BajaDispositivoForm(
        request.POST or None,
        initial={"fecha_baja": timezone.localdate()},
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            baja = form.save(commit=False)
            baja.dispositivo = dispositivo
            baja.registrado_por = request.user
            baja.save()

            Dispositivo.objects.filter(pk=dispositivo.pk).update(
                estado=EstadoDispositivo.DADO_DE_BAJA,
                modificado_por=request.user,
                fecha_modificado=timezone.now(),
            )

        messages.success(
            request,
            f"Equipo {dispositivo.codigo} dado de baja correctamente.",
        )
        return redirect("detalle_dispositivo_biomedicos", dispositivo_id=dispositivo.id)

    return render(
        request,
        "equipos_biomedicos/dar_baja_dispositivo_biomedicos.html",
        {
            "form": form,
            "dispositivo": dispositivo,
            "url_regresar": reverse(
                "detalle_dispositivo_biomedicos",
                kwargs={"dispositivo_id": dispositivo.id},
            ),
        },
    )



@registrar_errores_vista("Error al registrar mantenimiento de equipo")
def registrar_mantenimiento(request):
    consulta = request.GET.get("q", "").strip()
    dispositivo_id = _parametro_entero(
        request.POST.get("dispositivo_id") or request.GET.get("dispositivo", "")
    )
    dispositivo = None
    dispositivos_resultado = []

    if dispositivo_id:
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
        if dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA:
            messages.warning(
                request,
                "No se puede registrar mantenimiento a un equipo dado de baja.",
            )
            return redirect(
                "detalle_dispositivo_biomedicos",
                dispositivo_id=dispositivo.id,
            )
    elif consulta:
        dispositivos = _aplicar_busqueda_dispositivos(
            _obtener_dispositivos_base().exclude(
                estado=EstadoDispositivo.DADO_DE_BAJA,
            ),
            consulta,
        )
        dispositivos_resultado = list(_ordenar_dispositivos(dispositivos)[:10])
        _preparar_dispositivos_para_tabla(dispositivos_resultado)

    form = MantenimientoEquipoForm(
        request.POST or None,
        initial={
            "fecha_solicitud": timezone.localdate(),
            "estado": EstadoMantenimiento.EN_PROCESO,
        },
    )
    formset = RepuestoMantenimientoFormSet(
        request.POST or None,
        prefix="repuestos",
    )

    if request.method == "POST":
        if not dispositivo:
            messages.error(request, "Selecciona un equipo antes de registrar mantenimiento.")
        elif form.is_valid() and formset.is_valid():
            with transaction.atomic():
                mantenimiento = form.save(commit=False)
                mantenimiento.dispositivo = dispositivo
                mantenimiento.creado_por = request.user
                mantenimiento.save()

                formset.instance = mantenimiento
                formset.save()

                _sincronizar_estado_por_mantenimiento(
                    dispositivo,
                    mantenimiento,
                    request.user,
                )

            messages.success(
                request,
                f"Mantenimiento registrado para {dispositivo.codigo}.",
            )
            return redirect(
                "detalle_dispositivo_biomedicos",
                dispositivo_id=dispositivo.id,
            )

    return render(
        request,
        "equipos_biomedicos/registrar_mantenimiento_biomedicos.html",
        {
            "consulta": consulta,
            "dispositivo": dispositivo,
            "dispositivos_resultado": dispositivos_resultado,
            "form": form,
            "formset": formset,
        },
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
        "detalle_dispositivo_biomedicos",
        kwargs={"dispositivo_id": dispositivo_id},
    )
    base_url = getattr(settings, "EQUIPOS_QR_BASE_URL", "").strip()

    if base_url:
        return f"{base_url.rstrip('/')}{ruta_detalle}"

    return request.build_absolute_uri(ruta_detalle)


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
        "equipos_biomedicos/qr_dispositivo_biomedicos.html",
        {
            "dispositivo": dispositivo,
            "detalle_url": detalle_url,
            "qr_data_uri": _generar_qr_data_uri(detalle_url),
        },
    )


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
        'equipos_biomedicos/buscar_dispositivo_biomedicos.html',
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

        if termino.isdigit():
            filtro |= Q(pk=int(termino))

        empleados = empleados.filter(filtro)

    resultados = [
        {
            "id": empleado.id,
            "text": f"{empleado.id} | {empleado.dni} - {empleado.nombre_completo}",
        }
        for empleado in empleados.order_by(
            "primer_nombre",
            "primer_apellido",
            "dni",
        )[:10]
    ]

    return JsonResponse({"results": resultados})

