# Garantias de los equipos: panel de seguimiento y pausas por envio a
# reparacion, con sus salidas y retornos.


from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .forms import RetornoGarantiaForm, SalidaGarantiaForm
from .models import (
    DIAS_AVISO_GARANTIA,
    Dispositivo,
    EstadoDispositivo,
    EstadoGarantiaDispositivo,
    PausaGarantia,
)
from .decorators import exige_editar_equipos, exige_ver_equipos
from .permisos import puede_editar_equipos
from .services.garantia_service import calcular_estado_garantia, puede_pausarse
from .view_helpers import _obtener_asignacion_actual, registrar_errores_vista
from .view_constants import CSS_ESTADO_GARANTIA


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
        # Serie y ubicacion sirven para confirmar que es el equipo correcto
        # antes de pulsar; la ubicacion vive en la asignacion vigente.
        "asignacion_actual": _obtener_asignacion_actual(dispositivo),
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
