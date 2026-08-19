"""
Vistas del módulo de Encuestas (UAU).

Fase 1: acceso y pantalla de inicio. Solo la UAU ve el módulo; cada usuario
solo verá sus propias encuestas y el personal `is_staff` (supervisión) las verá
todas. La pantalla de inicio muestra el encabezado (según el tema) y el combobox
para elegir a qué servicio se levantará la encuesta.
"""
from django.views.generic import TemplateView

from core.mixins import UnidadRolRequiredMixin
from usuario.permisos import verificar_permisos_usuario
from core.constants.permisos import (
    ENCUESTAS_VISUALIZACION_ROLES, ENCUESTAS_VISUALIZACION_UNIDADES,
)

from encuestas.models import Encuesta


# =============================================================================
# Acceso: mismo mecanismo que el resto de módulos (unidad UAU).
# =============================================================================
def _tiene_permiso_encuestas(user):
    return verificar_permisos_usuario(
        user, ENCUESTAS_VISUALIZACION_ROLES, ENCUESTAS_VISUALIZACION_UNIDADES
    )


def _ve_todas_las_encuestas(user):
    """
    Cada usuario ve solo lo que él ingresó; la supervisión (personal `is_staff`,
    p. ej. ROSAA/DENNISP) ve TODAS las encuestas.
    """
    return bool(user.is_superuser or user.is_staff)


class EncuestasInicioView(UnidadRolRequiredMixin, TemplateView):
    """Inicio del módulo: encabezado + selección del servicio a encuestar."""
    template_name = 'encuestas/inicio.html'
    required_roles = ENCUESTAS_VISUALIZACION_ROLES
    required_unidades = ENCUESTAS_VISUALIZACION_UNIDADES

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['servicios'] = Encuesta.SERVICIOS
        return ctx
