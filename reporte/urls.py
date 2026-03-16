from django.urls import path

# Importar vistas generales
from .views import views as vistas_gen

# Importar vistas específicas
from .views import paciente
from .views import ingreso
from .views import imagenologia
from .views import referencia
# Reportes de paciente

reportes_paciente = [
    path('hospitalizacion/<int:ingreso_id>/', paciente.reporte_hospitalizacion, name='reporte_hospitalizacion'),
    path('hospitalizacion-26/<int:ingreso_id>/', paciente.reporte_hospitalizacion_2026.as_view(), name='reporte_hospitalizacion_26'),

    path('entrega-cadaver/<int:defuncion_id>/', paciente.reporte_entrega_cadaver.as_view(), name='entrega-cadaver'),
]

# Reportes de ingreso
reportes_ingreso = [
    path("recepcion-ingresos_sala/<int:recepcion_id>/", ingreso.reporte_detalle_recepcion_ingresos_sala.as_view(), name="reporte_detalle_recepcion_ingresos_sala"),
    path("recepcion-ingresos_sdgi/<int:recepcion_id>/", ingreso.reporte_detalle_recepcion_ingresos_SDGI.as_view(), name="reporte_detalle_recepcion_ingresos_sdgi"),
]

reportes_imagenologia = [
    path("informes-imagenologia/", imagenologia.InformesImagenologia.as_view(), name="informes_imagenologia"),
]

reportes_referencia = [
    path("informes-referencia/", referencia.InformesReferencia.as_view(), name="informes_referencia"),
    path("formato-referencia-SINAR/<int:referencia_id>/", referencia.FormatoReferencia.as_view(), name="formato_referencia_SINAR"),
    path("formato-respuesta-SINAR/<int:respuesta_id>/", referencia.FormatoRespuesta.as_view(), name="formato_respuesta_SINAR")


]

# Reportes generales
reportes_generales = [
    path("recepcion-atenciones/<int:recepcion_id>/", vistas_gen.reporte_detalle_recepcion_atenciones.as_view(), name="reporte_detalle_recepcion_atenciones"),
    path("generador-reporte/", vistas_gen.ReporteGeneradorView.as_view(), name="generador_reporte"),
    path("reporte-generado/", vistas_gen.ReporteGenerador.as_view(), name="reporte_generado"),
    path("obtener-interaccion-filtro-agrupacion/", vistas_gen.ObtenerInteraccionFiltroAgrupacion.as_view(), name="obtener_interaccion_filtro_agrupacion"),
    path("obtener-opciones-filtro/", vistas_gen.ObtenerOpcionesFiltro.as_view(), name="obtener_opciones_filtro"),
    path("informes-catalogo/",vistas_gen.InformesCatalogo.as_view(), name="informes_catalogo") 
]



# URLs finales
urlpatterns = reportes_paciente + reportes_ingreso + reportes_generales +reportes_imagenologia +reportes_referencia
