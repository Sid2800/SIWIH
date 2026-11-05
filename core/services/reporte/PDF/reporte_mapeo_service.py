from types import SimpleNamespace
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import os 
from django.utils import timezone
# locales
from core.services.reporte.PDF.reporte_pdf_base_service import ReportePdfBaseService

from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy_hh_mm, formatear_fecha

from core.services.usuario_service import UsuarioService
from django.conf import settings
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


class ReporteMapeoService:
   estilosGeneralesMapeo = [
         # Fuente general
         ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
         ('FONTSIZE', (0, 0), (-1, -1), 9),
         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

         # Encabezado de columnas
         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F2F2C")),
         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
         ('FONTSIZE', (0, 0), (-1, 0), 10),
         ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

         # Filas normales: fondo alternado
         (
            'ROWBACKGROUNDS',
            (0, 1),
            (-1, -1),
            [colors.white, colors.HexColor("#D7DBE7")],
         ),

         # Espaciado
         ('TOPPADDING', (0, 0), (-1, -1), 4),
         ('BOTTOMPADDING', (0, 0), (-1, -1), 4),

         # Bordes
         ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#0F2F2C")),
         ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#AAB2BD")),
      ]
         
   estilosServicioMapeo = [
      ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#D7DACB")),
      ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0F2F2C")),
      ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
      ('FONTSIZE', (0, 0), (-1, 0), 10),
      ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
      ('TOPPADDING', (0, 0), (-1, 0), 6),
      ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
   ]


   
   @classmethod
   def generar_reporte_sesion(cls, data, usuario):
      try:
         if not data:
               log_warning(
                  "Intento de generar reporte de mapeo sin datos.",
                  app=LogApp.REPORTE,
               )
               raise ValueError(
                  "No hay datos para generar el reporte de mapeo."
               )

         sesion = data.get("sesion")
         servicios = data.get("servicios")

         # Crear la respuesta como un PDF.
         response = HttpResponse(content_type="application/pdf")
         response["Content-Disposition"] = (
               f'inline; filename="Reporte_mapeo_{sesion.id}.pdf"'
         )

         pdf = canvas.Canvas(response, pagesize=landscape(letter))
         pdf.setTitle(f"Reporte Mapeo-#{sesion.id}")
         ancho, alto = landscape(letter)
         y = alto - 30  # Margen superior inicial
         filas_por_pagina = 17
         filas_datos_primera_pagina = filas_por_pagina - 1 
         filas_datos_siguientes = filas_por_pagina - 1 + 3

         paginas = []
         pagina_actual = []
         fechaActual = timezone.now()

         indices_servicios = []
         encabezado = [
            "#C",
            "CUBÍCULO",
            "ESTADO",
            "# EXP",
            "PACIENTE",
            "HORA",
            "OBSERVACIÓN",
         ]

         anchos_columnas = [
            30,   # CAMA
            130,  # CUBÍCULO
            75,   # ESTADO
            55,   # EXP
            180,  # PACIENTE
            50,   # HORA
            180,  # OBSERVACIÓN
         ]


         def dibujar_titulo_reporte():
            pdf.setFont("Helvetica-Bold", 16)
            titulo = f"REPORTE DE MAPEO DE CAMAS"
            pdf.drawCentredString(ancho / 2, alto - 100, titulo)
            pdf.setFont("Helvetica-Bold", 14)
            subtitulo = f"Sesion #{sesion.id} · {sesion.estado_codigo}"
            pdf.drawCentredString(ancho / 2, alto - 117, subtitulo)\

            pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
            pdf.line(55, alto - 122, 760, alto - 122)
            
            pdf.setFillColor(colors.HexColor("#D7DBE7"))
            pdf.rect(55, alto - 143, 705, 16, fill=1, stroke=0)


            pdf.setFillColor(colors.black)
            
            # Línea divisoria gris clara

            y_info = alto - 138
    
            # Subtítulos de campos
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawRightString(100, y_info, "Inicio:")
            pdf.drawRightString(215, y_info, "|")

            pdf.drawRightString(260, y_info, "Fin:")
            pdf.drawRightString(385, y_info, "|")

            pdf.drawRightString(480, y_info, "Responsable:")
            pdf.drawRightString(580, y_info, "|")

            pdf.drawRightString(645, y_info, "Estado:")

            # Texto blanco para los valores
            pdf.setFont("Helvetica", 11)
            pdf.setFillColor(colors.black)

            fecha_inicial = formatear_fecha_dd_mm_yyyy_hh_mm(sesion.fecha_inicio)
            fecha_final = formatear_fecha_dd_mm_yyyy_hh_mm(sesion.fecha_fin)

            # # Datos informativos
            pdf.drawString(105, y_info, fecha_inicial)
            pdf.drawString(265, y_info, fecha_final)
            pdf.drawString(485, y_info, sesion.usuario)

            pdf.drawString(650, y_info, sesion.estado_codigo)

         def dibujar_resumen():
            resumen = data["resumen"]

            resumen_items = [
               ("SERVICIOS INCLUIDOS", resumen.total_servicios),
               ("CAMAS REGISTRADAS", resumen.total_camas),
               ("CAMBIOS DETECTADOS", resumen.total_cambios),
               ("CAMAS VALIDADAS", resumen.total_validadas),
            ]

            margen = 70
            separacion = 10
            ancho_bloque = (
               ancho - (2 * margen) - (3 * separacion)
            ) / 4

            y_bloque = alto - 200
            alto_bloque = 38

            for i, (etiqueta, cantidad) in enumerate(resumen_items):
               x = margen + i * (ancho_bloque + separacion)

               # Fondo de la tarjeta
               pdf.setFillColor(colors.HexColor("#E3E7F0"))
               pdf.roundRect(
                     x,
                     y_bloque,
                     ancho_bloque,
                     alto_bloque,
                     4,
                     fill=1,
                     stroke=0,
               )

               # Cantidad
               pdf.setFillColor(colors.HexColor("#173F3A"))
               pdf.setFont("Helvetica-Bold", 14)
               pdf.drawCentredString(
                     x + ancho_bloque / 2,
                     y_bloque + 21,
                     str(cantidad),
               )

               # Etiqueta
               pdf.setFillColor(colors.black)
               pdf.setFont("Helvetica", 8)
               pdf.drawCentredString(
                     x + ancho_bloque / 2,
                     y_bloque + 8,
                     etiqueta,
               )

         def escribir_paginas(indices_servicios):
      
            for numero_pagina, pagina in enumerate(paginas, start=1):
               
               if numero_pagina > 1:
                  pdf.showPage()

               ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
               dibujar_titulo_reporte()

               if numero_pagina == 1:
                  dibujar_resumen()
                              

               

               # Construir los datos de la tabla de esta página.
               datos_tabla = [encabezado] + pagina["filas"]
               altura_encabezado_total = 25  # encabezado y total
               altura_fila = 18              # filas normales
               estilos_finales = cls.estilosGeneralesMapeo.copy()
               alturas_filas = [altura_encabezado_total] + [altura_fila] * len(pagina["filas"])

               tabla = Table(datos_tabla, anchos_columnas, alturas_filas)

               indices_servicio_actual = indices_servicios.get(numero_pagina-1,[])
               for fila_idx in indices_servicio_actual:
                  fila_idx += 1  # La fila 0 es el encabezado de columnas

                  estilos_finales.extend([
               
                     # Estilos de la fila de servicio
                     ('BACKGROUND', (0, fila_idx), (-1, fila_idx),
                        colors.HexColor("#B1C1BF")),
                     ('ALIGN', (0, fila_idx), (-1, fila_idx), 'LEFT'),
                     ('FONTNAME', (0, fila_idx), (-1, fila_idx), 'Helvetica-Bold'),
                     ('LINEABOVE', (0, fila_idx), (-1, fila_idx),
                        0.5, colors.HexColor("#0F2F2C")),
                           # Combinar las columnas del nombre del servicio
                        ('SPAN', (0, fila_idx), (2, fila_idx)),
                        ('SPAN', (4, fila_idx), (-1, fila_idx)),
                     ('ALIGN', (4, fila_idx), (-1, fila_idx), 'RIGHT'),

                     
                  ])


               tabla.setStyle(TableStyle(estilos_finales))
               

               # Posicionamiento
               ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)

               margenSuperior = 220 if numero_pagina <= 1 else 160

               ubicacionYTabla1 = alto - margenSuperior - alto_tabla
               tabla.drawOn(pdf, 60, ubicacionYTabla1)


               # Pie de página
               ReportePdfBaseService.dibujar_pie_pagina_carta(
                     pdf, alto, ancho,
                     formatear_fecha(fechaActual),
                     usuario,
                     UsuarioService.obtener_nombre_empleado(usuario),
                     numero_pagina, len(paginas),
                     False
               )
         
         filas_por_pagina = 10

         paginas = []
         pagina_actual = []
         indices_servicios = {}

         for servicio in servicios:
            fila_servicio = [
               servicio.nombre,
               "",
               "",
               "",
               (
                     f"Camas: {servicio.total_camas}  |  "
                     f"Cambios: {servicio.total_cambios}  |  "
                     f"Validadas: {servicio.total_validadas}   "
               ),
               "",
               "",
            ]

            # Límite de filas según la página actual.
            limite_filas = (
               filas_datos_primera_pagina
               if not paginas
               else filas_datos_siguientes
            )

            if len(pagina_actual) >= limite_filas:
               paginas.append({
                     "filas": pagina_actual,
               })
               pagina_actual = []

            # Número de página que estamos construyendo.
            numero_pagina = len(paginas)

            # Guardar el índice del encabezado del servicio.
            indices_servicios.setdefault(numero_pagina, []).append(
               len(pagina_actual)
            )

            pagina_actual.append(fila_servicio)

            for detalle in servicio.detalles:
               fila_cama = [
                     detalle.cama.numero,
                     detalle.cubiculo[:20],
                     detalle.estado[:10],
                     detalle.expediente,
                     detalle.paciente,
                     (
                        detalle.fecha_hora.strftime("%H:%M")
                        if detalle.fecha_hora
                        else ""
                     ),
                     detalle.observacion,
               ]

               # Recalcular el límite para la página donde irá esta cama.
               limite_filas = (
                     filas_datos_primera_pagina
                     if not paginas
                     else filas_datos_siguientes
               )

               if len(pagina_actual) >= limite_filas:
                     paginas.append({
                        "filas": pagina_actual,
                     })
                     pagina_actual = []

               pagina_actual.append(fila_cama)

         # Guardar la última página.
         if pagina_actual:
            paginas.append({
               "filas": pagina_actual,
            })
         


         # Primero dibujamos el contenido.
         
         escribir_paginas(indices_servicios)

         # Después finalizamos el PDF.
         pdf.save()

         return response

      except ValueError:
         raise

      except Exception:
         log_error(
               "Error generando reporte de mapeo.",
               app=LogApp.REPORTE,
         )
         raise
