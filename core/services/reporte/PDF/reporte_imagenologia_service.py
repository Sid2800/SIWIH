from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import  legal, landscape
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from django.utils import timezone
from reportlab.lib.units import  mm
from django.utils.translation import gettext as _
import math

from core.utils.utilidades_fechas import formatear_fecha
from core.services.reporte.PDF.reporte_pdf_base_service import ReportePdfBaseService, VerticalText

from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle




class ReporteImagenologiaService:
    
    
    @staticmethod
    def generarInformeGastoCostoPelicula(reporte_criterios, indice=1):
        """
        Genera un PDF con el control de gasto de película según los criterios dados:
        """

        if reporte_criterios:
            anio = reporte_criterios['anio']
            mes = reporte_criterios['mes']
            data = reporte_criterios['data']
            total = reporte_criterios['total']
            dias = reporte_criterios['dias']

        #mapear los title el nombre del archivo y el tirulo de reporte
        if indice == 1:
            titulo = f"INFORME DE ESTUDIOS IMPRESOS POR DEPENDENCIA"
            archivo_name = f"Estudios_impresos_dependencia_{mes}_{anio}.pdf"
            title = f"Estudios impresos por dependencia {str(mes).upper()}"
        elif indice == 2:
            titulo = f"INFORME DEL GASTO DE MATERIAL POR DEPENDENCIA"
            archivo_name = f"Gasto_material_dependencia_{mes}_{anio}.pdf"
            title = f"Gasto de material por dependencia {str(mes).upper()}"
        elif indice == 3:
            titulo = f"INFORME DE PACIENTES ATENDIDIOS POR DEPENDENCIA"
            archivo_name = f"Informe_paciente_dependencia_{mes}_{anio}.pdf"
            title = f"Informe de pacientes por dependencia {str(mes).upper()}"



        # Crear la respuesta como un PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{archivo_name}"'

        # Inicializar el canvas PDF
        pdf = canvas.Canvas(response, pagesize=landscape(legal))
        pdf.setTitle(title)
        ancho, alto = landscape(legal)
        y = alto - 30  # Margen superior inicial
        fechaActual = timezone.now()

        # --- Función interna para dibujar el título del reporte ---
        def dibujar_titulo_reporte(pdf, ancho, alto):
            # Mapear el nombre del mes
            meses = {
                1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
                5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
                9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
            }

            # Título principal centrado
            pdf.setFont("Helvetica-Bold", 14)
            


            pdf.drawCentredString(ancho / 2, alto - 100, titulo)

            # Línea divisoria gris clara
            pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
            pdf.line(60, alto - 105, 975, alto - 105)

            # Campos de información
            pdf.setFont("Helvetica", 11)
            pdf.drawRightString(90, alto - 130, "MES:")
            pdf.drawRightString(520, alto - 130, "AÑO:")
            pdf.drawRightString(850, alto - 130, "UNIDAD:")

            # Fondos para los campos de datos
            pdf.setFillColor(colors.HexColor("#D7DBE7"))
            pdf.rect(90, alto - 132, 150, 14, fill=1, stroke=0)
            pdf.rect(520, alto - 132, 50, 14, fill=1, stroke=0)
            pdf.rect(850, alto - 132, 90, 14, fill=1, stroke=0)

            # Valores de los campos
            pdf.setFont("Helvetica-Bold", 12)
            pdf.setFillColor(colors.black)
            pdf.drawString(100, alto - 130, meses.get(mes, 'NO DEFINIDO'))
            pdf.drawString(525, alto - 130, str(anio))
            pdf.drawString(855, alto - 130, "RADIOLOGIA")

        # --- Estilos generales de la tabla ---
        estilosGenerales = [
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Fondo tipo zebra (alternado blanco y gris claro)
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#D7DBE7")]),

            # Encabezado: celeste pastel con texto negro
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F2F2C")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            # Primera columna (dependencias): negrita, alineada a la izquierda
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),

            # Totales (última columna): solo negrita
            ('FONTNAME', (-1, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (-1, 0), (-1, -1), 11),

            # Espaciado vertical
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

            # Bordes
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#0F2F2C")),

            # Línea final más marcada
            ('LINEBELOW', (0, -1), (-1, -1), 2.5, colors.HexColor("#0F2F2C")),

            # Líneas internas
            ('LINEBEFORE', (1, 0), (-1, -1), 0.01, colors.black),
            ('LINEAFTER', (0, 0), (-2, -1), 0.01, colors.black),
        ]

        estilosTotal = [
            # Totales (última fila): verde pastel y negrita
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#DDDAC3")),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
        ]

        # --- Preparar encabezados y columnas ---
        encabezado = ['DEPENDENCIA']
        anchos_column = [80 * mm]

        # Decidir tamaño base según cantidad de días
        if len(dias) == 30:
            mili = 7.63
        elif len(dias) == 31:
            mili = 7.33
        else:  # febrero u otros casos
            mili = 8

        for dia in dias:
            encabezado.append(dia)
            anchos_column.append(mili * mm)

        encabezado.append('TOTAL')
        encabezado = [encabezado]
        anchos_column.append(15 * mm)
        filas_por_pagina = 19
        paginas_necesarias = math.ceil(len(data) / filas_por_pagina)

        # --- Función interna para escribir cada página ---
        def escribir_pagina(pagina, pagina_actual, paginas_totales):
            ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
            dibujar_titulo_reporte(pdf, ancho, alto)

            if pagina_actual == paginas_totales:
                estilos_finales = estilosGenerales + estilosTotal
            else:
                estilos_finales = estilosGenerales

            tabla_data = encabezado + pagina
            tabla = Table(tabla_data, anchos_column)
            tabla.setStyle(TableStyle(estilos_finales))

            ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
            ubicacionYTabla1 = alto - 150 - alto_tabla
            tabla.drawOn(pdf, 60, ubicacionYTabla1)

            ReportePdfBaseService.dibujar_pie_pagina_legal_horizontal(
                pdf, alto, ancho,
                formatear_fecha(fechaActual),
                reporte_criterios['usuario'],
                reporte_criterios['usuario_nombre'],
                pagina_actual, paginas_totales
            )
            pdf.showPage()  # Mover al final para que no agregue página al inicio

        # --- Dividir datos en páginas ---
        pagina = []
        pagina_actual = 1
        for i, linea in enumerate(data, start=1):
            pagina.append(linea)
            if len(pagina) == filas_por_pagina:
                escribir_pagina(pagina, pagina_actual, paginas_necesarias)
                pagina_actual += 1
                pagina = []

        # Escribir última página si queda contenido
        if pagina:
            escribir_pagina(pagina, pagina_actual, paginas_necesarias)

        pdf.save()
        return response

    @staticmethod
    def generarInformeEstudioDependecia(reporte_criterios):

        # --- Validar parámetros de entrada ---
        if reporte_criterios:
            anio = reporte_criterios['anio']
            mes = reporte_criterios['mes']
            data = reporte_criterios['data']
            total = reporte_criterios['total']
            columnas = reporte_criterios['columnas']

        # --- Configuración general del reporte ---
        titulo = "INFORME CONTROL DE ESTUDIOS RADIOGRAFICOS POR DEPENDENCIA"
        archivo_name = f"Estudios_control_dependencia_{mes}_{anio}.pdf"
        title = f"Estudios control dependencia {str(mes).upper()}"

        # Respuesta como PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{archivo_name}"'

        # Inicializar canvas PDF
        pdf = canvas.Canvas(response, pagesize=landscape(legal))
        pdf.setTitle(title)
        ancho, alto = landscape(legal)
        y = alto - 30  # Margen superior inicial
        fechaActual = timezone.now()

        # ======================================================
        # Función interna: Dibujar título del reporte
        # ======================================================
        def dibujar_titulo_reporte(pdf, ancho, alto):
            # Mapear el nombre del mes
            meses = {
                1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
                5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
                9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
            }

            # Título principal centrado
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawCentredString(ancho / 2, alto - 100, titulo)

            # Línea divisoria
            pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
            pdf.line(60, alto - 105, 975, alto - 105)

            # Etiquetas
            pdf.setFont("Helvetica", 11)
            pdf.drawRightString(90, alto - 130, "MES:")
            pdf.drawRightString(520, alto - 130, "AÑO:")
            pdf.drawRightString(850, alto - 130, "UNIDAD:")

            # Fondos para los campos
            pdf.setFillColor(colors.HexColor("#D7DBE7"))
            pdf.rect(90, alto - 132, 150, 14, fill=1, stroke=0)
            pdf.rect(520, alto - 132, 50, 14, fill=1, stroke=0)
            pdf.rect(850, alto - 132, 90, 14, fill=1, stroke=0)

            # Valores
            pdf.setFont("Helvetica-Bold", 12)
            pdf.setFillColor(colors.black)
            pdf.drawString(100, alto - 130, meses.get(mes, 'NO DEFINIDO'))
            pdf.drawString(525, alto - 130, str(anio))
            pdf.drawString(855, alto - 130, "RADIOLOGIA")

        # ======================================================
        # Estilos de tablas
        # ======================================================
        estilosGenerales = [
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Zebra
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#D7DBE7")]),

            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F2F2C")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TEXTROTATE', (0, 0), (-1, 0), 90),

            # Primera columna
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),

            # Última columna (totales)
            ('FONTNAME', (-1, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (-1, 0), (-1, -1), 11),

            # Espaciado
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

            # Bordes
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#0F2F2C")),

            # Línea final
            ('LINEBELOW', (0, -1), (-1, -1), 2.5, colors.HexColor("#0F2F2C")),

            # Líneas internas
            ('LINEBEFORE', (1, 0), (-1, -1), 0.01, colors.black),
            ('LINEAFTER', (0, 0), (-2, -1), 0.01, colors.black),
        ]

        estilosTotales = [
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -2), (-1, -1), colors.black),
            ('FONTSIZE', (0, -2), (-1, -1), 11),
            ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor("#DDDAC3")),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#B1C1BF")),
        ]

        estilosTitulosVerticales = [
            ('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
            ('VALIGN', (-1, 0), (-1, -1), 'MIDDLE'),
            ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
        ]

        # ======================================================
        # Manejar disposición de títulos y anchos
        # ======================================================
        ancho_columna_data = 35
        filas_por_pagina = 20

        if columnas <= 9:
            styles = getSampleStyleSheet()
            style_header = ParagraphStyle(
                name="HeaderBoldWhite",
                parent=styles["Normal"],
                alignment=1,
                fontName="Helvetica-Bold",
                textColor=colors.white
            )
            data[0] = [Paragraph(str(col), style_header) for col in data[0]]
            ancho_columna_data = 80
        else:
            for i in range(1, columnas + 1):
                data[0][i] = VerticalText(str(data[0][i]))
            estilosGenerales += estilosTitulosVerticales
            filas_por_pagina = 16
            if columnas >= 21:
                ancho_columna_data = 26

        # Configuración de tabla
        paginas_necesarias = math.ceil(len(data) / filas_por_pagina)
        num_columnas = len(data[0])
        col_widths = [130] + [ancho_columna_data] * (num_columnas - 2) + [50]
        titulos_columnas = data[0]


        def escribir_pagina(pagina, pagina_actual, paginas_totales):
            ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
            dibujar_titulo_reporte(pdf, ancho, alto)

            estilos_finales = estilosGenerales + estilosTotales if pagina_actual == paginas_totales else estilosGenerales

            if pagina_actual > 1:
                pagina = [titulos_columnas] + pagina

            tabla = Table(pagina, col_widths)
            tabla.setStyle(TableStyle(estilos_finales))

            ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
            ubicacionYTabla1 = alto - 150 - alto_tabla
            tabla.drawOn(pdf, 60, ubicacionYTabla1)

            ReportePdfBaseService.dibujar_pie_pagina_legal_horizontal(
                pdf, alto, ancho,
                formatear_fecha(fechaActual),
                reporte_criterios['usuario'],
                reporte_criterios['usuario_nombre'],
                pagina_actual, paginas_totales
            )
            pdf.showPage()

        # ======================================================
        # Dividir datos en páginas
        # ======================================================
        pagina = []
        pagina_actual = 1


        for i, linea in enumerate(data, start=1):
            pagina.append(linea)
            if len(pagina) == filas_por_pagina:
                escribir_pagina(pagina, pagina_actual, paginas_necesarias)
                pagina_actual += 1
                pagina = []

        if pagina:
            escribir_pagina(pagina, pagina_actual, paginas_necesarias)

        # Finalizar PDF
        pdf.save()
        return response

    