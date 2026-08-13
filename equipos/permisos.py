"""Fuente unica de los permisos del modulo de Equipos.

Todo lo que decida si alguien puede hacer algo con el inventario pasa por
aqui: las vistas, los decoradores y los filtros de plantilla. Duplicar la
regla en el template es como acaba ocurriendo que un boton se oculta pero la
URL escrita a mano sigue funcionando.

El modelo de autorizacion es el del resto del sistema: rol mas unidad, via
PerfilUnidad. La unidad es EQ, que no es un area fisica del hospital sino el
grupo de quienes mantienen los equipos.

is_staff no concede acceso: abre el admin de Django, que es otra cosa. Solo
cuentan el rol con su unidad y ser superusuario.
"""

from core.constants import permisos as constantes
from usuario.permisos import verificar_permisos_usuario


def _tiene(user, roles, unidades):
    # verificar_permisos_usuario ya resuelve superusuario y alcance GLOBAL:
    # un admin o un directivo global pasan sin pertenecer a EQ, mientras que
    # a un digitador se le exige la unidad.
    if not user or not user.is_authenticated:
        return False

    return verificar_permisos_usuario(user, roles, unidades)


def puede_visualizar_equipos(user):
    """Consultar el inventario sin modificarlo.

    Es el permiso de entrada al modulo y el techo del directivo: listado,
    busqueda, detalle, fotografias, QR y ficha de activo fijo.
    """
    return _tiene(
        user,
        constantes.EQUIPOS_VISUALIZACION_ROLES,
        constantes.EQUIPOS_VISUALIZACION_UNIDADES,
    )


def puede_editar_equipos(user):
    """Registrar y editar equipos, y subir sus fotografias."""
    return _tiene(
        user,
        constantes.EQUIPOS_EDICION_ROLES,
        constantes.EQUIPOS_EDICION_UNIDADES,
    )


def puede_administrar_catalogos_equipos(user):
    """Mantener los catalogos de tipos, marcas y modelos."""
    return _tiene(
        user,
        constantes.EQUIPOS_CATALOGO_ROLES,
        constantes.EQUIPOS_CATALOGO_UNIDADES,
    )


def puede_dar_baja_equipos(user):
    """Tramitar la baja de un equipo.

    Va aparte de la edicion porque no tiene vuelta atras: crea el registro,
    deja el equipo dado de baja y bloquea su edicion para siempre.
    """
    return _tiene(
        user,
        constantes.EQUIPOS_BAJA_ROLES,
        constantes.EQUIPOS_BAJA_UNIDADES,
    )


def puede_usar_formularios_equipos(user):
    """Permiso de los buscadores que alimentan los formularios.

    Los Select2 de tipo, marca, modelo, procedencia y empleado los usan tanto
    el alta como la edicion, asi que basta con cualquiera de las dos
    capacidades. Se resuelve aqui para que las vistas no repitan la disyuncion.
    """
    return puede_editar_equipos(user) or puede_administrar_catalogos_equipos(user)
