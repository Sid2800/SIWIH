"""Choices y catálogos de códigos para mapeo_camas."""


class DetalleMapeoTipoAccion:
    """Códigos permitidos para acciones de detalle de mapeo."""

    # 2026-06-09: centralizado desde models.DetalleMapeoCama.TipoAccion.
    CONFIRMACION = "CONFIRMACION"
    ALTA = "ALTA"
    CAMBIO = "CAMBIO"
    TRASLADO = "TRASLADO"
    CORRECCION = "CORRECCION"
