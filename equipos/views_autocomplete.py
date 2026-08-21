# Puntos JSON que alimentan los desplegables Select2 de los
# formularios: busqueda paginada de catalogos y empleados.


from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from core.constants.choices_constants import EstadoRegistro
from rrhh.models import Empleado
from .models import (
    MarcaDispositivo,
    ModeloDispositivo,
    Procedencia,
    TipoDispositivo,
)
from .decorators import exige_formularios_equipos_json
from .view_helpers import registrar_errores_vista


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
@registrar_errores_vista("Error al buscar procedencias de equipo")
def buscar_procedencias(request):
    """Alimenta el Select2 de procedencia en el formulario de equipo.

    Se busca por nombre y tambien por RTN, porque una factura trae el RTN y es
    lo que el tecnico tiene delante al registrar. Solo se ofrecen las activas:
    una procedencia desactivada no debe poder elegirse en un equipo nuevo.
    """
    consulta = request.GET.get("q", "").strip()
    procedencias = Procedencia.objects.filter(activo=True)

    if consulta:
        procedencias = procedencias.filter(
            Q(nombre__icontains=consulta) | Q(rtn__icontains=consulta)
        )

    pagina = _paginar_autocompletado(
        procedencias.order_by("nombre"),
        request,
        lambda procedencia: {
            "id": procedencia.id,
            "text": procedencia.nombre,
        },
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
