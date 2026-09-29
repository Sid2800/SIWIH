# Mantenimiento de los catalogos del modulo: tipos, marcas, modelos y
# procedencias. Altas, ediciones y cambios de estado.


from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import (
    CatalogoSimpleForm,
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
    TecnologiaEquipo,
    TipoDispositivo,
    normalizar_nombre_catalogo,
)
from .decorators import (
    exige_catalogo_equipos,
    exige_catalogo_equipos_json,
    exige_ver_equipos,
)
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

    ORDEN = ("-activo", "categoria__nombre", "nombre")

    tipos = TipoDispositivo.objects.order_by(*ORDEN)

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
        tipos = tipos.filter(tecnologia_id=int(tecnologia))

    # Se pagina sobre los identificadores y los contadores se calculan solo
    # para las diez filas que se van a dibujar. Contando en la misma consulta,
    # los dos contadores obligan a unir la tabla de equipos y la de marcas y a
    # contar distinto sobre el producto de ambas, y eso lo paga tambien el
    # COUNT del paginador: sobre el catalogo entero, para saber cuantas
    # paginas hay, se acababa recorriendo un cruce de tres tablas cuando basta
    # contar filas de una.
    paginador = Paginator(tipos.values_list("pk", flat=True), TIPOS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get("pagina"))

    filas = (
        TipoDispositivo.objects
        .filter(pk__in=list(pagina.object_list))
        .select_related("categoria", "tecnologia")
        .annotate(
            total_equipos=Count("dispositivos", distinct=True),
            total_marcas=Count("marcas", distinct=True),
        )
        .order_by(*ORDEN)
    )

    # Los enlaces de paginacion tienen que conservar busqueda y filtros: sin
    # esto, pasar a la pagina 2 perdia lo que el usuario acababa de filtrar.
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    # "parcial" es como pide el navegador solo los trozos que cambian; no debe
    # acabar dentro de los enlaces que esos trozos dibujan, o al pulsarlos se
    # abriria una pagina sin menu ni estilos.
    parametros.pop("parcial", None)
    parametros.pop("form", None)

    return {
        "tipos": filas,
        "pagina_tipos": pagina,
        "total_tipos": paginador.count,
        "busqueda_tipos": busqueda,
        "filtro_categoria": categoria,
        "filtro_tecnologia": tecnologia,
        "hay_filtros": bool(busqueda or categoria or tecnologia),
        "querystring_tipos": parametros.urlencode(),
        # Los dos filtros son desplegables y no botones: son los mismos
        # campos que el formulario de arriba, asi que el usuario ya sabe
        # donde mirar, y "Todas" es una opcion visible en lugar de un gesto
        # que hay que adivinar.
        "categorias_filtro": CategoriaEquipo.objects.filter(activo=True),
        "tecnologias_filtro": TecnologiaEquipo.objects.filter(activo=True),
    }


def _preseleccion_catalogo(request):
    """Valores que el modal acaba de crear, para dejarlos ya elegidos.

    Quien agrega una categoria desde el modal la esta agregando porque la
    necesita para el tipo que esta escribiendo: lo natural es encontrarla ya
    seleccionada al volver, no tener que buscarla en el desplegable.
    """
    inicial = {}

    for parametro, campo in (
        ("nueva_categoria", "categoria"),
        ("nueva_tecnologia", "tecnologia"),
    ):
        valor = (request.GET.get(parametro) or "").strip()

        if valor.isdigit():
            inicial[campo] = int(valor)

    return inicial


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
        "form_tipo": TipoCatalogoForm(
            instance=tipo_editado,
            initial=_preseleccion_catalogo(request),
        ),
        "form_categoria": CatalogoSimpleForm(
            modelo=CategoriaEquipo,
            etiqueta="categoría",
        ),
        "form_tecnologia": CatalogoSimpleForm(
            modelo=TecnologiaEquipo,
            etiqueta="tecnología",
        ),
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
        # El formulario de arriba solo se manda en la respuesta parcial
        # cuando el usuario pidio abrir un tipo para editarlo -o volver al
        # modo alta-, que es el unico caso en que quiere que se rellene. En
        # los demas no viaja, para no borrarle lo que lleve escrito.
        "incluir_formulario": bool(
            request.GET.get("editar") or request.GET.get("form")
        ),
    }
    contexto.update(_filtrar_tipos(request))

    # El navegador puede pedir solo los trozos que cambian. Filtrar la lista o
    # elegir un tipo no toca el formulario de alta de arriba, y recargar la
    # pagina entera por eso borraba lo que el usuario llevaba escrito ahi.
    if request.GET.get("parcial"):
        return render(
            request,
            "equipos/partials/catalogo_parcial.html",
            contexto,
        )

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
    # Se vuelve con el tipo nuevo elegido y buscado por su nombre: la lista va
    # paginada y ordenada por categoria, asi que un tipo recien creado podia
    # caer en otra pagina y parecer que no se habia guardado.
    return redirect(f"{_url_catalogo(tipo)}&q={quote(tipo.nombre)}")


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


# =====================================================================
# Categorias y tecnologias
# ---------------------------------------------------------------------
# Son los dos catalogos de los que cuelga un tipo de equipo. Se dan de
# alta desde el propio formulario del tipo, en un cuadro de dialogo: si
# alguien esta registrando "NEBULIZADOR" y descubre que falta su
# categoria, mandarlo a otra pantalla le haria perder lo que llevaba
# escrito.
# =====================================================================


def _alta_catalogo_simple(request, modelo, etiqueta, parametro):
    """Alta comun de categoria y tecnologia: nombre y descripcion.

    Al terminar se vuelve a la pantalla del catalogo con el valor nuevo ya
    elegido en el desplegable, para que quien lo acaba de crear no tenga
    que buscarlo en la lista.
    """
    formulario = CatalogoSimpleForm(
        request.POST,
        modelo=modelo,
        etiqueta=etiqueta,
    )

    if not formulario.is_valid():
        primer_error = next(
            (str(e) for errores in formulario.errors.values() for e in errores),
            f"Revise los datos de la {etiqueta}.",
        )
        messages.error(request, primer_error)
        return redirect(_url_catalogo(request=request))

    creado = formulario.guardar()
    messages.success(
        request,
        f"{etiqueta.capitalize()} {creado.nombre} agregada correctamente.",
    )

    # Se vuelve con el valor nuevo preseleccionado en el formulario del tipo.
    destino = _url_catalogo(request=request)
    separador = "&" if "?" in destino else "?"

    return redirect(f"{destino}{separador}{parametro}={creado.pk}")


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar categoria de equipo")
@require_POST
def agregar_categoria_catalogo(request):
    return _alta_catalogo_simple(
        request,
        CategoriaEquipo,
        "categoría",
        "nueva_categoria",
    )


@exige_catalogo_equipos
@login_required
@registrar_errores_vista("Error al agregar tecnologia de equipo")
@require_POST
def agregar_tecnologia_catalogo(request):
    return _alta_catalogo_simple(
        request,
        TecnologiaEquipo,
        "tecnología",
        "nueva_tecnologia",
    )


# =====================================================================
# Renombrar en el sitio
# ---------------------------------------------------------------------
# Una marca y un modelo no tienen mas dato que su nombre, asi que
# corregir una errata no merece abrir un formulario ni recargar la
# pantalla: se escribe encima de la fila y se guarda. El tipo no entra
# aqui porque tiene ademas tecnologia y categorias, y eso si es un
# formulario.
# =====================================================================


def _nombre_pedido(request):
    """Nombre que llega para renombrar, ya normalizado.

    normalizar_nombre_catalogo recorta espacios y pasa a mayusculas, de modo
    que "  epson " y "EPSON" acaban siendo el mismo nombre y las
    comprobaciones de duplicado los detectan.
    """
    nombre = normalizar_nombre_catalogo(request.POST.get("nombre"))

    if not nombre:
        raise ValueError("Debe ingresar el nombre.")

    if len(nombre) > 100:
        raise ValueError("El nombre no puede pasar de 100 caracteres.")

    return nombre


@exige_catalogo_equipos_json
@login_required
@registrar_errores_vista("Error al renombrar marca")
@require_POST
def renombrar_marca_catalogo(request, marca_id):
    """Cambia el nombre de la marca en todo el sistema.

    Los equipos y los modelos que la usan apuntan por identificador, no por
    texto, asi que corregir la errata no toca nada de lo registrado.
    """
    marca = get_object_or_404(MarcaDispositivo, pk=marca_id)

    try:
        nombre = _nombre_pedido(request)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    if nombre != marca.nombre and MarcaDispositivo.objects.filter(
        nombre=nombre
    ).exists():
        return JsonResponse(
            {"error": f"Ya existe una marca llamada {nombre}."},
            status=400,
        )

    marca.nombre = nombre
    marca.save(update_fields=["nombre"])

    return JsonResponse({"nombre": marca.nombre})


@exige_catalogo_equipos_json
@login_required
@registrar_errores_vista("Error al renombrar modelo")
@require_POST
def renombrar_modelo_catalogo(request, modelo_id):
    """Cambia el nombre del modelo dentro de su pareja tipo-marca.

    El nombre solo tiene que ser unico ahi: la L3250 de Epson en impresoras no
    estorba a una L3250 de otra marca o de otro aparato.
    """
    modelo = get_object_or_404(
        ModeloDispositivo.objects.select_related("tipo", "marca"), pk=modelo_id
    )

    try:
        nombre = _nombre_pedido(request)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    hermano = (
        ModeloDispositivo.objects
        .filter(tipo=modelo.tipo, marca=modelo.marca, nombre=nombre)
        .exclude(pk=modelo.pk)
    )

    if hermano.exists():
        return JsonResponse(
            {
                "error": (
                    f"{modelo.marca.nombre} ya tiene un modelo {nombre} "
                    f"en {modelo.tipo.nombre}."
                )
            },
            status=400,
        )

    modelo.nombre = nombre
    modelo.save(update_fields=["nombre"])

    return JsonResponse({"nombre": modelo.nombre})


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
