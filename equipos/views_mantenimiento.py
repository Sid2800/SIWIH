"""Pantallas del mantenimiento: calendario, planes y ordenes de trabajo.

Tres pantallas y un monton de puntos JSON. Las pantallas son el panel (que
esta atrasado, que viene), el calendario de una persona y la hoja de trabajo.
Los puntos JSON son todo lo que se hace sin recargar: mover una visita,
agregar un equipo a la hoja, agregar una linea de actividad, pedir
sugerencias.

Que sea asincrono no es un adorno. La hoja se llena de pie junto al aparato,
escribiendo una linea tras otra; una recarga por linea perderia lo escrito
arriba y haria el trabajo mas lento que el papel, que es contra lo que esto
compite.
"""

import json
from datetime import date, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import (
    exige_mantenimiento_equipos,
    exige_mantenimiento_equipos_json,
    exige_ver_equipos,
)
from .forms import (
    ActividadEnOrdenForm,
    EquipoEnOrdenForm,
    MoverVisitaForm,
    OrdenTrabajoForm,
    PlanMantenimientoForm,
    RealizarVisitaForm,
    usuarios_de_mantenimiento,
)
from .models import (
    ActividadEnOrdenTrabajo,
    ClaseMantenimiento,
    Dispositivo,
    EquipoEnOrdenTrabajo,
    EstadoOrdenTrabajo,
    EstadoVisitaPreventiva,
    OrdenTrabajoMantenimiento,
    PlanMantenimiento,
    TipoDispositivo,
    VisitaPreventiva,
)
from .services import actividades_service
from .services.calendario_service import (
    calendario_de,
    crear_plan,
    mover_visita,
    omitir_visita,
    regenerar_visitas,
    registrar_realizacion,
    visitas_atrasadas,
)
from .view_helpers import registrar_errores_vista

# Cuantas ordenes se listan por pagina.
ORDENES_POR_PAGINA = 20

# Dias que el panel mira hacia adelante. Dos semanas es lo que se planifica de
# verdad: mas alla es una lista que nadie usa para decidir la semana.
DIAS_DE_HORIZONTE_DEL_PANEL = 14


def _cuerpo_json(request):
    """Lee el cuerpo de la peticion venga como JSON o como formulario.

    El JavaScript de la pagina manda JSON, pero conviene aceptar las dos
    formas: asi el mismo punto se puede probar desde una prueba con el cliente
    de Django sin armar el JSON a mano.
    """
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or b"{}")
        except (ValueError, TypeError):
            return {}

    return request.POST


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

@exige_ver_equipos
@registrar_errores_vista("Error al abrir el panel de mantenimiento")
def panel_mantenimiento(request):
    """Lo que hace falta saber al empezar el dia.

    Lo atrasado va primero y sin paginar: es la unica lista cuya longitud es
    en si misma la noticia. Si hay cuarenta preventivos vencidos, verlos de
    diez en diez lo esconde.
    """
    hoy = timezone.localdate()
    atrasadas = visitas_atrasadas()

    proximas = (
        VisitaPreventiva.objects.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            plan__activo=True,
            fecha_programada__gte=hoy,
            fecha_programada__lte=hoy + timedelta(days=DIAS_DE_HORIZONTE_DEL_PANEL),
        )
        .select_related(
            "plan",
            "plan__responsable",
            "plan__dispositivo",
            "plan__dispositivo__tipo",
        )
        .order_by("fecha_programada")
    )

    abiertas = (
        OrdenTrabajoMantenimiento.objects.filter(estado=EstadoOrdenTrabajo.ABIERTA)
        .select_related("tipo", "operario")
        .annotate(total_equipos=Count("equipos", distinct=True))
        .order_by("fecha")
    )

    # Equipos que deberian tener plan y no lo tienen. Es el agujero que de
    # otro modo no se ve: un aparato con frecuencia declarada pero sin plan no
    # aparece en ningun calendario y nadie lo echa de menos hasta que falla.
    sin_plan = (
        Dispositivo.objects.filter(
            plan_mantenimiento__isnull=True,
            baja__isnull=True,
        )
        .filter(
            Q(frecuencia_mantenimiento_meses__isnull=False)
            | Q(tipo__frecuencia_mantenimiento_meses__isnull=False)
        )
        .select_related("tipo", "marca")
        .order_by("tipo__nombre", "id")
    )

    return render(
        request,
        "equipos/panel_mantenimiento_equipos.html",
        {
            "titulo": "Mantenimiento",
            "hoy": hoy,
            "atrasadas": atrasadas,
            "total_atrasadas": atrasadas.count(),
            "proximas": proximas,
            "dias_horizonte": DIAS_DE_HORIZONTE_DEL_PANEL,
            "ordenes_abiertas": abiertas,
            "sin_plan": sin_plan[:50],
            "total_sin_plan": sin_plan.count(),
            "responsables": usuarios_de_mantenimiento(),
        },
    )


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------

def _mes_pedido(request, hoy):
    """El mes que se esta mirando, tomado de ?mes=2026-03."""
    crudo = (request.GET.get("mes") or "").strip()

    if crudo:
        try:
            anio, mes = crudo.split("-")
            return date(int(anio), int(mes), 1)
        except (ValueError, TypeError):
            # Un mes ilegible no es motivo para una pantalla de error: se
            # muestra el mes en curso, que es lo que se queria ver.
            pass

    return hoy.replace(day=1)


def _mes_vecino(primero, pasos):
    """El dia 1 del mes anterior o siguiente."""
    total = primero.month - 1 + pasos
    anio = primero.year + total // 12
    mes = total % 12 + 1

    return date(anio, mes, 1)


@exige_ver_equipos
@registrar_errores_vista("Error al abrir el calendario de mantenimiento")
def calendario_mantenimiento(request):
    """El calendario de una persona, mes a mes.

    Por defecto el de quien mira, porque el caso normal es un tecnico abriendo
    lo que le toca. Quien administra puede cambiar de responsable con el
    desplegable.
    """
    hoy = timezone.localdate()
    primero = _mes_pedido(request, hoy)
    siguiente = _mes_vecino(primero, 1)
    ultimo = siguiente - timedelta(days=1)

    responsables = list(usuarios_de_mantenimiento())
    elegido = request.user

    pedido = (request.GET.get("responsable") or "").strip()
    if pedido.isdigit():
        for usuario in responsables:
            if usuario.pk == int(pedido):
                elegido = usuario
                break

    dias = calendario_de(elegido, primero, ultimo, solo_pendientes=False)

    return render(
        request,
        "equipos/calendario_mantenimiento_equipos.html",
        {
            "titulo": "Calendario de mantenimiento",
            "hoy": hoy,
            "mes": primero,
            "mes_anterior": _mes_vecino(primero, -1).strftime("%Y-%m"),
            "mes_siguiente": siguiente.strftime("%Y-%m"),
            "dias": dias,
            "responsable_elegido": elegido,
            "responsables": responsables,
            "atrasadas": visitas_atrasadas(elegido),
            "total_visitas": sum(dia.total for dia in dias),
        },
    )


# ---------------------------------------------------------------------------
# Plan de un equipo
# ---------------------------------------------------------------------------

@exige_mantenimiento_equipos
@registrar_errores_vista("Error al programar el mantenimiento de un equipo")
def programar_mantenimiento(request, dispositivo_id):
    """Crea o corrige el plan preventivo de un equipo."""
    dispositivo = get_object_or_404(
        Dispositivo.objects.select_related("tipo", "marca", "modelo"),
        pk=dispositivo_id,
    )

    plan = PlanMantenimiento.objects.filter(dispositivo=dispositivo).first()

    # Un equipo dado de baja no se programa: estaria ocupando el calendario de
    # alguien para ir a revisar algo que ya no esta.
    if getattr(dispositivo, "baja", None) is not None:
        messages.error(
            request,
            "Ese equipo está dado de baja: no se le puede programar mantenimiento.",
        )
        return redirect("detalle_dispositivo_equipos", dispositivo_id=dispositivo.pk)

    if request.method == "POST":
        formulario = PlanMantenimientoForm(
            request.POST, instance=plan, dispositivo=dispositivo
        )

        if formulario.is_valid():
            with transaction.atomic():
                if plan is None:
                    plan = crear_plan(
                        dispositivo=dispositivo,
                        responsable=formulario.cleaned_data["responsable"],
                        frecuencia_meses=formulario.cleaned_data["frecuencia_meses"],
                        fecha_inicio=formulario.cleaned_data["fecha_inicio"],
                        trabaja_fines_de_semana=formulario.cleaned_data[
                            "trabaja_fines_de_semana"
                        ],
                        creado_por=request.user,
                        observaciones=formulario.cleaned_data.get("observaciones", ""),
                    )
                    messages.success(
                        request,
                        f"Mantenimiento programado. Primera visita: "
                        f"{plan.fecha_inicio:%d/%m/%Y}.",
                    )
                else:
                    plan = formulario.save()
                    # Cambiar frecuencia o responsable redibuja lo que viene;
                    # lo realizado se queda donde esta.
                    regenerar_visitas(plan)
                    messages.success(request, "Plan de mantenimiento actualizado.")

            return redirect(
                "detalle_dispositivo_equipos", dispositivo_id=dispositivo.pk
            )
    else:
        formulario = PlanMantenimientoForm(instance=plan, dispositivo=dispositivo)

    visitas = []
    if plan is not None:
        visitas = plan.visitas.select_related("orden").order_by(
            "-fecha_programada"
        )[:24]

    return render(
        request,
        "equipos/programar_mantenimiento_equipos.html",
        {
            "titulo": "Programar mantenimiento",
            "dispositivo": dispositivo,
            "plan": plan,
            "form": formulario,
            "visitas": visitas,
            "frecuencia_del_tipo": dispositivo.tipo.frecuencia_mantenimiento_meses,
        },
    )


@exige_mantenimiento_equipos
@registrar_errores_vista("Error al desactivar un plan de mantenimiento")
def cambiar_estado_plan(request, plan_id):
    """Activa o desactiva el plan sin borrar su historial."""
    if request.method != "POST":
        return redirect("panel_mantenimiento_equipos")

    plan = get_object_or_404(PlanMantenimiento, pk=plan_id)
    plan.activo = not plan.activo
    plan.save(update_fields=["activo", "fecha_modificado"])
    regenerar_visitas(plan)

    if plan.activo:
        messages.success(request, "Plan reactivado y calendario redibujado.")
    else:
        messages.info(
            request,
            "Plan desactivado. Las visitas realizadas se conservan.",
        )

    return redirect(
        "detalle_dispositivo_equipos", dispositivo_id=plan.dispositivo_id
    )


# ---------------------------------------------------------------------------
# Visitas: mover, realizar, omitir
# ---------------------------------------------------------------------------

@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al mover una visita de mantenimiento")
def mover_visita_calendario(request, visita_id):
    """Cambia la fecha de una visita y arrastra a las siguientes."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    visita = get_object_or_404(
        VisitaPreventiva.objects.select_related("plan", "plan__dispositivo"),
        pk=visita_id,
    )

    formulario = MoverVisitaForm(_cuerpo_json(request))

    if not formulario.is_valid():
        return JsonResponse(
            {"error": " ".join(formulario.errors.get("fecha", ["Fecha no válida."]))},
            status=400,
        )

    try:
        mover_visita(visita, formulario.cleaned_data["fecha"])
    except ValueError as detalle:
        return JsonResponse({"error": str(detalle)}, status=400)

    siguientes = list(
        visita.plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA
        ).order_by("fecha_programada")
    )

    return JsonResponse(
        {
            "ok": True,
            "fecha": visita.fecha_programada.isoformat(),
            "movida_a_mano": visita.movida_a_mano,
            # Se devuelven las siguientes porque es lo que la pantalla tiene
            # que repintar: mover una arrastro a las demas, y si solo se
            # actualizara la movida el calendario mentiria hasta la siguiente
            # recarga.
            "siguientes": [
                {
                    "id": otra.pk,
                    "fecha": otra.fecha_programada.isoformat(),
                }
                for otra in siguientes
            ],
        }
    )


@exige_mantenimiento_equipos
@registrar_errores_vista("Error al registrar una visita realizada")
def realizar_visita(request, visita_id):
    """Marca la visita como hecha y abre la hoja donde se escribe lo que se hizo.

    Las dos cosas van juntas a proposito: una visita marcada como hecha sin
    hoja no dice que se hizo, y la hoja es justamente lo que el taller venia
    llenando en papel.
    """
    visita = get_object_or_404(
        VisitaPreventiva.objects.select_related(
            "plan", "plan__dispositivo", "plan__dispositivo__tipo"
        ),
        pk=visita_id,
    )

    if visita.estado == EstadoVisitaPreventiva.REALIZADA:
        messages.info(request, "Esa visita ya estaba registrada.")

        if visita.orden_id:
            return redirect("orden_trabajo_equipos", orden_id=visita.orden_id)

        return redirect("calendario_mantenimiento_equipos")

    dispositivo = visita.plan.dispositivo

    if request.method == "POST":
        formulario = RealizarVisitaForm(request.POST)

        if formulario.is_valid():
            fecha = formulario.cleaned_data["fecha_realizada"]

            with transaction.atomic():
                # Si ya hay una orden abierta de ese tipo y esa fecha, el
                # equipo se suma a ella en lugar de abrir otra: una salida a
                # revisar cinco monitores es una hoja, no cinco.
                orden = (
                    OrdenTrabajoMantenimiento.objects.filter(
                        tipo=dispositivo.tipo,
                        clase=ClaseMantenimiento.PREVENTIVO,
                        estado=EstadoOrdenTrabajo.ABIERTA,
                        fecha=fecha,
                        operario=visita.plan.responsable,
                    )
                    .order_by("id")
                    .first()
                )

                if orden is None:
                    orden = OrdenTrabajoMantenimiento(
                        tipo=dispositivo.tipo,
                        clase=ClaseMantenimiento.PREVENTIVO,
                        fecha=fecha,
                        operario=visita.plan.responsable,
                        creado_por=request.user,
                    )
                    orden.save()

                EquipoEnOrdenTrabajo.objects.get_or_create(
                    orden=orden,
                    dispositivo=dispositivo,
                    defaults={
                        "ambiente": _ambiente_de(dispositivo),
                    },
                )

                registrar_realizacion(
                    visita,
                    fecha,
                    orden=orden,
                    observaciones=formulario.cleaned_data.get("observaciones", ""),
                )

            messages.success(
                request,
                f"Visita registrada en la orden {orden.numero_orden}. "
                "Escriba lo que se hizo.",
            )
            return redirect("orden_trabajo_equipos", orden_id=orden.pk)
    else:
        formulario = RealizarVisitaForm()

    return render(
        request,
        "equipos/realizar_visita_equipos.html",
        {
            "titulo": "Registrar visita realizada",
            "visita": visita,
            "dispositivo": dispositivo,
            "form": formulario,
        },
    )


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al omitir una visita de mantenimiento")
def omitir_visita_calendario(request, visita_id):
    """Da por no hecha una visita, dejando dicho por que."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    visita = get_object_or_404(VisitaPreventiva, pk=visita_id)
    datos = _cuerpo_json(request)

    try:
        omitir_visita(visita, (datos.get("motivo") or "").strip())
    except ValueError as detalle:
        return JsonResponse({"error": str(detalle)}, status=400)

    return JsonResponse({"ok": True, "motivo": visita.observaciones})


def _ambiente_de(dispositivo):
    """Donde esta el equipo ahora mismo, para proponerlo como ambiente."""
    abierta = (
        dispositivo.asignaciones.filter(fecha_fin__isnull=True)
        .select_related("ubicacion_fisica", "ubicacion")
        .first()
    )

    donde = getattr(abierta, "ubicacion_fisica", None) or getattr(
        abierta, "ubicacion", None
    )

    return str(donde)[:120] if donde else ""


# ---------------------------------------------------------------------------
# Ordenes de trabajo
# ---------------------------------------------------------------------------

@exige_ver_equipos
@registrar_errores_vista("Error al listar las ordenes de trabajo")
def listado_ordenes(request):
    """Las hojas de trabajo, de la mas reciente a la mas antigua."""
    ordenes = (
        OrdenTrabajoMantenimiento.objects.select_related("tipo", "operario")
        .annotate(
            total_equipos=Count("equipos", distinct=True),
            total_actividades=Count("actividades", distinct=True),
        )
        .order_by("-fecha", "-id")
    )

    busqueda = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    clase = (request.GET.get("clase") or "").strip()

    if busqueda:
        # Se busca por numero de orden y por tipo. El numero que la gente
        # tiene en la mano es "OTM-2026-00031" o simplemente "31", asi que se
        # acepta tanto el id como el texto del tipo.
        solo_digitos = "".join(c for c in busqueda if c.isdigit())
        filtro = Q(tipo__nombre__icontains=busqueda)

        if solo_digitos:
            filtro |= Q(pk=int(solo_digitos))

        ordenes = ordenes.filter(filtro)

    if estado.isdigit():
        ordenes = ordenes.filter(estado=int(estado))

    if clase.isdigit():
        ordenes = ordenes.filter(clase=int(clase))

    pagina = Paginator(ordenes, ORDENES_POR_PAGINA).get_page(
        request.GET.get("pagina")
    )

    return render(
        request,
        "equipos/listado_ordenes_equipos.html",
        {
            "titulo": "Órdenes de trabajo",
            "pagina": pagina,
            "ordenes": pagina.object_list,
            "busqueda": busqueda,
            "estado": estado,
            "clase": clase,
            "estados": EstadoOrdenTrabajo.choices,
            "clases": ClaseMantenimiento.choices,
        },
    )


@exige_mantenimiento_equipos
@registrar_errores_vista("Error al crear una orden de trabajo")
def crear_orden(request):
    """Levanta una hoja nueva.

    Sirve igual para el correctivo -se dano algo y hay que ir- y para la
    solicitud que llego en papel, que es el caso que de verdad importa: quien
    recibe el papel es el mismo que levanta la orden, porque quien lo escribio
    no usa el sistema.
    """
    if request.method == "POST":
        formulario = OrdenTrabajoForm(request.POST)

        if formulario.is_valid():
            orden = formulario.save(commit=False)
            orden.creado_por = request.user
            orden.save()

            messages.success(
                request,
                f"Orden {orden.numero_orden} abierta. Agregue los equipos.",
            )
            return redirect("orden_trabajo_equipos", orden_id=orden.pk)
    else:
        inicial = {"operario": request.user.pk}
        formulario = OrdenTrabajoForm(initial=inicial)

    return render(
        request,
        "equipos/crear_orden_equipos.html",
        {
            "titulo": "Nueva orden de trabajo",
            "form": formulario,
        },
    )


def _contexto_de_la_orden(orden, request):
    """Todo lo que la hoja necesita mostrar, en una sola consulta por bloque."""
    equipos = (
        orden.equipos.select_related(
            "dispositivo", "dispositivo__marca", "dispositivo__modelo"
        ).order_by("id")
    )

    actividades = orden.actividades.select_related("actividad").order_by(
        "posicion", "id"
    )

    minutos = [fila.minutos for fila in equipos if fila.minutos is not None]

    return {
        "orden": orden,
        "equipos": equipos,
        "actividades": actividades,
        "form_equipo": EquipoEnOrdenForm(orden=orden),
        "form_actividad": ActividadEnOrdenForm(),
        # Lo que normalmente se le hace a este tipo, para poder elegir en vez
        # de escribir. Se ofrece, no se precarga: nadie debe acabar firmando
        # una tarea que no hizo.
        "habituales": actividades_service.habituales_del_tipo(orden.tipo),
        "total_minutos": sum(minutos) if minutos else None,
        "puede_editar": orden.esta_abierta,
    }


@exige_ver_equipos
@registrar_errores_vista("Error al abrir una orden de trabajo")
def orden_trabajo(request, orden_id):
    """La hoja: cabecera, equipos atendidos y lo que se hizo."""
    orden = get_object_or_404(
        OrdenTrabajoMantenimiento.objects.select_related(
            "tipo", "operario", "jefe_servicio", "creado_por"
        ),
        pk=orden_id,
    )

    contexto = _contexto_de_la_orden(orden, request)
    contexto["titulo"] = orden.numero_orden

    return render(request, "equipos/orden_trabajo_equipos.html", contexto)


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al agregar un equipo a la orden de trabajo")
def agregar_equipo_orden(request, orden_id):
    """Suma una fila a la hoja."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    orden = get_object_or_404(OrdenTrabajoMantenimiento, pk=orden_id)

    if not orden.esta_abierta:
        return JsonResponse(
            {"error": "La orden está cerrada: ya no admite cambios."}, status=400
        )

    formulario = EquipoEnOrdenForm(request.POST, orden=orden)

    if not formulario.is_valid():
        return JsonResponse({"errores": formulario.errors}, status=400)

    fila = formulario.save()

    return JsonResponse(
        {
            "ok": True,
            "fila": {
                "id": fila.pk,
                # La pantalla lo usa para quitar ese equipo del desplegable:
                # ofrecerlo otra vez solo sirve para que la unicidad lo
                # rechace con un error que no explica nada.
                "id_dispositivo": fila.dispositivo_id,
                "codigo": fila.dispositivo.codigo,
                "equipo": str(fila.dispositivo.tipo.nombre),
                "ambiente": fila.ambiente,
                "hora_inicio": (
                    fila.hora_inicio.strftime("%H:%M") if fila.hora_inicio else ""
                ),
                "hora_final": (
                    fila.hora_final.strftime("%H:%M") if fila.hora_final else ""
                ),
                "minutos": fila.minutos,
            },
        }
    )


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al quitar un equipo de la orden de trabajo")
def quitar_equipo_orden(request, fila_id):
    """Saca una fila de la hoja mientras sigue abierta."""
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    fila = get_object_or_404(
        EquipoEnOrdenTrabajo.objects.select_related("orden"), pk=fila_id
    )

    if not fila.orden.esta_abierta:
        return JsonResponse(
            {"error": "La orden está cerrada: ya no admite cambios."}, status=400
        )

    # Una visita preventiva apuntando a esta orden se queda sin el equipo que
    # la justificaba. Es mejor impedirlo que dejar la visita diciendo que se
    # hizo en una hoja donde el aparato no aparece.
    if fila.orden.visitas.filter(
        plan__dispositivo_id=fila.dispositivo_id
    ).exists():
        return JsonResponse(
            {
                "error": (
                    "Ese equipo entró por una visita del calendario. Anule la "
                    "visita si no se atendió."
                )
            },
            status=400,
        )

    fila.delete()

    return JsonResponse({"ok": True})


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al agregar una actividad a la orden de trabajo")
def agregar_actividad_orden(request, orden_id):
    """Agrega una linea de lo que se hizo, escrita a mano.

    Es el punto central de la pantalla. La linea se guarda en la hoja y
    tambien en el catalogo, de modo que la proxima vez se pueda sugerir. El
    catalogo no rechaza nada por no estar en una lista: lo que entra es lo que
    de verdad se hizo.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    orden = get_object_or_404(
        OrdenTrabajoMantenimiento.objects.select_related("tipo"), pk=orden_id
    )

    if not orden.esta_abierta:
        return JsonResponse(
            {"error": "La orden está cerrada: ya no admite cambios."}, status=400
        )

    formulario = ActividadEnOrdenForm(_cuerpo_json(request))

    if not formulario.is_valid():
        return JsonResponse({"errores": formulario.errors}, status=400)

    with transaction.atomic():
        actividad = actividades_service.registrar_actividad(
            formulario.cleaned_data["nombre"], tipo=orden.tipo
        )

        # La misma linea dos veces en la misma hoja no aporta nada y la
        # unicidad la rechazaria con un error que no explica nada.
        if orden.actividades.filter(actividad=actividad).exists():
            return JsonResponse(
                {
                    "error": (
                        f"«{actividad.nombre}» ya está en esta orden. Si hace "
                        "falta precisar algo, use el detalle de esa línea."
                    )
                },
                status=400,
            )

        ultima = orden.actividades.order_by("-posicion").first()

        linea = ActividadEnOrdenTrabajo(
            orden=orden,
            actividad=actividad,
            posicion=(ultima.posicion + 1) if ultima else 1,
            detalle=formulario.cleaned_data.get("detalle", ""),
            registrado_por=request.user,
        )
        linea.save()

    return JsonResponse(
        {
            "ok": True,
            "linea": {
                "id": linea.pk,
                "posicion": linea.posicion,
                "nombre": actividad.nombre,
                "detalle": linea.detalle,
                "texto": linea.texto,
                # Dice si la linea es nueva en el catalogo. La pantalla lo usa
                # para avisar de que a partir de ahora se va a sugerir, que es
                # lo que hace util escribirla bien la primera vez.
                "nueva_en_catalogo": actividad.veces_usada <= 1,
            },
        }
    )


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al quitar una actividad de la orden de trabajo")
def quitar_actividad_orden(request, linea_id):
    """Borra una linea de la hoja.

    No se descuenta el uso en el catalogo: la linea se escribio y la palabra
    ya forma parte del vocabulario del taller. Descontarla haria que una
    correccion de dedo borrara una actividad que si se usa.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)

    linea = get_object_or_404(
        ActividadEnOrdenTrabajo.objects.select_related("orden"), pk=linea_id
    )

    if not linea.orden.esta_abierta:
        return JsonResponse(
            {"error": "La orden está cerrada: ya no admite cambios."}, status=400
        )

    linea.delete()

    return JsonResponse({"ok": True})


@exige_mantenimiento_equipos_json
@registrar_errores_vista("Error al sugerir actividades de mantenimiento")
def sugerir_actividades(request):
    """Las sugerencias del autocompletado, segun lo que se va escribiendo."""
    texto = (request.GET.get("q") or "").strip()
    tipo_id = (request.GET.get("tipo") or "").strip()
    tipo = None

    if tipo_id.isdigit():
        tipo = TipoDispositivo.objects.filter(pk=int(tipo_id)).first()

    sugerencias = actividades_service.sugerir(texto, tipo=tipo)

    return JsonResponse(
        {
            "sugerencias": [
                {
                    "id": actividad.pk,
                    "nombre": actividad.nombre,
                    "veces": actividad.veces_usada,
                }
                for actividad in sugerencias
            ]
        }
    )


@exige_mantenimiento_equipos
@registrar_errores_vista("Error al cerrar una orden de trabajo")
def cerrar_orden(request, orden_id):
    """Cierra la hoja: a partir de aqui no se toca.

    Se exige al menos un equipo y al menos una linea de lo que se hizo. Una
    hoja cerrada sin ninguna de las dos cosas no documenta nada, y cerrarla
    es justamente lo que la vuelve inmodificable.
    """
    if request.method != "POST":
        return redirect("orden_trabajo_equipos", orden_id=orden_id)

    orden = get_object_or_404(OrdenTrabajoMantenimiento, pk=orden_id)

    if not orden.esta_abierta:
        messages.info(request, "Esa orden ya estaba cerrada.")
        return redirect("orden_trabajo_equipos", orden_id=orden.pk)

    faltas = []

    if not orden.equipos.exists():
        faltas.append("no tiene ningún equipo")

    if not orden.actividades.exists():
        faltas.append("no dice qué se hizo")

    if faltas:
        messages.error(
            request,
            f"No se puede cerrar la orden: {' y '.join(faltas)}.",
        )
        return redirect("orden_trabajo_equipos", orden_id=orden.pk)

    orden.estado = EstadoOrdenTrabajo.CERRADA
    orden.cerrada_por = request.user
    orden.fecha_cierre = timezone.now()
    orden.save(update_fields=["estado", "cerrada_por", "fecha_cierre"])

    messages.success(request, f"Orden {orden.numero_orden} cerrada.")

    return redirect("orden_trabajo_equipos", orden_id=orden.pk)


@exige_ver_equipos
@registrar_errores_vista("Error al imprimir una orden de trabajo")
def imprimir_orden(request, orden_id):
    """La hoja en el formato que el taller venia llenando a mano.

    Se imprime desde el navegador y no se genera como PDF del servidor porque
    lo que se necesita es el papel para firmar, y el formato es el mismo que
    ya se usaba: una hoja por tipo de equipo, con sus aparatos, sus horas, la
    lista de lo que se hizo y el espacio de las dos firmas.
    """
    orden = get_object_or_404(
        OrdenTrabajoMantenimiento.objects.select_related(
            "tipo", "operario", "jefe_servicio"
        ),
        pk=orden_id,
    )

    equipos = orden.equipos.select_related(
        "dispositivo", "dispositivo__marca", "dispositivo__modelo"
    ).order_by("id")

    return render(
        request,
        "equipos/imprimir_orden_equipos.html",
        {
            "orden": orden,
            "equipos": equipos,
            "actividades": orden.actividades.select_related("actividad").order_by(
                "posicion", "id"
            ),
            # El formato en papel reserva un numero de filas fijo; se rellena
            # para que la tabla impresa no quede a medias.
            "filas_en_blanco": range(max(0, 8 - equipos.count())),
        },
    )
