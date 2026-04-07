
from reportlab.lib import colors
from django.utils.translation import gettext as _
from django.conf import settings
import os 
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from reportlab.platypus.flowables import Flowable

class ReportePdfBaseService:

    @staticmethod
    def dibujar_encabezado(pdf, ancho, y):
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 9)
        pdf.drawCentredString(ancho / 2, y, "FUNDACIÓN GESTORA DE LA SALUD")
        pdf.drawCentredString(ancho / 2, y-11, "HOSPITAL DR. ENRIQUE AGUILAR CERRATO")
        pdf.drawCentredString(ancho / 2, y-22, "INTIBUCÁ, INTIBUCÁ, HONDURAS, C.A.")
        pdf.drawCentredString(ancho / 2, y-33, "(504) 2783-0242 / 2783-1939")
        pdf.drawCentredString(ancho / 2, y-44, "fundagesheac@gmail.com")

        # Logos
        logo1 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_sesal.jpg')
        logo2 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_gobierno.jpg')
        logo3 = os.path.join(settings.BASE_DIR, 'core/static/core/img/logo_FUNDAGES.jpg')
        aside = os.path.join(settings.BASE_DIR, 'core/static/core/img/aside_azul.jpg')

        try:
            pdf.drawImage(aside, x=0, y=-55, width=105, height=900, preserveAspectRatio=True, mask='auto')
            pdf.drawImage(logo1, x=60, y=y-45, width=75, height=55, preserveAspectRatio=True, mask='auto')
            pdf.drawImage(logo2, x=ancho-175, y=y-50, width=90, height=65, preserveAspectRatio=True, mask='auto')
            pdf.drawImage(logo3, x=ancho-105, y=y-50, width=90, height=65, preserveAspectRatio=True, mask='auto')
        except Exception:
            log_warning(
                "No se pudo cargar logo en encabezado PDF",
                app=LogApp.REPORTE
            )

    @staticmethod
    def dibujar_pie_pagina_carta(pdf, alto, ancho, fecha, usuario, usuario_nombre, pagina_actual, total_paginas):
        y = alto - 750  
        pdf.setFillColor(colors.black)
        

        fecha = fecha[:40]
        user_info = f"{usuario} ({usuario_nombre})"[:40]

        # --------- IZQUIERDA: FECHA ---------
        texto_izq = "IMPRESO EL -> "
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, y, texto_izq)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(40 + pdf.stringWidth(texto_izq, "Helvetica", 7), y, fecha.upper())
        
        # --------- DERECHA: USUARIO ---------
        texto_der = "POR -> "
        ancho_texto_der = pdf.stringWidth(texto_der, "Helvetica", 7)
        ancho_user_info = pdf.stringWidth(user_info, "Helvetica-Bold", 7)

        x_derecha = ancho - 40 - ancho_texto_der - ancho_user_info
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x_derecha, y, texto_der)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x_derecha + ancho_texto_der, y, user_info)

        # --------- CENTRO: PÁGINA ---------
        pagina_str_normal = "Página "
        pagina_str_bold = f"{pagina_actual:02d} de {total_paginas:02d}"

        x_centro = (ancho / 2) - (pdf.stringWidth(pagina_str_normal + pagina_str_bold, "Helvetica", 7) / 2)
        
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x_centro, y - 15, pagina_str_normal)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x_centro + pdf.stringWidth(pagina_str_normal, "Helvetica", 7), y - 15, pagina_str_bold)

        try:
            watermark = os.path.join(settings.BASE_DIR, 'core/static/core/img/SIWIFINAL.png')

            pdf.saveState()                
            pdf.setFillAlpha(0.08)         # Opacidad suave 
            
            # Centramos la marca de agua
            pdf.translate(265, 40)  
        
            pdf.drawImage(
                watermark,
                x=0, y=0,            
                width=80, height=80,     
                preserveAspectRatio=True,
                mask='auto'
            )

            pdf.restoreState()             
        except Exception as e:
            log_warning(
                "Error dibujando marca de agua en PDF",
                app=LogApp.REPORTE
            )


    @staticmethod
    def dibujar_pie_pagina_legal_horizontal(pdf, alto, ancho, fecha, usuario, usuario_nombre, pagina_actual, total_paginas):
        """
        Dibuja el pie de página en una posición fija desde el borde inferior.
        """
        # Se define la posición 'y' a 40 puntos desde la parte inferior de la página.
        y = 40
        
        pdf.setFillColor(colors.black)

        fecha_formato = fecha[:40]
        user_info = f"{usuario} ({usuario_nombre})"[:40]

        # --------- IZQUIERDA: FECHA ---------
        texto_izq = "IMPRESO EL -> "
        pdf.setFont("Helvetica", 7)
        pdf.drawString(40, y, texto_izq)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(40 + pdf.stringWidth(texto_izq, "Helvetica", 7), y, fecha_formato.upper())
        
        # --------- DERECHA: USUARIO ---------
        texto_der = "POR -> "
        ancho_texto_der = pdf.stringWidth(texto_der, "Helvetica", 7)
        ancho_user_info = pdf.stringWidth(user_info, "Helvetica-Bold", 7)

        x_derecha = ancho - 40 - ancho_texto_der - ancho_user_info
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x_derecha, y, texto_der)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x_derecha + ancho_texto_der, y, user_info)

        # --------- CENTRO: PÁGINA ---------
        pagina_str_normal = "Página "
        pagina_str_bold = f"{pagina_actual:02d} de {total_paginas:02d}"

        x_centro = (ancho / 2) - (pdf.stringWidth(pagina_str_normal + pagina_str_bold, "Helvetica", 7) / 2)
        
        pdf.setFont("Helvetica", 7)
        pdf.drawString(x_centro, y +5, pagina_str_normal)

        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x_centro + pdf.stringWidth(pagina_str_normal, "Helvetica", 7), y + 5, pagina_str_bold)   



    @staticmethod
    def dibujar_borde_pagina(pdf, ancho, alto, pagina=None, radius=8):
        """
        Dibuja un borde redondeado para el PDF.

        :param pdf: Canvas de ReportLab
        :param ancho: Ancho total de página
        :param alto: Alto total de página
        :param pagina: Si es página interna o primera
        :param radius: Radio de las esquinas
        """

        if not pagina:
            x, ancho_marco = 25, ancho - 20 * 2
            y, alto_marco = 23, alto - 19 * 2
        else:
            x, ancho_marco = 28, ancho - 30 * 2
            y, alto_marco = 27, alto - 29 * 2

        pdf.setFillColorRGB(0, 0, 0)
        pdf.roundRect(x, y, ancho_marco, alto_marco, radius=radius, stroke=1, fill=0)

    @staticmethod
    def texto_seguro(valor, max_len):
        if valor is None:
            return ""
        try:
            return str(valor).strip().upper()[:max_len]
        except Exception:
            return ""
    

class VerticalText(Flowable):
    """Rotates a text in a table cell."""
    def __init__(self, text):
        Flowable.__init__(self)
        self.text = text

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.rotate(90)
        fs = canvas._fontsize
        canvas.translate(1, -fs/1.2)
        canvas.drawString(0, 0, self.text)
        canvas.restoreState()

    def wrap(self, aW, aH):
        canv = self.canv
        fn, fs = canv._fontname, canv._fontsize
        return canv._leading, 1 + canv.stringWidth(self.text, fn, fs)