# Mantenimiento de los catalogos del modulo: tipos, marcas, modelos y
# procedencias. Altas, ediciones y cambios de estado.


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import (
    MarcaCatalogoForm,
    ModeloCatalogoForm,
    ProcedenciaCatalogoForm,
    TipoCatalogoForm,
)
from .models import (
    MarcaDispositivo,
    ModeloDispositivo,
    Procedencia,
    TipoDispositivo,
)
from .decorators import exige_catalogo_equipos, exige_ver_equipos
from .view_helpers import registrar_errores_vista


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


def _url_catalogo_procedencias(procedencia=None):
    url = reverse("catalogo_procedencias_equipos")
    if procedencia is None:
        return url
    return f"{url}?procedencia={procedencia.pk}"


@exige_ver_equipos
@login_required
@registrar_errores_vista("Error en catalogo de procedencias")
def catalogo_procedencias(request):
    procedencia_editada = None
    procedencia_id = request.GET.get("procedencia")

    if str(procedencia_id or "").isdigit():
        procedencia_editada = get_object_or_404(
            Procedencia,
            pk=int(procedencia_id),
        )

    procedencias = Procedencia.objects.annotate(
        total_equipos=Count("dispositivos"),
    ).order_by("-activo", "nombre")

    return render(
        request,
        "equipos/catalogo_procedencias_equipos.html",
        {
            "procedencias": procedencias,
            "procedencia_editada": procedencia_editada,
            "form_procedencia": ProcedenciaCatalogoForm(
                instance=procedencia_editada
            ),
            "url_regresar": reverse("inicio_equipos"),
        },
    )


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar procedencia")
@require_POST
def agregar_procedencia_catalogo(request):
    form = ProcedenciaCatalogoForm(request.POST)

    if not form.is_valid():
        primer_error = next(
            (str(error) for errores in form.errors.values() for error in errores),
            "Revise los datos de la procedencia.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo_procedencias())

    procedencia = form.save()
    messages.success(
        request,
        f"Procedencia {procedencia.nombre} agregada correctamente.",
    )
    return redirect(_url_catalogo_procedencias())


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al editar procedencia")
@require_POST
def editar_procedencia_catalogo(request, procedencia_id):
    procedencia = get_object_or_404(Procedencia, pk=procedencia_id)
    form = ProcedenciaCatalogoForm(request.POST, instance=procedencia)

    if not form.is_valid():
        primer_error = next(
            (str(error) for errores in form.errors.values() for error in errores),
            "Revise los datos de la procedencia.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo_procedencias(procedencia))

    procedencia = form.save()
    messages.success(
        request,
        f"Procedencia {procedencia.nombre} actualizada correctamente.",
    )
    return redirect(_url_catalogo_procedencias())


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al cambiar estado de procedencia")
@require_POST
def cambiar_estado_procedencia(request, procedencia_id):
    procedencia = get_object_or_404(Procedencia, pk=procedencia_id)
    procedencia.activo = not procedencia.activo
    procedencia.save(update_fields=["activo"])

    messages.success(
        request,
        (
            f"Procedencia {procedencia.nombre} "
            f"{'reactivada' if procedencia.activo else 'desactivada'}."
        ),
    )
    return redirect(_url_catalogo_procedencias())
