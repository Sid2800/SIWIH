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


class FichaActivoFijoPdfService:
    """Genera la ficha de activo fijo con los datos actuales del equipo."""

    INDEFINIDO = "INDEFINIDO"
    CODIGO_FORMATO = "AV-GR-SG-MANT-003 A"

    @classmethod
    def _texto(cls, valor, *, permitir_vacio=False):
        texto = str(valor or "").strip()
        if texto:
            return texto
        return "" if permitir_vacio else cls.INDEFINIDO

    @classmethod
    def _fecha_registro(cls, dispositivo):
        fecha = getattr(dispositivo, "fecha_creado", None)
        if not fecha:
            return cls.INDEFINIDO
        if timezone.is_aware(fecha):
            fecha = timezone.localtime(fecha)
        return fecha.strftime("%d/%m/%Y")

    @classmethod
    def _descripcion(cls, dispositivo):
        return " | ".join(
            [
                cls._texto(dispositivo.tipo),
                f"MARCA: {cls._texto(dispositivo.marca)}",
                f"MODELO: {cls._texto(dispositivo.modelo)}",
            ]
        )

    @classmethod
    def _colores(cls, dispositivo):
        principal = cls._texto(dispositivo.color)
        secundario = cls._texto(
            dispositivo.color_secundario,
            permitir_vacio=True,
        )
        if secundario:
            return f"{principal} / {secundario}"
        return principal

    @classmethod
    def _precio(cls, dispositivo):
        if dispositivo.costo_adquisicion is None:
            return cls.INDEFINIDO
        return f"L {dispositivo.costo_formateado}"

    @classmethod
    def _garantia(cls, dispositivo):
        """Vencimiento y duracion de la garantia para la ficha.

        Se imprime el vencimiento REAL, ya ajustado con las pausas: es la
        fecha hasta la que se puede reclamar al proveedor, que es lo que
        interesa a quien tenga el papel en la mano. La duracion se expresa en
        meses porque las garantias reales no caen siempre en anios enteros.
        """
        from .garantia_service import calcular_estado_garantia

        estado = calcular_estado_garantia(dispositivo)

        if not estado.tiene_garantia:
            return cls.INDEFINIDO, cls.INDEFINIDO

        registro = dispositivo.fecha_creado
        if registro is None:
            return cls.INDEFINIDO, estado.fin_real.strftime("%d/%m/%Y")

        if timezone.is_aware(registro):
            registro = timezone.localtime(registro)

        meses = round((estado.fin_real - registro.date()).days / 30.44)
        duracion = f"{meses} mes{'es' if meses != 1 else ''}"

        return duracion, estado.fin_real.strftime("%d/%m/%Y")

    @classmethod
    def _departamento(cls, asignacion):
        ubicacion = asignacion.ubicacion if asignacion else None
        return cls._texto(ubicacion)

    @classmethod
    def construir_datos(cls, dispositivo, asignacion):
        """Mapea SIWIH al formato; las casillas manuales quedan vacias."""
        duracion_garantia, fin_garantia = cls._garantia(dispositivo)

        return {
            "numero_inventario": cls._texto(
                dispositivo.inventario_bienes_nacionales
            ),
            "inventario_bn": cls._texto(
                dispositivo.inventario_numero_ficha
            ),
            "descripcion": cls._descripcion(dispositivo),
            "marca": cls._texto(dispositivo.marca),
            "modelo": cls._texto(dispositivo.modelo),
            "tipo": cls._texto(dispositivo.tipo),
            "color": cls._colores(dispositivo),
            "numero_serie": cls._texto(dispositivo.numero_serie),
            "potencia": "",
            "principal_componente": "",
            "inactivo": "",
            "en_reparacion": "",
            "fecha_baja": "",
            "precio": cls._precio(dispositivo),
            "numero_factura": "",
            "tipo_garantia": "",
            "activo_sustituido": "",
            "fecha_entrega": cls._fecha_registro(dispositivo),
            "orden_compra": "",
            "comprobante": "",
            "familia": "",
            "subfamilia": "",
            "codigo_local": "",
            "centro_costo": "",
            "departamento": cls._departamento(asignacion),
            "sala_ambiente": "",
            "jefe_departamento": "",
            "proveedor": cls._texto(dispositivo.procedencia),
            "proveedor_mantenimiento": "",
            "contrato_mantenimiento": "",
            "fecha_inicio_contrato": "",
            "fecha_fin_contrato": "",
            "tipo_contrato": "",
            "duracion_garantia": duracion_garantia,
            "fecha_fin_garantia": fin_garantia,
        }

    @classmethod
    def generar(cls, *, dispositivo, asignacion, usuario):
        """Devuelve una ficha PDF de una pagina sin modificar la base."""
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="ficha_activo_fijo_{dispositivo.codigo}.pdf"'
        )

        pdf = canvas.Canvas(response, pagesize=letter)
        pdf.setTitle(f"Ficha de activo fijo {dispositivo.codigo}")
        ancho, alto = letter
        ReportePdfBaseService.dibujar_encabezado(pdf, ancho, alto - 25)

        # La franja visible del membrete ocupa 27 puntos. El contenido se
        # centra dentro del espacio blanco restante, igual que la ficha de baja.
        ancho_franja_visible = 27
        ancho_contenido = 17.2 * cm
        x_contenido = ancho_franja_visible + (
            (ancho - ancho_franja_visible - ancho_contenido) / 2
        )
        datos = cls.construir_datos(dispositivo, asignacion)

        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 6.5)
        codigo_ancho = 3.5 * cm
        codigo_alto = 14
        codigo_x = x_contenido + ancho_contenido - codigo_ancho
        codigo_y = alto - 103
        pdf.rect(codigo_x, codigo_y, codigo_ancho, codigo_alto)
        pdf.drawCentredString(
            codigo_x + (codigo_ancho / 2),
            codigo_y + 4,
            cls.CODIGO_FORMATO,
        )

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(
            x_contenido + (ancho_contenido / 2),
            alto - 122,
            "FICHA DE ACTIVO FIJO",
        )
        pdf.setStrokeColor(colors.HexColor("#333333"))
        pdf.setLineWidth(1)
        pdf.line(
            x_contenido,
            alto - 130,
            x_contenido + ancho_contenido,
            alto - 130,
        )

        estilo_etiqueta = ParagraphStyle(
            "FichaActivoEtiqueta",
            fontName="Helvetica-Bold",
            fontSize=6.3,
            leading=7.5,
            textColor=colors.black,
        )
        estilo_valor = ParagraphStyle(
            "FichaActivoValor",
            fontName="Helvetica",
            fontSize=6.5,
            leading=7.8,
            textColor=colors.black,
            wordWrap="CJK",
        )
        estilo_firma = ParagraphStyle(
            "FichaActivoFirma",
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            alignment=1,
            textColor=colors.black,
        )

        def parrafo(texto, estilo=estilo_valor):
            valor = str(texto or "").strip() or "&nbsp;"
            return Paragraph(valor, estilo)

        # Las tres parejas etiqueta/valor respetan la organizacion del formato
        # de papel. Los campos administrativos no disponibles quedan en blanco
        # para completarlos manualmente cuando corresponda.
        filas = [
            (
                ("Nº Inventario", datos["numero_inventario"]),
                ("Nº Inventario B/N", datos["inventario_bn"]),
                ("Familia", datos["familia"]),
            ),
            (
                ("Descripción", datos["descripcion"]),
                ("", ""),
                ("Subfamilia", datos["subfamilia"]),
            ),
            (
                ("Marca", datos["marca"]),
                ("", ""),
                ("Código local", datos["codigo_local"]),
            ),
            (
                ("Modelo", datos["modelo"]),
                ("", ""),
                ("Centro de costo", datos["centro_costo"]),
            ),
            (
                ("Tipo", datos["tipo"]),
                ("", ""),
                ("Departamento", datos["departamento"]),
            ),
            (
                ("Color", datos["color"]),
                ("", ""),
                ("Sala / Ambiente", datos["sala_ambiente"]),
            ),
            (
                ("Nº serie", datos["numero_serie"]),
                ("", ""),
                ("Nombre jefe departamento/sala", datos["jefe_departamento"]),
            ),
            (
                ("Potencia", datos["potencia"]),
                ("", ""),
                ("Proveedor", datos["proveedor"]),
            ),
            (
                ("Principal / Componente", datos["principal_componente"]),
                ("", ""),
                ("Proveedor mnto.", datos["proveedor_mantenimiento"]),
            ),
            (
                ("Inactivo", datos["inactivo"]),
                ("", ""),
                ("Contrato mnto.", datos["contrato_mantenimiento"]),
            ),
            (
                ("En reparación", datos["en_reparacion"]),
                ("", ""),
                ("Fecha inicio contr.", datos["fecha_inicio_contrato"]),
            ),
            (
                ("Fecha de baja", datos["fecha_baja"]),
                ("", ""),
                ("Fecha fin contr.", datos["fecha_fin_contrato"]),
            ),
            (
                ("Precio", datos["precio"]),
                ("Nº Orden compra", datos["orden_compra"]),
                ("Tipo contrato", datos["tipo_contrato"]),
            ),
            (
                ("Nº Factura", datos["numero_factura"]),
                ("Comprobante", datos["comprobante"]),
                ("Duración garantía", datos["duracion_garantia"]),
            ),
            (
                ("Tipo garantía", datos["tipo_garantia"]),
                ("", ""),
                ("Fecha fin garantía", datos["fecha_fin_garantia"]),
            ),
            (
                ("Nº activo sustituido", datos["activo_sustituido"]),
                ("", ""),
                ("", ""),
            ),
            (
                ("Fecha de entrega", datos["fecha_entrega"]),
                ("", ""),
                ("", ""),
            ),
        ]

        datos_tabla = []
        for fila in filas:
            celdas = []
            for etiqueta, valor in fila:
                celdas.extend(
                    [
                        parrafo(etiqueta, estilo_etiqueta),
                        parrafo(valor),
                    ]
                )
            datos_tabla.append(celdas)

        tabla = Table(
            datos_tabla,
            colWidths=[
                2.25 * cm,
                3.35 * cm,
                2.25 * cm,
                2.35 * cm,
                2.55 * cm,
                4.45 * cm,
            ],
        )
        estilo_tabla = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#777777")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E7EEEE")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E7EEEE")),
            ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#E7EEEE")),
        ]
        tabla.setStyle(TableStyle(estilo_tabla))
        _, alto_tabla = tabla.wrap(ancho_contenido, alto)
        y_tabla = alto - 142 - alto_tabla
        tabla.drawOn(pdf, x_contenido, y_tabla)

        firmas = [
            [
                parrafo(
                    "______________________________<br/>"
                    "<b>Firma Responsable de Mantenimiento</b>",
                    estilo_firma,
                ),
                parrafo(
                    "______________________________<br/>"
                    "<b>Firma Responsable Bienes Nacionales / Contabilidad</b>",
                    estilo_firma,
                ),
            ],
            [
                parrafo(
                    "______________________________<br/>"
                    "<b>Firma Jefe Sala / Departamento / Unidad</b>",
                    estilo_firma,
                ),
                parrafo(
                    "______________________________<br/>"
                    "<b>Firma Jefe de Logística y Suministros</b>",
                    estilo_firma,
                ),
            ],
            [
                parrafo(
                    "______________________________<br/>"
                    "<b>VoBo Sub Dirección de Gestión de Recursos</b>",
                    estilo_firma,
                ),
                "",
            ],
        ]
        tabla_firmas = Table(
            firmas,
            colWidths=[ancho_contenido / 2, ancho_contenido / 2],
            rowHeights=[43, 43, 43],
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
            y_tabla - alto_firmas - 8,
        )

        ahora_local = timezone.localtime()
        ReportePdfBaseService.dibujar_pie_pagina_carta(
            pdf,
            alto,
            ancho,
            ahora_local.strftime("%d/%m/%Y %H:%M"),
            usuario.username,
            "",
            1,
            1,
            mostrar_paginacion=False,
            etiqueta_usuario="GENERADO POR: ",
        )
        pdf.save()
        return response
