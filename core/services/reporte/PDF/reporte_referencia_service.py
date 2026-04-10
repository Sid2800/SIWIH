from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from django.utils import timezone
from django.utils.translation import gettext as _
import math
import textwrap
from types import SimpleNamespace
import calendar
import os 
from django.conf import settings

from core.utils.utilidades_fechas import formatear_fecha, mes_nombre
from core.utils.utilidades_textos import formatear_ubicacion_completo
from core.services.reporte.PDF.reporte_pdf_base_service import ReportePdfBaseService
from reportlab.lib.styles import getSampleStyleSheet


class ReporteReferenciaService:
    
    estilosGeneralesPub = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Fondo tipo zebra
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#D7DBE7")]),

        # Encabezado de tabla
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F2F2C")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        # Primera columna
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica'),

        # Última columna (porcentajes)
        ('FONTNAME', (-1, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-1, 0), (-1, -1), 11),

        # Espaciado
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

        # Bordes y líneas
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#0F2F2C")),
        ('LINEBELOW', (0, -1), (-1, -1), 2.5, colors.HexColor("#0F2F2C")),
        ('LINEBEFORE', (1, 0), (-1, -1), 0.01, colors.black),
        ('LINEAFTER', (0, 0), (-2, -1), 0.01, colors.black),
    ]

    estilosTotalPub = [
        # Fila de total
    
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#DDDAC3")),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
    ]

    """
ZONA INFORMES ESTADÍSTICOS
    """
    @staticmethod
    def dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio):
        """Dibuja el título principal y la información contextual para UAU."""
            
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(ancho / 2, alto - 110, informe_titulo)

        pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
        pdf.line(60, alto - 115, 565, alto - 115)

        pdf.setFont("Helvetica", 11)
        pdf.drawRightString(90, alto - 140, "MES:")
        pdf.drawRightString(320, alto - 140, "AÑO:")
        pdf.drawRightString(520, alto - 140, "UNIDAD:")

        pdf.setFillColor(colors.HexColor("#D7DBE7"))
        pdf.rect(95, alto - 143, 100, 15, fill=1, stroke=0)
        pdf.rect(325, alto - 143, 40, 15, fill=1, stroke=0)
        pdf.rect(525, alto - 143, 40, 15, fill=1, stroke=0)

        pdf.setFont("Helvetica-Bold", 12)
        pdf.setFillColor(colors.black)
        pdf.drawString(100, alto - 140, nombre_mes.upper())
        pdf.drawString(330, alto - 140, str(anio))
        pdf.drawString(530, alto - 140, "UAU")  # ← fijo, institucional


    @staticmethod
    def GenerarInformeReferencia(reporte_criterios):
        """
        Genera un informe PDF de referencias según los criterios dados.
        """

        # --- Parámetros recibidos ---
        if reporte_criterios:
            anio = reporte_criterios['anio']
            mes = reporte_criterios['mes']
            nombre_mes = calendar.month_name[mes]
            usuario = reporte_criterios['usuario']
            usuario_nombre = reporte_criterios['usuario_nombre']
            informe_titulo = reporte_criterios['informe_titulo']
            data = reporte_criterios['data']
            total = reporte_criterios['total']
            etiqueta = reporte_criterios['etiqueta']
            informe = reporte_criterios['informe']
            observacion = reporte_criterios.get('observacion', '0')

            if informe==1:
                detalle_diagnostico = reporte_criterios['detalle_informe_1']


        # --- Configuración inicial del PDF ---
        archivo_name = f"{informe_titulo}_{mes}_{anio}.pdf"
        title = f"{informe_titulo} {str(nombre_mes).upper()}"
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{archivo_name}"'

        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(title)
        ancho, alto = letter
        y = alto - 30
        fechaActual = timezone.now()

        # --- Datos y configuración de tabla ---
        encabezado = [[etiqueta.upper(), "CONTEO", "PORCENTAJE"]]
        filas_por_pagina = 25
        paginas_necesarias = math.ceil(len(data) / filas_por_pagina)
        anchos_columnas = [220, 100, 100]
        
        
        pagina = []
        pagina_actual = 1

        # --- Función para escribir cada página ---
        def escribir_pagina(pagina, pagina_actual, paginas_totales, indices=[]):
            """Escribe una página con encabezado, tabla y pie."""
            ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
            ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)

            altura_encabezado_total = 28  # encabezado y total
            altura_fila = 18              # filas normales
            estilos_finales = []

            if pagina_actual == paginas_totales:
                estilos_finales = ReporteReferenciaService.estilosGeneralesPub.copy() + ReporteReferenciaService.estilosTotalPub.copy()
                alturas_filas = [altura_encabezado_total] + [altura_fila] * (len(pagina) - 1) + [altura_encabezado_total]
            else:
                estilos_finales = ReporteReferenciaService.estilosGeneralesPub.copy()
                alturas_filas = [altura_encabezado_total] + [altura_fila] * len(pagina)


            tabla_data = encabezado + pagina
            tabla = Table(tabla_data, anchos_columnas, alturas_filas)
            
            for fila_idx in indices:
                # luego los demás estilos
                estilos_finales.extend([
                    ('BACKGROUND', (0, fila_idx), (-1, fila_idx), colors.HexColor("#B1C1BF")),
                    ('ALIGN', (0, fila_idx), (-1, fila_idx), 'CENTER'),
                    ('FONTNAME', (0, fila_idx), (-1, fila_idx), 'Helvetica-Bold'),
                    ('LINEABOVE', (0, fila_idx), (-1, fila_idx), 0.5, colors.HexColor("#0F2F2C")),
                    
                ])

            tabla.setStyle(TableStyle(estilos_finales))

            # Posicionamiento
            ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
            ubicacionYTabla1 = alto - 165 - alto_tabla
            tabla.drawOn(pdf, 100, ubicacionYTabla1)

            # Pie de página
            ReportePdfBaseService.dibujar_pie_pagina_carta(
                pdf, alto, ancho,
                formatear_fecha(fechaActual),
                usuario,
                usuario_nombre,
                pagina_actual, paginas_totales
            )
            if pagina_actual != paginas_totales:
                pdf.showPage()


        indices_encabezados = []
        # --- Generación de páginas ---
        for pag, linea in enumerate(data, start=1):
            if linea[0] == '__HEADER__':
                celda1, celda2 = linea[1].split('-', 1)
                linea = (celda1, celda2 , linea[2])
                indices_encabezados.append(pag)


            pagina.append((linea[0][:35],linea[1],linea[2]))
        

            if len(pagina) == filas_por_pagina:
                escribir_pagina(pagina, pagina_actual, paginas_necesarias, indices_encabezados)
                pagina_actual += 1
                indices_encabezados = []
                pagina = []

        # Última página (si quedan registros)
        if pagina:
            escribir_pagina(pagina, pagina_actual, paginas_necesarias, indices_encabezados)

        filas_data = len(data)
        paginas_completas = filas_data // filas_por_pagina
        datos_ultima = (filas_data - (paginas_completas * filas_por_pagina)) + 1

        altura_fila = 19
        margen_detalle = 45
        y_base = alto - 165

        y_fin_tabla = y_base - (datos_ultima * altura_fila)

        y_detalle = y_fin_tabla - margen_detalle

        #observaciones
        if observacion != '0':
            # Estilo del texto
            styles = getSampleStyleSheet()
            estilo_obs = styles["Normal"]
            estilo_obs.fontName = "Helvetica"
            estilo_obs.fontSize = 9
            estilo_obs.leading = 14  # espacio entre líneas

            # Construir el Paragraph
            p = Paragraph(f"<b>OBSERVACIÓN:</b> {observacion }", estilo_obs)

            # Evitar que se salga de la página
            w, h = p.wrap(500, 50)  # área disponible (ancho, alto) 

            if y_detalle - h < 75: #75 espacio que rerqero el pie de pagina revisado y ajustado
                pdf.showPage()
                ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 30)
                ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)
                y_detalle = alto - 180 #revisado y ajustado inicio seiguiente pag

            p.drawOn(pdf, 65, y_detalle - h + 12)




        if informe and informe==1:
            
            #inicio a dibujar el detalle 
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawCentredString(ancho/2, y_detalle, "DETALLE POR ESPECIALIDAD")
            y_detalle -= 18

            for det in detalle_diagnostico:

                # Línea: Especialidad + total
                linea_esp = f"{det['especialidad'].upper()} — Total: {det['total']}"
                pdf.setFont("Helvetica-Bold", 10)

                # salto automático si no cabe
                if y_detalle < 110:
                    pdf.showPage()
                    ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 30)
                    ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)
                    y_detalle = alto - 180

                pdf.drawString(60, y_detalle, linea_esp)
                y_detalle -= 20 # MARGEN ENTRES ESPECIALIDAD Y DIAGNOSTICOS ETIQUETA

                # Subtítulo: Diagnósticos
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(60, y_detalle, "Diagnósticos:")
                y_detalle -= 16

                # Los diagnósticos de cada referencia
                pdf.setFont("Helvetica", 8)

                for diag in det['items']:

                    # Partir línea si es muy larga
                    
                    lineas = textwrap.wrap(diag, 105)

                    primera_linea = True  # bandera

                    for l in lineas:

                        if y_detalle < 110:
                            pdf.showPage()
                            ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 30)
                            ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)
                            y_detalle = alto - 180
                            pdf.setFont("Helvetica", 8)

                        if primera_linea:
                            pdf.drawString(70, y_detalle, f"- {l}")
                            primera_linea = False
                        else:
                            pdf.drawString(85, y_detalle, l)  # sangría sin guion
                        y_detalle -= 12
                y_detalle -= 20

        # --- Guardar PDF ---
        pdf.save()
        return response


    @staticmethod
    def GenerarInformeReferenciaColumnas(reporte_criterios):
        """
        Genera un informe PDF de referencias según los criterios dados.
        """
        # --- Parámetros recibidos ---
        if reporte_criterios:
            anio = reporte_criterios['anio']
            mes = reporte_criterios['mes']
            nombre_mes = calendar.month_name[mes]
            usuario = reporte_criterios['usuario']
            usuario_nombre = reporte_criterios['usuario_nombre']
            informe_titulo = reporte_criterios['informe_titulo']
            informe = reporte_criterios['informe']
            data = reporte_criterios['data']
            total = reporte_criterios['total']
            etiqueta = reporte_criterios['etiqueta']
            observacion = reporte_criterios.get('observacion', '0')



        # --- Configuración inicial del PDF ---
        archivo_name = f"{informe_titulo}_{mes}_{anio}.pdf"
        title = f"{informe_titulo} {str(nombre_mes).upper()}"
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{archivo_name}"'

        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(title)
        ancho, alto = letter
        y = alto - 30
        fechaActual = timezone.now()

        # --- Datos y configuración de tabla ---

        config_informes = {
            10: {
                "encabezado": [
                    [
                        etiqueta.upper(),
                        "REF RECIB",
                        "RESP",
                        "% RESP",
                        "DERIV",
                        "% DERIV"
                    ]
                ],
                "ancho_columnas": [160, 70, 70, 70, 70, 70]
            },
            11: {
                "encabezado": [
                    [
                        etiqueta.upper(),
                        "UAPS",
                        "CIS",
                        "SMI",
                        "ZPP",
                        "TOTAL",
                        "%/ TOTAL "
                    ]
                ],
                "ancho_columnas": [155, 56, 56, 56, 56, 60, 60]
            }
        }


        cfg = config_informes.get(informe)

        if cfg is None:
            raise ValueError(f"No se definieron encabezados/anchos para el informe {informe}")

        encabezado = cfg["encabezado"]
        anchos_columnas = cfg["ancho_columnas"]
        
        filas_por_pagina = 25
        paginas_necesarias = math.ceil(len(data) / filas_por_pagina)

        
        
        pagina = []
        pagina_actual = 1

        # --- Función para escribir cada página ---
        def escribir_pagina(pagina, pagina_actual, paginas_totales, indices=[]):
            """Escribe una página con encabezado, tabla y pie."""
            ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
            ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)

            altura_encabezado_total = 28  # encabezado y total
            altura_fila = 18              # filas normales
            estilos_finales = []

            if pagina_actual == paginas_totales:
                estilos_finales = ReporteReferenciaService.estilosGeneralesPub.copy() + ReporteReferenciaService.estilosTotalPub.copy()
                alturas_filas = [altura_encabezado_total] + [altura_fila] * (len(pagina) - 1) + [altura_encabezado_total]
            else:
                estilos_finales = ReporteReferenciaService.estilosGeneralesPub.copy()
                alturas_filas = [altura_encabezado_total] + [altura_fila] * len(pagina)

            estilos_finales.append(
                    ('FONTSIZE', (0, 0), (-1, 0), 10)
                )

            tabla_data = encabezado + pagina
            tabla = Table(tabla_data, anchos_columnas, alturas_filas)
            
            for fila_idx in indices:
                # luego los demás estilos
                estilos_finales.extend([
                    ('BACKGROUND', (0, fila_idx), (-1, fila_idx), colors.HexColor("#B1C1BF")),
                    ('ALIGN', (0, fila_idx), (-1, fila_idx), 'CENTER'),
                    ('FONTNAME', (0, fila_idx), (-1, fila_idx), 'Helvetica-Bold'),
                    ('LINEABOVE', (0, fila_idx), (-1, fila_idx), 0.5, colors.HexColor("#0F2F2C")),
                    
                ])

            tabla.setStyle(TableStyle(estilos_finales))

            # Posicionamiento
            ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
            ubicacionYTabla1 = alto - 165 - alto_tabla
            tabla.drawOn(pdf, 60, ubicacionYTabla1)

            # Pie de página
            ReportePdfBaseService.dibujar_pie_pagina_carta(
                pdf, alto, ancho,
                formatear_fecha(fechaActual),
                usuario,
                usuario_nombre,
                pagina_actual, paginas_totales
            )
            if pagina_actual != paginas_totales:
                pdf.showPage()

        indices_encabezados = []
        for pag, linea in enumerate(data, start=1):

            # --- Detecta encabezados de agrupación ---
            if linea[0] == '__HEADER__':
                celda1, celda2 = linea[1].split('-', 1)
                # Reconstruye la línea dinámicamente
                linea = (celda1, celda2, *linea[2:])
                indices_encabezados.append(pag)

            # --- Construcción dinámica de la fila ---
            fila = [linea[0][:35]] + list(linea[1:])
            pagina.append(tuple(fila))

            # --- Si se llegó al límite de filas por página ---
            if len(pagina) == filas_por_pagina:
                escribir_pagina(pagina, pagina_actual, paginas_necesarias, indices_encabezados)
                pagina_actual += 1
                pagina = []               # Resetea filas
                indices_encabezados = []  # Resetea índices de agrupación

        # --- Última página (si quedan registros) ---
        if pagina:
            escribir_pagina(pagina, pagina_actual, paginas_necesarias, indices_encabezados)


        filas_data = len(data)
        paginas_completas = filas_data // filas_por_pagina
        datos_ultima = (filas_data - (paginas_completas * filas_por_pagina)) + 1

        altura_fila = 18.5
        margen_detalle = 45
        y_base = alto - 165

        y_fin_tabla = y_base - (datos_ultima * altura_fila)

        y_detalle = y_fin_tabla - margen_detalle

        #observaciones
        if observacion != '0':
            # Estilo del texto
            styles = getSampleStyleSheet()
            estilo_obs = styles["Normal"]
            estilo_obs.fontName = "Helvetica"
            estilo_obs.fontSize = 9
            estilo_obs.leading = 14  # espacio entre líneas

            # Construir el Paragraph
            p = Paragraph(f"<b>OBSERVACIÓN:</b> {observacion }", estilo_obs)

            # Evitar que se salga de la página
            w, h = p.wrap(500, 50)  # área disponible (ancho, alto) 


            if y_detalle - h < 75: #75 espacio que rerqero el pie de pagina revisado y ajustado
                pdf.showPage()
                ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 30)
                ReporteReferenciaService.dibujar_titulo_reporte_referencia(pdf, ancho, alto, informe_titulo, nombre_mes, anio)
                y_detalle = alto - 180 #revisado y ajustado inicio seiguiente pag

            p.drawOn(pdf, 65, y_detalle - h + 12)


        # --- Guardar PDF ---
        pdf.save()
        return response
    
#  ZONA FORMATO REFERENCIA/RESPUESTA



    @staticmethod
    def _dibujarEtiquetasEstaticasFormatoRefenciaRespuesta(pdf, ancho, alto):
        #etiquetas estaticas 
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(ancho / 2, alto - 35, "REFERENCIA Y RESPUESTA")

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(ancho-95, alto-35, "Repuesta: ")
        pdf.drawString(ancho-185, alto-35, "Referencia: ")
        #cuadros de marcado
        pdf.setLineWidth(0.7) 
        pdf.rect(ancho-45, alto-38, 15, 12 , stroke=1, fill=0)
        pdf.rect(ancho-130, alto-38, 15, 12 , stroke=1, fill=0)
        
        pdf.setFont("Helvetica-Bold", 8)
        x_primer_elemento = 36
        #bloque 1
        alto_bloque1 = alto - 53
        pdf.drawString(ancho-490, alto_bloque1, "Primer Apellido")
        pdf.drawString(ancho-380, alto_bloque1, "Segundo Apellido")
        pdf.drawString(ancho-220, alto_bloque1, "Nombre (s)")
        
        pdf.drawString(ancho-93, alto_bloque1 - 8, "Sexo:")
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(ancho-70, alto_bloque1 - 9, "H")
        pdf.drawString(ancho-46, alto_bloque1 - 9, "M")
        #cuadritos
    
        pdf.rect(ancho-35, alto_bloque1 - 10, 10, 10 , stroke=1, fill=0)
        pdf.rect(ancho-60, alto_bloque1 - 10, 10, 10 , stroke=1, fill=0)

        #bloque 2
        pdf.setFont("Helvetica-Bold", 8)
        alto_bloque2 = alto - 81
        pdf.drawString(x_primer_elemento, alto_bloque2, "No. de expediente:")
        pdf.drawString(ancho-350, alto_bloque2, "No. de Identidad:")
        pdf.drawString(ancho-94, alto_bloque2, "Edad:")

        #bloque 3
        alto_bloque3 = alto - 106
        pdf.drawString(x_primer_elemento, alto_bloque3, "Dirección:")
        pdf.drawString(ancho-520, alto_bloque3, "Colonia/Ciudad")
        pdf.drawString(ancho-380, alto_bloque3, "Municipio")
        pdf.drawString(ancho-258, alto_bloque3, "Departamento")
        pdf.drawString(ancho-110, alto_bloque3, "Teléfono")

        #bloque 4
        alto_bloque4 = alto - 131
        pdf.drawString(x_primer_elemento, alto_bloque4, "Correo Electrónico:")
        pdf.drawString(ancho-302, alto_bloque4 - 7, "Acompañante:")
        pdf.drawString(ancho-195, alto_bloque4 - 7, "Parentesco:")
        pdf.drawString(ancho-115, alto_bloque4 - 7, "Dirección/Teléfono")

        #bloque 5
        alto_bloque5 = alto - 155
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(x_primer_elemento, alto_bloque5, "Nombre del Establecimiento")
        pdf.drawString(x_primer_elemento, alto_bloque5-8, "que refiere/responde:")
        pdf.drawString(ancho-297, alto_bloque5-33, "Centralizado")
        pdf.drawString(ancho-297, alto_bloque5-45, "Descentralizado")
        
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(ancho-457, alto_bloque5-2, "Red:")

        pdf.setFont("Helvetica-Bold", 7.2)
        pdf.drawString(ancho-328, alto_bloque5-39, "Gestor")

        pdf.drawString(ancho-460, alto_bloque5-18, "Institución: SESAL")
        pdf.drawString(ancho-376, alto_bloque5-18, "Privado")
        pdf.drawString(ancho-453, alto_bloque5-32, "IHSS")
        pdf.drawString(ancho-418, alto_bloque5-32, "Militar")
        pdf.drawString(ancho-375, alto_bloque5-32, "ONG")
        pdf.drawString(ancho-453, alto_bloque5-45, "Otro")



        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(ancho-213, alto_bloque5-33, "Establecimiento que refiere y reponde:")
        pdf.drawString(ancho-90, alto_bloque5-33, "UAPS")
        pdf.drawString(ancho-55, alto_bloque5-33, "CIS")

        pdf.drawString(ancho-208, alto_bloque5-46, "Policlinico")
        pdf.drawString(ancho-158, alto_bloque5-46, "Hospital, Especifique:")

        #cuadritos
        pdf.setLineWidth(0.5) 
        #institucion
        pdf.rect(ancho-392, alto_bloque5 - 20, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-348, alto_bloque5 - 20, 10, 9 , stroke=1, fill=0)
        
        pdf.rect(ancho-433, alto_bloque5 - 34, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-392, alto_bloque5 - 34, 10, 9 , stroke=1, fill=0)

        pdf.rect(ancho-348, alto_bloque5 - 34, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-433, alto_bloque5 - 47, 10, 9 , stroke=1, fill=0)
        #linea
        pdf.line(ancho-417, alto_bloque5 - 48, ancho-345, alto_bloque5 - 48)
        #Gestor
        pdf.rect(ancho-234, alto_bloque5 - 35, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-234, alto_bloque5 - 48, 10, 9 , stroke=1, fill=0)


        #ESTABLECMIENTO CUADRITOS
        pdf.rect(ancho-41, alto_bloque5 - 35, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-69, alto_bloque5 - 35, 10, 9 , stroke=1, fill=0)

        pdf.rect(ancho-173, alto_bloque5 - 48, 10, 9 , stroke=1, fill=0)
        pdf.rect(ancho-88, alto_bloque5 - 48, 10, 9 , stroke=1, fill=0)


        #bloque 6
        alto_bloque6 = alto - 216
        pdf.setFont("Helvetica-Bold", 7.2)
        pdf.drawString(x_primer_elemento, alto_bloque6-5, "Motivo")
        pdf.drawString(x_primer_elemento, alto_bloque6 -13, "de Envio")


        pdf.drawString(ancho-510, alto_bloque6-2, "Diagnóstico:")
        pdf.drawString(ancho-395, alto_bloque6-2, "Tratamiento:")
        pdf.drawString(ancho-260, alto_bloque6-2, "Seguimiento:")
        pdf.drawString(ancho-130, alto_bloque6-2, "Rehabilitación:")
        pdf.drawString(ancho-535, alto_bloque6-19, "Describa:")



        #cuadritos
        pdf.rect(ancho-463, alto_bloque6 - 6, 18, 12 , stroke=1, fill=0)
        pdf.rect(ancho-347, alto_bloque6 - 6, 18, 12 , stroke=1, fill=0)
        pdf.rect(ancho-210, alto_bloque6 - 6, 18, 12 , stroke=1, fill=0)
        pdf.rect(ancho-75, alto_bloque6 - 6, 18, 12 , stroke=1, fill=0)

        #lineas
        pdf.drawString(x_primer_elemento, alto_bloque6 -33, "Signos y Síntomas principales:")
        pdf.drawString(x_primer_elemento, alto_bloque6 -48, "Resumen de datos clinicos:")

        #bloque13
        alto_bloque13 = alto_bloque6-120
        pdf.drawString(x_primer_elemento, alto_bloque13, "Signos Vitales:")
        pdf.drawString(ancho-517, alto_bloque13, "P/A:")
        pdf.drawString(ancho-447, alto_bloque13, "FR:")
        pdf.drawString(ancho-377, alto_bloque13, "P/FC:")
        pdf.drawString(ancho-307, alto_bloque13, "T°:")
        pdf.drawString(ancho-237, alto_bloque13, "Peso:")
        pdf.drawString(ancho-137, alto_bloque13, "Talla:")

        #bloque14  al  30
        alto_bloque14 = alto_bloque13-15
        pdf.drawString(x_primer_elemento, alto_bloque14, "Datos Gineco Obstétricos:")
        pdf.drawString(ancho-485, alto_bloque14, "FUM:")
        pdf.drawString(ancho-385, alto_bloque14, "FPP:")
        pdf.drawString(ancho-285, alto_bloque14, "E:")
        pdf.drawString(ancho-249, alto_bloque14, "P:")
        pdf.drawString(ancho-213, alto_bloque14, "C:")
        pdf.drawString(ancho-177, alto_bloque14, "HV:")
        pdf.drawString(ancho-141, alto_bloque14, "HM:")
        pdf.drawString(ancho-105, alto_bloque14, "O:")
        pdf.drawString(ancho-69,  alto_bloque14, "A:")

        alto_bloque15 = alto_bloque14-14
        pdf.drawString(x_primer_elemento, alto_bloque15, "Cabeza:")
        pdf.drawString(x_primer_elemento, alto_bloque15-14, "ORL:")
        pdf.drawString(x_primer_elemento, alto_bloque15-28, "Ojos:")
        pdf.drawString(x_primer_elemento, alto_bloque15-43, "Cuello:")
        pdf.drawString(x_primer_elemento, alto_bloque15-58, "Tórax:")
        pdf.drawString(x_primer_elemento, alto_bloque15-73, "Abdomen:")
        pdf.drawString(x_primer_elemento, alto_bloque15-87, "Genitales:")
        pdf.drawString(x_primer_elemento, alto_bloque15-101, "Extremidades:")
        pdf.drawString(x_primer_elemento, alto_bloque15-115, "Neurológico:")

        pdf.drawString(ancho-105, alto_bloque15-116, "Evaluación de Riesgo")
        pdf.drawString(x_primer_elemento, alto_bloque15-131, "Resultados Complementarios:")
        pdf.drawString(ancho-105, alto_bloque15-130, "Con Riesgo")
        pdf.drawString(ancho-105, alto_bloque15-144, "Sin Riesgo")

        pdf.drawString(x_primer_elemento, alto_bloque15-159, "Impresión Diagnóstica:")
        pdf.drawString(x_primer_elemento, alto_bloque15-188, "Recomendaciones/observaciones:")
        #cuadritos
        pdf.rect(ancho-55, alto_bloque15-133, 18, 9 , stroke=1, fill=0)
        pdf.rect(ancho-55, alto_bloque15-147, 18, 9 , stroke=1, fill=0)


        #bloque31
        alto_bloque31 = alto_bloque15 - 218
        pdf.drawString(x_primer_elemento, alto_bloque31, "Referido/Responde a:")

        pdf.drawString(ancho-490, alto_bloque31, "UAPS")
        pdf.drawString(ancho-430, alto_bloque31, "CIS")
        pdf.drawString(ancho-380, alto_bloque31, "Policlinico")
        pdf.drawString(x_primer_elemento, alto_bloque31-16, "Hospital, especifique")


        
        pdf.drawString(ancho-289, alto_bloque31+1, "America atención en:")
        pdf.setFont("Helvetica-Bold", 6.8)
        pdf.drawString(ancho-287, alto_bloque31-9, "Consulta Externa")
        pdf.drawString(ancho-182, alto_bloque31-6, "Emergencia")
        pdf.drawString(ancho-102, alto_bloque31-6, "Hospitalizacion")

        pdf.drawString(ancho-287, alto_bloque31-19, "Otros; especifique:")

        #cuadritos
        pdf.rect(ancho-465, alto_bloque31-1.5, 14, 9 , stroke=1, fill=0)
        pdf.rect(ancho-412, alto_bloque31-1.5, 14, 9 , stroke=1, fill=0)
        pdf.rect(ancho-336, alto_bloque31-1.5, 14, 9 , stroke=1, fill=0)
        pdf.rect(ancho-500, alto_bloque31-18, 14, 9 , stroke=1, fill=0)

        pdf.rect(ancho-220, alto_bloque31-10, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-140, alto_bloque31-7, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-48, alto_bloque31-7, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-220, alto_bloque31-20, 14, 8 , stroke=1, fill=0)
        

        pdf.line(ancho-480, alto_bloque31 - 19, ancho-310, alto_bloque31 - 19)
        pdf.line(ancho-200, alto_bloque31 - 20, ancho-35, alto_bloque31 - 20)

        #bloque32
        pdf.setFont("Helvetica-Bold", 7.2)
        alto_bloque32 = alto_bloque31-31
        pdf.drawString(x_primer_elemento, alto_bloque32, "Nombre del Establecimiento al que se Refiere o Responde:")
        pdf.drawString(ancho-289, alto_bloque32, "Fecha y hora de la elaboración de la referencia o respuesta:")
        pdf.drawString(ancho-286, alto_bloque32-15, "Día:")
        pdf.drawString(ancho-230, alto_bloque32-15, "Mes:")
        pdf.drawString(ancho-165, alto_bloque32-15, "Año:")
        pdf.drawString(ancho-101, alto_bloque32-15, "Hora:")

        #bloque33
        alto_bloque33 = alto_bloque32-32
        pdf.drawString(x_primer_elemento, alto_bloque33, "Se contactó al Establecimiento al que se remitirá o responderá:")
        pdf.drawString(ancho-289, alto_bloque33, "Nombre y cargo de la persona contactada:")

        pdf.drawString(x_primer_elemento +2, alto_bloque33-14, "SI:")
        pdf.drawString(ancho-541, alto_bloque33-14, "NO:")
        pdf.drawString(ancho-500, alto_bloque33-15, "Especifique:")

        #cuadritos
        pdf.rect(ancho-563, alto_bloque33-16, 14, 9 , stroke=1, fill=0)
        pdf.rect(ancho-524, alto_bloque33-16, 14, 9 , stroke=1, fill=0)
        pdf.line(ancho-455, alto_bloque33 - 18, ancho-310, alto_bloque33 - 19)

        #bloque34
        alto_bloque34 = alto_bloque33-32
        pdf.drawString(x_primer_elemento, alto_bloque34, "Referencia/Respuesta")
        pdf.drawString(x_primer_elemento, alto_bloque34-10, "Elaborado por:")

        pdf.drawString(ancho-490, alto_bloque34-1, "Médico General")
        pdf.drawString(ancho-400, alto_bloque34-1, "Médico Especialista")
        pdf.drawString(ancho-490, alto_bloque34-13, "Enfermera")
        pdf.drawString(ancho-400, alto_bloque34-13, "Auxiliar Enfermeria")
        pdf.drawString(ancho-575, alto_bloque34-23, "Otro")
        pdf.drawString(ancho-535, alto_bloque34-23, "Especificar:")
        pdf.line(ancho-490, alto_bloque34 - 25, ancho-310, alto_bloque34 - 25)

        pdf.drawString(ancho-289, alto_bloque34, "Nombre, Firma y Sello del que elabora la Referencia/Respuesta:")
        #cuadritos
        pdf.rect(ancho-430, alto_bloque34-2, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-430, alto_bloque34-14, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-323, alto_bloque34-2, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-323, alto_bloque34-14, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-555, alto_bloque34-24, 14, 8 , stroke=1, fill=0)

        #bloque35
        alto_bloque35 = alto_bloque34-36
        pdf.drawString(x_primer_elemento, alto_bloque35, "Cita en el servicio de:")

        pdf.drawString(ancho-441, alto_bloque35, "Día:")
        pdf.drawString(ancho-406, alto_bloque35, "Mes:")
        pdf.drawString(ancho-369, alto_bloque35, "Año:")
        pdf.drawString(ancho-336, alto_bloque35, "Hora:")

        pdf.drawString(ancho-289, alto_bloque35, "Fecha y hora de recibo de la referencia o respuesta")
        pdf.drawString(ancho-286, alto_bloque35-15, "Día:")
        pdf.drawString(ancho-230, alto_bloque35-15, "Mes:")
        pdf.drawString(ancho-165, alto_bloque35-15, "Año:")
        pdf.drawString(ancho-101, alto_bloque35-15, "Hora:")

        #bloque36
        alto_bloque36 = alto_bloque35-29
        pdf.drawString(x_primer_elemento, alto_bloque36, "Este campo es para ser llenado exclusivamente por el Establecimiento que recibe la referencia:")


        pdf.drawString(x_primer_elemento+10, alto_bloque36-14, "Referencia:")

        pdf.drawString(ancho-500, alto_bloque36-14, "Oportuna:")
        pdf.drawString(ancho-450, alto_bloque36-14, "SI:")
        pdf.drawString(ancho-415, alto_bloque36-14, "NO:")

        pdf.drawString(ancho-315, alto_bloque36-14, "Justificada:")
        pdf.drawString(ancho-265, alto_bloque36-14, "SI:")
        pdf.drawString(ancho-230, alto_bloque36-14, "NO:")
        
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(ancho-60, alto_bloque36-10, "HC-10")

        pdf.rect(ancho-439, alto_bloque36-15.4, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-400, alto_bloque36-15.4, 14, 8 , stroke=1, fill=0)

        pdf.rect(ancho-254, alto_bloque36-15.4, 14, 8 , stroke=1, fill=0)
        pdf.rect(ancho-215, alto_bloque36-15.4, 14, 8 , stroke=1, fill=0)

    @staticmethod
    def _dibujarEstructuraFormatoReferenciaRespuesta(pdf,ancho,alto):
        #estructura
        inicioIzquierda = 33
        espacioColumna = 8.5
        #borde pagina
        
        #logo
        logo1 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_sesal_clasico.png')
        pdf.drawImage(logo1, x=28, y=alto-67, width=68, height=48, preserveAspectRatio=True, mask='auto')


        
        #tabla del cuerpo
        datos = [[""] * 66 for _ in range(46)]
        colWidths = [7] + [espacioColumna] * 64 + [7]
        alt = 14.5

        rowHeights = [
            9, 11, 9,                                       # Bloque 1
            11, alt,                                         # Bloque 2
            11, alt,                                         # Bloque 3
            11, alt,                                         # Bloque 4
            alt+1, alt, alt, alt,                                 # Bloque 5
            2, alt, 2, alt,                                   # Bloque 6    
            alt, alt, alt, alt, alt, alt, alt,                     # Bloque 7  
            alt, alt, alt, alt, alt, alt, alt, alt, alt, alt,         # al 
            alt, alt, alt, alt, alt, alt,   # Bloque 10
            32, 32, 32, 36, 32, 
            25,            
            ]

        tabla = Table(datos, colWidths=colWidths, rowHeights=rowHeights)

        estilo = [
            #quitamos el borde de la tabla
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),                # Fuente para toda la tabla
            ('FONTSIZE', (0, 0), (-1, -1), 5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centra el texto horizontalmente
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centra el texto verticalmente

            ('LINEBELOW', (0, 2), (7, 2), .7, colors.black),
            ('LINEBEFORE', (8, 0), (8, 2), .7, colors.black),
            ('LINEABOVE', (8, 0), (-1, 0), .7, colors.black),
            ('LINEBEFORE', (0, 3), (0, -1), .7, colors.black),
            ('LINEAFTER', (-1, 0), (-1, -1), .7, colors.black),
        ]

        estilo += [
            #primer bloque 3
            ('SPAN', (57, 0), (65, 2)),
            ('SPAN', (35, 0), (56, 2)),
            ('SPAN', (21, 0), (34, 2)),
            ('SPAN', (8, 0), (20, 2)),
            ('GRID', (8, 0), (-1, 2), .1, colors.black),
            #segundo bloque  2
            ('SPAN', (57, 3), (65, 4)),
            ('SPAN', (0, 3), (56, 4)),
            #tercera bloque 2
            ('SPAN', (0, 5), (-1, 6)),

            #cuarto bloque 
            ('SPAN', (53, 7), (65, 8)),
            ('SPAN', (43, 7), (52, 8)),
            ('SPAN', (29, 7), (42, 8)),
            ('SPAN', (0, 7), (28, 8)),
            #quito bloque
                #linea 1  1 fila
                ('SPAN', (53, 9), (65, 9)),
                ('SPAN', (43, 9), (52, 9)),
                ('SPAN', (29, 9), (42, 9)),
                ('SPAN', (14, 9), (28, 9)),
                #linea 2  1 fila
                ('SPAN', (53, 10), (65, 10)),
                ('SPAN', (43, 10), (52, 10)),
                ('SPAN', (29, 10), (42, 10)),
                ('SPAN', (14, 10), (28, 12)),
                #linea 3   2 filas
                ('SPAN', (43, 11), (65, 12)),
                ('SPAN', (33, 11), (42, 12)),
                
                ('SPAN', (29, 11), (32, 12)),
                # bloque unido
                ('SPAN', (0, 9), (13, 12)),

        #sexto bloque 
            #linea1 3 filas
            ('SPAN', (5, 13), (-1, 15)),
            ('SPAN', (5, 16), (-1, 16)),
            ('SPAN', (0, 13), (4, 16)),
        
        #septimo bloque al doceavo
        ('SPAN', (0, 17), (-1, 17)),
        ('SPAN', (0, 18), (-1, 18)),
        ('SPAN', (0, 19), (-1, 19)),
        ('SPAN', (0, 20), (-1, 20)),
        ('SPAN', (0, 21), (-1, 21)),
        ('SPAN', (0, 22), (-1, 22)),
        #13avo 
        ('SPAN', (7, 23), (-1, 23)),
        ('SPAN', (0, 23), (6, 23)),
        #14avo al 23avo
        ('SPAN', (0, 24), (-1, 24)),
        ('SPAN', (0, 25), (-1, 25)),
        ('SPAN', (0, 26), (-1, 26)),
        ('SPAN', (0, 27), (-1, 27)),
        ('SPAN', (0, 28), (-1, 28)),
        ('SPAN', (0, 29), (-1, 29)),
        ('SPAN', (0, 30), (-1, 30)),
        ('SPAN', (0, 31), (-1, 31)),
        ('SPAN', (0, 32), (-1, 32)),
        ('SPAN', (0, 33), (-1, 33)),
        ('SPAN', (0, 34), (-1, 34)),
        ('SPAN', (0, 35), (-1, 35)),
        ('SPAN', (0, 36), (-1, 36)),
        ('SPAN', (0, 37), (-1, 37)),
        ('SPAN', (0, 38), (-1, 38)),
        ('SPAN', (0, 39), (-1, 39)),
        #24VO   
        ('SPAN', (0, 40), (33, 40)),
        ('SPAN', (34, 40), (-1, 40)),
        ('SPAN', (0, 41), (33, 41)),
        ('SPAN', (34, 41), (-1, 41)),
        ('SPAN', (0, 42), (33, 42)),
        ('SPAN', (34, 42), (-1, 42)),
        ('SPAN', (0, 43), (33, 43)),
        ('SPAN', (34, 43), (-1, 43)),
        ('SPAN', (0, 44), (15, 44)),
        ('SPAN', (16, 44), (33, 44)),

        ('SPAN', (34, 44), (-1, 44)),

        ('SPAN', (0, 45), (59, 45)),
        ('SPAN', (60, 45), (-1, 45)),
        ('GRID', (0, 3), (-1, 45), .1, colors.black),
        ]

        table_style = TableStyle(estilo)
    
        tabla.setStyle(table_style)

        tabla.wrapOn(pdf, ancho, alto)

        tabla.drawOn(pdf, inicioIzquierda, alto - 762)

    @staticmethod
    def _texto_seguro(valor, max_len):
        if valor is None:
            return ""
        try:
            return str(valor).strip().upper()[:max_len]
        except Exception:
            return ""

    @staticmethod
    def _dibujarDatosPaciente(pdf, ancho,alto, paciente):
        pdf.setFont("Helvetica-Bold", 11)

        #bloque 1
        alto_bloque1 = alto - 67
        pdf.drawString(ancho-505, alto_bloque1, ReporteReferenciaService._texto_seguro(paciente.apellido1, 20))
        pdf.drawString(ancho-395, alto_bloque1, ReporteReferenciaService._texto_seguro(paciente.apellido2, 20))
        
        pdf.drawString(ancho-265, alto_bloque1, paciente.nombres)
        #Sexo X

        #bloque2
        alto_bloque2 = alto_bloque1-22
        pdf.setFont("Helvetica-Bold", 12)

        pdf.drawString(ancho-480, alto_bloque2, ReporteReferenciaService._texto_seguro(paciente.expediente, 6))
        pdf.drawString(ancho-245, alto_bloque2, ReporteReferenciaService._texto_seguro(paciente.dni, 16))
        pdf.setFont("Helvetica-Bold", 11)
        edad = paciente.edad_texto.split(',')[0] if paciente.edad_texto else ""
        pdf.drawString(ancho-84, alto_bloque2-3, ReporteReferenciaService._texto_seguro(edad, 16))

        #bloque3h
        alto_bloque3 = alto_bloque2-30
        pdf.drawString(60, alto_bloque3, ReporteReferenciaService._texto_seguro(paciente.direccion, 22))
        pdf.drawString(ancho-385, alto_bloque3, ReporteReferenciaService._texto_seguro(paciente.municipio, 22))
        pdf.drawString(ancho-262, alto_bloque3, ReporteReferenciaService._texto_seguro(paciente.departamento, 22))

        pdf.drawString(ancho-100, alto_bloque3, ReporteReferenciaService._texto_seguro(paciente.telefono, 12))

        # X sexo
        pdf.setFont("Helvetica-Bold", 11)
        xSexo = ancho-33.5
        if paciente.sexo == 'H':
            xSexo = ancho-58.5
        pdf.drawString(xSexo, alto_bloque1+5, "X")

        return alto_bloque2
    
    @staticmethod
    def _dibujarDatosInstitucion(pdf, ancho, institucion, alturaReferencia):
        pdf.setFont("Helvetica-Bold", 11)
        alto_bloque5 = alturaReferencia - 90

        institucion_nombre = (institucion.institucion_nombre or "").upper()

        if len(institucion_nombre) > 16:
            pdf.drawString(40, alto_bloque5, institucion_nombre[:16])
            pdf.drawString(40, alto_bloque5 - 12, institucion_nombre[16:32])

            if len(institucion_nombre) > 32:
                pdf.drawString(40, alto_bloque5 - 24, institucion_nombre[32:48])
        else:
            # centrado vertical cuando es una sola línea
            pdf.drawString(40, alto_bloque5 - 10, institucion_nombre[:16])

        #red
        pdf.drawString(ancho-435, alto_bloque5+20, ReporteReferenciaService._texto_seguro(institucion.institucion_red, 15))


        #proveedor de salud = Instiucion
        #institucion_proveedor_salud_id
        POSICIONES_PROVEEDOR = {
            6: (ancho - 390.5, alto_bloque5 + 5),    #sesal
            5: (ancho - 346.5, alto_bloque5 + 5),    #privado
            1: (ancho - 431.5, alto_bloque5 - 9),    #IHSS
            2: (ancho - 390.5, alto_bloque5 - 9),    #militar
            3: (ancho - 346.5, alto_bloque5 - 9),    #ong
            4: (ancho - 431.5, alto_bloque5 - 22.5), #otro
        }

        pos = POSICIONES_PROVEEDOR.get(institucion.institucion_proveedor_salud_id)
        if pos:
            pdf.drawString(*pos, "X")

        #Centralizado
        if institucion.institucion_centralizado:
            pdf.drawString(ancho - 232.5, alto_bloque5 - 10.5, "X")
        else:
            pdf.drawString(ancho - 232.5, alto_bloque5 - 23.4, "X")

        #nivel de complejidad
        POSICIONES_COMPLEJIDAD_ORIGEN = {
            1: (ancho - 67.5, alto_bloque5 - 10.5),   #UAPS
            2: (ancho - 39.5, alto_bloque5 - 10.5),   #CIS
            3: (ancho - 171.5, alto_bloque5 - 23.46), #SMI o policlinico
        }

        pos = POSICIONES_COMPLEJIDAD_ORIGEN.get(
            institucion.institucion_complejidad,
            (ancho - 87, alto_bloque5 - 23.46)
        )
        pdf.drawString(*pos, "X")

        if institucion.institucion_complejidad and institucion.institucion_complejidad > 3:
            pdf.drawString(pos[0]+15, pos[1], ReporteReferenciaService._texto_seguro(institucion.institucion_complejidad_nombre, 6))

        return alto_bloque5


    @staticmethod
    def _dibujarDatosHospitalizacion(pdf, ancho, alto, paciente, institucion):
        alto_bloque2 = ReporteReferenciaService._dibujarDatosPaciente(pdf, ancho, alto, paciente)
        ReporteReferenciaService._dibujarDatosInstitucion(pdf, ancho, institucion, alto_bloque2)



    @staticmethod
    def _dibujarDatosDinamicosFormatoReferencia(pdf, ancho, alto, referencia, paciente):

        #dibujar al paciente
        alto_bloque2 = ReporteReferenciaService._dibujarDatosPaciente(pdf, ancho, alto, paciente)
        pdf.setFont("Helvetica-Bold", 11)
        #bloque4 no hay data

        #bloque5
        alto_bloque5 = ReporteReferenciaService._dibujarDatosInstitucion(pdf, ancho,  referencia, alto_bloque2)



        #bloque6
        alto_bloque6 = alto_bloque5 - 30
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(
            ancho-495,
            alto_bloque6-27,
            ReporteReferenciaService._texto_seguro(referencia.ref_motivo_detalle, 35)
        )

        #bloque28 diagnosticos
        alto_bloque28 = alto_bloque6-317.5
        pdf.drawString(ancho-490, alto_bloque28, (referencia.ref_diagnosticos[:68] or "").upper())
        if len(referencia.ref_diagnosticos) > 68:
            pdf.drawString(
                40,
                alto_bloque28-14.5,
                ReporteReferenciaService._texto_seguro(referencia.ref_diagnosticos[68:].upper(), 75)
            )


        #detalle debe se diferir entre el tipo de referencia is es enviada debe mostrar especialidad destino si es recibida mostrar, atencion requerida        
        #bloque32
        alto_bloque32 = alto_bloque28-57.5

        if referencia.institucion_dest_complejidad > 3:
                pdf.drawString(
                    ancho - 477,
                    alto_bloque32-16,
                    ReporteReferenciaService._texto_seguro(referencia.institucion_dest_complejidad_nombre, 24)
                )

        if referencia.ref_tipo == 1: #enviada
            pdf.drawString(
                    ancho - 200,
                    alto_bloque32-17,
                    ReporteReferenciaService._texto_seguro(referencia.ref_especialidad_destino, 24)
                )
        else: # recibida
            if referencia.ref_atencion not in [3, 2, 4]:
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(
                    ancho - 200,
                    alto_bloque32-17,
                    ReporteReferenciaService._texto_seguro(referencia.ref_atencion_descripcion, 24)
                )
        pdf.setFont("Helvetica-Bold", 11)

        #bloque33
        alto_bloque33 = alto_bloque32-47
        pdf.drawString(40, alto_bloque33, ReporteReferenciaService._texto_seguro(referencia.instirucion_dest_nombre, 30))
        pdf.drawString(ancho-261, alto_bloque33+1, f"{referencia.ref_fecha_elaboracion_dia:02d}")
        pdf.drawString(ancho-205, alto_bloque33+1, f"{referencia.ref_fecha_elaboracion_mes:02d}")
        pdf.drawString(ancho-140, alto_bloque33+1, f"{referencia.ref_fecha_elaboracion_anio}")
        pdf.drawString(ancho-65, alto_bloque33+1, ReporteReferenciaService._texto_seguro(referencia.ref_fecha_elaboracion_hora, 8))

        #bloque35
        alto_bloque35 = alto_bloque33-49
        if referencia.ref_elaborado_por > 4:
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(
                ancho - 485,
                alto_bloque35-22,
                ReporteReferenciaService._texto_seguro(referencia.ref_elaborado_descripcion, 24)
            )

        #bloque36
        alto_bloque36 = alto_bloque35-50
        #Cita en servicio
        if referencia.ref_tipo == 1: # si es enviada mostrar la especialidad
            pdf.drawString(40, alto_bloque36, ReporteReferenciaService._texto_seguro(referencia.ref_especialidad_destino,17))
        #fecha de elaboracion
        
        if referencia.ref_tipo == 0:
            pdf.drawString(ancho-261, alto_bloque36, f"{referencia.ref_fecha_recepcion_dia:02d}")
            pdf.drawString(ancho-205, alto_bloque36, f"{referencia.ref_fecha_recepcion_mes:02d}")
            pdf.drawString(ancho-140, alto_bloque36, f"{referencia.ref_fecha_recepcion_anio}")
            pdf.drawString(ancho-65, alto_bloque36, ReporteReferenciaService._texto_seguro(referencia.ref_fecha_recepcion_hora, 8))

        pdf.drawString(ancho-130, alto_bloque36-28, ReporteReferenciaService._texto_seguro(f"# {referencia.ref_id}", 10))
        

        #bloque37
        alto_bloque37 = alto_bloque36-28

        #escritra de las X
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(ancho-127, alto-37, "X")

        #peques
        pdf.setFont("Helvetica-Bold", 11)

        
        #motivo
        pdf.setFont("Helvetica-Bold", 12)
        POSICIONES_MOTIVO = {
            4: (ancho - 70, alto_bloque6 - 12),   #Rehabilitación
            3: (ancho - 205, alto_bloque6 - 12),  #Seguimiento
            2: (ancho - 342, alto_bloque6 - 12),  #Tratamiento
            1: (ancho - 458, alto_bloque6 - 12),  #Diagnóstico
        }

        pos = POSICIONES_MOTIVO.get(referencia.ref_motivo)
        if pos:
            pdf.drawString(*pos, "X")

        pdf.setFont("Helvetica-Bold", 11)

        #instiucion destino
        POSICIONES_COMPLEJIDAD_DESTINO = {
            1: (ancho - 462, alto_bloque32), #UAPS
            2: (ancho - 409, alto_bloque32), #CIS
            3: (ancho - 333, alto_bloque32), #SMI o policlinico
        }

        pos = POSICIONES_COMPLEJIDAD_DESTINO.get(
            referencia.institucion_dest_complejidad,
            (ancho - 497, alto_bloque32-16)
        )
        pdf.drawString(*pos, "X")

        #Amerita atencion
        POSICIONES_ATENCION = {
            3: (ancho - 217, alto_bloque32-9), #Consulta Externa
            2: (ancho - 137, alto_bloque32-6), #Emergencia
            4: (ancho - 45, alto_bloque32-6),  #Hospitalizacion
        }


        if referencia.ref_tipo == 0: #recibida
            pos = POSICIONES_ATENCION.get(
                referencia.ref_atencion,
                (ancho - 217, alto_bloque32-19)
            )
        else:#enviada
            pos = (ancho - 217, alto_bloque32-19)

        pdf.drawString(*pos, "X")

        #elaborado por:
        POSICIONES_ELABORADO = {
            1: (ancho - 427, alto_bloque35),     #Medico General
            2: (ancho - 320, alto_bloque35),     #Medico Especialista
            3: (ancho - 427, alto_bloque35-12),  #Enfermera
            4: (ancho - 320, alto_bloque35-12),  #Auxiliar Enf
        }

        pos = POSICIONES_ELABORADO.get(
            referencia.ref_elaborado_por,
            (ancho - 552, alto_bloque35-22)
        )
        pdf.drawString(*pos, "X")

        if referencia.ref_tipo == 0:
            #evaluacion
            if referencia.ref_oportuna != 3:
                if referencia.ref_oportuna == 1:
                    oportunaX = ancho - 436
                else:
                    oportunaX = ancho - 396.5
                pdf.drawString(oportunaX, alto_bloque37, "X")

            #justificada
            if referencia.ref_justificada != 3:
                if referencia.ref_justificada == 1:
                    oportunaX = ancho - 251
                else:
                    oportunaX = ancho - 211.5
                pdf.drawString(oportunaX, alto_bloque37, "X")


    @staticmethod
    def _dibujarDatosDinamicosFormatoRespuesta(pdf, ancho, alto, respuesta, paciente):

        #dibujar al paciente
        alto_bloque2 = ReporteReferenciaService._dibujarDatosPaciente(pdf, ancho, alto, paciente)
        pdf.setFont("Helvetica-Bold", 11)
        #bloque4 no hay data

        #bloque5
        alto_bloque5 = alto_bloque2 - 90

        instituticion = (respuesta.institucion_resp_nombre or "").upper()

        if len(instituticion) > 16:
            pdf.drawString(40, alto_bloque5, instituticion[:16])
            pdf.drawString(40, alto_bloque5 - 12, instituticion[16:32])

            if len(instituticion) > 32:
                pdf.drawString(40, alto_bloque5 - 24, instituticion[32:48])
        else:
            # centrado vertical cuando es una sola línea
            pdf.drawString(40, alto_bloque5 - 10, instituticion[:16])

        #red
        pdf.drawString(ancho-435, alto_bloque5+20, ReporteReferenciaService._texto_seguro(respuesta.institucion_resp_red, 15))

        #bloque6
        alto_bloque6 = alto_bloque5 - 30
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(
            ancho-495,
            alto_bloque6-27,
            ReporteReferenciaService._texto_seguro(respuesta.res_motivo_detalle, 35)
        )

        #bloque28 diagnosticos
        alto_bloque28 = alto_bloque6-317.5
        pdf.drawString(ancho-490, alto_bloque28, (respuesta.res_diagnosticos[:68] or "").upper())
        if len(respuesta.res_diagnosticos) > 68:
            pdf.drawString(
                40,
                alto_bloque28-14.5,
                ReporteReferenciaService._texto_seguro(respuesta.res_diagnosticos[68:].upper(), 75)
            )

        #bloque32
        alto_bloque32 = alto_bloque28-57.5

        institucion = ""
        institucion_comple = None
        institucion_comple_nombre = ""

        #seguimiento determinar que mostrar wn funcion del seguimeiento
        if respuesta.tipo_seguimiento == 1:
            institucion = respuesta.institucion_or_nombre or ""
            institucion_comple = respuesta.institucion_or_complejidad
            institucion_comple_nombre = respuesta.institucion_or_complejidad_nombre or ""
        elif respuesta.tipo_seguimiento in [2,3]:
            institucion = respuesta.institucion_seg_nombre or ""
            institucion_comple = respuesta.institucion_seg_complejidad
            institucion_comple_nombre = respuesta.institucion_seg_complejidad_nombre or ""

        if institucion_comple > 3:
                pdf.drawString(
                    ancho - 477,
                    alto_bloque32-16,
                    ReporteReferenciaService._texto_seguro(institucion_comple_nombre, 24)
                )

        POSICIONES_COMPLEJIDAD_DESTINO = {
            1: (ancho - 462, alto_bloque32), #UAPS
            2: (ancho - 409, alto_bloque32), #CIS
            3: (ancho - 333, alto_bloque32), #SMI o policlinico
        }

        pos = POSICIONES_COMPLEJIDAD_DESTINO.get(
            institucion_comple,
            (ancho - 497, alto_bloque32-16)
        )
        pdf.drawString(*pos, "X")

        #amerita atencion en lo determina el siguiento tambien si es 1 instucional escribir 
        if respuesta.tipo_seguimiento == 3:
            pdf.drawString(
                    ancho - 200,
                    alto_bloque32-17,
                    ReporteReferenciaService._texto_seguro(respuesta.institucion_seg_especialidad, 24)
                )
        else:
            if respuesta.res_atencion not in [3, 2, 4]:
                pdf.drawString(
                        ancho - 200,
                        alto_bloque32-17,
                        ReporteReferenciaService._texto_seguro(respuesta.res_atencion_descripcion, 24)
                    )
        
        #Amerita atencion
        POSICIONES_ATENCION = {
            3: (ancho - 217, alto_bloque32-9), #Consulta Externa
            2: (ancho - 137, alto_bloque32-6), #Emergencia
            4: (ancho - 45, alto_bloque32-6),  #Hospitalizacion
        }

        if respuesta.res_atencion:
            if respuesta.tipo_seguimiento != 3: #recibida
                pos = POSICIONES_ATENCION.get(
                    respuesta.res_atencion,
                    (ancho - 217, alto_bloque32-19)
                )
            else:#enviada
                pos = (ancho - 217, alto_bloque32-19)

            pdf.drawString(*pos, "X")


        #escritra de las X
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(ancho-42, alto-37, "X")

        #peques
        pdf.setFont("Helvetica-Bold", 11)

        #proveedor de salud = Instiucion
        #institucion_proveedor_salud_id
        POSICIONES_PROVEEDOR = {
            6: (ancho - 390.5, alto_bloque5 + 5),    #sesal
            5: (ancho - 346.5, alto_bloque5 + 5),    #privado
            1: (ancho - 431.5, alto_bloque5 - 9),    #IHSS
            2: (ancho - 390.5, alto_bloque5 - 9),    #militar
            3: (ancho - 346.5, alto_bloque5 - 9),    #ong
            4: (ancho - 431.5, alto_bloque5 - 22.5), #otro
        }

        pos = POSICIONES_PROVEEDOR.get(respuesta.institucion_resp_proveedor_salud_id)
        if pos:
            pdf.drawString(*pos, "X")

        #Centralizado
        if respuesta.institucion_resp_centralizado:
            pdf.drawString(ancho - 232.5, alto_bloque5 - 10.5, "X")
        else:
            pdf.drawString(ancho - 232.5, alto_bloque5 - 23.4, "X")

        #nivel de complejidad
        POSICIONES_COMPLEJIDAD_ORIGEN = {
            1: (ancho - 67.5, alto_bloque5 - 10.5),   #UAPS
            2: (ancho - 39.5, alto_bloque5 - 10.5),   #CIS
            3: (ancho - 171.5, alto_bloque5 - 23.46), #SMI o policlinico
        }

        pos = POSICIONES_COMPLEJIDAD_ORIGEN.get(
            respuesta.institucion_resp_complejidad,
            (ancho - 87, alto_bloque5 - 23.46)
        )                                                                   
        pdf.drawString(*pos, "X")

        if respuesta.institucion_resp_complejidad > 3:
            pdf.drawString(pos[0]+15, pos[1], ReporteReferenciaService._texto_seguro(respuesta.institucion_resp_complejidad_nombre, 6))

        #motivo
        pdf.setFont("Helvetica-Bold", 12)
        POSICIONES_MOTIVO = {
            4: (ancho - 70, alto_bloque6 - 11.5),   #Rehabilitación
            3: (ancho - 205, alto_bloque6 - 11.5),  #Seguimiento
            2: (ancho - 342, alto_bloque6 - 11.5),  #Tratamiento
            1: (ancho - 458, alto_bloque6 - 11.5),  #Diagnóstico
        }

        pos = POSICIONES_MOTIVO.get(respuesta.res_motivo)
        if pos:
            pdf.drawString(*pos, "X")

        pdf.setFont("Helvetica-Bold", 11)

        #bloque33
        alto_bloque33 = alto_bloque32-47
        pdf.drawString(40, alto_bloque33, ReporteReferenciaService._texto_seguro(institucion, 30))
        pdf.drawString(ancho-261, alto_bloque33+1, f"{respuesta.res_fecha_elaboracion_dia:02d}")
        pdf.drawString(ancho-205, alto_bloque33+1, f"{respuesta.res_fecha_elaboracion_mes:02d}")
        pdf.drawString(ancho-140, alto_bloque33+1, f"{respuesta.res_fecha_elaboracion_anio}")
        pdf.drawString(ancho-65, alto_bloque33+1, ReporteReferenciaService._texto_seguro(respuesta.res_fecha_elaboracion_hora, 8))

        #bloque35
        alto_bloque35 = alto_bloque33-49
        if respuesta.res_elaborado_por > 4:
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(
                ancho - 485,
                alto_bloque35-22,
                ReporteReferenciaService._texto_seguro(respuesta.res_elaborado_descripcion, 24)
            )

        #elaborado por:
        POSICIONES_ELABORADO = {
            1: (ancho - 427, alto_bloque35),     #Medico General
            2: (ancho - 320, alto_bloque35),     #Medico Especialista
            3: (ancho - 427, alto_bloque35-12),  #Enfermera
            4: (ancho - 320, alto_bloque35-12),  #Auxiliar Enf
        }

        pos = POSICIONES_ELABORADO.get(
            respuesta.res_elaborado_por,
            (ancho - 552, alto_bloque35-22)
        )
        pdf.drawString(*pos, "X")

        #bloque36
        alto_bloque36 = alto_bloque35-50

        if respuesta.tipo_seguimiento == 1:
            pdf.drawString(40, alto_bloque36, ReporteReferenciaService._texto_seguro(respuesta.seguimiento_area,17))

        pdf.drawString(ancho-130, alto_bloque36-28, ReporteReferenciaService._texto_seguro(f"# {respuesta.ref_id}", 10))



    @staticmethod
    def _dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario):
        #Dibuja el pie de página en una posición fija desde el borde inferior.
        
        
        fechaActual = timezone.now()
        pdf.setFillColor(colors.black)

        fecha_formato = formatear_fecha(fechaActual)[:40]
        user_info = f"{usuario.username} ({usuario.first_name} {usuario.last_name})"[:40]

        alto_texto = alto-778

        # --------- IZQUIERDA: FECHA ---------
        texto_izq = "IMPRESO EL -> "
        pdf.setFont("Courier", 7)
        pdf.drawString(40,alto_texto, texto_izq)
        
        pdf.setFont("Courier-Bold", 7)
        pdf.drawString(45 + pdf.stringWidth(texto_izq, "Helvetica", 7), alto_texto, fecha_formato.upper())
        
        
        # --------- DERECHA: USUARIO ---------
        texto_der = "POR -> "
        ancho_texto_der = pdf.stringWidth(texto_der, "Courier", 7)
        ancho_user_info = pdf.stringWidth(user_info, "Courier-Bold", 7)
        
        x_derecha = ancho - 40 - ancho_texto_der - ancho_user_info
        pdf.setFont("Courier", 7)
        pdf.drawString(x_derecha, alto_texto, texto_der)

        pdf.setFont("Courier-Bold", 7)
        pdf.drawString(x_derecha + ancho_texto_der, alto_texto, user_info)

    @staticmethod
    def _dibujarEstructuraPagina2FormatoReferenciaRespuesta(pdf, ancho, alto):

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, alto-85, "FECHA: ______/________________/_______           NUMERO:______  ES:_________  RED:___________________")

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(ancho / 2, alto - 200, "REFERENCIA  /  RESPUESTA A:")

        pdf.setFillColorRGB(0, 0, 0)
        pdf.roundRect(40, alto-380, ancho - 85, 160, radius=8, stroke=1, fill=0)

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, alto-250, "ESTABLECIMIENTO:")
        pdf.line(175, alto-252, 560, alto-252)
        pdf.drawString(50, alto-280, "AL SERVICIO DE:")
        pdf.line(160, alto-282, 560, alto-282)
        pdf.drawString(50, alto-310, "DIRECCION:")
        pdf.line(135, alto-312, 560, alto-312)
        pdf.drawString(50, alto-340, "PARA:")

        pdf.roundRect(120, alto-360, 50, 30, radius=4, stroke=1, fill=0)
        pdf.roundRect(235, alto-360, 50, 30, radius=4, stroke=1, fill=0)
        pdf.roundRect(350, alto-360, 50, 30, radius=4, stroke=1, fill=0)
        pdf.roundRect(465, alto-360, 50, 30, radius=4, stroke=1, fill=0)

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(110, alto-374, "DIAGNOSTICO")
        pdf.drawString(225, alto-374, "TRATAMIENTO")
        pdf.drawString(340, alto-374, "SEGUIMIENTO")
        pdf.drawString(450, alto-374, "REHABILITACION")

        # Bloque IMPORTANTE
        pdf.setFont("Helvetica-Bold", 18)
        pdf.setFillColor(colors.black)
        pdf.roundRect(225, alto-462, 160, 35, radius=4, stroke=1, fill=1)
        pdf.setFillColor(colors.white)
        pdf.drawCentredString(ancho / 2, alto - 450, "¡ IMPORTANTE !")

        pdf.setFillColor(colors.black)
        pdf.drawCentredString(ancho / 2, alto - 485, "LEA ESTO")

        pdf.drawCentredString(ancho / 2, alto - 530, "ESTE DOCUMENTO CONTIENE INFORMACION")
        pdf.drawCentredString(ancho / 2, alto - 557, "INDISPENSABLE PARA SU SALUD")
        pdf.roundRect(96, alto-537, 420, 28, radius=4, stroke=1, fill=0)
        pdf.roundRect(145, alto-565, 320, 28, radius=4, stroke=1, fill=0)

        pdf.drawCentredString(ancho / 2, alto - 605, "ES IMPORTANTE QUE CUMPLA BIEN LAS")
        pdf.drawCentredString(ancho / 2, alto - 632, "INDICACIONES QUE LE DIERON")
        pdf.roundRect(115, alto-612, 385, 28, radius=4, stroke=1, fill=0)
        pdf.roundRect(155, alto-640, 300, 28, radius=4, stroke=1, fill=0)

        pdf.drawCentredString(ancho / 2, alto - 680, "PRESENTARSE AL ESTABLECIMIENTO DE SALUD")
        pdf.drawCentredString(ancho / 2, alto - 707, "INMEDIATAMENTE O COMO LE INDICARON")
        pdf.roundRect(75, alto-687, 460, 28, radius=4, stroke=1, fill=0)
        pdf.roundRect(105, alto-715, 400, 28, radius=4, stroke=1, fill=0)

    @staticmethod
    def _dibujarDatosPagina2FormatoReferencia(pdf, ancho, alto, referencia, hospitalizacion=False):




        pdf.setFont("Helvetica-Bold", 12)
        
        pdf.drawString(340, alto-82, ReporteReferenciaService._texto_seguro(referencia.institucion_complejidad,2))
        pdf.drawString(395, alto-82, ReporteReferenciaService._texto_seguro(referencia.institucion_complejidad_nombre, 4))
        pdf.drawString(470, alto-82, ReporteReferenciaService._texto_seguro(referencia.institucion_red,12))

        if not hospitalizacion:
            pdf.drawString(90, alto-83, f"{referencia.ref_fecha_elaboracion_dia}")
            pdf.drawString(125, alto-83, f"{mes_nombre(referencia.ref_fecha_elaboracion_mes, True)}")
            pdf.drawString(215, alto-83, f"{referencia.ref_fecha_elaboracion_anio}")

        
            pdf.drawString(190, alto-246, ReporteReferenciaService._texto_seguro(referencia.instirucion_dest_nombre, 45))
            if referencia.ref_especialidad_destino:
                pdf.drawString(170, alto-276, referencia.ref_especialidad_destino)
            else:
                pdf.drawString(170, alto-276, referencia.ref_atencion_descripcion)

            pdf.drawString(150, alto-306, ReporteReferenciaService._texto_seguro(referencia.institucion_dest_direccion, 60))

            # Marca X según motivo
            pdf.setLineWidth(3)
            posiciones_motivo = {
                1: (123, 167),
                2: (238, 282),
                3: (353, 397),
                4: (468, 512)
            }

            coords = posiciones_motivo.get(referencia.ref_motivo)
            if coords:
                x1, x2 = coords
                y1, y2 = alto - 358, alto - 334
                pdf.line(x1, y1, x2, y2)
                pdf.line(x1, y2, x2, y1)

    @staticmethod
    def _dibujarDatosPagina2FormatoRespuesta(pdf, ancho, alto, respuesta):

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(90, alto-83, f"{respuesta.res_fecha_elaboracion_dia}")
        pdf.drawString(125, alto-83, f"{mes_nombre(respuesta.res_fecha_elaboracion_mes, True)}")
        pdf.drawString(215, alto-83, f"{respuesta.res_fecha_elaboracion_anio}")

        pdf.drawString(340, alto-82, f"{respuesta.institucion_resp_complejidad}")
        pdf.drawString(395, alto-82, f"{respuesta.institucion_resp_complejidad_nombre}")
        pdf.drawString(470, alto-82, f"{respuesta.institucion_resp_red[:14]}")


        if respuesta.tipo_seguimiento == 1:
            institucion = respuesta.institucion_or_nombre
        elif respuesta.tipo_seguimiento in [2,3]:
            institucion = respuesta.institucion_seg_nombre
        pdf.drawString(190, alto-246, ReporteReferenciaService._texto_seguro(institucion, 45))

        if respuesta.tipo_seguimiento == 3:
            pdf.drawString(170, alto-276, respuesta.institucion_seg_especialidad)
        else:
        #elif respuesta.tipo_seguimiento == 2:
            pdf.drawString(170, alto-276, ReporteReferenciaService._texto_seguro(respuesta.res_atencion_descripcion,30))
        #else:
        #    pdf.drawString(170, alto-276, ReporteReferenciaService._texto_seguro(respuesta.seguimiento_area,30))

        
        
        pdf.drawString(150, alto-306, ReporteReferenciaService._texto_seguro(respuesta.institucion_seg_direccion, 60))
        
        # Marca X según motivo
        pdf.setLineWidth(3)
        posiciones_motivo = {
            1: (123, 167),
            2: (238, 282),
            3: (353, 397),
            4: (468, 512)
        }

        coords = posiciones_motivo.get(respuesta.res_motivo)
        if coords:
            x1, x2 = coords
            y1, y2 = alto - 358, alto - 334
            pdf.line(x1, y1, x2, y2)
            pdf.line(x1, y2, x2, y1)

    @staticmethod
    def GenerarFormatoRefencia(referencia, paciente, usuario):


        referencia = SimpleNamespace(**referencia)
        paciente = SimpleNamespace(**paciente)


        #Crecion del documento
        nombre_paciente = f"{paciente.nombres}".strip().replace(" ", "_") 
        nombre_archivo = f"reporte_referencia_{nombre_paciente}.pdf"


        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'
        
        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(f"Formato SINAR Referencia - {nombre_paciente}")
        ancho, alto = letter


        #//// Escritura del contenido
        # ===== PÁGINA 1 =====
        ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto, None)

        ReporteReferenciaService._dibujarEstructuraFormatoReferenciaRespuesta(pdf,ancho,alto)
        
        ReporteReferenciaService._dibujarEtiquetasEstaticasFormatoRefenciaRespuesta(pdf,ancho,alto)
        
        ReporteReferenciaService._dibujarDatosDinamicosFormatoReferencia(pdf,ancho,alto,referencia, paciente)

        ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)

        # ===== PÁGINA 2 =====

        pdf.showPage()
        ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto, 2)

        ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)

        ReporteReferenciaService._dibujarEstructuraPagina2FormatoReferenciaRespuesta(pdf, ancho, alto)

        ReporteReferenciaService._dibujarDatosPagina2FormatoReferencia(pdf, ancho, alto, referencia)

        pdf.save()

        return response


    @staticmethod
    def GenerarFormatoRespuesta(respuesta, paciente , usuario):

        respuesta = SimpleNamespace(**respuesta)
        paciente = SimpleNamespace(**paciente)


        #Crecion del documento
        nombre_paciente = f"{paciente.nombres}".strip().replace(" ", "_") 
        nombre_archivo = f"reporte_respuesta_{paciente.nombres}.pdf"


        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'
        
        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(f"Formato SINAR Respuesta - {nombre_paciente}")
        ancho, alto = letter

        # ===== PÁGINA 1 =====
        ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto)

        ReporteReferenciaService._dibujarEstructuraFormatoReferenciaRespuesta(pdf,ancho,alto)

        ReporteReferenciaService._dibujarEtiquetasEstaticasFormatoRefenciaRespuesta(pdf,ancho,alto)

        ReporteReferenciaService._dibujarDatosDinamicosFormatoRespuesta(pdf,ancho,alto,respuesta,paciente)

        ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)

        # ===== PÁGINA 2 =====

        pdf.showPage()
        ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto, 2)

        ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)

        ReporteReferenciaService._dibujarEstructuraPagina2FormatoReferenciaRespuesta(pdf, ancho, alto)


        ReporteReferenciaService._dibujarDatosPagina2FormatoRespuesta(pdf, ancho, alto, respuesta)

        


        pdf.save()

        return response