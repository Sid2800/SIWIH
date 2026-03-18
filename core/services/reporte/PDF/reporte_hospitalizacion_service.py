from types import SimpleNamespace
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import os 
from django.utils import timezone
# locales
from core.services.reporte.PDF.reporte_pdf_base_service import ReportePdfBaseService
from core.utils.utilidades_textos import formatear_dni, formatear_expediente
from core.utils.utilidades_fechas import formatear_fecha, mes_nombre
from core.services.reporte.PDF.reporte_referencia_service import ReporteReferenciaService
from django.conf import settings
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


class ReporteHospitalizacionService:
    MARGEN_IZQUIERDO = 24

    @staticmethod
    def __dibujarEstructuraHojaHospitalizacion2026(pdf, ancho, alto):

        inicio_x = 18
        espacio_columna = 11.9
        columnas = 50
        filas = 58

        alt_normal = 11.2
        alt_contenido = 17
        alt_contenido_mano = 16

        alt_margen = 2.6

        # Logos
        try:
            logo1 = os.path.join(settings.BASE_DIR, 'core/static/core/img/escudo_nacional.png')
            pdf.drawImage(logo1, x=12, y=alto-62, width=62, height=42,
                        preserveAspectRatio=True, mask='auto')

            logo2 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_HEAC.png')
            pdf.drawImage(logo2, x=ancho-78, y=alto-62, width=62, height=42,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            log_warning(
                "No se logro cargar los logotipos de la empresa",
                app=LogApp.REPORTES
            )

        # Tabla
        datos = [[""] * columnas for _ in range(filas)]
        colWidths = [4] + [espacio_columna] * 48 + [4]

        rowHeights = [
            81,
            alt_normal, alt_contenido,                                                      # Bloque 1 – Identificación
            alt_margen, alt_normal -2, alt_contenido, alt_normal-2, alt_margen,             # Bloque 2 – Fecha nacimiento
            alt_normal, alt_contenido, alt_margen,                                          # Bloque 3 – Residencia
            10, 10, alt_contenido, alt_margen,                                              # Bloque 4 – Acompañante                   
            alt_normal, alt_contenido, alt_margen,                                          # Bloque 5 – Padres    
            alt_margen, alt_normal, alt_contenido, alt_margen,                              # Bloque 6 – Ingres  
            alt_margen, alt_margen, alt_contenido_mano, alt_margen, alt_contenido_mano, 5,  # Bloque 7 – DIAGNOSTICO DE ING 
            57,                                                                             # bloque 8 - CAUSA DE ACCIDENTE O VIO
            alt_normal, alt_normal, alt_contenido_mano,                                     # bloque 9 - traslado
            alt_margen, alt_normal, alt_contenido_mano, alt_contenido_mano, alt_contenido_mano, alt_contenido_mano,
            alt_normal, alt_normal, alt_contenido_mano, alt_contenido_mano, alt_contenido_mano, alt_contenido_mano, alt_normal -2,
            alt_normal, alt_normal-1, alt_normal-1, alt_margen,                                # bloque 12 - traslado
            alt_normal, alt_normal, alt_normal, alt_normal, alt_normal + 2, alt_normal + 2, alt_normal + 2, alt_normal + 4,
            22#Firmas

        ]

        tabla = Table(datos, colWidths=colWidths, rowHeights=rowHeights)

        estilo = []

        # General
        estilo += [
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            ('LINEABOVE', (0, 0), (-1, 0), 1.1, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 1.1, colors.black),
            ('LINEBEFORE', (0, 0), (0, -1), 1.1, colors.black),
            ('LINEAFTER', (-1, 0), (-1, -1), 1.1, colors.black),

        ]

        # Encabezado
        estilo += [
            ('SPAN', (0, 0), (-1, 1)),
        ]

        # Bloque 1 – Identificación
        estilo += [
            ('GRID', (1, 2), (48, 2), 0.4, colors.black),

            ('SPAN', (1, 2), (12, 2)),
            ('SPAN', (13, 2), (24, 2)),
            ('SPAN', (25, 2), (38, 2)),
            ('SPAN', (39, 2), (48, 2)),
        ]

        # Bloque 2 – Fecha nacimiento
        estilo += [
            ('GRID', (1, 5), (7, 5), 0.4, colors.black),
            ('GRID', (10, 5), (13, 5), 0.4, colors.black),
            ('GRID', (20, 5), (21, 5), 0.4, colors.black),
            ('GRID', (28, 5), (29, 5), 0.4, colors.black),
            ('GRID', (39, 5), (41, 5), 0.4, colors.black),

            ('SPAN', (1, 5), (2, 5)),
            ('SPAN', (3, 5), (4, 5)),
            ('SPAN', (5, 5), (7, 5)),
            ('SPAN', (10, 5), (11, 5)),
            ('SPAN', (12, 5), (13, 5)),
            ('SPAN', (20, 5), (21, 5)),
            ('SPAN', (28, 5), (29, 5)),
            ('SPAN', (39, 5), (41, 5)),

            ('LINEBELOW', (0, 7), (-1, 7), 0.5, colors.black),
        ]

        # Bloque 3 – Residencia
        estilo += [
            ('GRID', (1, 9), (48, 9), 0.4, colors.black),

            ('SPAN', (1, 9), (11, 9)),
            ('SPAN', (12, 9), (25, 9)),
            ('SPAN', (26, 9), (41, 9)),
            ('SPAN', (42, 9), (48, 9)),

            ('LINEBELOW', (0, 10), (-1, 10), 0.5, colors.black),
        ]

        # Bloque 4 – Acompañante
        estilo += [
            ('GRID', (1, 13), (48, 13), 0.4, colors.black),

            ('SPAN', (1, 13), (21, 13)),
            ('SPAN', (22, 13), (41, 13)),
            ('SPAN', (42, 13), (48, 13)),
        ]

        # Bloque 5 – Padres
        estilo += [
            ('GRID', (1, 16), (48, 16), 0.4, colors.black),

            ('SPAN', (1, 16), (24, 16)),
            ('SPAN', (25, 16), (48, 16)),

            ('LINEBELOW', (0, 17), (-1, 17), 0.5, colors.black),
        ]

        # Bloque 6 – INGRESO
        estilo += [
            ('GRID', (1, 20), (2, 20), 0.4, colors.black),
            ('GRID', (9, 20), (19, 20), 0.4, colors.black),
            ('GRID', (21, 20), (33, 20), 0.4, colors.black),
            ('GRID', (36, 20), (42, 20), 0.4, colors.black),
            ('GRID', (44, 20), (46, 20), 0.4, colors.black),

            ('GRID', (40, 24), (48, 24), 0.4, colors.black),
            ('GRID', (40, 26), (48, 26), 0.4, colors.black),



            ('SPAN', (1, 20), (2, 20)),
            ('SPAN', (9, 20), (19, 20)),
            ('SPAN', (21, 20), (33, 20)),

            ('SPAN', (36, 20), (37, 20)),
            ('SPAN', (38, 20), (39, 20)),
            ('SPAN', (40, 20), (42, 20)),
            ('SPAN', (44, 20), (46, 20)),

            ('SPAN', (40, 24), (42, 24)),
            ('SPAN', (43, 24), (44, 24)),
            ('SPAN', (45, 24), (46, 24)),
            ('SPAN', (47, 24), (48, 24)),

            ('SPAN', (40, 26), (42, 26)),
            ('SPAN', (43, 26), (44, 26)),
            ('SPAN', (45, 26), (46, 26)),
            ('SPAN', (47, 26), (48, 26)),


            ('LINEBELOW', (10, 24), (38, 24), 0.5, colors.black),
            ('LINEBELOW', (2, 26), (38, 26), 0.5, colors.black),
            ('LINEBELOW', (0, 27), (-1, 27), 0.5, colors.black),
        ]

        # Bloque 7 – Causa accidente
        estilo += [
            ('GRID', (0, 28), (-1, 28), 0.4, colors.black),
            ('SPAN', (0, 28), (31, 28)),
            ('SPAN', (32, 28), (49, 28)),
        ]

        # Bloque 8 – Traslado y egreso
        estilo += [
            ('GRID', (1, 29), (48, 31), 0.4, colors.black),
            ('SPAN', (1, 29), (17, 29)), 
            ('SPAN', (1, 30), (8, 30)), 
            ('SPAN', (9, 30), (17, 30)), 
            ('SPAN', (1, 31), (8, 31)), 
            ('SPAN', (9, 31), (17, 31)), 
            ('SPAN', (18, 29), (24, 30)), 
            ('SPAN', (18, 31), (19, 31)), 
            ('SPAN', (20, 31), (21, 31)), 
            ('SPAN', (22, 31), (24, 31)),
            
            ('SPAN', (25, 29), (41, 29)),
            ('SPAN', (25, 30), (32, 30)),
            ('SPAN', (33, 30), (41, 30)), 
            ('SPAN', (25, 31), (32, 31)), 
            ('SPAN', (33, 31), (41, 31)), 
            ('SPAN', (42, 29), (48, 30)), 
            ('SPAN', (42, 31), (43, 31)), 
            ('SPAN', (44, 31), (45, 31)), 
            ('SPAN', (46, 31), (48, 31)),
        ]

        # Bloque 9 – diagnostico de egreso
        estilo += [

            ('SPAN', (40, 33), (48, 33)),
            ('SPAN', (40, 34), (42, 34)),
            ('SPAN', (43, 34), (44, 34)),
            ('SPAN', (45, 34), (46, 34)),
            ('SPAN', (47, 34), (48, 34)),

            ('SPAN', (40, 35), (42, 35)),
            ('SPAN', (43, 35), (44, 35)),
            ('SPAN', (45, 35), (46, 35)),
            ('SPAN', (47, 35), (48, 35)),

            ('SPAN', (40, 36), (42, 36)),
            ('SPAN', (43, 36), (44, 36)),
            ('SPAN', (45, 36), (46, 36)),
            ('SPAN', (47, 36), (48, 36)),

            ('SPAN', (40, 37), (42, 37)),
            ('SPAN', (43, 37), (44, 37)),
            ('SPAN', (45, 37), (46, 37)),
            ('SPAN', (47, 37), (48, 37)),


            ('GRID', (40, 33), (48, 37), 0.4, colors.black),

            ('LINEBELOW', (6, 34), (38, 34), 0.5, colors.black),
            ('LINEBELOW', (2, 35), (38, 35), 0.5, colors.black),
            ('LINEBELOW', (2, 36), (38, 36), 0.5, colors.black),
            ('LINEBELOW', (2, 37), (38, 37), 0.5, colors.black),
        ]

        # Bloque 10 – procemiento quirugico
        estilo += [
            ('SPAN', (40, 39), (48, 39)),

            ('SPAN', (40, 40), (42, 40)),
            ('SPAN', (43, 40), (44, 40)),
            ('SPAN', (45, 40), (46, 40)),
            ('SPAN', (47, 40), (48, 40)),

            ('SPAN', (40, 41), (42, 41)),
            ('SPAN', (43, 41), (44, 41)),
            ('SPAN', (45, 41), (46, 41)),
            ('SPAN', (47, 41), (48, 41)),

            ('SPAN', (40, 42), (42, 42)),
            ('SPAN', (43, 42), (44, 42)),
            ('SPAN', (45, 42), (46, 42)),
            ('SPAN', (47, 42), (48, 42)),

            ('SPAN', (40, 43), (42, 43)),
            ('SPAN', (43, 43), (44, 43)),
            ('SPAN', (45, 43), (46, 43)),
            ('SPAN', (47, 43), (48, 43)),

            ('SPAN', (33, 39), (34, 39)),
            ('SPAN', (35, 39), (36, 39)),
            ('SPAN', (37, 39), (39, 39)),

            ('SPAN', (33, 40), (34, 40)),
            ('SPAN', (35, 40), (36, 40)),
            ('SPAN', (37, 40), (39, 40)),

            ('SPAN', (33, 41), (34, 41)),
            ('SPAN', (35, 41), (36, 41)),
            ('SPAN', (37, 41), (39, 41)),

            ('SPAN', (33, 42), (34, 42)),
            ('SPAN', (35, 42), (36, 42)),
            ('SPAN', (37, 42), (39, 42)),

            ('SPAN', (33, 43), (34, 43)),
            ('SPAN', (35, 43), (36, 43)),
            ('SPAN', (37, 43), (39, 43)),

            ('GRID', (33, 39), (48, 43), 0.4, colors.black),

            ('LINEBELOW', (6, 40), (31, 40), 0.5, colors.black),
            ('LINEBELOW', (2, 41), (31, 41), 0.5, colors.black),
            ('LINEBELOW', (2, 42), (31, 42), 0.5, colors.black),
            ('LINEBELOW', (2, 43), (31, 43), 0.5, colors.black),
        ]

        # Bloque 11 – condicion de egreso
        estilo += [
            ('SPAN', (2, 46), (4, 47)),
            ('SPAN', (15, 46), (17, 47)),
            ('SPAN', (29, 46), (42, 47)),

            ('SPAN', (43, 45), (48, 45)),
            ('SPAN', (43, 46), (45, 46)),
            ('SPAN', (46, 46), (48, 46)),

            ('SPAN', (43, 47), (45, 47)),
            ('SPAN', (46, 47), (48, 47)),


            ('GRID', (2, 46), (4, 47), 0.4, colors.black),
            ('GRID', (43, 45), (48, 45), 0.4, colors.black),

            ('GRID', (15, 46), (17, 47), 0.4, colors.black),
            ('GRID', (29, 46), (48, 47), 0.4, colors.black),

            ('LINEBELOW', (0, 48), (49, 48), 0.5, colors.black),
            ('LINEBELOW', (0, 49), (49, 49), 0.5, colors.black),
        ]

        # Bloque 11 – condicion de egreso
        estilo += [
            ('SPAN', (1, 50), (17, 54)),
            ('SPAN', (18, 50), (27, 51)),
            ('SPAN', (18, 52), (27, 53)),
            ('SPAN', (18, 54), (27, 55)),
            ('SPAN', (18, 56), (27, 56)),

            ('SPAN', (28, 50), (29, 51)),
            ('SPAN', (28, 52), (29, 53)),
            ('SPAN', (28, 54), (29, 55)),
            ('SPAN', (28, 56), (29, 56)),

            ('SPAN', (30, 50), (48, 50)),
            ('SPAN', (30, 51), (31, 52)),

            ('SPAN', (30, 53), (31, 53)),
            ('SPAN', (30, 54), (31, 54)),
            ('SPAN', (30, 55), (31, 55)),
            ('SPAN', (30, 56), (31, 56)),

            ('SPAN', (32, 51), (37, 51)),
            ('SPAN', (38, 51), (43, 51)),


            # sexo
            ('SPAN', (32, 52), (34, 52)),
            ('SPAN', (35, 52), (37, 52)),

            ('SPAN', (32, 53), (34, 53)),
            ('SPAN', (35, 53), (37, 53)),

            ('SPAN', (32, 54), (34, 54)),
            ('SPAN', (35, 54), (37, 54)),

            ('SPAN', (32, 55), (34, 55)),
            ('SPAN', (35, 55), (37, 55)),

            ('SPAN', (32, 56), (34, 56)),
            ('SPAN', (35, 56), (37, 56)),


            # condicion al nacer
            ('SPAN', (38, 52), (40, 52)),
            ('SPAN', (41, 52), (43, 52)),

            ('SPAN', (38, 53), (40, 53)),
            ('SPAN', (41, 53), (43, 53)),

            ('SPAN', (38, 54), (40, 54)),
            ('SPAN', (41, 54), (43, 54)),

            ('SPAN', (38, 55), (40, 55)),
            ('SPAN', (41, 55), (43, 55)),

            ('SPAN', (38, 56), (40, 56)),
            ('SPAN', (41, 56), (43, 56)),

            ('SPAN', (38, 57), (40, 57)),
            ('SPAN', (41, 57), (43, 57)),

            # peso en gramos
            ('SPAN', (44, 51), (48, 52)), 

            ('SPAN', (44, 53), (48, 53)),
            ('SPAN', (44, 54), (48, 54)),
            ('SPAN', (44, 55), (48, 55)),
            ('SPAN', (44, 56), (48, 56)),

            ('GRID', (18, 50), (48, 56), 0.4, colors.black),
            ('GRID', (1, 50), (17, 54), 0.4, colors.black),
        ]

        tabla.setStyle(TableStyle(estilo))

        _, alto_tabla = tabla.wrap(ancho, alto)
        tabla.drawOn(pdf, inicio_x, alto - alto_tabla - 16)

    
    @staticmethod
    def __dibujarEtiquetasEstaticasHojaHospitalizacion2026(pdf, ancho, alto):
        primer_elemento_izquierda = ReporteHospitalizacionService.MARGEN_IZQUIERDO
        # encabezado 
        alto_header = alto + 5  

        # ===== TÍTULOS SUPERIORES =====
        pdf.setFont("Helvetica-Oblique", 7.5)
        pdf.drawCentredString(ancho / 2, alto_header - 29, "SECRETARÍA DE SALUD")
        pdf.drawCentredString(ancho / 2, alto_header - 37, "UNIDAD DE GESTIÓN DE LA INFORMACIÓN")
        pdf.drawCentredString(ancho / 2, alto_header - 45, "ÁREA ESTADÍSTICA DE LA SALUD")

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(ancho / 2, alto_header - 58, "HC-13: HOJA DE HOSPITALIZACIÓN")


        # ===== ETIQUETAS =====
        pdf.setFont("Helvetica", 6.5)
        pdf.drawString(primer_elemento_izquierda, alto_header - 75, "ESTABLECIMIENTO:")
        pdf.drawString(primer_elemento_izquierda, alto_header - 85, "TIPO DE ESTABLECIMIENTO:")
        pdf.drawString(primer_elemento_izquierda, alto_header - 95, "ETNIA:")

        pdf.drawString(primer_elemento_izquierda + 235, alto_header - 75, "RUPS:")
        pdf.drawString(primer_elemento_izquierda + 235, alto_header - 85, "REGION:")
        pdf.drawString(primer_elemento_izquierda + 235, alto_header - 95, "FECHA:")

        pdf.drawString(primer_elemento_izquierda + 345, alto_header - 75, "DEPARTAMENTO:")
        pdf.drawString(primer_elemento_izquierda + 345, alto_header - 85, "MUNICIPIO:")
        pdf.drawString(primer_elemento_izquierda + 345, alto_header - 95, "RED:")

        pdf.drawString(primer_elemento_izquierda + 462, alto_header - 95, "NÚMERO EXPEDIENTE CLÍNICO")

        # ===== DATOS ESTÁTICOS =====
        pdf.setFont("Helvetica-Bold", 6.5)

        pdf.drawString(primer_elemento_izquierda + 73,  alto_header - 75, "HOSPITAL DR. ENRIQUE AGUILAR CERRATO")
        pdf.drawString(primer_elemento_izquierda + 120, alto_header - 85, "HOSPITAL BÁSICO")

        pdf.drawString(primer_elemento_izquierda + 270, alto_header - 75, "8753")
        pdf.drawString(primer_elemento_izquierda + 270, alto_header - 85, "#10 - INTIBUCÁ")

        pdf.drawString(primer_elemento_izquierda + 405, alto_header - 75, "INTIBUCÁ")
        pdf.drawString(primer_elemento_izquierda + 405, alto_header - 85, "INTIBUCÁ")
        pdf.drawString(primer_elemento_izquierda + 405, alto_header - 95, "UNIGES")


        # ===== LÍNEAS =====
        pdf.line(primer_elemento_izquierda + 65,  alto_header - 77, primer_elemento_izquierda + 220, alto_header - 77)
        pdf.line(primer_elemento_izquierda + 95,  alto_header - 87, primer_elemento_izquierda + 220, alto_header - 87)
        pdf.line(primer_elemento_izquierda + 25,  alto_header - 97, primer_elemento_izquierda + 220, alto_header - 97)

        pdf.line(primer_elemento_izquierda + 260, alto_header - 77, primer_elemento_izquierda + 327, alto_header - 77)
        pdf.line(primer_elemento_izquierda + 265, alto_header - 87, primer_elemento_izquierda + 327, alto_header - 87)
        pdf.line(primer_elemento_izquierda + 263, alto_header - 97, primer_elemento_izquierda + 327, alto_header - 97)

        pdf.line(primer_elemento_izquierda + 400, alto_header - 77, primer_elemento_izquierda + 445, alto_header - 77)
        pdf.line(primer_elemento_izquierda + 385, alto_header - 87, primer_elemento_izquierda + 445, alto_header - 87)
        pdf.line(primer_elemento_izquierda + 365, alto_header - 97, primer_elemento_izquierda + 445, alto_header - 97)

        pdf.line(primer_elemento_izquierda + 460, alto_header - 87, primer_elemento_izquierda + 565, alto_header - 87)


        #bloque 1
        pdf.setFont("Helvetica", 7)
        altura_bloque1 = alto - 106
        pdf.drawString(primer_elemento_izquierda, altura_bloque1 , "PRIMER APELLIDO")
        pdf.drawString(primer_elemento_izquierda + 142,  altura_bloque1, "SEGUNDO APELLIDO")
        pdf.drawString(primer_elemento_izquierda + 285,  altura_bloque1, "NOMBRES")
        pdf.drawString(primer_elemento_izquierda + 452,  altura_bloque1, "NUMERO DE IDENTIDAD (DNI)")

        #bloque 2
        altura_bloque2= altura_bloque1 - 29
        pdf.drawString(primer_elemento_izquierda, altura_bloque2 , "FECHA DE NACIMIENTO")
        pdf.drawString(primer_elemento_izquierda + 105, altura_bloque2 , "EDAD")
        pdf.drawString(primer_elemento_izquierda + 225, altura_bloque2 , "SEXO")
        pdf.drawString(primer_elemento_izquierda + 320, altura_bloque2 , "ESTADO CIVIL")
        pdf.drawString(primer_elemento_izquierda + 450, altura_bloque2 , "OCUPACIÓN")

        pdf.drawString(primer_elemento_izquierda+2, altura_bloque2 - 27, "DÍA")
        pdf.drawString(primer_elemento_izquierda+25, altura_bloque2 - 27, "MES")
        pdf.drawString(primer_elemento_izquierda+55, altura_bloque2 - 27, "AÑO")

        pdf.setFont("Helvetica", 5.8)
        pdf.drawString(primer_elemento_izquierda+160, altura_bloque2, "1. HORAS")
        pdf.drawString(primer_elemento_izquierda+160, altura_bloque2 - 8, "2. DÍAS")
        pdf.drawString(primer_elemento_izquierda+160, altura_bloque2 - 16, "3. MESES")
        pdf.drawString(primer_elemento_izquierda+160, altura_bloque2 - 24, "4. AÑOS")

        pdf.drawString(primer_elemento_izquierda+255, altura_bloque2 - 7, "1. HOMBRE")
        pdf.drawString(primer_elemento_izquierda+255, altura_bloque2 - 16, "2. MUJER")


     
        pdf.drawString(primer_elemento_izquierda+377, altura_bloque2,   "1. CASADO")
        pdf.drawString(primer_elemento_izquierda+377, altura_bloque2 - 8,   "2. SOLTERO")
        pdf.drawString(primer_elemento_izquierda+377, altura_bloque2 - 16,  "3. UNIÓN LIBRE")
        pdf.drawString(primer_elemento_izquierda+377, altura_bloque2 - 24,  "4. NO APLICA")
        #pdf.drawString(primer_elemento_izquierda+377, altura_bloque2 - 9,   "3. VIUDO")
        #pdf.drawString(primer_elemento_izquierda+377, altura_bloque2 - 21,  "5. DESCONOCIDO")


        pdf.setFont("Helvetica", 5)
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 + 3,       "1. EMPLEADO PÚBLICO")
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 - 3,       "2. EMPLEADO PRIVADO")
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 - 9,       "3. SERVICIO DOMÉSTICO")
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 - 15,      "4. DESEMPLEADO")
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 - 21,      "5. NEGOCIO PROPIO O SOCIO")
        pdf.drawString(primer_elemento_izquierda+496, altura_bloque2 - 27,      "6. NO APLICA")

        #bloque 3
        pdf.setFont("Helvetica-Bold", 7)
        altura_bloque3 = altura_bloque2 - 40
        pdf.drawString(primer_elemento_izquierda, altura_bloque3 , "RESIDENCIA")
        pdf.setFont("Helvetica", 7)
        pdf.drawString(primer_elemento_izquierda + 54, altura_bloque3 , "DEPARTAMENTO")
        pdf.drawString(primer_elemento_izquierda + 132, altura_bloque3 , "MUNICIPIO")
        pdf.drawString(primer_elemento_izquierda + 300, altura_bloque3 , "LOCALIDAD (BARRIO O COLONIA, NÚMERO DE CASA)")
        pdf.drawString(primer_elemento_izquierda + 490, altura_bloque3 , "TELEFONO")

        #bloque 4
        altura_bloque4 = altura_bloque3 - 30
        pdf.drawCentredString(ancho /2, altura_bloque4 , "EN CASO DE EMERGENCIA LLAMAR A:")
        pdf.drawString(primer_elemento_izquierda, altura_bloque4 - 10, "NOMBRE Y APELLIDO")
        pdf.drawString(primer_elemento_izquierda + 250, altura_bloque4 - 10, "DIRECCIÓN EXACTA")
        pdf.drawString(primer_elemento_izquierda + 490, altura_bloque4 - 10, "TELEFONO")

        #bloque 5 padres
        altura_bloque5 = altura_bloque4 - 30
        pdf.drawString(primer_elemento_izquierda, altura_bloque5 - 10, "NOMBRE DEL PADRE:")
        pdf.drawString(primer_elemento_izquierda + 290, altura_bloque5 - 10, "NOMBRE DE LA MADRE:")


        #bloque 6 ingreso
        altura_bloque6 = altura_bloque5 - 43
        pdf.drawString(primer_elemento_izquierda, altura_bloque6 , "INGRESO POR:")
        pdf.drawString(primer_elemento_izquierda + 90, altura_bloque6 , "INGRESO A:")
        pdf.drawString(primer_elemento_izquierda + 415, altura_bloque6 , "FECHA DE INGRESO")
        pdf.drawString(primer_elemento_izquierda + 517, altura_bloque6 , "HORA")


        pdf.drawString(primer_elemento_izquierda + 145, altura_bloque6 , "SERVICIO:")
        pdf.drawString(primer_elemento_izquierda + 248, altura_bloque6 , "SALA:")

        pdf.drawString(primer_elemento_izquierda, altura_bloque6 - 41, "DIAGNOSTICO DE INGRESO:  1).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque6 - 61, "2).")



        pdf.setFont("Helvetica", 5.5)
        pdf.drawString(primer_elemento_izquierda + 560, altura_bloque6 - 6 , "AM")
        pdf.drawString(primer_elemento_izquierda + 560, altura_bloque6 - 17 , "PM")
        pdf.drawString(primer_elemento_izquierda+27, altura_bloque6 - 10, "1. C EXTERNA")
        pdf.drawString(primer_elemento_izquierda+27, altura_bloque6 - 18, "2. EMERGENCIA")
        pdf.drawString(primer_elemento_izquierda+27, altura_bloque6 - 26, "3. NACIMIENTO")

        pdf.setLineWidth(0.5)
        pdf.rect(primer_elemento_izquierda + 550, altura_bloque6 -8, 7, 7, stroke=1, fill=0)
        pdf.rect(primer_elemento_izquierda + 550, altura_bloque6 -19, 7, 7, stroke=1, fill=0)


        #bloque 7 causa de accidente
        pdf.setFont("Helvetica", 7)
        altura_bloque7 = altura_bloque6 - 78
        pdf.drawString(primer_elemento_izquierda, altura_bloque7, "CAUSA DE ACCIDENTE O VIOLENCIA:")
        pdf.drawString(primer_elemento_izquierda + 375, altura_bloque7, "LUGAR DE ACCIDENTE O VIOLENCIA:")
    
        pdf.setFont("Helvetica-Bold", 7)
        columnas_x = [
            primer_elemento_izquierda,
            primer_elemento_izquierda + 110,
            primer_elemento_izquierda + 220,
            primer_elemento_izquierda + 374,
            primer_elemento_izquierda + 477
        ]

        filas_offset = [-11, -21, -31, -41]

        for col in columnas_x:
            for offset in filas_offset:
                pdf.drawString(col, altura_bloque7 + offset, "(   )")

        pdf.setFont("Helvetica", 5.5)
        pdf.drawString(primer_elemento_izquierda + 236, altura_bloque7 -31, "CONTACTO POR AGENTE FISICO (RAD./CALOR)")

        pdf.setFont("Helvetica", 6.4)
        pdf.drawString(primer_elemento_izquierda + 15, altura_bloque7 -11, "VEHÍCULO MOTORIZADO")
        pdf.drawString(primer_elemento_izquierda + 15, altura_bloque7 -21, "OTRO TRASPORTE")
        pdf.drawString(primer_elemento_izquierda + 15, altura_bloque7 -31, "CAÍDA")
        pdf.drawString(primer_elemento_izquierda + 15, altura_bloque7 -41, "MAQUINARIA")

        pdf.drawString(primer_elemento_izquierda + 125, altura_bloque7 -11, "INCENDIO O EXPLOSIÓN ")
        pdf.drawString(primer_elemento_izquierda + 125, altura_bloque7 -21, "FENÓMENO NATURAL")
        pdf.drawString(primer_elemento_izquierda + 125, altura_bloque7 -31, "ASALTO O AGRESIÓN")
        pdf.drawString(primer_elemento_izquierda + 125, altura_bloque7 -41, "INTENTO DE SUCIDIO")

        pdf.drawString(primer_elemento_izquierda + 236, altura_bloque7 -11, "EXPOSICIÓN SUSTANCIAS NOCIVAS")
        pdf.drawString(primer_elemento_izquierda + 236, altura_bloque7 -21, "DESCARGA ELÉCTRICA")
        pdf.drawString(primer_elemento_izquierda + 236, altura_bloque7 -41, "OTROS")

        pdf.drawString(primer_elemento_izquierda + 391, altura_bloque7 -11, "TRABAJO")
        pdf.drawString(primer_elemento_izquierda + 391, altura_bloque7 -21, "VIVIENDA")
        pdf.drawString(primer_elemento_izquierda + 391, altura_bloque7 -31, "CENTRO DE ESTUDIOS")
        pdf.drawString(primer_elemento_izquierda + 391, altura_bloque7 -41, "CENTRO MÉDICO")

        pdf.drawString(primer_elemento_izquierda + 494, altura_bloque7 -11, "DEPORTE O DIVERSIÓN")
        pdf.drawString(primer_elemento_izquierda + 494, altura_bloque7 -21, "VIA PÚBLICA")
        pdf.drawString(primer_elemento_izquierda + 494, altura_bloque7 -31, "DESCONOCIDO")
        pdf.drawString(primer_elemento_izquierda + 494, altura_bloque7 -41, "OTROS")

        #BLOQUE 8
        altura_bloque8 = altura_bloque7 - 55
        pdf.setFont("Helvetica", 8)
        pdf.drawString(primer_elemento_izquierda + 70, altura_bloque8, "TRASLADO A :")
        pdf.drawString(primer_elemento_izquierda + 355, altura_bloque8, "EGRESO DE :")

        pdf.drawString(primer_elemento_izquierda + 25, altura_bloque8 -11, "SERVICIO:")
        pdf.drawString(primer_elemento_izquierda + 135, altura_bloque8 -11, "SALA:")

        pdf.drawString(primer_elemento_izquierda + 315, altura_bloque8 -11, "SERVICIO:")
        pdf.drawString(primer_elemento_izquierda + 425, altura_bloque8 -11, "SALA:")

        pdf.setFont("Helvetica", 7.4)
        pdf.drawString(primer_elemento_izquierda + 203, altura_bloque8 -5, "FECHA DE TRASLADO")
        pdf.drawString(primer_elemento_izquierda + 493, altura_bloque8 -5, "FECHA DE EGRESO")

        #BLOQUE 9 DIAGNOSTICO DE EGRESO
        altura_bloque9 = altura_bloque8 - 43
        pdf.setFont("Helvetica", 8)
        pdf.drawString(primer_elemento_izquierda, altura_bloque9, "DIAGNÓSTICO DE EGRESO:")
        pdf.drawString(primer_elemento_izquierda, altura_bloque9 - 16, "PRINCIPAL: 1 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque9 - 30, "2 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque9 - 47, "3 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque9 - 63, "4 ).")

        pdf.drawString(primer_elemento_izquierda + 500, altura_bloque9+2, "CÓDIGO")

        #BLOQUE 10 PROCEDIMIENTO QUIRÚRGIC
        altura_bloque10 = altura_bloque9 - 82
        pdf.drawString(primer_elemento_izquierda, altura_bloque10, "PROCEDIMIENTO QUIRÚRGICO:")
        pdf.drawString(primer_elemento_izquierda, altura_bloque10 - 18, "PRINCIPAL: 1 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque10 - 34, "2 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque10 - 50, "3 ).")
        pdf.drawString(primer_elemento_izquierda, altura_bloque10 - 67, "4 ).")


        pdf.drawString(primer_elemento_izquierda+ 384, altura_bloque10 - 3, "DÍA")
        pdf.drawString(primer_elemento_izquierda+ 406, altura_bloque10 - 3, "MES")
        pdf.drawString(primer_elemento_izquierda+ 437, altura_bloque10 - 3, "AÑO")

        pdf.drawString(primer_elemento_izquierda + 500, altura_bloque10 - 3, "CÓDIGO")

        #BLOQUE 11 CONDICION DE EGRESO
        altura_bloque11 = altura_bloque10 - 86

        pdf.drawString(primer_elemento_izquierda+11, altura_bloque11, "CONDICIÓN DE EGRESO:")
        pdf.drawString(primer_elemento_izquierda+168, altura_bloque11, "RAZÓN DE EGRESO:")
        pdf.drawString(primer_elemento_izquierda+335, altura_bloque11, "REFERIDO A:")
        pdf.drawString(primer_elemento_izquierda+515, altura_bloque11, "AUTOPSIA")
        pdf.drawString(primer_elemento_izquierda+513, altura_bloque11 -12, "SI")
        pdf.drawString(primer_elemento_izquierda+546, altura_bloque11 -12, "NO")

        pdf.setFont("Helvetica", 5.5)
        pdf.drawString(primer_elemento_izquierda+53, altura_bloque11 - 9, "1. IGUAL CONDICIÓN")
        pdf.drawString(primer_elemento_izquierda+53, altura_bloque11 - 16, "2. MEJORADO")
        pdf.drawString(primer_elemento_izquierda+53, altura_bloque11 - 23, "3. CURADO")
        pdf.drawString(primer_elemento_izquierda+115, altura_bloque11 - 9, "4. FALLECIDO")

        pdf.drawString(primer_elemento_izquierda+210, altura_bloque11 - 9,  "1. ALTA MÉDICA")
        pdf.drawString(primer_elemento_izquierda+210, altura_bloque11 - 16, "2. ALTA EXIGIDA")
        pdf.drawString(primer_elemento_izquierda+210, altura_bloque11 - 23, "3. FUGA")
        pdf.drawString(primer_elemento_izquierda+270, altura_bloque11 - 9,  "4. REFERIDO")
        pdf.drawString(primer_elemento_izquierda+270, altura_bloque11 - 16, "5. FALLECIDO")

        #BLOQUE 12 PARTO O ABORTO
        altura_bloque12 = altura_bloque11 - 35
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(ancho /2, altura_bloque12, "PARTO O ABORTO")
        pdf.drawString(primer_elemento_izquierda, altura_bloque12-14, "PERSONAL QUE ATENDIO EL PARTO:")
        pdf.drawString(primer_elemento_izquierda + 375,  altura_bloque12-11, "DATOS DEL PRODUCTO DEL EMBARAZO:")
        
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(primer_elemento_izquierda + 5, altura_bloque12 - 27, "(   )")
        pdf.drawString(primer_elemento_izquierda + 5, altura_bloque12 - 37, "(   )")
        pdf.drawString(primer_elemento_izquierda + 5, altura_bloque12 - 47, "(   )")

        pdf.drawString(primer_elemento_izquierda + 92, altura_bloque12 - 27, "(   )")
        pdf.drawString(primer_elemento_izquierda + 92, altura_bloque12 - 37, "(   )")
        pdf.drawString(primer_elemento_izquierda + 92, altura_bloque12 - 47, "(   )")
        pdf.drawString(primer_elemento_izquierda + 92, altura_bloque12 - 57, "(   )")


        pdf.drawString(primer_elemento_izquierda + 353, altura_bloque12 -29, "N°")
        pdf.drawString(primer_elemento_izquierda + 353, altura_bloque12 -46, "1")
        pdf.drawString(primer_elemento_izquierda + 353, altura_bloque12 -59, "2")
        pdf.drawString(primer_elemento_izquierda + 353, altura_bloque12 -72, "3")
        pdf.drawString(primer_elemento_izquierda + 353, altura_bloque12 -85, "4")

        pdf.setFont("Helvetica", 6.4)
        pdf.drawString(primer_elemento_izquierda + 22, altura_bloque12 -27, "ESTUDIANTE")
        pdf.drawString(primer_elemento_izquierda + 22, altura_bloque12 -37, "MÉDICO GENERAL")
        pdf.drawString(primer_elemento_izquierda + 22, altura_bloque12 -47, "RESIDENTE ")

        pdf.drawString(primer_elemento_izquierda + 109, altura_bloque12 -27, "MÉDICO ESPECIALISTA")
        pdf.drawString(primer_elemento_izquierda + 109, altura_bloque12 -37, "AUXILIAR DE ENFERMERÍA")
        pdf.drawString(primer_elemento_izquierda + 109, altura_bloque12 -47, "ENFERMERO PROFESIONAL")
        pdf.drawString(primer_elemento_izquierda + 109, altura_bloque12 -57, "EXTRAHOSPITALARIO")


        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -12, "NÚMERO DE EMBARAZO")
        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -20, "INCLUYENDO ESTE")

        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -34, "PERÍODO GESTACIONAL")
        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -42, "EN SEMANAS")

        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -60, "TOTAL NÚMERO DE CONSULTAS")
        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -68, "PRENATALES")

        pdf.drawString(primer_elemento_izquierda + 391, altura_bloque12 -22, "SEXO")
        pdf.drawString(primer_elemento_izquierda + 438.7, altura_bloque12 -22, "CONDICIÓN AL NACER")
        pdf.drawString(primer_elemento_izquierda + 370, altura_bloque12 -34, "HOMBRE")
        pdf.drawString(primer_elemento_izquierda + 410, altura_bloque12 -34, "MUJER")

        pdf.drawString(primer_elemento_izquierda + 448, altura_bloque12 -34, "VIVO")
        pdf.drawString(primer_elemento_izquierda + 478, altura_bloque12 -34, "MUERTO")


        pdf.drawString(primer_elemento_izquierda + 515, altura_bloque12 -24, "PESO AL NACER")
        pdf.drawString(primer_elemento_izquierda + 521, altura_bloque12 -32, "EN GRAMOS")

        pdf.setFont("Helvetica", 6.2)
        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -82, "CONSULTAS PRENATALES")
        pdf.drawString(primer_elemento_izquierda + 205, altura_bloque12 -89, "POR MÉDICO")

        #BLOQUE 13 firmas
        altura_bloque13 = altura_bloque12 - 108
        pdf.setFont("Helvetica", 8)
        pdf.drawString(primer_elemento_izquierda + 17, altura_bloque13, "FIRMA DEL RESPONSABLE DE LA SALA")
        pdf.drawString(primer_elemento_izquierda + 240, altura_bloque13, "FECHA DE LA FIRMA:")

        
        pdf.setLineWidth(.8)
        pdf.line(primer_elemento_izquierda, altura_bloque13+10, primer_elemento_izquierda+ 190, altura_bloque13+10)
        pdf.line(primer_elemento_izquierda + 325, altura_bloque13, primer_elemento_izquierda+ 405, altura_bloque13)


    @staticmethod
    def __dibujarDatosPacienteHojaHospitalizacion2026(pdf, ancho, alto, paciente):
        
        primer_elemento_izquierda = ReporteHospitalizacionService.MARGEN_IZQUIERDO

        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(primer_elemento_izquierda + 75, alto - 90,ReportePdfBaseService.texto_seguro(paciente.etnia,24))  
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(primer_elemento_izquierda + 485, alto - 80, formatear_expediente(paciente.expediente))  
        


        pdf.setFont("Helvetica-Bold", 13)
        altura_bloque1 = alto - 122
        pdf.drawCentredString(primer_elemento_izquierda + 67, altura_bloque1, ReportePdfBaseService.texto_seguro(paciente.apellido1, 20))
        pdf.drawCentredString(primer_elemento_izquierda + 210, altura_bloque1, ReportePdfBaseService.texto_seguro(paciente.apellido2, 20))
        pdf.drawCentredString(primer_elemento_izquierda + 366, altura_bloque1, ReportePdfBaseService.texto_seguro(paciente.nombres, 21))
        pdf.drawCentredString(primer_elemento_izquierda + 510, altura_bloque1, ReportePdfBaseService.texto_seguro(formatear_dni(paciente.dni), 15))
        
        altura_bloque2 = altura_bloque1 - 35
        dia_nac = f"{paciente.fecha_nacimiento.day:02d}" if paciente.fecha_nacimiento else ""
        mes_nac = f"{paciente.fecha_nacimiento.month:02d}" if paciente.fecha_nacimiento else ""
        anio_nac = f"{paciente.fecha_nacimiento.year}" if paciente.fecha_nacimiento else ""

        pdf.drawCentredString(primer_elemento_izquierda + 9, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(dia_nac, 2))
        pdf.drawCentredString(primer_elemento_izquierda + 33, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(mes_nac, 2))
        pdf.drawCentredString(primer_elemento_izquierda + 64, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(anio_nac, 4))

        pdf.drawCentredString(primer_elemento_izquierda + 116.5, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(paciente.edad_valor, 2))
        pdf.drawCentredString(primer_elemento_izquierda + 140, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(paciente.edad_tipo, 1))
        pdf.drawCentredString(primer_elemento_izquierda + 236, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(paciente.sexo, 1))

        pdf.drawCentredString(primer_elemento_izquierda + 331, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(paciente.estado_civil_id, 1))
        pdf.drawCentredString(primer_elemento_izquierda + 468, altura_bloque2 + 7, ReportePdfBaseService.texto_seguro(paciente.ocupacion_id, 1))


        altura_bloque3 = altura_bloque2 - 33

        pdf.drawCentredString(primer_elemento_izquierda + 63, altura_bloque3, ReportePdfBaseService.texto_seguro(paciente.departamento, 15))
        pdf.drawCentredString(primer_elemento_izquierda + 212, altura_bloque3, ReportePdfBaseService.texto_seguro(paciente.municipio , 20))
        pdf.drawCentredString(primer_elemento_izquierda + 390, altura_bloque3, ReportePdfBaseService.texto_seguro(paciente.direccion , 24)) 

        pdf.drawCentredString(primer_elemento_izquierda + 528, altura_bloque3, ReportePdfBaseService.texto_seguro(paciente.telefono, 9))

        return altura_bloque3


    @staticmethod
    def __dibujarDatosIngresoHojaHospitalizacion2026(pdf, ancho, alto,altura_bloque3, acompaniante, padres, ingreso, usuario_creacion):
        altura_bloque4 = altura_bloque3 - 40
        primer_elemento_izquierda = ReporteHospitalizacionService.MARGEN_IZQUIERDO
        pdf.setFont("Helvetica-Bold", 12)

        if ingreso.cama:
            pdf.rect(primer_elemento_izquierda+428, alto-43, 68, 14, stroke=1, fill=0)
            pdf.drawString(primer_elemento_izquierda + 430, alto - 40, f"CAMA: {ingreso.cama}")

        

        pdf.drawCentredString(primer_elemento_izquierda + 123 , altura_bloque4, ReportePdfBaseService.texto_seguro(acompaniante.nombre, 32))
        pdf.drawCentredString(primer_elemento_izquierda + 365 , altura_bloque4, ReportePdfBaseService.texto_seguro(acompaniante.direccion, 28))
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(primer_elemento_izquierda + 528 , altura_bloque4, ReportePdfBaseService.texto_seguro(acompaniante.telefono, 9))

        altura_bloque5 = altura_bloque4 - 31
        pdf.setFont("Helvetica", 8)
        pdf.drawString(primer_elemento_izquierda + 195 , altura_bloque5 + 16, ReportePdfBaseService.texto_seguro(padres.dni_padre, 15))
        pdf.drawString(primer_elemento_izquierda + 480 , altura_bloque5 + 16, ReportePdfBaseService.texto_seguro(padres.dni_madre, 15))

        pdf.setFont("Helvetica-Bold", 13)

        pdf.drawCentredString(primer_elemento_izquierda + 140 , altura_bloque5, ReportePdfBaseService.texto_seguro(padres.nombre_padre, 32))
        pdf.drawCentredString(primer_elemento_izquierda + 430 , altura_bloque5, ReportePdfBaseService.texto_seguro(padres.nombre_madre, 32))

        altura_bloque6 = altura_bloque5 - 33
        pdf.drawCentredString(primer_elemento_izquierda + 10 , altura_bloque6, ReportePdfBaseService.texto_seguro(ingreso.zona_codigo, 1))
        
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(primer_elemento_izquierda + 158 , altura_bloque6, ReportePdfBaseService.texto_seguro(ingreso.servicio, 20))

        pdf.drawCentredString(primer_elemento_izquierda + 314 , altura_bloque6, ReportePdfBaseService.texto_seguro(ingreso.sala, 20))
        
        
        fecha = ingreso.fecha_ingreso

        pdf.setFont("Helvetica-Bold", 13)

        if fecha:
            # -------- Fecha --------
            pdf.drawCentredString(primer_elemento_izquierda + 427, altura_bloque6, f"{fecha.day:02d}")
            pdf.drawCentredString(primer_elemento_izquierda + 451, altura_bloque6, f"{fecha.month:02d}")
            pdf.drawCentredString(primer_elemento_izquierda + 480, altura_bloque6, f"{fecha.year:04d}")

            # -------- Hora --------
            hora_12 = fecha.strftime("%I:%M")
            pdf.drawCentredString(primer_elemento_izquierda + 527, altura_bloque6, hora_12)

            # -------- Indicador AM / PM --------
            pdf.setFont("Helvetica-Bold", 10)

            es_am = fecha.hour < 12
            offset_y = 8 if es_am else -3

            pdf.drawCentredString(
                primer_elemento_izquierda + 553.5,
                altura_bloque6 + offset_y,
                "X"
            )

            pdf.setFont("Helvetica-Bold", 6.5)
            fecha_titulo = fecha.strftime("%d/%m/%y")  # dd/mm/yy
            pdf.drawString(primer_elemento_izquierda + 270, alto - 90, ReportePdfBaseService.texto_seguro(fecha_titulo,8))


        alto_texto = alto-762
        texto_izq = "CREADO -> "
        pdf.setFont("Courier", 7)
        pdf.drawString(ancho-150,alto_texto, texto_izq)
        pdf.setFont("Courier-Bold", 7)
        pdf.drawString(ancho-145 + pdf.stringWidth(texto_izq, "Courier", 7), alto_texto, ReportePdfBaseService.texto_seguro(f"{usuario_creacion.usuario_nick} {usuario_creacion.usuario_nombre}",20))
        

    @staticmethod
    def __dibujarPiePaginaFormatoHojaHospitalizacion2026(pdf, ancho, alto, usuario):
        updated_local = timezone.localtime(timezone.now())
        fecha = formatear_fecha(updated_local)
        user_info = f"{usuario.username} ({usuario.first_name} {usuario.last_name})"[:40]

        alto_texto = alto-779
        # --------- IZQUIERDA: FECHA ---------
        texto_izq = "IMPRESO EL -> "
        pdf.setFont("Courier", 7)
        pdf.drawString(40,alto_texto, texto_izq)
        
        pdf.setFont("Courier-Bold", 7)
        pdf.drawString(45 + pdf.stringWidth(texto_izq, "Courier", 7), alto_texto, fecha.upper())

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
    def __dibujarAutorizacionFormatoHojaHospitalizacion2026(pdf, ancho, alto, ingreso, paciente, padre, acompaniante):

        pdf.showPage()
        # TÍTULOS
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawCentredString(ancho / 2, alto - 50, "AUTORIZACIÓN")
        pdf.drawCentredString(ancho / 2, alto - 330, "SALIDA EXIGIDA")
        pdf.drawCentredString(ancho / 2, alto - 565, "AUTORIZACIÓN RETIRO DEL PACIENTE")

        # CONFIGURACIÓN PÁRRAFOS
        styles = getSampleStyleSheet()
        style = styles["Normal"]
        style.alignment = 4
        style.leading = 16

        inicioPagina2 = inch - 20
        ancho_max = 7 * inch
        altoP2 = alto

        def draw_paragraph(texto, y):
            p = Paragraph(texto, style)
            p.wrapOn(pdf, ancho_max, 100)
            p.drawOn(pdf, inicioPagina2, y)

        # PÁRRAFOS
        draw_paragraph(
            "Por la presente autorizo al personal médico del hospital para que, durante mi hospitalización, "
            "se me practiquen los procedimientos clínicos de gabinete, laboratorio, quirúrgicos o anatomopatológicos "
            "que sean útiles para el diagnóstico, tratamiento y recuperación de mi salud.",
            altoP2 - 110
        )

        draw_paragraph(
            "Del mismo modo autorizo a la institución para que se lleve a cabo los procedimientos completados "
            "en las leyes nacionales, que sean necesarias para el reconocimiento de mi enfermedad a fin de evitar "
            "riesgos de contagio y facilitar la protección futura a la salud de mis familiares y allegados.",
            altoP2 - 165
        )

        draw_paragraph(
            "Exonero de toda responsabilidad a los médicos tratantes, porque en contra de las indicaciones médicas "
            "he exigido la salida de mi ____________________________________________________ (PARENTESCO), quien se encuentra "
            "internado en este hospital. Al tomar tal actitud, asumo por completo la responsabilidad por los riesgos "
            "que me han sido advertidos.",
            altoP2 - 410
        )

        # FIRMA VOLUNTARIA
        pdf.setFont("Helvetica", 10.5)
        pdf.drawCentredString(
            ancho / 2,
            altoP2 - 190,
            "Firmo voluntariamente a los _________ días del mes de __________________________ del año 20_____"
        )

        # BLOQUE FIRMAS
        pdf.setFont("Helvetica", 10)

        def draw_firma(x, y_linea, label_offset, label):
            pdf.drawString(x, y_linea, "__________________________________________")
            pdf.drawString(x + label_offset, y_linea - 12, label)

        # Paciente
        draw_firma(inicioPagina2, altoP2 - 225, 80, "Nombre y apellidos")
        pdf.drawString(inicioPagina2 + 350, altoP2 - 225, "___________________________")
        pdf.drawString(inicioPagina2 + 410, altoP2 - 237, "Firma")

        # Testigo
        draw_firma(inicioPagina2, altoP2 - 270, 105, "Testigo")
        pdf.drawString(inicioPagina2 + 350, altoP2 - 270, "___________________________")
        pdf.drawString(inicioPagina2 + 410, altoP2 - 283, "Firma")

        # INFORMACIÓN ADICIONAL
        pdf.setFont("Helvetica", 10.5)

        pdf.drawCentredString(ancho / 2, altoP2 - 430,
            "Nombre: _________________________________________________________  DNI __________________")

        pdf.drawCentredString(ancho / 2, altoP2 - 460,
            "Fecha: _______________________________________                      Firma: _________________________")

        pdf.drawCentredString(ancho / 2, altoP2 - 490,
            "Testigo: ___________________________________  Firma: ________________  DNI __________________")

        pdf.drawCentredString(ancho / 2, alto - 595,
            "Yo, _____________________________________________  DNI __________________  Domicilio Exacto:")

        pdf.drawCentredString(ancho / 2, alto - 620,
            "_____________________________________________________________________________________")

        pdf.drawCentredString(ancho / 2, alto - 650,
            "He retirado en esta fecha a mi ________________________________________  (relación con el paciente)")

        pdf.drawCentredString(ancho / 2, alto - 680,
            "Del servicio de _____________________________________  con la autorización médica correspondiente.")

        pdf.drawCentredString(ancho / 2, altoP2 - 730,
            "Fecha: _________________________                Firma: _________________________")


        # DATOS DINÁMICOS
        pdf.setFont("Helvetica-Bold", 12)

        fecha = ingreso.fecha_ingreso
        if fecha:
            pdf.drawString(ancho - 405, altoP2 - 187, f"{fecha.day:02d}")
            pdf.drawString(ancho - 240, altoP2 - 187, mes_nombre(f"{fecha.month:02d}", upper=True))
            pdf.drawString(ancho - 80, altoP2 - 187, f"{fecha.year % 100:02d}")

        nombre_completo = f"{paciente.nombres} {paciente.apellido1} {paciente.apellido2 or ''}".strip()

        if paciente.tipo_identificacion in [3, 4]:
            pdf.drawString(inicioPagina2, altoP2 - 265, (padre.nombre_madre or ""))
        else:
            pdf.drawString(inicioPagina2, altoP2 - 220, nombre_completo)
            pdf.drawString(inicioPagina2, altoP2 - 265, (acompaniante.nombre or ""))


    @staticmethod
    def __dibujar_encabezado_epicrisis(pdf, ancho, y):
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawCentredString(ancho / 2, y, "FUNDACIÓN GESTORA DE LA SALUD")
        pdf.drawCentredString(ancho / 2, y-11, "HOSPITAL DR. ENRIQUE AGUILAR CERRATO")
        pdf.drawCentredString(ancho / 2, y-22, "INTIBUCÁ, INTIBUCÁ, HONDURAS, C.A.")
        pdf.drawCentredString(ancho / 2, y-33, "(504) 2783-0242 / 2783-1939")
        pdf.drawCentredString(ancho / 2, y-44, "fundagesheac@gmail.com")

        # Logos
        logo1 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_sesal.jpg')
        logo2 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_gobierno.jpg')
        logo3 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_FUNDAGES.jpg')


        pdf.drawImage(logo1, x=85, y=y-45, width=65, height=45, preserveAspectRatio=True, mask='auto')
        pdf.drawImage(logo2, x=ancho-175, y=y-50, width=80, height=55, preserveAspectRatio=True, mask='auto')
        pdf.drawImage(logo3, x=ancho-115, y=y-50, width=80, height=55, preserveAspectRatio=True, mask='auto')

    @staticmethod
    def __dibujarEpicrisisFormatoHojaHospitalizacion2026(pdf, ancho, alto, paciente, ingreso):
        pdf.showPage()
        ReporteHospitalizacionService.__dibujar_encabezado_epicrisis(pdf, ancho, 755)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawCentredString(ancho / 2, alto - 110, "HC-16 EPICRISIS")

        pdf.rect(ancho-130, alto-110, 95, 14, stroke=1, fill=0)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(ancho-128,alto-106,"AX-GC-INT-NQ-010 D")

        # Dibujar el rectángulo con esquinas redondeadas
        pdf.roundRect(40, 20, 550, 750, radius=80, stroke=1, fill=0)

        # Genera la tabla vacía
        datos2 = [[""] * 42 for _ in range(42)]  # 63 filas, 34 columnas

        # Ancho de columnas (coincide con las 34 columnas)
        colWidths2 = [13] * 42

        # Alto de filas (debe haber 63 valores)
        rowHeights2 = [
        10, 20, 8,      # BLOQUE 1
        27,             # BLOQUE 2
        13, 20, 5,     # BLOQUE 3
        *([14] * 31),   # 31 filas iguales de altura 14
        15,             # Separador
        12, 12, 12      # Final
        ]

        # Crear tabla
        tabla2 = Table(datos2, colWidths=colWidths2, rowHeights=rowHeights2)

        estilo2 = TableStyle([
        #quitamos el borde de la tabla
        ('GRID', (0, 0), (-1, -1), .1, colors.Color(1, 1, 1)),
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),                # Fuente para toda la tabla
        ('FONTSIZE', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centra el texto horizontalmente
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), 


        #bordes externos
        ('LINEABOVE', (0, 0), (41, 0), 0.1, colors.black),     # borde superior
        ('LINEBELOW', (0, 41), (41, 41), 0.1, colors.black),   # borde inferior
        ('LINEBEFORE', (0, 0), (0, 41), 0.1, colors.black),    # borde izquierdo
        ('LINEAFTER', (41, 0), (41, 41), 0.1, colors.black),   # borde derecho


        #bordes externos bloque 1
        ('LINEAFTER', (22, 0), (22, 2), .1, colors.black), 
        ('LINEAFTER', (25, 0), (25, 2), .1, colors.black), 
        ('LINEAFTER', (32, 0), (32, 2), .1, colors.black), 
        ('LINEBELOW', (0, 2), (42, 2), .1, colors.black),
        #lineas internas 
        ('SPAN', (31, 1), (31, 1)),
        ('GRID', (31, 1), (31, 1), .8, colors.black),  


        #bordes externos bloque 2
        ('LINEBELOW', (0, 3), (42, 3), .1, colors.black),
        ('LINEAFTER', (15, 3), (15, 3), .1, colors.black), 
        ('LINEAFTER', (33, 3), (33, 3), .1, colors.black), 

        #bordes externos bloque 3
        ('LINEBELOW', (0, 6), (42, 6), .1, colors.black),
        ('LINEAFTER', (15, 4), (15, 6), .1, colors.black),
        ('LINEAFTER', (28, 4), (28, 6), .1, colors.black),
        #cuadrad
        ('SPAN', (1, 5), (3, 5)),
        ('GRID', (1, 5), (3, 5), .8, colors.black),  
        

        ('LINEBELOW', (9, 7), (40, 7), .1, colors.black), #LINEA DIAGNOPSTICO INGRESO
        ('LINEBELOW', (1, 8), (40, 8), .1, colors.black),

        ('LINEBELOW', (12, 10), (40, 10), .1, colors.black),# RESUMEN DE HISOTIRA CLINDA
        ('LINEBELOW', (1, 11), (40, 11), .1, colors.black),
        ('LINEBELOW', (1, 12), (40, 12), .1, colors.black),
        ('LINEBELOW', (1, 13), (40, 13), .1, colors.black),
        ('LINEBELOW', (1, 14), (40, 14), .1, colors.black),
        ('LINEBELOW', (1, 15), (40, 15), .1, colors.black),
        ('LINEBELOW', (1, 16), (40, 16), .1, colors.black),
        ('LINEBELOW', (1, 17), (40, 17), .1, colors.black),
        ('LINEBELOW', (1, 18), (40, 18), .1, colors.black),
        ('LINEBELOW', (1, 19), (40, 19), .1, colors.black),

        ('LINEBELOW', (5, 21), (40, 21), .1, colors.black),#EXAMENES
        ('LINEBELOW', (1, 22), (40, 22), .1, colors.black),

        ('LINEBELOW', (6, 24), (40, 24), .1, colors.black),#TRATAMIENTO
        ('LINEBELOW', (1, 25), (40, 25), .1, colors.black),
        ('LINEBELOW', (1, 26), (40, 26), .1, colors.black),
        ('LINEBELOW', (1, 27), (40, 27), .1, colors.black),
        
        ('LINEBELOW', (10, 29), (40, 29), .1, colors.black),#DIAGNOSTICO
        ('LINEBELOW', (1, 30), (40, 30), .1, colors.black),
        ('LINEBELOW', (1, 31), (40, 31), .1, colors.black),

        ('LINEBELOW', (8, 33), (40, 33), .1, colors.black),
        ('LINEBELOW', (1, 34), (40, 34), .1, colors.black),
        ('LINEBELOW', (1, 35), (40, 35), .1, colors.black),
        ('LINEBELOW', (1, 36), (40, 36), .1, colors.black),

        ('LINEBELOW', (0, 37), (41, 37), .1, colors.black),

        ('SPAN', (3, 39), (4, 40)),
        ('GRID', (3, 39), (4, 40), .8, colors.black), 

        ('SPAN', (15, 39), (16, 40)),
        ('GRID', (15, 39), (16, 40), .8, colors.black), 

        ('SPAN', (29, 39), (30, 40)),
        ('GRID', (29, 39), (30, 40), .8, colors.black), 
    ])

        tabla2.setStyle(estilo2)
        tabla2.wrapOn(pdf, 0,0)
        alturaTabla = 85
        tabla2.drawOn(pdf, 42, 85)

        pdf.drawString(50,alto-alturaTabla-45,"1er APELLIDO")
        pdf.drawString(130,alto-alturaTabla-45,"2do APELLIDO")
        pdf.drawString(250,alto-alturaTabla-45,"NOMBRES")
        pdf.drawString(348,alto-alturaTabla-45,"EDAD")
        pdf.drawString(385,alto-alturaTabla-45,"SEXO")
        
        pdf.drawString(482,alto-alturaTabla-45,"No. HISTORIA CLINICA")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(385,alto-alturaTabla-57,"1.  HOMBRE")
        pdf.drawString(385,alto-alturaTabla-67,"2.  MUJER")
        
        #texto bloque2
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(50,alto-alturaTabla-83,"SERVICIO")
        pdf.drawString(255,alto-alturaTabla-83,"SALA")
        pdf.drawString(486,alto-alturaTabla-83,"CAMA")

        #TEXTO bloque3
        pdf.drawString(50,alto-alturaTabla-109,"INGRESADO POR:")
        pdf.drawString(255,alto-alturaTabla-109,"FECHA INGRESO")
        pdf.drawString(424,alto-alturaTabla-109,"FECHA EGRESO")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(150,alto-alturaTabla-109,"1.  CONSULTA EXT")
        pdf.drawString(150,alto-alturaTabla-120,"2.  EMERGENCIA")
        pdf.drawString(150,alto-alturaTabla-131,"3.  NACIMIENTO")

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(255,alto-alturaTabla-134,"DIA")
        pdf.drawString(305,alto-alturaTabla-134,"MES")
        pdf.drawString(355,alto-alturaTabla-134,"AÑO")

        pdf.drawString(424,alto-alturaTabla-134,"DIA")
        pdf.drawString(474,alto-alturaTabla-134,"MES")
        pdf.drawString(524,alto-alturaTabla-134,"AÑO")

        pdf.drawString(50,alto-alturaTabla-150,"DIAGNOSTICO INGRESO:")
        pdf.drawString(50,alto-alturaTabla-191,"RESUMEN DE HISTORIA CLINICA:")
        pdf.drawString(50,alto-alturaTabla-345,"EXAMENES:")
        pdf.drawString(50,alto-alturaTabla-387,"TRATAMIENTO:")
        pdf.drawString(50,alto-alturaTabla-458,"DIAGNÓSTICO DE FINALES:")
        pdf.drawString(50,alto-alturaTabla-514,"RECOMENDACIONES:")

        #BLOQUE FINAL
        pdf.drawString(50,alto-alturaTabla-582,"CONDICIONES DE EGRESO:")
        pdf.drawString(205,alto-alturaTabla-582,"RAZÓN DE EGRESO:")
        pdf.drawString(380,alto-alturaTabla-582,"DESTINO DEL ALTA:")

        #OPCIONES
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(115,alto-alturaTabla-592,"1.  IGUAL CONDICIÓN")
        pdf.drawString(115,alto-alturaTabla-601,"2.  MEJORADO")
        pdf.drawString(115,alto-alturaTabla-610,"3.  CURADO")
        pdf.drawString(115,alto-alturaTabla-619,"4.  FALLECIDO")

        pdf.drawString(305,alto-alturaTabla-582,"1.  ALTA MÉDICA")
        pdf.drawString(305,alto-alturaTabla-591,"2.  ALTA EXIGIDA")
        pdf.drawString(305,alto-alturaTabla-600,"3.  FUGA")
        pdf.drawString(305,alto-alturaTabla-609,"4.  REFERIDO")
        pdf.drawString(305,alto-alturaTabla-618,"5.  FALLECIDO")

        pdf.setFont("Helvetica-Bold", 6.5)

        pdf.drawString(475,alto-alturaTabla-580,"1.  A SU CASA")
        pdf.drawString(475,alto-alturaTabla-589,"2.  ATENCIÓN PRIMARIA EN SALUD")
        pdf.drawString(475,alto-alturaTabla-598,"3.  CONSULTA ESPECIALIZADA")
        pdf.drawString(475,alto-alturaTabla-607,"4.  MORGUE")
        pdf.drawString(475,alto-alturaTabla-616,"5.  INSTITUCIÓN NO SANITARIA")

        #BLOQUE FINAL FIRMAS
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(ancho / 2, alto-alturaTabla-666, "FIRMA Y CLAVE DE MÉDICO:_______________________________________________")


        #-------  DATOS DINAMICOS 
        pdf.setFont("Helvetica-Bold", 11)

        pdf.drawString(235,alto-alturaTabla-65, ReportePdfBaseService.texto_seguro(paciente.nombres, 18))
        pdf.drawString(50,alto-alturaTabla-65, ReportePdfBaseService.texto_seguro(paciente.apellido1,10))
        pdf.drawString(130,alto-alturaTabla-65, ReportePdfBaseService.texto_seguro(paciente.apellido2,10))

        #----- MAPEAR LA EDAD
        if paciente.edad_tipo:
            if paciente.edad_tipo == "4":
                medida = "AÑOS"
            elif paciente.edad_tipo == "3":
                medida = "MESES"
            elif paciente.edad_tipo == "2":
                medida = "DIAS"
            elif paciente.edad_tipo == "1":
                medida = "HORAS"

        pdf.drawString(354,alto-alturaTabla-59, paciente.edad_valor)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(349,alto-alturaTabla-70, medida)
        
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(448,alto-alturaTabla-60, paciente.sexo)
        
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(480,alto-alturaTabla-58, paciente.expediente)
        pdf.drawString(480,alto-alturaTabla-69, formatear_dni(paciente.dni))
        
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(60,alto-alturaTabla-95, ingreso.servicio)
        pdf.drawString(265,alto-alturaTabla-95, ingreso.sala)
        pdf.drawString(496,alto-alturaTabla-95, f"# {ingreso.cama}")
    
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(70,alto-alturaTabla-127, str(ingreso.zona_codigo))
        
        fecha = ingreso.fecha_ingreso
        if fecha:
            pdf.drawString(275,alto-alturaTabla-130, f"{fecha.day:02d}")
            pdf.drawString(330,alto-alturaTabla-130, f"{fecha.month:02d}")
            pdf.drawString(380,alto-alturaTabla-130, f"{fecha.year:04d}")


    @staticmethod
    def GenerarFormatoHojaHospitalizacion2026(data, usuario):
        try:
            if not data:
                log_warning(
                    f"Intento de generar hoja hospitalización sin data ",
                    app=LogApp.REPORTES
                )
                raise ValueError("No hay datos para generar hoja hospitalización")
            # 1. NORMALIZAR DATA
            paciente = SimpleNamespace(**data["paciente"])
            padres = SimpleNamespace(**data["padres"])
            acompaniante = SimpleNamespace(**data["acompaniante"])
            ingreso = SimpleNamespace(**data["ingreso"])
            usuario_creacion =  SimpleNamespace(**data["usuario"])
            institucion =  SimpleNamespace(**data["institucion"])


            # 2. CONFIGURACIÓN DOCUMENTO
            nombre_paciente = f"{paciente.nombres} {paciente.apellido1}".strip().replace(" ", "_") 
            fecha_str = ingreso.fecha_ingreso.strftime("%Y%m%d_%H%M")
            nombre_archivo = f"reporte_ingreso_{nombre_paciente}_{fecha_str}.pdf"
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'

            pdf = canvas.Canvas(response, pagesize=letter)
            pdf.setTitle(f"Hoja de Hospitalizacion- {nombre_paciente}")
            ancho, alto = letter


            # 3. DIBUJO DOCUMENTO
            #pagina 1 
            ReporteHospitalizacionService.__dibujarEstructuraHojaHospitalizacion2026(pdf,ancho,alto)
            ReporteHospitalizacionService.__dibujarEtiquetasEstaticasHojaHospitalizacion2026(pdf,ancho,alto)
            altura_bloque3 = ReporteHospitalizacionService.__dibujarDatosPacienteHojaHospitalizacion2026(pdf,ancho,alto,paciente)
            
            ReporteHospitalizacionService.__dibujarDatosIngresoHojaHospitalizacion2026(pdf,ancho,alto,altura_bloque3,acompaniante,padres,ingreso,usuario_creacion)
            ReporteHospitalizacionService.__dibujarPiePaginaFormatoHojaHospitalizacion2026(pdf, ancho, alto, usuario)
            #PAGINA2
            ReporteHospitalizacionService.__dibujarAutorizacionFormatoHojaHospitalizacion2026(pdf, ancho, alto, ingreso, paciente, padres, acompaniante)
            ReporteHospitalizacionService.__dibujarPiePaginaFormatoHojaHospitalizacion2026(pdf, ancho, alto, usuario)
            #pagina 3
            ReporteHospitalizacionService.__dibujarEpicrisisFormatoHojaHospitalizacion2026(pdf, ancho, alto, paciente, ingreso)
            ReporteHospitalizacionService.__dibujarPiePaginaFormatoHojaHospitalizacion2026(pdf, ancho, alto, usuario)

            #pagina 4 referencia
            pdf.showPage()
            ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto, None)

            ReporteReferenciaService._dibujarEstructuraFormatoReferenciaRespuesta(pdf,ancho,alto)
            ReporteReferenciaService._dibujarEtiquetasEstaticasFormatoRefenciaRespuesta(pdf,ancho,alto)
            ReporteReferenciaService._dibujarDatosHospitalizacion(pdf,ancho,alto, paciente, institucion)
            ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)
            #pagina 5
            pdf.showPage()
            ReportePdfBaseService.dibujar_borde_pagina(pdf, ancho, alto, 2)
            ReporteReferenciaService._dibujarEstructuraPagina2FormatoReferenciaRespuesta(pdf,ancho,alto)
            ReporteReferenciaService._dibujarPiePaginaFormatoReferenciaRespuesta(pdf, ancho, alto, usuario)
            ReporteReferenciaService._dibujarDatosPagina2FormatoReferencia(pdf, ancho, alto, institucion, True)

            # Finalizar el PDF
            pdf.save()
            return response
        except ValueError:
            raise

        except Exception:
            log_error(
                f"Error generando hoja hospitalización",
                app=LogApp.REPORTES
            )
            raise
    
