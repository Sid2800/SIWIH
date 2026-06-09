"""Services de consultas ORM para mapeo_camas."""

import logging

from django.db.models import OuterRef, Subquery

from mapeo_camas.models import AsignacionCamaPaciente, HistorialEstadoCama


# 2026-06-09: logging de capa service (no en vistas) para diagnóstico en producción.
logger = logging.getLogger(__name__)


class MapeoCamasQueryService:
    """Consultas reutilizables para reducir carga ORM en vistas."""

    @staticmethod
    def obtener_ultimas_asignaciones_por_cama(cama_ids=None):
        """Retorna dict {cama_id: AsignacionCamaPaciente} de la asignación más reciente."""
        try:
            ultima_asignacion_id = (
                AsignacionCamaPaciente.objects
                .filter(cama_id=OuterRef("cama_id"))
                .order_by("-fecha_inicio", "-id")
                .values("id")[:1]
            )
            qs = (
                AsignacionCamaPaciente.objects
                .select_related("ingreso", "estado")
                .filter(id=Subquery(ultima_asignacion_id))
            )
            if cama_ids:
                qs = qs.filter(cama_id__in=cama_ids)
            resultado = {asig.cama_id: asig for asig in qs}
            logger.debug(
                "MapeoCamasQueryService.obtener_ultimas_asignaciones_por_cama ejecutado",
                extra={"camas_filtradas": len(cama_ids) if cama_ids else 0, "total_asignaciones": len(resultado)},
            )
            return resultado
        except Exception:
            logger.exception(
                "Error al obtener ultimas asignaciones por cama",
                extra={"camas_filtradas": len(cama_ids) if cama_ids else 0},
            )
            raise

    @staticmethod
    def obtener_ultimos_historiales_por_cama(cama_ids=None):
        """Retorna dict {cama_id: HistorialEstadoCama} del historial más reciente."""
        try:
            ultima_historial_id = (
                HistorialEstadoCama.objects
                .filter(cama_id=OuterRef("cama_id"))
                .order_by("-fecha_hora", "-id")
                .values("id")[:1]
            )
            qs = (
                HistorialEstadoCama.objects
                .select_related("usuario")
                .filter(id=Subquery(ultima_historial_id))
            )
            if cama_ids:
                qs = qs.filter(cama_id__in=cama_ids)
            resultado = {historial.cama_id: historial for historial in qs}
            logger.debug(
                "MapeoCamasQueryService.obtener_ultimos_historiales_por_cama ejecutado",
                extra={"camas_filtradas": len(cama_ids) if cama_ids else 0, "total_historiales": len(resultado)},
            )
            return resultado
        except Exception:
            logger.exception(
                "Error al obtener ultimos historiales por cama",
                extra={"camas_filtradas": len(cama_ids) if cama_ids else 0},
            )
            raise
