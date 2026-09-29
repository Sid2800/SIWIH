"""Estado de la garantia de un equipo.

Un equipo puede pasar por varias garantias a lo largo de su vida: se renueva
al vencer, se termina a mano cuando el proveedor incumple o cuando el aparato
se sustituye. Aqui se resuelve la que esta en curso; las cerradas viven en la
misma tabla como historial y no entran en el calculo.

La fecha del contrato no se toca nunca. El vencimiento real se calcula
sumandole los dias que el equipo estuvo fuera por reparacion, de modo que
siempre pueda mostrarse por separado lo que firmo el proveedor y el ajuste
posterior.

Los dias se suman al cerrar la pausa, no dia a dia. Hasta que el equipo no
vuelve no se sabe cuanto estuvo fuera, asi que una pausa abierta suma cero y
la pantalla avisa de que el vencimiento se ajustara al retorno. Es
conservador: nunca promete mas cobertura de la que consta.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from ..models import DIAS_AVISO_GARANTIA, EstadoGarantiaDispositivo


@dataclass(frozen=True)
class EstadoGarantia:
    """Lo que hay que saber de la garantia de un equipo, ya resuelto."""

    estado: str
    #: La fila de la garantia en curso. None si el equipo no tiene ninguna.
    garantia: object | None
    #: Fecha del contrato, tal cual se registro. None si no tiene garantia.
    fin_contrato: date | None
    #: Fecha real una vez sumadas las pausas cerradas.
    fin_real: date | None
    #: Dias que aportan las pausas ya cerradas.
    dias_pausados: int
    #: Dias que faltan para vencer. Negativo si ya vencio.
    dias_restantes: int | None
    #: Pausa sin cerrar, si la hay.
    pausa_abierta: object | None

    @property
    def tiene_garantia(self):
        return self.garantia is not None

    @property
    def esta_pausada(self):
        return self.pausa_abierta is not None

    @property
    def esta_vigente(self):
        return self.estado in (
            EstadoGarantiaDispositivo.VIGENTE,
            EstadoGarantiaDispositivo.POR_VENCER,
            EstadoGarantiaDispositivo.PAUSADA,
        )

    @property
    def etiqueta(self):
        return EstadoGarantiaDispositivo(self.estado).label


def sumar_dias(fecha, dias):
    """Suma dias a una fecha. Aislado para poder probarlo por separado."""
    return fecha + timedelta(days=dias)


SIN_GARANTIA = EstadoGarantia(
    estado=EstadoGarantiaDispositivo.SIN_GARANTIA,
    garantia=None,
    fin_contrato=None,
    fin_real=None,
    dias_pausados=0,
    dias_restantes=None,
    pausa_abierta=None,
)


def calcular_estado_garantia(dispositivo, hoy=None, garantia=None):
    """Resuelve la situacion de la garantia en curso de un equipo.

    `garantia` permite pasar la fila ya cargada y evitar una consulta por
    equipo cuando se calcula sobre un listado.
    """
    hoy = hoy or timezone.localdate()

    if garantia is None:
        garantia = dispositivo.garantia_vigente

    if garantia is None:
        return SIN_GARANTIA

    pausas = list(garantia.pausas.all())
    abierta = next((p for p in pausas if p.esta_abierta), None)

    # Solo las pausas cerradas suman: de las abiertas todavia no se sabe
    # cuanto duraran.
    dias_pausados = sum(p.dias for p in pausas)

    fin_contrato = garantia.fecha_fin
    fin_real = sumar_dias(fin_contrato, dias_pausados)
    dias_restantes = (fin_real - hoy).days

    # Un equipo que esta fuera se muestra como pausado aunque su fecha ya
    # hubiera pasado: lo relevante para el tecnico es que no lo tiene.
    if abierta is not None:
        estado = EstadoGarantiaDispositivo.PAUSADA
    elif dias_restantes < 0:
        estado = EstadoGarantiaDispositivo.VENCIDA
    elif dias_restantes <= DIAS_AVISO_GARANTIA:
        estado = EstadoGarantiaDispositivo.POR_VENCER
    else:
        estado = EstadoGarantiaDispositivo.VIGENTE

    return EstadoGarantia(
        estado=estado,
        garantia=garantia,
        fin_contrato=fin_contrato,
        fin_real=fin_real,
        dias_pausados=dias_pausados,
        dias_restantes=dias_restantes,
        pausa_abierta=abierta,
    )


def calcular_estado_cerrada(garantia, hoy=None):
    """Estado de una garantia del historial, para mostrarla en la lista.

    Una garantia cerrada no se recalcula contra hoy: lo que consta es que
    dejo de estar vigente el dia que se cerro y por que motivo.
    """
    pausas = list(garantia.pausas.all())
    dias_pausados = sum(p.dias for p in pausas)

    return EstadoGarantia(
        estado=EstadoGarantiaDispositivo.TERMINADA,
        garantia=garantia,
        fin_contrato=garantia.fecha_fin,
        fin_real=sumar_dias(garantia.fecha_fin, dias_pausados),
        dias_pausados=dias_pausados,
        dias_restantes=None,
        pausa_abierta=None,
    )


def puede_pausarse(dispositivo, estado=None, hoy=None):
    """Si tiene sentido registrar una salida a reparacion.

    Devuelve (permitido, motivo). El motivo se muestra al tecnico para que
    sepa por que no aparece el boton.
    """
    from ..models import EstadoDispositivo

    estado = estado or calcular_estado_garantia(dispositivo, hoy=hoy)

    if dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA:
        return False, "El equipo está dado de baja."

    if not estado.tiene_garantia:
        return False, "El equipo no tiene garantía vigente."

    if estado.esta_pausada:
        return False, "El equipo ya tiene una pausa abierta."

    if estado.estado == EstadoGarantiaDispositivo.VENCIDA:
        return False, "La garantía ya venció. Puede renovarla."

    return True, ""


def puede_renovarse(dispositivo):
    """Si se le puede registrar una garantia nueva.

    Se permite siempre que el equipo no este de baja: un equipo sin garantia
    puede recibir la primera, y uno con garantia vigente puede renovarla
    -la anterior se cierra y queda en el historial-. Lo unico que se impide
    es tener dos vigentes a la vez, y de eso se encarga el modelo.
    """
    from ..models import EstadoDispositivo

    if dispositivo.estado == EstadoDispositivo.DADO_DE_BAJA:
        return False, "El equipo está dado de baja."

    return True, ""


def puede_terminarse(dispositivo, estado=None):
    """Si hay una garantia vigente que cerrar a mano."""
    estado = estado or calcular_estado_garantia(dispositivo)

    if not estado.tiene_garantia:
        return False, "El equipo no tiene garantía vigente."

    if estado.esta_pausada:
        return False, (
            "El equipo está fuera por reparación. Registre el retorno antes "
            "de terminar la garantía."
        )

    return True, ""
