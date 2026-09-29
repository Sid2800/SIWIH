# Mantenimiento de los catalogos del modulo: tipos, marcas, modelos y
# procedencias. Altas, ediciones y cambios de estado.


from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import (
    MarcaEnTipoForm,
    ModeloCatalogoForm,
    ProcedenciaCatalogoForm,
    TipoCatalogoForm,
)
from .models import (
    CategoriaEquipo,
    Dispositivo,
    MarcaDispositivo,
    ModeloDispositivo,
    Procedencia,
    TipoDispositivo,
    TipoTecnologiaDispositivo,
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


def _parametro_modelo(request, nombre, modelo):
    """Lee un id de la querystring y devuelve el objeto, o None.

    La seleccion viaja en la URL y no en la sesion para que la pantalla se
    pueda recargar, compartir y navegar con el boton atras sin perder el paso
    en el que iba el usuario.
    """
    valor = (request.GET.get(nombre) or "").strip()

    if not valor.isdigit():
        return None

    return modelo.objects.filter(pk=int(valor)).first()


TIPOS_POR_PAGINA = 10


def _url_catalogo(tipo=None, marca=None, editar_tipo=None, request=None):
    """Arma la URL del catalogo conservando el paso en que esta el usuario.

    Tras cualquier operacion se vuelve al mismo sitio: si acababa de agregar
    un modelo a Epson dentro de impresoras, sigue ahi y puede agregar el
    siguiente sin volver a bajar por los tres pasos.

    Con `request` se conservan ademas la busqueda y los filtros de la lista de
    tipos, para no devolver al usuario a la primera pagina sin filtrar cada
    vez que da de alta algo.
    """
    url = reverse("catalogo_marcas_equipos")
    partes = []

    if tipo is not None:
        partes.append(f"tipo={tipo.pk}")
    if marca is not None:
        partes.append(f"marca={marca.pk}")
    # Renombrar un tipo es una accion aparte de seleccionarlo: antes
    # compartian parametro y al pulsar un tipo para ver sus marcas se abria el
    # formulario de renombrado, que no era lo que el usuario pedia.
    if editar_tipo is not None:
        partes.append(f"editar={editar_tipo.pk}")

    if request is not None:
        for nombre in ("q", "categoria", "tecnologia", "pagina"):
            valor = (request.GET.get(nombre) or "").strip()

            if valor:
                partes.append(f"{nombre}={quote(valor)}")

    return f"{url}?{'&'.join(partes)}" if partes else url


def _filtrar_tipos(request):
    """Lista de tipos segun la busqueda y los filtros, ya paginada.

    Se filtra y se pagina contra la base y no en el navegador. El catalogo de
    tipos puede llegar a varios miles, y mandarlos todos al navegador para
    filtrarlos alli haria una pagina de megas que tarda en dibujarse. Una
    consulta con LIKE sobre unos miles de filas es trabajo despreciable para
    MySQL, y el campo de busqueda espera a que se deje de teclear antes de
    pedir, asi que escribir "computadora" son una consulta y no once.
    """
    busqueda = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()
    tecnologia = (request.GET.get("tecnologia") or "").strip()

    tipos = (
        TipoDispositivo.objects
        .select_related("categoria")
        .annotate(
            total_equipos=Count("dispositivos", distinct=True),
            total_marcas=Count("marcas", distinct=True),
        )
        .order_by("-activo", "categoria__nombre", "nombre")
    )

    if busqueda:
        # Se busca tambien por categoria: quien escribe "electrico" espera
        # ver los de esa familia aunque el nombre no lleve la palabra.
        tipos = tipos.filter(
            Q(nombre__icontains=busqueda)
            | Q(categoria__nombre__icontains=busqueda)
        )

    if categoria.isdigit():
        tipos = tipos.filter(categoria_id=int(categoria))

    if tecnologia.isdigit():
        tipos = tipos.filter(tipo_tecnologia=int(tecnologia))

    paginador = Paginator(tipos, TIPOS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("pagina"))

    # Los enlaces de paginacion tienen que conservar busqueda y filtros: sin
    # esto, pasar a la pagina 2 perdia lo que el usuario acababa de filtrar.
    parametros = request.GET.copy()
    parametros.pop("pagina", None)

    return {
        "tipos": pagina.object_list,
        "pagina_tipos": pagina,
        "total_tipos": paginador.count,
        "busqueda_tipos": busqueda,
        "filtro_categoria": categoria,
        "filtro_tecnologia": tecnologia,
        "hay_filtros": bool(busqueda or categoria or tecnologia),
        "querystring_tipos": parametros.urlencode(),
        # Los botones de filtro: cada uno lleva la URL que lo activa y, si ya
        # esta activo, la que lo quita. Volver a pulsarlo muestra todo otra
        # vez, que es lo que espera cualquiera de un boton de filtro.
        "categorias_filtro": _botones_filtro(
            request,
            "categoria",
            [
                (str(c.pk), c.nombre)
                for c in CategoriaEquipo.objects.filter(activo=True)
            ],
        ),
        "tecnologias_filtro": _botones_filtro(
            request,
            "tecnologia",
            [
                (str(valor), etiqueta)
                for valor, etiqueta in TipoTecnologiaDispositivo.choices
            ],
        ),
    }


def _botones_filtro(request, parametro, opciones):
    """Construye los botones de un filtro, con su URL de activar y quitar."""
    actual = (request.GET.get(parametro) or "").strip()
    botones = []

    for valor, etiqueta in opciones:
        activo = actual == valor
        parametros = request.GET.copy()
        # Al cambiar un filtro se vuelve a la primera pagina: la 7 del listado
        # sin filtrar no tiene nada que ver con la 7 del filtrado.
        parametros.pop("pagina", None)

        if activo:
            parametros.pop(parametro, None)
        else:
            parametros[parametro] = valor

        consulta = parametros.urlencode()
        botones.append({
            "valor": valor,
            "etiqueta": etiqueta,
            "activo": activo,
            "url": f"?{consulta}" if consulta else "?",
        })

    return botones


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error en catalogo de equipos")
def catalogo_marcas_modelos(request):
    """Catalogo en tres pasos: tipo de equipo, sus marcas y sus modelos.

    Se muestran activos e inactivos: desactivar no es esconder, y desde aqui
    se reactiva. Los contadores dejan ver de un vistazo que ramas del catalogo
    estan vacias y cuales se estan usando.
    """
    tipo = _parametro_modelo(request, "tipo", TipoDispositivo)
    marca = _parametro_modelo(request, "marca", MarcaDispositivo)
    tipo_editado = _parametro_modelo(request, "editar", TipoDispositivo)

    # La marca solo tiene sentido dentro del tipo elegido. Si no le pertenece
    # se descarta en lugar de mostrar los modelos de otra combinacion.
    if marca and (not tipo or not tipo.marcas.filter(pk=marca.pk).exists()):
        marca = None

    marcas = []
    if tipo:
        marcas = (
            tipo.marcas
            .annotate(
                total_modelos=Count(
                    "modelos",
                    filter=Q(modelos__tipo=tipo),
                    distinct=True,
                ),
            )
            .order_by("-activo", "nombre")
        )

    modelos = []
    if tipo and marca:
        modelos = (
            ModeloDispositivo.objects
            .filter(tipo=tipo, marca=marca)
            .annotate(total_equipos=Count("dispositivos"))
            .order_by("-activo", "nombre")
        )

    contexto = {
        "tipo_seleccionado": tipo,
        "tipo_editado": tipo_editado,
        "marcas": marcas,
        "marca_seleccionada": marca,
        "modelos": modelos,
        # El mismo formulario sirve para alta y edicion; lo unico que
        # cambia es si se le pasa la instancia que se esta editando.
        "form_tipo": TipoCatalogoForm(instance=tipo_editado),
        "form_marca": MarcaEnTipoForm(tipo=tipo) if tipo else None,
        "form_modelo": (
            ModeloCatalogoForm(tipo=tipo, marca=marca)
            if tipo and marca
            else None
        ),
        # Sugerencias del campo de marca: el catalogo global, para
        # reutilizar una marca que ya existe en otro tipo en vez de
        # escribirla de nuevo y arriesgarse a un duplicado.
        "marcas_existentes": MarcaDispositivo.objects.filter(
            activo=True
        ).values_list("nombre", flat=True),
        "url_regresar": reverse("inicio_equipos"),
    }
    contexto.update(_filtrar_tipos(request))

    return render(
        request,
        "equipos/catalogo_marcas_equipos.html",
        contexto,
    )


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar marca")
@require_POST
def agregar_marca_catalogo(request, tipo_id):
    """Declara una marca en el tipo, creandola si no existia.

    Un solo gesto para el usuario: escribe el nombre. Que la marca ya exista
    en otro tipo o sea nueva es un detalle del sistema, no algo que deba
    resolver quien esta llenando el catalogo.
    """
    tipo = get_object_or_404(TipoDispositivo, pk=tipo_id)
    form = MarcaEnTipoForm(request.POST, tipo=tipo)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos de la marca.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo(tipo, request=request))

    marca, creada = form.guardar()
    messages.success(
        request,
        f"Marca {marca.nombre} {'creada y agregada' if creada else 'agregada'} "
        f"a {tipo.nombre}.",
    )
    # Se deja seleccionada para poder cargarle modelos de inmediato.
    return redirect(_url_catalogo(tipo, marca, request=request))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar modelo")
@require_POST
def agregar_modelo_catalogo(request, tipo_id, marca_id):
    tipo = get_object_or_404(TipoDispositivo, pk=tipo_id)
    marca = get_object_or_404(MarcaDispositivo, pk=marca_id)
    form = ModeloCatalogoForm(request.POST, tipo=tipo, marca=marca)

    if not form.is_valid():
        primer_error = next(
            (str(e) for errores in form.errors.values() for e in errores),
            "Revise los datos del modelo.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo(tipo, marca, request=request))

    modelo = form.save()
    messages.success(
        request,
        f"Modelo {modelo.nombre} agregado a {marca.nombre} en {tipo.nombre}.",
    )
    return redirect(_url_catalogo(tipo, marca, request=request))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al quitar marca del tipo")
@require_POST
def quitar_marca_tipo(request, tipo_id, marca_id):
    """Desvincula una marca de un tipo sin borrar la marca.

    Se bloquea si esa marca tiene modelos registrados en el tipo: quitarla
    dejaria esos modelos colgando de una combinacion que ya no existe. Primero
    hay que desactivar o reasignar los modelos.
    """
    tipo = get_object_or_404(TipoDispositivo, pk=tipo_id)
    marca = get_object_or_404(MarcaDispositivo, pk=marca_id)

    modelos = ModeloDispositivo.objects.filter(tipo=tipo, marca=marca).count()

    if modelos:
        messages.error(
            request,
            f"{marca.nombre} tiene {modelos} modelo"
            f"{'s' if modelos != 1 else ''} en {tipo.nombre}. "
            f"Quitelos antes de desvincular la marca.",
        )
        return redirect(_url_catalogo(tipo, marca, request=request))

    if Dispositivo.objects.filter(tipo=tipo, marca=marca).exists():
        messages.error(
            request,
            f"Hay equipos registrados como {tipo.nombre} de {marca.nombre}. "
            f"La marca no se puede quitar del tipo.",
        )
        return redirect(_url_catalogo(tipo, marca, request=request))

    tipo.marcas.remove(marca)
    messages.success(request, f"{marca.nombre} quitada de {tipo.nombre}.")
    return redirect(_url_catalogo(tipo, request=request))


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al cambiar estado de marca")
@require_POST
def cambiar_estado_marca(request, marca_id):
    # Afecta a todos los tipos donde figure: la marca es una sola en el
    # sistema y desactivarla la saca de todos los selectores.
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
    return redirect(request.POST.get("volver") or _url_catalogo())


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
        return redirect(_url_catalogo(editar_tipo=tipo, request=request))

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
        ModeloDispositivo.objects.select_related("marca", "tipo"), pk=modelo_id
    )
    modelo.activo = not modelo.activo
    modelo.save(update_fields=["activo"])

    messages.success(
        request,
        f"Modelo {modelo.nombre} {'reactivado' if modelo.activo else 'desactivado'}.",
    )
    return redirect(_url_catalogo(modelo.tipo, modelo.marca, request=request))


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
