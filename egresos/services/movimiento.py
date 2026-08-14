"""
Movimiento de ubicación de expedientes para el flujo de Egresos.

Cuando Estadística toma un expediente para llenar su egreso, el expediente se
marca físicamente "prestado" y se ubica en ESTADÍSTICA. Con eso el módulo s_exp
deja de considerarlo disponible (solo presta lo que está en ADMISIÓN/ARCHIVO),
sin tocar el módulo Ingreso ni el catálogo de estados de s_exp.

Al cerrar el lote (Admisión recibe todo), el expediente vuelve a ADMISIÓN y a
estado DISPONIBLE.

Se reutiliza el catálogo de ubicaciones y el modelo de estado físico de s_exp,
para que ambos módulos compartan la MISMA fuente de la verdad.
"""
from expediente.services.ubicaciones import CatalogoUbicaciones
from s_exp.models import ExpedientePrestamo, EstadoExpedienteFisico

from core.utils.utilidades_logging import log_warning
from core.constants.domain_constants import LogApp


def ubicacion_estadistica():
    """
    Fila ExpedienteUbicacion correspondiente a ESTADÍSTICA (unidad no clínica).
    La crea si no existe (get_or_create), como hace ubicacion_admision().
    Devuelve None si no existe la unidad ESTADÍSTICA.
    """
    from servicio.models import Unidad
    unidad = Unidad.objects.filter(nombre_unidad__iexact='ESTADISTICA', estado=1).first()
    if not unidad:
        unidad = Unidad.objects.filter(nombre_corto_unidad__iexact='EST', estado=1).first()
    if not unidad:
        return None
    return CatalogoUbicaciones.obtener_o_crear_por_unidad_no_clinica(unidad)


def _fijar_ubicacion(expediente, usuario, ubicacion_obj, estado_codigo):
    """
    Fija el estado físico + la ubicación de un expediente, en las dos tablas que
    consultan los buscadores (ExpedientePrestamo y Expediente.ubicacion), igual
    que hace s_exp al entregar/devolver.
    """
    estado_id = EstadoExpedienteFisico.id_de(estado_codigo)

    # 1) ExpedientePrestamo (estado físico + ubicación). Puede no existir aún.
    ep, _ = ExpedientePrestamo.objects.get_or_create(
        expediente=expediente,
        defaults={'estado_id': estado_id},
    )
    ep.estado_id = estado_id
    if ubicacion_obj is not None:
        ep.ubicacion = ubicacion_obj
    ep.save()

    # 2) Expediente.ubicacion (tabla principal), para que la resolución de
    #    ubicación sea consistente en ambos módulos.
    try:
        expediente.modificado_por = usuario
        campos = ['modificado_por', 'fecha_modificado']
        if ubicacion_obj is not None:
            expediente.ubicacion = ubicacion_obj
            campos.append('ubicacion')
        expediente.save(update_fields=campos)
    except Exception as e:
        log_warning(f"No se pudo fijar ubicacion del expediente #{expediente.numero}: {e}",
                    app=LogApp.EGRESOS)


def mover_a_estadistica(expediente, usuario):
    """Marca el expediente como prestado a Estadística (no disponible para otros)."""
    _fijar_ubicacion(expediente, usuario, ubicacion_estadistica(), 'EXP_PRESTADO')


def devolver_a_admision(expediente, usuario):
    """Regresa el expediente a Admisión y lo deja DISPONIBLE."""
    ubic_adm = None
    try:
        ubic_adm = CatalogoUbicaciones.ubicacion_admision()
    except Exception as e:
        log_warning(f"No se pudo resolver ADMISION: {e}", app=LogApp.EGRESOS)
    _fijar_ubicacion(expediente, usuario, ubic_adm, 'EXP_DISPONIBLE')
