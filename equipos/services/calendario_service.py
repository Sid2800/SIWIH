"""El calendario de preventivos: que dia le toca a cada equipo y a quien.

Las fechas no se escriben a mano una por una. Del plan de un equipo -su
frecuencia y su primera visita- sale una cadena de visitas hacia adelante, y
esa cadena se vuelve a calcular cada vez que cambia algo que la afecta.

Tres reglas gobiernan todo lo de aqui, y conviene tenerlas juntas porque el
resto son consecuencias:

1. Lo realizado no se toca. Una visita hecha es un hecho; cambiarle la fecha
   seria falsear el historial. Solo las programadas se mueven.

2. La siguiente visita se cuenta desde la fecha en que se hizo la anterior, no
   desde la que estaba programada. Si el preventivo de marzo se hizo el 20 de
   abril, el siguiente semestral toca en octubre y no en septiembre: lo que el
   intervalo protege es el tiempo que el aparato lleva sin revisarse.

3. Mover una visita arrastra a las que vienen detras. Correr una fecha dos
   semanas y dejar la siguiente en su sitio acortaria ese intervalo sin que
   nadie lo haya decidido.

De la 2 y la 3 sale que la cadena se regenera, y de ahi la unica sutileza del
archivo: una visita que alguien movio a mano no se regenera. Se movio por un
motivo que el calculo no conoce -una compra, un permiso, una sala cerrada por
obra- y pasa a ser ancla de lo que viene detras.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from ..models import (
    HORIZONTE_PREVENTIVO_MESES,
    EstadoVisitaPreventiva,
    PlanMantenimiento,
    VisitaPreventiva,
    corresponde_dia_habil,
    sumar_meses,
)


def horizonte_del_calendario(hoy=None):
    """Hasta que fecha se dibujan visitas.

    Mas alla de esto no se crean filas: serian fechas que nadie va a mirar y
    que se van a recalcular de todos modos cuando se hagan las de en medio.
    Cada visita realizada empuja el horizonte hacia adelante.
    """
    return sumar_meses(hoy or timezone.localdate(), HORIZONTE_PREVENTIVO_MESES)


def _ancla_de(plan):
    """Desde que fecha se cuenta la siguiente visita automatica.

    Es la fecha en que se hizo lo ultimo que se hizo, y solo eso. Si no se ha
    hecho nada todavia, la cadena no tiene ancla: la primera visita es la
    fecha de inicio del plan tal cual.

    Lo que alguien movio a mano NO sirve de ancla, aunque sea posterior. Una
    visita de 2028 corrida a mano no dice nada sobre cuando toca la de 2027:
    tomarla como ancla borraba todas las de en medio, porque el calculo
    arrancaba despues de ella.
    """
    ultima = plan.ultima_realizada

    if ultima and ultima.fecha_realizada:
        return ultima.fecha_realizada

    return None


def _visitas_intocables(plan):
    """Las fechas programadas que una regeneracion tiene que respetar.

    Son las que alguien movio a mano. Se movieron por un motivo que el calculo
    no conoce -una compra, un permiso, una sala cerrada por obra- y devolverlas
    a la fecha calculada seria deshacer una decision tomada.
    """
    return list(
        plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            movida_a_mano=True,
        ).values_list("fecha_programada", flat=True)
    )


def _choca_con_una_intocable(fecha, intocables, frecuencia_meses):
    """Si esa fecha calculada es, en la practica, una visita que ya existe.

    Sin esta comprobacion una visita movida a mano y la que el calculo pone en
    su lugar quedarian las dos en el calendario, a pocos dias una de otra, y
    el tecnico iria dos veces al mismo aparato. Se considera la misma cuando
    cae dentro de media frecuencia: lo que esta mas cerca que eso no es la
    siguiente visita, es la misma corrida.
    """
    if not intocables:
        return False

    margen = max(1, int(frecuencia_meses * 30 / 2))

    return any(abs((fecha - otra).days) < margen for otra in intocables)


@transaction.atomic
def regenerar_visitas(plan, hoy=None):
    """Vuelve a dibujar las visitas automaticas del plan hasta el horizonte.

    Borra y reconstruye solo lo automatico y futuro. Lo realizado y lo movido
    a mano sobrevive siempre: son los dos tipos de dato que el calculo no
    puede reponer si los pierde.

    Devuelve la lista de visitas programadas que quedo, ordenada.
    """
    hoy = hoy or timezone.localdate()

    if not plan.activo:
        # Un plan desactivado no ocupa el calendario de nadie. Lo realizado
        # se queda como historial.
        plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            movida_a_mano=False,
        ).delete()
        return []

    plan.visitas.filter(
        estado=EstadoVisitaPreventiva.PROGRAMADA,
        movida_a_mano=False,
    ).delete()

    ancla = _ancla_de(plan)
    limite = horizonte_del_calendario(hoy)
    intocables = _visitas_intocables(plan)

    if ancla is None:
        # Plan nuevo: la primera visita es la que se pidio, movida a dia
        # habil si hace falta.
        siguiente = corresponde_dia_habil(
            plan.fecha_inicio, plan.trabaja_fines_de_semana
        )
    else:
        siguiente = corresponde_dia_habil(
            sumar_meses(ancla, plan.frecuencia_meses),
            plan.trabaja_fines_de_semana,
        )

    nuevas = []

    # El tope por iteraciones es una red, no la condicion de salida: con
    # frecuencia de un mes y dos anios de horizonte salen 24 visitas. Si
    # alguna vez una fecha dejara de avanzar, es preferible cortar que llenar
    # la tabla.
    for _ in range(200):
        if siguiente is None or siguiente > limite:
            break

        # La cadena sigue avanzando aunque este hueco lo ocupe ya una visita
        # movida a mano: lo que se salta es crear una duplicada, no el turno.
        if not _choca_con_una_intocable(
            siguiente, intocables, plan.frecuencia_meses
        ):
            nuevas.append(
                VisitaPreventiva(plan=plan, fecha_programada=siguiente)
            )

        siguiente = corresponde_dia_habil(
            sumar_meses(siguiente, plan.frecuencia_meses),
            plan.trabaja_fines_de_semana,
        )

    if nuevas:
        # bulk_create se salta clean(), y aqui es correcto: estas filas las
        # construyo yo con fecha calculada y estado programada, que es
        # exactamente lo que clean() comprobaria.
        VisitaPreventiva.objects.bulk_create(nuevas)

    return list(
        plan.visitas.filter(estado=EstadoVisitaPreventiva.PROGRAMADA).order_by(
            "fecha_programada", "id"
        )
    )


@transaction.atomic
def crear_plan(
    dispositivo,
    responsable,
    frecuencia_meses,
    fecha_inicio,
    trabaja_fines_de_semana,
    creado_por,
    observaciones="",
):
    """Programa el preventivo de un equipo y le llena el calendario."""
    plan = PlanMantenimiento(
        dispositivo=dispositivo,
        responsable=responsable,
        frecuencia_meses=frecuencia_meses,
        fecha_inicio=fecha_inicio,
        trabaja_fines_de_semana=trabaja_fines_de_semana,
        observaciones=observaciones,
        creado_por=creado_por,
    )
    plan.save()
    regenerar_visitas(plan)

    return plan


@transaction.atomic
def mover_visita(visita, nueva_fecha):
    """Cambia la fecha de una visita programada y arrastra a las siguientes.

    El desplazamiento se aplica en dias y no recalculando desde cero para que
    el intervalo entre visitas se conserve: si el preventivo de marzo se corre
    dos semanas, el de septiembre se corre las mismas dos semanas y los seis
    meses entre uno y otro siguen siendo seis meses.

    La visita movida queda marcada, de modo que una regeneracion posterior no
    la devuelva a la fecha calculada.
    """
    if visita.estado != EstadoVisitaPreventiva.PROGRAMADA:
        raise ValueError(
            "Una visita que ya se realizó no cambia de fecha: es un hecho."
        )

    anterior = visita.fecha_programada
    nueva_fecha = corresponde_dia_habil(
        nueva_fecha, visita.plan.trabaja_fines_de_semana
    )

    if nueva_fecha == anterior:
        return visita

    desplazamiento = (nueva_fecha - anterior).days

    # Las que venian detras, antes de mover esta. Se resuelven a lista antes
    # de tocar nada para que el propio cambio no altere el conjunto.
    siguientes = list(
        visita.plan.visitas.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            fecha_programada__gt=anterior,
        ).exclude(pk=visita.pk)
    )

    visita.fecha_programada = nueva_fecha
    visita.movida_a_mano = True
    visita.save(update_fields=["fecha_programada", "movida_a_mano"])

    for otra in siguientes:
        otra.fecha_programada = corresponde_dia_habil(
            otra.fecha_programada + timedelta(days=desplazamiento),
            visita.plan.trabaja_fines_de_semana,
        )
        otra.save(update_fields=["fecha_programada"])

    return visita


@transaction.atomic
def registrar_realizacion(visita, fecha_realizada, orden=None, observaciones=""):
    """Marca la visita como hecha y recalcula lo que viene detras.

    Es el momento en que la regla 2 entra en juego: a partir de aqui las
    siguientes se cuentan desde el dia en que de verdad se reviso el aparato.
    """
    if visita.estado == EstadoVisitaPreventiva.REALIZADA:
        raise ValueError("Esa visita ya estaba registrada como realizada.")

    visita.estado = EstadoVisitaPreventiva.REALIZADA
    visita.fecha_realizada = fecha_realizada
    visita.orden = orden

    if observaciones:
        visita.observaciones = observaciones

    visita.save()
    regenerar_visitas(visita.plan)

    return visita


@transaction.atomic
def omitir_visita(visita, motivo):
    """Da por no hecha una visita, dejando dicho por que.

    Hace falta porque si no la unica salida es borrarla, y entonces el
    historial no distingue entre un preventivo que no tocaba y uno que se
    salto. El motivo es obligatorio justamente por eso.
    """
    motivo = (motivo or "").strip()

    if not motivo:
        raise ValueError("Para omitir una visita hay que decir por qué.")

    if visita.estado == EstadoVisitaPreventiva.REALIZADA:
        raise ValueError("Una visita realizada no se puede omitir.")

    visita.estado = EstadoVisitaPreventiva.OMITIDA
    visita.observaciones = motivo[:250]
    visita.save()

    # Una omision no mueve la cadena: el aparato sigue debiendo su revision en
    # la fecha que le tocaba, y regenerar desde aqui la premiaria con mas
    # plazo. Solo se rellena el horizonte si hiciera falta.
    regenerar_visitas(visita.plan)

    return visita


@dataclass(frozen=True)
class DiaDelCalendario:
    """Lo que hay que mostrar de un dia, ya resuelto."""

    fecha: date
    visitas: list

    @property
    def es_fin_de_semana(self):
        return self.fecha.weekday() >= 5

    @property
    def atrasadas(self):
        return [visita for visita in self.visitas if visita.esta_atrasada]

    @property
    def total(self):
        return len(self.visitas)


def calendario_de(responsable, desde, hasta, solo_pendientes=True):
    """Las visitas de una persona entre dos fechas, agrupadas por dia.

    Se agrupa aqui y no en la plantilla porque un dia puede llevar quince
    equipos y el template no deberia estar decidiendo donde empieza y acaba
    cada dia. No hay tope de equipos por dia: quien reparte el trabajo sabe
    que quince monitores de la misma sala son una manana.
    """
    visitas = (
        VisitaPreventiva.objects.filter(
            plan__responsable=responsable,
            plan__activo=True,
            fecha_programada__gte=desde,
            fecha_programada__lte=hasta,
        )
        .select_related(
            "plan",
            "plan__dispositivo",
            "plan__dispositivo__tipo",
            "plan__dispositivo__marca",
        )
        .order_by("fecha_programada", "plan__dispositivo__tipo__nombre")
    )

    if solo_pendientes:
        visitas = visitas.filter(estado=EstadoVisitaPreventiva.PROGRAMADA)

    por_dia = {}

    for visita in visitas:
        por_dia.setdefault(visita.fecha_programada, []).append(visita)

    return [
        DiaDelCalendario(fecha=fecha, visitas=por_dia[fecha])
        for fecha in sorted(por_dia)
    ]


def visitas_atrasadas(responsable=None):
    """Lo que ya paso de fecha y sigue sin hacerse.

    Es la consulta que importa de verdad: un calendario sin esta lista deja
    que un preventivo vencido desaparezca de la pantalla al pasar su semana.
    """
    visitas = (
        VisitaPreventiva.objects.filter(
            estado=EstadoVisitaPreventiva.PROGRAMADA,
            plan__activo=True,
            fecha_programada__lt=timezone.localdate(),
        )
        .select_related(
            "plan",
            "plan__responsable",
            "plan__dispositivo",
            "plan__dispositivo__tipo",
        )
        .order_by("fecha_programada")
    )

    if responsable is not None:
        visitas = visitas.filter(plan__responsable=responsable)

    return visitas
