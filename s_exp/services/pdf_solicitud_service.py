"""
Generador de PDF para una Solicitud de Préstamo de Expedientes.
Encabezado (2cm arriba) + Pie (2cm abajo) + contenido + tabla + firmas.
"""
import os
from io import BytesIO
from datetime import timedelta, datetime

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
from reportlab.graphics.shapes import Drawing, Rect, Line

from usuario.models import PerfilUnidad


IMG_DIR = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'img')
IMG_GOB_SESAL = os.path.join(IMG_DIR, 'GOB_SESAL_COLOR.png')
IMG_HEAC = os.path.join(IMG_DIR, 'logo_HEAC.png')
IMG_FUNDAGES = os.path.join(IMG_DIR, 'logo_FUNDAGES2.png')
IMG_SIWIH = os.path.join(IMG_DIR, 'SIWIFINAL_3.png')


def _checkbox_pdf(marcado=False, size=11):
    """Devuelve un Drawing con un checkbox dibujado.
    - marcado=False: cuadro vacío (para marcado manual antes de la entrega)
    - marcado=True: cuadro con check verde (expediente sí prestado/finalizado)
    """
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, strokeWidth=0.6,
               strokeColor=colors.HexColor('#444444'),
               fillColor=colors.white))
    if marcado:
        # Checkmark V (de izquierda-medio hacia abajo-medio y luego arriba-derecha)
        d.add(Line(size * 0.18, size * 0.50, size * 0.42, size * 0.22,
                   strokeWidth=1.5, strokeColor=colors.HexColor('#16a34a')))
        d.add(Line(size * 0.42, size * 0.22, size * 0.85, size * 0.78,
                   strokeWidth=1.5, strokeColor=colors.HexColor('#16a34a')))
    return d


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
    """
    Devuelve el nombre de la unidad del usuario.

    Estrategia de resolución (en orden):
    1. PerfilUnidad (sistema de roles del módulo s_exp)
    2. Cadena RRHH: Empleado → PersonalNoClinico → servicio_unidad
    3. Cadena RRHH: Empleado → PersonalSalud → servicio_unidad

    Esto permite que tanto solicitantes (usualmente con PerfilUnidad) como
    admins/digitadores (usualmente solo con registro RRHH) aparezcan en el PDF.
    """
    if not user:
        return ''

    # 1) PerfilUnidad
    try:
        perfil = PerfilUnidad.objects.filter(usuario=user).select_related('servicio_unidad').first()
        if perfil and perfil.servicio_unidad:
            return perfil.servicio_unidad.nombre_unidad
    except Exception:
        pass

    # 2) RRHH: PersonalNoClinico
    try:
        from rrhh.models import Empleado, PersonalNoClinico, PersonalSalud
        empleado = Empleado.objects.filter(usuario_id=user.id).first()
        if empleado:
            pnc = PersonalNoClinico.objects.filter(
                empleado_id=empleado.id
            ).select_related('servicio_unidad').first()
            if pnc and pnc.servicio_unidad:
                return pnc.servicio_unidad.nombre_unidad

            # 3) RRHH: PersonalSalud
            ps = PersonalSalud.objects.filter(
                empleado_id=empleado.id
            ).select_related('servicio_unidad').first()
            if ps and ps.servicio_unidad:
                return ps.servicio_unidad.nombre_unidad
    except Exception:
        pass

    return ''


def _fmt_fecha(dt, con_hora=True):
    if not dt:
        return ''
    # Convertir a la zona horaria local del sistema antes de formatear
    if timezone.is_aware(dt):
        dt = dt.astimezone(timezone.get_current_timezone())
    # Formato de 12 horas (AM/PM), consistente con el resto del sistema
    if con_hora:
        return dt.strftime('%d/%m/%Y %I:%M %p').strip()
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
                IMG_HEAC, ancho - 5 * cm, y_top - 2.0 * cm,
                width=2.2 * cm, height=2.2 * cm, preserveAspectRatio=True, mask='auto'
            )
            canvas_obj.drawImage(
                IMG_FUNDAGES, ancho - 2.5 * cm, y_top - 2.0 * cm,
                width=2.2 * cm, height=2.2 * cm, preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

        canvas_obj.restoreState()

    def dibujar_footer(canvas_obj, total_pages):
        canvas_obj.saveState()
        ancho, alto = canvas_obj._pagesize
        y_bot = 1.2 * cm  # más abajo

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
    tz = timezone.get_current_timezone()
    ahora = timezone.now().astimezone(tz)
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
                               alignment=TA_CENTER, spaceAfter=6,
                               borderBottom=1, borderPadding=4)
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

    # "Hora de salida" = momento real en que el expediente sale del archivo.
    # Si el préstamo ya tiene fecha_entrega, usarla; si no, usar la hora actual del sistema.
    fecha_salida_dt = None
    try:
        if solicitud.prestamo and solicitud.prestamo.fecha_entrega:
            fecha_salida_dt = solicitud.prestamo.fecha_entrega
    except Exception:
        fecha_salida_dt = None
    if fecha_salida_dt is None:
        fecha_salida_dt = ahora
    fecha_salida = _fmt_fecha(fecha_salida_dt, con_hora=True)

    # Datos del solicitante: usamos los servicios para que sean consistentes
    # con el resto del sistema (consulta en vivo, no snapshots).
    from s_exp.services.datos_solicitud import DatosSolicitud
    responsable = DatosSolicitud.usuario_nombre_completo(solicitud)
    # Unidad: prioridad a la FK servicio_unidad (capturada al crear la solicitud).
    # Si por alguna razón no hay FK, caemos al resolver via RRHH del usuario.
    unidad = DatosSolicitud.unidad_nombre(solicitud) or _unidad_usuario(solicitud.usuario) or '—'

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

    # Estilo de cabecera más pequeño para columna "Disponible"
    st_tabla_head_sm = ParagraphStyle('tabla_head_sm', parent=st_tabla_head, fontSize=7, leading=9)

    cabeceras = [
        Paragraph('Fecha salida', st_tabla_head),
        Paragraph('Expediente', st_tabla_head),
        Paragraph('Disponible', st_tabla_head_sm),
        Paragraph('Identidad', st_tabla_head),
        Paragraph('Paciente', st_tabla_head),
        Paragraph('Motivo', st_tabla_head),
        Paragraph('Fecha entrega', st_tabla_head),
        Paragraph('Observaciones entrega', st_tabla_head),
        Paragraph('Observaciones devolución', st_tabla_head),
    ]

    filas = [cabeceras]
    # Optimizamos joins: traemos expediente_prestamo + expediente + paciente
    # de un solo, evita N+1 queries dentro del loop.
    detalles_list = list(solicitud.detalles.select_related(
        'expediente_prestamo__expediente', 'paciente'
    ).order_by('id'))

    # Estado del flujo: si la solicitud está finalizada/incompleta/etc., los comentarios
    # de devolución y rechazo individual ya tienen sentido y deben imprimirse.
    estado_flujo = (solicitud.estado_flujo_id or '').upper() if hasattr(solicitud, 'estado_flujo_id') else ''
    estados_con_revision = {'SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION',
                             'SOL_INCOMPLETA', 'SOL_FINALIZADA', 'SOL_RECHAZADA'}
    mostrar_comentarios = estado_flujo in estados_con_revision
    # Solo en estos estados ya se sabe definitivamente si el expediente se prestó o no
    estados_finalizado = {'SOL_FINALIZADA', 'SOL_RECHAZADA', 'SOL_INCOMPLETA'}
    pdf_finalizado = estado_flujo in estados_finalizado

    # Filas que NO se prestaron — para resaltar en rojo pastel
    filas_no_prestadas = []  # índices de fila (1-based porque cabecera es fila 0)

    from s_exp.services.datos_solicitud import DatosDetalleSolicitud

    # Agregar filas de detalles.
    # IMPORTANTE: número de expediente, identidad y nombre del paciente se
    # obtienen vía servicio (consulta en vivo desde FK), no desde snapshots.
    for idx, d in enumerate(detalles_list, start=1):
        num_exp = DatosDetalleSolicitud.numero_expediente(d)
        identidad = DatosDetalleSolicitud.paciente_dni(d)
        paciente = DatosDetalleSolicitud.paciente_nombre_completo(d)

        # Observaciones de entrega:
        #   - Si NO se prestó (aprobado=False) y hay revisión, mostrar el motivo del rechazo
        #     individual; si no hay motivo, fallback a "[NO PRESTADO]".
        #   - Si sí se prestó, queda vacío (lo llena el responsable a mano si aplica).
        if not d.aprobado:
            if mostrar_comentarios and d.motivo_rechazo_individual:
                obs_entrega_text = d.motivo_rechazo_individual
            else:
                obs_entrega_text = '[NO PRESTADO]'
        else:
            obs_entrega_text = ''

        # Observaciones de devolución:
        #   - Sólo se imprime si el flujo ya pasó por revisión/devolución/finalizada
        #   - Usa el comentario individual guardado durante la auditoría de devolución
        if mostrar_comentarios and d.aprobado and d.comentario_devolucion:
            obs_devolucion_text = d.comentario_devolucion
        else:
            obs_devolucion_text = ''

        # Checkbox visual:
        #   - Antes de finalizar: SIEMPRE vacío (el responsable lo marca a mano)
        #   - Si finalizado: marcado para los que sí se prestaron, vacío para no prestados
        if pdf_finalizado:
            cb = _checkbox_pdf(marcado=bool(d.aprobado))
        else:
            cb = _checkbox_pdf(marcado=False)

        # Marcar para resaltado rojo pastel si NO se prestó y el flujo ya finalizó
        if pdf_finalizado and not d.aprobado:
            filas_no_prestadas.append(idx)

        filas.append([
            Paragraph(fecha_salida, st_tabla_cell),
            Paragraph(f'#{num_exp}', st_tabla_cell),
            cb,  # Checkbox visual centrado
            Paragraph(identidad, st_tabla_cell),
            Paragraph(paciente, st_tabla_cell),
            Paragraph(motivo_solicitud, st_tabla_cell),
            Paragraph(fecha_entrega_str if d.aprobado else '—', st_tabla_cell),
            Paragraph(obs_entrega_text, st_tabla_cell),
            Paragraph(obs_devolucion_text, st_tabla_cell),
        ])

    col_w = doc.width
    tabla_exp = Table(
        filas,
        colWidths=[
            col_w * 0.10, col_w * 0.08, col_w * 0.07, col_w * 0.11, col_w * 0.14,
            col_w * 0.11, col_w * 0.10, col_w * 0.14, col_w * 0.15,
        ],
        repeatRows=1,
    )
    # Construir estilos de la tabla
    tabla_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#008b8b')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#444444')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Centrar checkbox en su columna
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f5')]),
    ]

    # Resaltar en rojo pastel las filas de expedientes NO prestados (sólo cuando el PDF ya finalizó)
    rojo_pastel = colors.HexColor('#fde2e2')
    for fila_idx in filas_no_prestadas:
        tabla_styles.append(('BACKGROUND', (0, fila_idx), (-1, fila_idx), rojo_pastel))

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
