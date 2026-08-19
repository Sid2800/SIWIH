"""Estado de la garantia de un equipo.

La garantia se guarda como la fecha que dice el contrato y no se toca nunca.
El vencimiento real se calcula sumandole los dias que el equipo estuvo fuera
por reparacion, de modo que siempre pueda mostrarse por separado lo que firmo
el proveedor y el ajuste posterior.

Los dias se suman al cerrar la pausa, no dia a dia. Hasta que el equipo no
vuelve no se sabe cuanto estuvo fuera, asi que una pausa abierta suma cero y
la pantalla avisa de que el vencimiento se ajustara al retorno. Es
conservador: nunca promete mas cobertura de la que consta.
"""

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from ..models import DIAS_AVISO_GARANTIA, EstadoGarantiaDispositivo


@dataclass(frozen=True)
class EstadoGarantia:
    """Lo que hay que saber de la garantia de un equipo, ya resuelto."""

    estado: str
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
        return self.fin_contrato is not None

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
    from datetime import timedelta

    return fecha + timedelta(days=dias)


def calcular_estado_garantia(dispositivo, hoy=None, pausas=None):
    """Resuelve la situacion de la garantia de un equipo.

    `pausas` permite pasar la lista ya cargada y evitar una consulta por
    equipo cuando se calcula sobre un listado.
    """
    hoy = hoy or timezone.localdate()

    if pausas is None:
        pausas = list(dispositivo.pausas_garantia.all())

    abierta = next((p for p in pausas if p.esta_abierta), None)

    # Solo las pausas cerradas suman: de las abiertas todavia no se sabe
    # cuanto duraran.
    dias_pausados = sum(
        (p.fecha_retorno - p.fecha_salida).days
        for p in pausas
        if p.fecha_retorno is not None
    )

    fin_contrato = dispositivo.fecha_fin_garantia

    if fin_contrato is None:
        return EstadoGarantia(
            estado=EstadoGarantiaDispositivo.SIN_GARANTIA,
            fin_contrato=None,
            fin_real=None,
            dias_pausados=dias_pausados,
            dias_restantes=None,
            pausa_abierta=abierta,
        )

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
        fin_contrato=fin_contrato,
        fin_real=fin_real,
        dias_pausados=dias_pausados,
        dias_restantes=dias_restantes,
        pausa_abierta=abierta,
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
        return False, "El equipo no tiene garantía registrada."

    if estado.esta_pausada:
        return False, "El equipo ya tiene una pausa abierta."

    if estado.estado == EstadoGarantiaDispositivo.VENCIDA:
        return False, "La garantía ya venció."

    return True, ""
