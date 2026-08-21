# Fachada del modulo de vistas. Las vistas viven repartidas por tema; aqui
# solo se reexportan para que equipos/urls.py y cualquier import externo sigan
# encontrandolas en equipos.views sin cambiar una linea.
#
# Donde tocar cada cosa:
#   view_constants.py      mapas CSS, etiquetas e iconos compartidos
#   view_helpers.py        errores, y consultas que necesitan varios temas
#   views_inventario.py    alta, listado, busqueda, detalle, edicion, fotos
#   views_bajas.py         tramite de baja y ficha firmada
#   views_documentos.py    ficha de activo fijo y pantalla del QR
#   views_autocomplete.py  puntos JSON de los Select2
#   views_catalogos.py     tipos, marcas, modelos y procedencias
#   views_garantias.py     panel de garantias y pausas por reparacion

# MediaService no es una vista, pero se reexporta a proposito: hay codigo que
# lo sustituye por un doble apuntando a equipos.views.MediaService, y quitarlo
# de aqui romperia esa via sin que nada mas lo delatara.
from core.services.server_image.media_service import MediaService

from .views_autocomplete import (
    buscar_empleados,
    buscar_marcas,
    buscar_modelos,
    buscar_procedencias,
    buscar_tipos,
)
from .views_bajas import (
    ficha_baja_dispositivo_pdf,
    tramite_baja_dispositivo,
)
from .views_catalogos import (
    agregar_marca_catalogo,
    agregar_modelo_catalogo,
    agregar_procedencia_catalogo,
    agregar_tipo_catalogo,
    cambiar_estado_marca,
    cambiar_estado_modelo,
    cambiar_estado_procedencia,
    cambiar_estado_tipo,
    catalogo_marcas_modelos,
    catalogo_procedencias,
    editar_procedencia_catalogo,
    editar_tipo_catalogo,
)
from .views_documentos import (
    ficha_activo_fijo_pdf,
    qr_dispositivo,
)
from .views_garantias import (
    gestionar_garantia,
    panel_garantias,
    registrar_retorno_garantia,
    registrar_salida_garantia,
)
from .views_inventario import (
    agregar_imagen_dispositivo,
    buscar_dispositivo,
    detalle_dispositivo,
    editar_dispositivo,
    inicio,
    listado_dispositivos,
    registrar_dispositivo,
)

__all__ = [
    "MediaService",
    # inventario
    "inicio",
    "registrar_dispositivo",
    "listado_dispositivos",
    "buscar_dispositivo",
    "detalle_dispositivo",
    "editar_dispositivo",
    "agregar_imagen_dispositivo",
    # bajas
    "tramite_baja_dispositivo",
    "ficha_baja_dispositivo_pdf",
    # documentos
    "ficha_activo_fijo_pdf",
    "qr_dispositivo",
    # autocompletado
    "buscar_tipos",
    "buscar_procedencias",
    "buscar_marcas",
    "buscar_modelos",
    "buscar_empleados",
    # catalogos
    "catalogo_marcas_modelos",
    "agregar_marca_catalogo",
    "agregar_modelo_catalogo",
    "cambiar_estado_marca",
    "agregar_tipo_catalogo",
    "editar_tipo_catalogo",
    "cambiar_estado_tipo",
    "cambiar_estado_modelo",
    "catalogo_procedencias",
    "agregar_procedencia_catalogo",
    "editar_procedencia_catalogo",
    "cambiar_estado_procedencia",
    # garantias
    "panel_garantias",
    "gestionar_garantia",
    "registrar_salida_garantia",
    "registrar_retorno_garantia",
]
