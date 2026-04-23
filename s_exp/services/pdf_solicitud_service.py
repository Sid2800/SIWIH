"""
Generador de PDF para una Solicitud de Préstamo de Expedientes.
Encabezado (2cm arriba) + Pie (2cm abajo) + contenido + tabla + firmas.
"""
import os
from io import BytesIO
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle,
    Spacer, KeepTogether,
)

from usuario.models import PerfilUnidad


IMG_DIR = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'img')
IMG_GOB_SESAL = os.path.join(IMG_DIR, 'GOB_SESAL_COLOR.png')
IMG_HEAC = os.path.join(IMG_DIR, 'logo_HEAC.png')
IMG_FUNDAGES = os.path.join(IMG_DIR, 'logo_FUNDAGES2.png')
IMG_SIWIH = os.path.join(IMG_DIR, 'SIWIFINAL_3.png')


class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas que pinta 'Página X de Y' tras conocer el total de páginas."""

    def __init__(self, *args, draw_footer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []
        self._draw_footer = draw_footer

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            if self._draw_footer:
                self._draw_footer(self, total)
            super().showPage()
        super().save()


def _unidad_usuario(user):
    perfil = PerfilUnidad.objects.filter(usuario=user).select_related('servicio_unidad').first()
    if perfil and perfil.servicio_unidad:
        return perfil.servicio_unidad.nombre_unidad
    return ''


def _fmt_fecha(dt, con_hora=True):
    if not dt:
        return ''
    if con_hora:
        return dt.strftime('%d/%m/%Y %H:%M')
    return dt.strftime('%d/%m/%Y')


def _calcular_fecha_entrega(solicitud, ahora):
    """Calcula fecha de entrega prevista según el Prestamo asociado."""
    try:
        p = solicitud.prestamo
    except Exception:
        return None
    if p.fecha_limite:
        return p.fecha_limite
    # Aún no se ha marcado entregado: simular basado en 'ahora'
    if p.es_minutos:
        return ahora + timedelta(minutes=p.tiempo_limite_horas)
    return ahora + timedelta(hours=p.tiempo_limite_horas)


def _header_footer_factory(solicitud, fecha_impresion, con_hora_footer):
    """Devuelve callbacks onPage (header) y draw_footer para el canvas."""

    def dibujar_header(canvas_obj, doc):
        canvas_obj.saveState()
        ancho, alto = doc.pagesize
        y_top = alto - 0.5 * cm  # 0.5 cm desde arriba

        # GOB_SESAL a la izquierda (reducido: 6 cm ancho x 1.5 cm alto)
        try:
            canvas_obj.drawImage(
                IMG_GOB_SESAL, 0.5 * cm, y_top - 1.5 * cm,
                width=6 * cm, height=1.5 * cm, preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

        # Texto centrado (Times-Bold)
        canvas_obj.setFont('Times-Bold', 11)
        canvas_obj.drawCentredString(
            ancho / 2, y_top - 0.75 * cm,
            'FUNDAGES - HOSPITAL DR. ENRIQUE AGUILAR CERRATO'
        )

        # Logos a la derecha: HEAC y FUNDAGES2 - más abajo
        try:
            canvas_obj.drawImage(
                IMG_HEAC, ancho - 5 * cm, y_top - 0.8 * cm,
                width=2.2 * cm, height=2.2 * cm, preserveAspectRatio=True, mask='auto'
            )
            canvas_obj.drawImage(
                IMG_FUNDAGES, ancho - 2.5 * cm, y_top - 0.8 * cm,
                width=2.2 * cm, height=2.2 * cm, preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

        # Línea separadora bajo el encabezado
        canvas_obj.setStrokeColor(colors.HexColor('#008b8b'))
        canvas_obj.setLineWidth(0.7)
        canvas_obj.line(0.5 * cm, y_top - 1.8 * cm, ancho - 0.5 * cm, y_top - 1.8 * cm)

        canvas_obj.restoreState()

    def dibujar_footer(canvas_obj, total_pages):
        canvas_obj.saveState()
        ancho, alto = canvas_obj._pagesize
        y_bot = 1.2 * cm  # más abajo

        # Línea superior del pie
        canvas_obj.setStrokeColor(colors.HexColor('#008b8b'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(1.5 * cm, y_bot + 0.6 * cm, ancho - 1.5 * cm, y_bot + 0.6 * cm)

        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.black)

        # Izquierda: fecha impresión
        fecha_str = _fmt_fecha(fecha_impresion, con_hora=con_hora_footer)
        canvas_obj.drawString(1.5 * cm, y_bot, f'Impreso: {fecha_str}')

        # Centro: página X de Y
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawCentredString(ancho / 2, y_bot, f'Página {page_num} de {total_pages}')

        # Derecha: SIWIH + logo
        try:
            canvas_obj.drawImage(
                IMG_SIWIH, ancho - 3.3 * cm, y_bot - 0.1 * cm,
                width=1.3 * cm, height=0.9 * cm, preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass
        canvas_obj.setFont('Helvetica-Bold', 8)
        canvas_obj.drawRightString(ancho - 3.5 * cm, y_bot, 'SIWIH')

        canvas_obj.restoreState()

    return dibujar_header, dibujar_footer


def generar_pdf_solicitud(solicitud):
    """
    Genera el PDF de la solicitud y retorna bytes.
    solicitud: instancia de SolicitudPrestamo
    """
    ahora = timezone.now()
    # Si ya fue entregado: pie sin hora
    try:
        p = solicitud.prestamo
        ya_entregado = bool(p.fecha_entrega)
    except Exception:
        ya_entregado = False
    con_hora_footer = not ya_entregado

    page_size = landscape(LETTER)
    ancho_pg, alto_pg = page_size

    # Márgenes: top 3cm, bottom 2.5cm
    margen_top = 3 * cm
    margen_bot = 2.5 * cm
    margen_lat = 1.5 * cm

    buf = BytesIO()

    doc = BaseDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margen_lat, rightMargin=margen_lat,
        topMargin=margen_top, bottomMargin=margen_bot,
        title=f'Solicitud #{solicitud.id}',
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id='contenido'
    )

    draw_header, draw_footer = _header_footer_factory(solicitud, ahora, con_hora_footer)
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=draw_header)])

    # =========================================================
    # Estilos
    # =========================================================
    styles = getSampleStyleSheet()
    st_titulo = ParagraphStyle('titulo', parent=styles['Title'],
                               fontName='Times-Bold', fontSize=16,
                               alignment=TA_CENTER, spaceAfter=6)
    st_dato_lbl = ParagraphStyle('dato_lbl', parent=styles['Normal'],
                                  fontName='Helvetica-Bold', fontSize=10,
                                  textColor=colors.HexColor('#006464'))
    st_dato_val = ParagraphStyle('dato_val', parent=styles['Normal'],
                                  fontName='Helvetica', fontSize=10)
    st_tabla_cell = ParagraphStyle('tabla_cell', parent=styles['Normal'],
                                   fontName='Helvetica', fontSize=8, leading=10)
    st_tabla_head = ParagraphStyle('tabla_head', parent=styles['Normal'],
                                   fontName='Helvetica-Bold', fontSize=8,
                                   textColor=colors.white, alignment=TA_CENTER, leading=10)
    st_firma_titulo = ParagraphStyle('firma_titulo', parent=styles['Normal'],
                                     fontName='Helvetica-Bold', fontSize=9,
                                     alignment=TA_CENTER, textColor=colors.white)
    st_firma_nombre = ParagraphStyle('firma_nombre', parent=styles['Normal'],
                                     fontName='Helvetica-Bold', fontSize=9,
                                     alignment=TA_CENTER)
    st_firma_area = ParagraphStyle('firma_area', parent=styles['Normal'],
                                   fontName='Helvetica', fontSize=8,
                                   alignment=TA_CENTER)

    elementos = []

    # =========================================================
    # Título y datos generales
    # =========================================================
    elementos.append(Paragraph(f'Solicitud #{solicitud.id}', st_titulo))
    elementos.append(Spacer(1, 4))

    fecha_salida = _fmt_fecha(solicitud.fecha_creacion, con_hora=not ya_entregado)
    responsable = f"{solicitud.usuario.first_name} {solicitud.usuario.last_name}".strip() or solicitud.usuario.username
    unidad = _unidad_usuario(solicitud.usuario) or solicitud.area_destino or '—'

    datos_tabla = [
        [Paragraph('Fecha de salida:', st_dato_lbl), Paragraph(fecha_salida, st_dato_val)],
        [Paragraph('Responsable de la solicitud:', st_dato_lbl), Paragraph(responsable, st_dato_val)],
        [Paragraph('Servicio / Sala / Unidad:', st_dato_lbl), Paragraph(unidad, st_dato_val)],
    ]
    t_datos = Table(datos_tabla, colWidths=[5.5 * cm, doc.width - 5.5 * cm])
    t_datos.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elementos.append(t_datos)
    elementos.append(Spacer(1, 10))

    # =========================================================
    # Tabla de expedientes
    # =========================================================
    motivo_solicitud = solicitud.motivo.nombre if solicitud.motivo else ''
    fecha_entrega_calc = _calcular_fecha_entrega(solicitud, ahora)
    fecha_entrega_str = _fmt_fecha(fecha_entrega_calc, con_hora=not ya_entregado) if fecha_entrega_calc else ''

    # Obtener comentario general
    comentarios_generales = ''
    try:
        p = solicitud.prestamo
        comentarios_generales = p.comentarios or ''
    except Exception:
        pass

    cabeceras = [
        Paragraph('Fecha salida', st_tabla_head),
        Paragraph('Expediente', st_tabla_head),
        Paragraph('Identidad', st_tabla_head),
        Paragraph('Paciente', st_tabla_head),
        Paragraph('Motivo', st_tabla_head),
        Paragraph('Fecha entrega', st_tabla_head),
        Paragraph('Observaciones entrega', st_tabla_head),
        Paragraph('Observaciones devolución', st_tabla_head),
    ]

    filas = [cabeceras]

    # Construir mensaje general de observaciones: motivos de rechazo o comentario general
    obs_general = ''
    detalles_list = list(solicitud.detalles.select_related('expediente_prestamo__expediente').order_by('id'))

    # Recolectar motivos de rechazo
    motivos_rechazo = []
    for d in detalles_list:
        if not d.aprobado:
            if d.motivo_rechazo_individual:
                motivos_rechazo.append(f"#{d.expediente_prestamo.expediente.numero}: {d.motivo_rechazo_individual}")
            else:
                motivos_rechazo.append(f"#{d.expediente_prestamo.expediente.numero}: [NO PRESTADO]")

    if motivos_rechazo:
        obs_general = '\n'.join(motivos_rechazo)
    else:
        obs_general = comentarios_generales

    # Agregar filas de detalles
    for idx, d in enumerate(detalles_list):
        num_exp = d.expediente_prestamo.expediente.numero
        identidad = d.paciente_identidad or ''
        paciente = d.paciente_nombre or ''

        # Solo la primera fila lleva el contenido; las demás quedarán vacías para combinar con SPAN
        obs_entrega_cell = Paragraph(obs_general, st_tabla_cell) if idx == 0 else Paragraph('', st_tabla_cell)

        filas.append([
            Paragraph(fecha_salida, st_tabla_cell),
            Paragraph(f'#{num_exp}', st_tabla_cell),
            Paragraph(identidad, st_tabla_cell),
            Paragraph(paciente, st_tabla_cell),
            Paragraph(motivo_solicitud, st_tabla_cell),
            Paragraph(fecha_entrega_str if d.aprobado else '—', st_tabla_cell),
            obs_entrega_cell,
            Paragraph('', st_tabla_cell),  # Observaciones devolución vacía
        ])

    col_w = doc.width
    tabla_exp = Table(
        filas,
        colWidths=[
            col_w * 0.10, col_w * 0.10, col_w * 0.12, col_w * 0.15,
            col_w * 0.12, col_w * 0.11, col_w * 0.15, col_w * 0.15,
        ],
        repeatRows=1,
    )
    # Construir estilos, incluyendo SPAN para la columna de observaciones entrega
    tabla_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#008b8b')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#444444')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f5')]),
    ]

    # Combinar y centrar observaciones entrega (columna 6)
    if len(filas) > 2:  # Más de encabezado + 1 detalle
        tabla_styles.append(('SPAN', (6, 1), (6, len(filas) - 1)))
    tabla_styles.append(('VALIGN', (6, 1), (6, -1), 'MIDDLE'))
    tabla_styles.append(('ALIGN', (6, 1), (6, -1), 'CENTER'))

    tabla_exp.setStyle(TableStyle(tabla_styles))
    elementos.append(tabla_exp)
    elementos.append(Spacer(1, 16))

    # =========================================================
    # Firmas (Entrega + Devolución)
    # =========================================================
    admin_nombre = ''
    admin_area = ''
    try:
        p = solicitud.prestamo
        a = p.admin_aprobador
        admin_nombre = (f"{a.first_name} {a.last_name}".strip() or a.username) if a else ''
        admin_area = _unidad_usuario(a) if a else ''
    except Exception:
        pass

    solicitante_nombre = responsable
    solicitante_area = unidad

    fecha_entrega_firma = _fmt_fecha(ahora, con_hora=True)
    fecha_devolucion_firma = _fmt_fecha(fecha_entrega_calc, con_hora=True) if fecha_entrega_calc else ''

    def _bloque_firma(encabezado, fecha_txt, nombre_izq, area_izq, nombre_der, area_der, ancho_total):
        """Construye una Table con el bloque de firma (2 celdas side-by-side + separador)."""
        col_ancho = ancho_total * 0.45
        sep_ancho = ancho_total * 0.1
        titulo_txt = f'<b>{encabezado}</b>'
        if fecha_txt:
            titulo_txt += f'<br/><font size=8>Fecha: {fecha_txt}</font>'

        contenido = [
            # Fila 0: título del bloque (atravesado)
            [Paragraph(titulo_txt, st_firma_titulo), '', ''],
            # Fila 1: celdas de firma (2cm alto x 5cm ancho) + separador
            ['', '', ''],
            # Fila 2: nombres
            [
                Paragraph(nombre_izq or '&nbsp;', st_firma_nombre),
                '',
                Paragraph(nombre_der or '&nbsp;', st_firma_nombre),
            ],
            # Fila 3: áreas
            [
                Paragraph(area_izq or '&nbsp;', st_firma_area),
                '',
                Paragraph(area_der or '&nbsp;', st_firma_area),
            ],
        ]
        t = Table(
            contenido,
            colWidths=[col_ancho, sep_ancho, col_ancho],
            rowHeights=[1.1 * cm, 2 * cm, 0.55 * cm, 0.5 * cm],
        )
        t.setStyle(TableStyle([
            # Título atravesado en fila 0
            ('SPAN', (0, 0), (2, 0)),
            ('BACKGROUND', (0, 0), (2, 0), colors.HexColor('#008b8b')),
            ('VALIGN', (0, 0), (2, 0), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (2, 0), 4),
            ('TOPPADDING', (0, 0), (2, 0), 4),
            # Bordes externos del bloque
            ('BOX', (0, 0), (0, -1), 0.6, colors.black),
            ('BOX', (2, 0), (2, -1), 0.6, colors.black),
            # Sin bordes en columna separadora
            # Borde superior grueso (línea de firma) en fila de nombres
            ('LINEABOVE', (0, 2), (0, 2), 1.2, colors.black),
            ('LINEABOVE', (2, 2), (2, 2), 1.2, colors.black),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        return t

    # Wrapper que pone los dos bloques lado a lado
    ancho_disp = doc.width
    sep_bloques = 1.5 * cm
    ancho_bloque = (ancho_disp - sep_bloques) / 2

    bloque_entrega = _bloque_firma(
        'Firma Entrega de Expedientes', fecha_entrega_firma,
        admin_nombre, admin_area,
        solicitante_nombre, solicitante_area,
        float(ancho_bloque),
    )
    bloque_devolucion = _bloque_firma(
        'Firma Devolución de Expedientes', fecha_devolucion_firma,
        admin_nombre, admin_area,
        solicitante_nombre, solicitante_area,
        float(ancho_bloque),
    )

    # Contenedor de 3 columnas: firma entrega - separador - firma devolución
    contenedor = Table(
        [[bloque_entrega, '', bloque_devolucion]],
        colWidths=[ancho_bloque, sep_bloques, ancho_bloque],
    )
    contenedor.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))

    elementos.append(KeepTogether([contenedor]))

    # =========================================================
    # Build con NumberedCanvas para pintar "Página X de Y"
    # =========================================================
    def make_canvas(*args, **kwargs):
        return _NumberedCanvas(*args, draw_footer=draw_footer, **kwargs)

    doc.build(elementos, canvasmaker=make_canvas)

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
