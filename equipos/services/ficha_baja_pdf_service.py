from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from core.services.reporte.PDF.reporte_pdf_base_service import (
    ReportePdfBaseService,
)


class FichaBajaPdfService:
    """Genera la ficha imprimible previa a la baja definitiva de un equipo."""

    INDEFINIDO = "INDEFINIDO"

    @classmethod
    def _texto(cls, valor):
        texto = str(valor or "").strip()
        return texto or cls.INDEFINIDO

    @classmethod
    def _fecha(cls, valor):
        if not valor:
            return cls.INDEFINIDO
        return valor.strftime("%d/%m/%Y")

    @classmethod
    def _nombre_empleado(cls, empleado):
        if not empleado:
            return cls.INDEFINIDO

        nombre = (empleado.nombre_completo or "").strip()
        dni = str(empleado.dni or "").strip()
        if dni and nombre:
            return f"{dni} - {nombre}"
        return nombre or dni or cls.INDEFINIDO

    @classmethod
    def _descripcion_activo(cls, dispositivo):
        return " | ".join(
            [
                cls._texto(dispositivo.tipo),
                f"MARCA: {cls._texto(dispositivo.marca)}",
                f"MODELO: {cls._texto(dispositivo.modelo)}",
                f"SERIE: {cls._texto(dispositivo.numero_serie)}",
            ]
        )

    @classmethod
    def _codigo_inventario(cls, dispositivo):
        # El formato administrativo llama "Código Inventario" únicamente al
        # número de ficha. Bienes nacionales no se imprime en este apartado.
        return cls._texto(dispositivo.inventario_numero_ficha)

    @classmethod
    def generar(
        cls,
        *,
        dispositivo,
        asignacion,
        usuario,
        fecha_orden_trabajo,
        motivo,
        habitacion_estancia,
        numero_orden_trabajo,
    ):
        """Devuelve el PDF en línea sin modificar datos del equipo."""
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="ficha_baja_{dispositivo.codigo}.pdf"'
        )

        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(f"Ficha de baja {dispositivo.codigo}")
        ancho, alto = letter
        ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 25)

        x_contenido = 110
        ancho_contenido = ancho - x_contenido - 25
        fecha_informe = timezone.localdate()
        ubicacion = asignacion.ubicacion if asignacion else None
        nombre_empleado_asignado = cls._nombre_empleado(
            asignacion.responsable if asignacion else None
        )

        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(
            x_contenido + (ancho_contenido / 2),
            alto - 120,
            f"INFORME DE BAJA DE ACTIVO INVENTARIADO {fecha_informe.year}",
        )
        pdf.setStrokeColor(colors.HexColor("#333333"))
        pdf.setLineWidth(1)
        pdf.line(
            x_contenido,
            alto - 128,
            x_contenido + ancho_contenido,
            alto - 128,
        )

        estilo_etiqueta = ParagraphStyle(
            "FichaBajaEtiqueta",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
        )
        estilo_valor = ParagraphStyle(
            "FichaBajaValor",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.black,
        )
        estilo_firma = ParagraphStyle(
            "FichaBajaFirma",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=1,
            textColor=colors.black,
        )

        def parrafo(texto, estilo=estilo_valor, permitir_vacio=False):
            if permitir_vacio and not str(texto or "").strip():
                return Paragraph("&nbsp;", estilo)
            return Paragraph(cls._texto(texto), estilo)

        filas = [
            ("Fecha del informe", cls._fecha(fecha_informe), False),
            (
                "Fecha de orden de trabajo",
                cls._fecha(fecha_orden_trabajo),
                False,
            ),
            (
                "Empleado asignado",
                nombre_empleado_asignado,
                False,
            ),
            (
                "Código de local",
                "",
                True,
            ),
            (
                "Sala / Departamento / Unidad",
                ubicacion or cls.INDEFINIDO,
                False,
            ),
            ("Habitación / Estancia", habitacion_estancia, False),
            ("Código interno del equipo", dispositivo.codigo, False),
            (
                "Código de inventario",
                cls._codigo_inventario(dispositivo),
                False,
            ),
            (
                "Descripción del activo",
                cls._descripcion_activo(dispositivo),
                False,
            ),
            ("Número de orden de trabajo", numero_orden_trabajo, False),
            ("Motivo de la baja", motivo or cls.INDEFINIDO, False),
        ]
        datos_tabla = [
            [
                Paragraph(etiqueta, estilo_etiqueta),
                parrafo(valor, permitir_vacio=permitir_vacio),
            ]
            for etiqueta, valor, permitir_vacio in filas
        ]
        tabla = Table(
            datos_tabla,
            colWidths=[4.7 * cm, ancho_contenido - (4.7 * cm)],
        )
        tabla.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#777777")),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        colors.HexColor("#E7EEEE"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        _, alto_tabla = tabla.wrap(ancho_contenido, alto)
        y_tabla = alto - 145 - alto_tabla
        tabla.drawOn(pdf, x_contenido, y_tabla)

        tabla_comentario = Table(
            [
                [
                    Paragraph(
                        "Comentario del responsable de mantenimiento",
                        estilo_etiqueta,
                    )
                ],
                [parrafo("", permitir_vacio=True)],
            ],
            colWidths=[ancho_contenido],
            # El comentario se completa a mano después de imprimir la ficha.
            rowHeights=[20, 90],
        )
        tabla_comentario.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#777777")),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#E7EEEE"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        _, alto_comentario = tabla_comentario.wrap(ancho_contenido, alto)
        y_comentario = y_tabla - alto_comentario - 12
        tabla_comentario.drawOn(pdf, x_contenido, y_comentario)

        firmas = [
            [
                Paragraph(
                    "______________________________<br/>"
                    "<b>Responsable de Mantenimiento</b><br/>Original",
                    estilo_firma,
                ),
                Paragraph(
                    "______________________________<br/>"
                    "<b>Jefe de Sala / Departamento / Unidad</b><br/>Copia",
                    estilo_firma,
                ),
            ],
            [
                Paragraph(
                    "______________________________<br/>"
                    "<b>Responsable de Bienes Nacionales</b><br/>Copia",
                    estilo_firma,
                ),
                Paragraph(
                    "______________________________<br/>"
                    "<b>Jefe de Servicios Generales</b><br/>Copia",
                    estilo_firma,
                ),
            ],
            [
                Paragraph(
                    "______________________________<br/>"
                    "<b>Subdirección de Gestión de Recursos</b><br/>Copia",
                    estilo_firma,
                ),
                "",
            ],
        ]
        tabla_firmas = Table(
            firmas,
            colWidths=[ancho_contenido / 2, ancho_contenido / 2],
            rowHeights=[55, 55, 55],
        )
        tabla_firmas.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("SPAN", (0, 2), (1, 2)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        _, alto_firmas = tabla_firmas.wrap(ancho_contenido, alto)
        tabla_firmas.drawOn(
            pdf,
            x_contenido,
            y_comentario - alto_firmas - 4,
        )

        ahora_local = timezone.localtime()
        ReportePdfBaseService.dibujar_pie_pagina_carta(
            pdf,
            alto,
            ancho,
            ahora_local.strftime("%d/%m/%Y %H:%M"),
            usuario.username,
            nombre_empleado_asignado,
            1,
            1,
        )
        pdf.save()
        return response
