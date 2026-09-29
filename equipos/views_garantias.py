# Garantias de los equipos: panel de seguimiento y pausas por envio a
# reparacion, con sus salidas y retornos.


from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from .forms import (
    CerrarGarantiaForm,
    GarantiaForm,
    RetornoGarantiaForm,
    SalidaGarantiaForm,
)
from .models import (
    DIAS_AVISO_GARANTIA,
    Dispositivo,
    EstadoDispositivo,
    EstadoGarantiaDispositivo,
    MotivoCierreGarantia,
    PausaGarantia,
)
from .decorators import exige_editar_equipos, exige_ver_equipos
from .permisos import puede_editar_equipos
from .services.garantia_service import (
    calcular_estado_cerrada,
    calcular_estado_garantia,
    puede_pausarse,
    puede_renovarse,
    puede_terminarse,
)
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
        # La garantia vigente y sus pausas se traen de una vez: sin esto el
        # panel hacia dos consultas por cada equipo de la lista.
        .prefetch_related("garantias__pausas")
    )

    filas = []
    conteo = {estado.value: 0 for estado in EstadoGarantiaDispositivo}

    for dispositivo in dispositivos:
        vigente = next(
            (
                garantia
                for garantia in dispositivo.garantias.all()
                if garantia.esta_vigente
            ),
            None,
        )
        estado = calcular_estado_garantia(dispositivo, garantia=vigente)
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


def _contexto_gestion_garantia(
    dispositivo,
    formulario=None,
    pausa_abierta=None,
    form_garantia=None,
    form_cierre=None,
):
    """Contexto de la pantalla de garantia: estado, operacion e historial."""
    garantia = calcular_estado_garantia(dispositivo)
    vigente = garantia.garantia
    pausas = list(vigente.pausas.all()) if vigente else []

    if pausa_abierta:
        url_envio = reverse(
            "registrar_retorno_garantia_equipos", args=[dispositivo.id]
        )
    else:
        url_envio = reverse(
            "registrar_salida_garantia_equipos", args=[dispositivo.id]
        )

    # El historial son las cerradas, de la mas reciente a la mas antigua, con
    # sus propias pausas: es el respaldo de lo que se reclamo en su momento.
    historial = [
        (cerrada, calcular_estado_cerrada(cerrada))
        for cerrada in dispositivo.garantias.filter(
            fecha_cierre__isnull=False
        ).prefetch_related("pausas")
    ]

    return {
        "dispositivo": dispositivo,
        # Serie y ubicacion sirven para confirmar que es el equipo correcto
        # antes de pulsar; la ubicacion vive en la asignacion vigente.
        "asignacion_actual": _obtener_asignacion_actual(dispositivo),
        "form": formulario,
        "form_garantia": form_garantia,
        "form_cierre": form_cierre,
        "garantia": garantia,
        "garantia_css": CSS_ESTADO_GARANTIA.get(garantia.estado, ""),
        "historial": historial,
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
    vigente = dispositivo.garantia_vigente
    pausa = (
        vigente.pausas.filter(fecha_retorno__isnull=True).first()
        if vigente
        else None
    )
    permitido, motivo_sin_pausa = puede_pausarse(dispositivo)

    # Los formularios solo se arman para quien puede usarlos y cuando hay algo
    # que registrar: reanudar si esta fuera, pausar si se puede pausar,
    # renovar siempre que el equipo no este de baja.
    formulario = None
    form_garantia = None
    form_cierre = None

    if puede_editar_equipos(request.user):
        if pausa is not None:
            formulario = RetornoGarantiaForm(pausa=pausa)
        elif permitido:
            formulario = SalidaGarantiaForm(dispositivo=dispositivo)

        if puede_renovarse(dispositivo)[0]:
            form_garantia = GarantiaForm(dispositivo=dispositivo)

        if puede_terminarse(dispositivo)[0]:
            form_cierre = CerrarGarantiaForm()

    contexto = _contexto_gestion_garantia(
        dispositivo,
        formulario,
        pausa,
        form_garantia,
        form_cierre,
    )
    contexto["motivo_sin_pausa"] = "" if pausa else motivo_sin_pausa

    return render(
        request, "equipos/gestionar_garantia_equipos.html", contexto
    )


@exige_editar_equipos
@registrar_errores_vista("Error al registrar la garantia del equipo")
def registrar_garantia(request, dispositivo_id):
    """Registra una garantia nueva y cierra la anterior si la habia.

    Es el mismo camino para la primera garantia del equipo y para una
    renovacion: si ya hay una vigente se cierra con motivo "renovada por
    otra" y queda en el historial. Las dos escrituras van en una transaccion
    para que no pueda quedar el equipo con dos vigentes ni con ninguna.
    """
    dispositivo = get_object_or_404(Dispositivo, pk=dispositivo_id)
    destino = redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    permitido, motivo = puede_renovarse(dispositivo)
    if not permitido:
        messages.error(request, motivo)
        return destino

    if request.method != "POST":
        return destino

    formulario = GarantiaForm(request.POST, dispositivo=dispositivo)

    if not formulario.is_valid():
        # Se vuelve a pintar la pantalla con lo escrito y el error al lado del
        # campo, en lugar de redirigir y perder lo que el usuario puso.
        return render(
            request,
            "equipos/gestionar_garantia_equipos.html",
            _contexto_gestion_garantia(
                dispositivo,
                form_garantia=formulario,
                form_cierre=CerrarGarantiaForm(),
            ),
        )

    anterior = dispositivo.garantia_vigente

    with transaction.atomic():
        if anterior is not None:
            anterior.cerrar(MotivoCierreGarantia.RENOVACION)

        garantia = formulario.save(commit=False)
        garantia.dispositivo = dispositivo
        garantia.registrado_por = request.user
        garantia.save()

    vence = garantia.fecha_fin.strftime("%d/%m/%Y")

    if anterior is None:
        messages.success(request, f"Garantia registrada. Vence el {vence}.")
    else:
        messages.success(
            request,
            f"Garantia renovada. La anterior queda en el historial y la nueva "
            f"vence el {vence}.",
        )

    return destino


@exige_editar_equipos
@registrar_errores_vista("Error al terminar la garantia del equipo")
def terminar_garantia(request, dispositivo_id):
    """Cierra a mano la garantia vigente, sin poner otra en su lugar.

    Se usa cuando la cobertura deja de valer antes de vencer: el proveedor
    incumplio, el equipo se sustituyo o la fecha estaba mal registrada. La
    fila no se borra, queda en el historial con su motivo.
    """
    dispositivo = get_object_or_404(Dispositivo, pk=dispositivo_id)
    destino = redirect("gestionar_garantia_equipos", dispositivo_id=dispositivo.id)

    permitido, motivo = puede_terminarse(dispositivo)
    if not permitido:
        messages.error(request, motivo)
        return destino

    if request.method != "POST":
        return destino

    formulario = CerrarGarantiaForm(request.POST)

    if not formulario.is_valid():
        return render(
            request,
            "equipos/gestionar_garantia_equipos.html",
            _contexto_gestion_garantia(
                dispositivo,
                form_garantia=GarantiaForm(dispositivo=dispositivo),
                form_cierre=formulario,
            ),
        )

    dispositivo.garantia_vigente.cerrar(
        formulario.cleaned_data["motivo"],
        formulario.cleaned_data["detalle"],
    )

    messages.success(
        request,
        f"Garantia de {dispositivo.codigo} terminada. Queda en el historial.",
    )
    return destino


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
        garantia=dispositivo.garantia_vigente,
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

    vigente = dispositivo.garantia_vigente
    pausa = (
        vigente.pausas.filter(fecha_retorno__isnull=True).first()
        if vigente
        else None
    )

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
