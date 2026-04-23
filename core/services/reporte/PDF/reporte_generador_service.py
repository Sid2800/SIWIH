from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, legal, landscape
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from django.utils import timezone
from reportlab.lib.units import  cm
from django.utils.translation import gettext as _

import math
import copy

from core.utils.utilidades_fechas import formatear_fecha, formatear_fecha2, formatear_fecha_dd_mm_yyyy
from core.utils.utilidades_textos import formatear_dni, formatear_nombre_completo, formatear_expediente
from core.services.reporte.PDF.reporte_pdf_base_service import ReportePdfBaseService
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


class ReporteGeneradorService:
    
    @staticmethod
    def GenerarReporteResumido(reporte_criterios):
        try:
            # Crear la respuesta como un PDF
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Reporte_generado_{reporte_criterios['modelo']}.pdf"'

            # Inicializar el canvas PDF
            pdf = canvas.Canvas(response, pagesize=letter)
            pdf.setTitle(f"Reporte generado {str(reporte_criterios['modelo']).upper()}")
            ancho, alto = letter
            y = alto - 30  # Margen superior inicial

            # --- Función interna para dibujar el encabezado del reporte ---rus
            def dibujar_titulo_reporte(pdf, ancho, alto):
                # Mapea el tipo de interacción con un título descriptivo

                mapear = {
                    'fecha': 'CREADOS',
                    'fecha_creado': ' CREADAS',
                    'fecha_modificado': 'MODIFICADOS',
                    'fecha_nacimiento': ' PACIENTES NACIDOS',
                    'fecha_ingreso': ' REGISTRADOS',
                    'fecha_egreso': ' EGRESADOS',
                    'fecha_recepcion_sdgi': ' RECEPCIONADOS',
                    'fecha_atencion': ' REGISTRADAS',
                    'fecha_recepcion': ' RECEPCIONADAS',
                    'evaluacionRx__fecha': 'REGISTRADOS'
                }

                mapear_modelo = {
                    'paciente': 'PACIENTES',
                    'ingreso': 'INGRESOS',
                    'atencion': 'ATENCIONES',
                    'imagenologia': 'EVALUACIONES RX',
                    'estudio_rx': 'ESTUDIOS'
                }


                # Título principal centrado
                pdf.setFont("Helvetica-Bold", 14)
                titulo = f"CONSOLIDADO DE {mapear_modelo.get(reporte_criterios['modelo'],"")} {mapear.get(reporte_criterios['interaccion'],"")}"
                pdf.drawCentredString(ancho / 2, alto - 100, titulo)

                # Línea divisoria gris clara
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 105, 584, alto - 105)

                # Subtítulos de campos
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawRightString(170, alto - 130, "FECHA INICIAL:")
                pdf.drawRightString(350, alto - 130, "FECHA FINAL:")
                pdf.drawRightString(510, alto - 130, "AGRUPADOS:")

                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawRightString(165, alto - 185, "CAMPO FILTRADO:")
                pdf.drawRightString(440, alto - 185, "VALOR FILTRADO:")

                # Fondos para los campos de datos
                pdf.setFillColor(colors.black)
                pdf.rect(60, alto - 160, 525, 22, fill=1, stroke=0)
                pdf.rect(168, alto - 190, 150, 22, fill=1, stroke=0)
                pdf.rect(445, alto - 190, 140, 22, fill=1, stroke=0)

                # Texto blanco para los valores
                pdf.setFont("Helvetica", 11.5)
                pdf.setFillColor(colors.white)

                # Fechas formateadas localmente
                fecha_local = timezone.localtime(reporte_criterios['fechaIni'])
                fechaInicial = fecha_local.strftime('%d/%m/%Y')
                fecha_local = timezone.localtime(reporte_criterios['fechaFin'])
                fechasFinal = fecha_local.strftime('%d/%m/%Y')

                # Datos informativos
                pdf.drawString(80, alto - 153, fechaInicial)
                pdf.drawString(267, alto - 153, fechasFinal)
                pdf.drawString(175, alto - 183, str(reporte_criterios['campoFiltroTexto']).upper())
                pdf.drawString(452, alto - 183, str(reporte_criterios['campoValorTexto']).upper())
                pdf.drawString(430, alto - 153, str(reporte_criterios['etiqueta']).upper())

                # Línea divisoria inferior
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 200, 584, alto - 200)

            # --- Estilos generales de la tabla ---
            estilosGenerales = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

                # Encabezado: fondo negro con texto blanco
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

                # Líneas internas
                ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.grey),
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.grey),

                # Línea de cierre en la última fila
                ('LINEBELOW', (0, -1), (-1, -1), 4, colors.black),

                # Espaciado vertical
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),

                # Centrado para columnas específicas
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),

                # Fondo tipo zebra (intercalado)
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ]

            # Encabezado de la tabla
            encabezado = [[str(reporte_criterios['etiqueta']).upper(), "TOTAL", "PORCENTAJE"]]
            data = encabezado.copy()
            fila_actual = 1
            paginas = []

            # Agregar fila de total general al final del resumen
            reporte_criterios["resumen"].append({
                reporte_criterios['campo_agrupado']: "TOTAL",
                "total": reporte_criterios["total"],
                "porcentaje": "100"
            })

            # Generar filas de la tabla
            for fila in reporte_criterios['resumen']:
                data.append([
                    str(fila[reporte_criterios['campo_agrupado']])[:35].upper(),
                    str(fila['total']),
                    f"{fila['porcentaje']}%"
                ])
                fila_actual += 1

                # Si se supera el límite de filas por página, guardar página
                if len(data) >= 19:
                    paginas.append(copy.deepcopy(data))
                    data.clear()
                    data = encabezado.copy()
                    fila_actual = 1

            # Guardar la última página si tiene contenido
            if len(data) > 1:
                paginas.append(copy.deepcopy(data))
                data.clear()

            # --- Dibujar cada página del reporte ---
            for i, pagina in enumerate(paginas):
                ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
                dibujar_titulo_reporte(pdf, ancho, alto)

                # Crear tabla con ancho de columnas definido
                tabla = Table(pagina, colWidths=[8.5 * cm, 3 * cm, 3.5 * cm])
                tabla.setStyle(TableStyle(estilosGenerales))

                ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
                ubicacionYTabla1 = alto - 140 - alto_tabla - 80
                tabla.drawOn(pdf, 110, ubicacionYTabla1)

                # Línea decorativa bajo la tabla
                pdf.line(60, ubicacionYTabla1 - 10, 584, ubicacionYTabla1 - 10)

                # Mostrar total grande en la última página
                if i == len(paginas) - 1:
                    pdf.setFillColor(colors.black)
                    pdf.setFont("Helvetica-Bold", 12)
                    pdf.drawString(425, ubicacionYTabla1 - 42, "TOTAL")
                    pdf.rect(475, ubicacionYTabla1 - 48, 60, 22, fill=1, stroke=0)
                    pdf.setFillColor(colors.white)
                    pdf.drawString(480, ubicacionYTabla1 - 41, str(reporte_criterios['total']))

                # Pie de página con paginación y usuario
                fechaActual = timezone.now()
                ReportePdfBaseService.dibujar_pie_pagina_carta(
                    pdf, alto, ancho,
                    formatear_fecha(fechaActual),
                    reporte_criterios['usuario'],
                    reporte_criterios['usuario_nombre'],
                    i + 1, len(paginas)
                )

                # Agregar nueva página si no es la última
                if i < len(paginas) - 1:
                    pdf.showPage()

            # Guardar y devolver el PDF final
            pdf.save()
            return response
        except Exception:
            log_error(
                f"Error generando PDF resumido modelo {reporte_criterios.get('modelo')} "
                f"mes {reporte_criterios.get('fechaIni')} - {reporte_criterios.get('fechaFin')}",
                app=LogApp.REPORTE
            )
            raise


    @staticmethod
    def GenerarReporteDetallado(data ,reporte_criterios):
        try:
            if not data:
                log_warning(
                    f"Reporte detallado sin datos modelo {reporte_criterios.get('modelo')}",
                    app=LogApp.REPORTE
                )
                raise ValueError("No hay datos para generar el reporte detallado")

            # Crear la respuesta como un PDF
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Reporte_generado_{reporte_criterios['modelo']}.pdf"'

            # Inicializar el canvas PDF
            pdf = canvas.Canvas(response, pagesize=landscape(legal))
            pdf.setTitle(f"Reporte generado {str(reporte_criterios['modelo']).upper()}")
            ancho, alto = landscape(legal)
            y = alto - 30  # Margen superior inicial
            # --- Función interna para dibujar el encabezado del reporte ---
            def dibujar_titulo_reporte(pdf, ancho, alto):
                # Mapea el tipo de interacción con un título descriptivo

                mapear = {
                    'fecha': 'CREADOS',
                    'fecha_creado': ' CREADAS',
                    'fecha_modificado': 'MODIFICADOS',
                    'fecha_nacimiento': ' PACIENTES NACIDOS',
                    'fecha_ingreso': ' REGISTRADOS',
                    'fecha_egreso': ' EGRESADOS',
                    'fecha_recepcion_sdgi': ' RECEPCIONADOS',
                    'fecha_atencion': ' REGISTRADAS',
                    'fecha_recepcion': ' RECEPCIONADAS',
                    'evaluacionRx__fecha': 'REGISTRADOS'
                }

                mapear_modelo = {
                    'paciente': 'PACIENTES',
                    'ingreso': 'INGRESOS',
                    'atencion': 'ATENCIONES',
                    'imagenologia': 'EVALUACIONES RX',
                    'estudio_rx': 'ESTUDIOS'
                }

                

                # Título principal centrado
                pdf.setFont("Helvetica-Bold", 14)
                titulo = f"DETALLE DE {mapear_modelo.get(reporte_criterios['modelo'],"")} {mapear.get(reporte_criterios['interaccion'],"")}"
                pdf.drawCentredString(ancho / 2, alto - 100, titulo)

                # Línea divisoria gris clara
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 105, 975, alto - 105)

                # Subtítulos de campos
                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawString(80, alto - 120, "FECHA INICIAL:")
                pdf.drawString(210, alto - 120, "FECHA FINAL:")
                pdf.drawString(350, alto - 120, "AGRUPADOS:")
                pdf.drawString(560, alto - 120, "CAMPO FILTRADO:")
                pdf.drawString(770, alto - 120, "VALOR FILTRADO:") 


                # Fondos para los campos de datos
                pdf.setFillColor(colors.black)
                pdf.rect(60, alto - 150, 915, 22, fill=1, stroke=0)

                # Texto blanco para los valores
                pdf.setFont("Helvetica", 11.5)
                pdf.setFillColor(colors.white)

                # Fechas formateadas localmente
                fecha_local = timezone.localtime(reporte_criterios['fechaIni'])
                fechaInicial = fecha_local.strftime('%d/%m/%Y')
                fecha_local = timezone.localtime(reporte_criterios['fechaFin'])
                fechasFinal = fecha_local.strftime('%d/%m/%Y')

                # Datos informativos
                pdf.drawString(90, alto - 143, fechaInicial)
                pdf.drawString(220, alto - 143, fechasFinal)
                pdf.drawString(350, alto - 143, str(reporte_criterios['etiqueta']).upper())
                pdf.drawString(560, alto - 143, str(reporte_criterios['campoFiltroTexto']).upper())
                pdf.drawString(770, alto - 143, str(reporte_criterios['campoValorTexto']).upper())
                #campoFiltroTexto
                #campoValorTexto
                #etiqueta

                # Línea divisoria inferior
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 155, 975, alto - 155)
            

            def dibujar_resumido(pdf, ubicacionYTabla1, ancho, alto, conteo_campo_agrupacion, total, columnas = 6):
                pares = []
                for agrupacion, cantidad in conteo_campo_agrupacion.items():
                    pares.extend([agrupacion[:23], str(cantidad)])  # cada agrupación es un par


                # Convertir pares en filas de hasta 6 columnas (3 pares por fila)
                data_subtotal = []
                for i in range(0, len(pares), columnas):
                    fila = pares[i:i+columnas]
                    while len(fila) < columnas:
                        fila.append("")
                    data_subtotal.append(fila)

                # Agregar fila del TOTAL como fila completa separada
                fila_total = [f"TOTAL {str(total)}"]
                data_subtotal.append(fila_total)


                colAncho = ([160, 40] * (columnas // 2))
                # Tabla con siempre 6 columnas
                tablaSubtotal = Table(data_subtotal, colWidths=colAncho)

                # Estilos
                estilos = [
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),  # todas las filas excepto TOTAL
                    #total
                    ('SPAN', (0, -1), (-1, -1)),                # ocupa toda la fila
                    ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),  # línea superior más gruesa
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),    # negrita
                    ('FONTSIZE', (0, -1), (-1, -1), 12),        # tamaño de fuente mayor
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),  # fondo gris
                    ('ALIGN', (0, -1), (-1, -1), 'CENTER'),     # centrar el texto
                ]

                tablaSubtotal.setStyle(TableStyle(estilos))
                ancho_tabla2, alto_tabla2 = tablaSubtotal.wrapOn(pdf, ancho, alto)
                ubicacionYTabla2 = ubicacionYTabla1 - alto_tabla2 - 20
                tablaSubtotal.drawOn(pdf, ancho - ancho_tabla2 - 30, ubicacionYTabla2)
        
        
            def definir_encabezados_anchos(modelo, campo_agrupado):
                #
                encabezados_y_anchos = {
                    'paciente': {
                        'encabezados': ['DNI', '# EXP', 'NOMBRE', 'F NAC.', 'SEXO','DIRECCION', 'F CREACION', 'USUARIO','F MODIFICAC.', 'USUARIO M'],
                        'anchos': [3.5 * cm, 1.7 * cm, 6.5 * cm, 2.2 * cm, 2 * cm,6.5 * cm, 3.5 * cm, 2.8 * cm,3.5 * cm,2.8 * cm]
                    },
                    'ingreso': {
                        'encabezados': ['F INGRESO', 'F EGRESO','USUARIO E','F SDGI','USUARIO S','DNI', '# EXP','NOMBRE','SERVICIO', 'ZONA'],
                        'anchos': [2.5 * cm, 2.5 * cm,2.8 * cm, 2.5 * cm,2.8 * cm,3.5 * cm, 1.7 * cm, 4.5 * cm,6 * cm, 3.4 *cm]
                    },
                    'atencion':{
                        'encabezados': ['NUM','F ATENCION','USUARIO C', 'F RECEPCION','USUARIO R','DNI', '# EXP','NOMBRE','SERVICIO'],
                        'anchos': [ 1.7 * cm,2.8 * cm, 2.8 * cm,2.8 * cm,2.8 * cm,3.5 * cm, 1.7 * cm, 6.5 * cm, 4.8 * cm,]
                    }
                }

                config = encabezados_y_anchos.get(modelo)

                if modelo == 'paciente':
                    if campo_agrupado in ['sector__aldea__municipio_id', 'sector__aldea__municipio__departamento_id']:
                        # quitar "DIRECCION" y su ancho (posición 5)
                        if config:
                            try:
                                idx = config['encabezados'].index('DIRECCION')
                                config['encabezados'].pop(idx)
                                config['anchos'].pop(idx)
                            except ValueError:
                                pass  # por si ya no está "DIRECCION"

                    if campo_agrupado in ['sexo']:
                        if config:
                            try:
                                idx = config['encabezados'].index('SEXO')
                                config['encabezados'].pop(idx)
                                config['anchos'].pop(idx)
                            except ValueError:
                                pass  # por si ya no está "SEXO"

                    if campo_agrupado in ['creado_por_id']:
                        if config:
                            try:
                                idx = config['encabezados'].index('USUARIO')
                                config['encabezados'].pop(idx)
                                config['anchos'].pop(idx)
                            except ValueError:
                                pass  # por si ya no está "SEXO"

                    if campo_agrupado in ['modificado_por_id', 'estado','tipo_id', 'zona_id']:
                        if config:
                            try:
                                idx = config['encabezados'].index('USUARIO M')
                                config['encabezados'].pop(idx)
                                config['anchos'].pop(idx)
                            except ValueError:
                                pass  # por si ya no está "SEXO"
                

                elif modelo == 'ingreso':
                    pass


                return config
            

            def construir_fila(modelo, reg, encabezados):
                fila = []

                if modelo == 'paciente':
                    for col in encabezados:
                        if col == 'DNI':
                            fila.append(formatear_dni(reg['dni']) if reg['dni'] else '----')
                        elif col == '# EXP':
                            fila.append(formatear_expediente(reg['expediente_numero']))
                        elif col == 'NOMBRE':
                            fila.append(formatear_nombre_completo(
                                reg["primer_nombre"],
                                reg["segundo_nombre"],
                                reg["primer_apellido"],
                                reg["segundo_apellido"],
                            )[:27])
                        elif col == 'F NAC.':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_nacimiento'], False))
                        elif col == 'SEXO':
                            fila.append('HOMBRE' if reg['sexo'] == 'H' else 'MUJER')
                        elif col == 'DIRECCION':
                            fila.append(
                                f"{reg['sector__aldea__municipio__departamento__nombre_departamento']} - {reg['sector__aldea__municipio__nombre_municipio']}"[:30]
                            )
                        elif col == 'F CREACION':
                            fila.append(str(formatear_fecha2(reg['fecha_creado'])).upper())
                        elif col == 'USUARIO':
                            fila.append(reg['creado_por__username'][:12])
                        elif col == 'F MODIFICAC.':
                            fila.append(str(formatear_fecha2(reg['fecha_modificado'])).upper())
                        elif col == 'USUARIO M':
                            fila.append(reg['modificado_por__username'][:12])
                        else:
                            fila.append('')  # fallback

                elif modelo == 'ingreso':
                    for col in encabezados:
                        if col == 'F INGRESO':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_ingreso'], False))
                        elif col == 'F EGRESO':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_egreso'], False))
                        elif col == 'F SDGI':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_recepcion_sdgi'], False))
                        elif col == 'DNI':
                            fila.append(formatear_dni(reg['paciente__dni']) if reg['paciente__dni'] else '----')
                        elif col == '# EXP':
                            fila.append(formatear_expediente(reg['paciente__expediente_numero']))
                        elif col == 'NOMBRE':
                            fila.append(f"{reg['paciente__primer_nombre']} {reg['paciente__primer_apellido']}"[:18])
                        elif col == 'SERVICIO':
                            fila.append(f"{reg['sala__servicio__nombre_servicio']}, {reg['sala__nombre_sala']}"[:26])
                        elif col == 'USUARIO E':
                            user = reg['recepcion_detalles_sala__recepcion__recibido_por__username'][:12] if reg['recepcion_detalles_sala__recepcion__recibido_por__username'] else ''
                            fila.append(user)
                        elif col == 'USUARIO S':
                            user = reg['recepcion_detalles_sdgi__recepcion__recibido_por__username'][:12] if reg['recepcion_detalles_sdgi__recepcion__recibido_por__username'] else ''
                            fila.append(user)
                        elif col == 'ZONA':
                            fila.append(reg['zona__nombre_zona'])
                        else:
                            fila.append('')  # fallback


                elif modelo == 'atencion':
                    for col in encabezados:
                        if col == 'NUM':
                            fila.append(formatear_expediente(reg['id']))
                        elif col == 'F ATENCION':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_atencion'], False))
                        elif col == 'USUARIO C':
                            user = reg['creado_por__username'][:12]
                            fila.append(user)
                        elif col == 'F RECEPCION':
                            fila.append(formatear_fecha_dd_mm_yyyy(reg['fecha_recepcion'], False))
                        elif col == 'USUARIO R':
                            user = reg['recepcion_detalles_atencion__recepcion__recibido_por__username'][:12] if reg['recepcion_detalles_atencion__recepcion__recibido_por__username'] else ''
                            fila.append(user)
                        elif col == 'DNI':
                            fila.append(formatear_dni(reg['paciente__dni']) if reg['paciente__dni'] else '----')
                        elif col == '# EXP':
                            fila.append(formatear_expediente(reg['paciente__expediente_numero']))
                        elif col == 'NOMBRE':
                            fila.append(formatear_nombre_completo(
                                reg["paciente__primer_nombre"],
                                reg["paciente__segundo_nombre"],
                                reg["paciente__primer_apellido"],
                                reg["paciente__segundo_apellido"],
                            )[:27])
                        elif col == 'SERVICIO':
                            fila.append(f"{reg['area_atencion__servicio__nombre_corto']}, {reg['area_atencion__nombre_area_atencion']}"[:20])
                        else:
                            fila.append('')  
                
                return fila


            def formatear_valor_agrupado(modelo,campo_agrupacion, reg):
                """
                Devuelve el valor ya formateado para mostrar en la fila de agrupación
                """

                if campo_agrupacion == 'creado_por_id' :
                        return f"{reg['creado_por__username']} - {reg['creado_por__first_name']} {reg['creado_por__last_name']}"

                elif campo_agrupacion == 'modificado_por_id' :
                    return f"{reg['modificado_por__username']} - {reg['modificado_por__first_name']} {reg['modificado_por__last_name']}"


                if modelo == 'paciente':
                    if campo_agrupacion == 'sector__aldea__municipio_id':
                        depto = reg['sector__aldea__municipio__departamento__nombre_departamento']
                        muni = reg['sector__aldea__municipio__nombre_municipio']
                        return f"{muni} - {depto}"

                    elif campo_agrupacion == 'sector__aldea__municipio__departamento_id':
                        return reg['sector__aldea__municipio__departamento__nombre_departamento']

                    
                    elif campo_agrupacion == 'tipo_id':
                        return reg['tipo__descripcion_tipo']
                    
                    elif campo_agrupacion == 'zona_id':
                        return reg['zona__nombre_zona']
                    
                    elif campo_agrupacion == 'estado':
                        # Mapeo de estados
                        estado_map = {
                            "A": "ACTIVO",
                            "P": "PASIVO",
                            "I": "INACTIVO"
                        }
                        return estado_map.get(reg['estado'], reg['estado'])


                    elif campo_agrupacion == 'sexo':
                        return 'HOMBRE' if reg['sexo'] == 'H' else 'MUJER'

                                    
                    else:
                        # fallback: lo devuelve tal cual
                        return reg.get(campo_agrupado, '----')


                if modelo == 'ingreso':
                    if campo_agrupacion == 'sala__servicio_id':
                        return reg['sala__servicio__nombre_servicio']
                    if campo_agrupacion == 'sala_id':
                        return f"{reg['sala__nombre_sala']}  {reg['sala__servicio__nombre_servicio']}"
                    if campo_agrupacion == 'paciente__sector__aldea__municipio__departamento_id':
                        return f"{reg['paciente__sector__aldea__municipio__departamento__nombre_departamento']}"


                if modelo == 'atencion':
                    if campo_agrupacion == 'area_atencion__servicio_id':
                        return reg['area_atencion__servicio__nombre_servicio']
                    if campo_agrupacion == 'area_atencion_id':
                        return f"{reg['area_atencion__nombre_area_atencion']}, {reg['area_atencion__servicio__nombre_corto']}"
                    if campo_agrupacion == 'paciente__sector__aldea__municipio__departamento_id':
                        return reg['paciente__sector__aldea__municipio__departamento__nombre_departamento'] 
                    
                else:
                    return reg.get(campo_agrupado, '----')
                
                
            # --- Estilos generales de la tabla ---
            estilosGenerales = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

                # Encabezado: fondo negro con texto blanco
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

                # Líneas internas
                ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.grey),
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.grey),

                # Línea de cierre en la última fila
                ('LINEBELOW', (0, -1), (-1, -1), 4, colors.black),

                # Espaciado vertical
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

            ]
        
            #agrupacion por campo en especifico

            #construir las paginas segun la canitdad de data
            conteo_campo_agrupacion = {}  
            total_general = 0
            config = definir_encabezados_anchos(
                    reporte_criterios['modelo'], 
                    reporte_criterios['agrupacion']
                )

            encabezados = config['encabezados']
            anchos = config['anchos']
            
            reporte_detalle = [encabezados.copy()]
            fila_actual = 1 
            campo_agrupado_actual = None
            paginas = []
            estilosPaginas = []
            estiloPagina = []
            subtotal = 0
            contador_agrupaciones_pagina = 0  


            for reg in data:
                campo_agrupado = reg[f"{reporte_criterios['campo_agrupado']}"]

                # Cambio de grupo
                if campo_agrupado_actual != campo_agrupado:

                    # Insertar subtotal del grupo anterior, si existe
                    if campo_agrupado_actual is not None:
                        reporte_detalle.append([f'{formatear_valor_agrupado(reporte_criterios['modelo'],reporte_criterios["agrupacion"], prev_reg)} -- SUBTOTAL: {subtotal}'])
                        estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                        estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.whitesmoke))
                        estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                        estiloPagina.append(('ALIGN', (0, fila_actual), (-1, fila_actual), 'RIGHT'))
                        fila_actual += 1
                        subtotal = 0

                    # Fila de título de nueva agrupación con subtotal inicial
                    reporte_detalle.append([f'{formatear_valor_agrupado(reporte_criterios['modelo'],reporte_criterios["agrupacion"], reg)}'])
                    estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                    estiloPagina.append(('LINEBELOW', (0, fila_actual), (-1, fila_actual), 0.5, colors.grey))
                    estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.lightgrey))
                    estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                    estiloPagina.append(('TOPPADDING', (0, fila_actual), (-1, fila_actual), 5))
                    estiloPagina.append(('BOTTOMPADDING', (0, fila_actual), (-1, fila_actual), 2))
                    estiloPagina.append(('LEFTPADDING', (0, fila_actual), (-1, fila_actual), 25))
                    fila_actual += 1
                    campo_agrupado_actual = campo_agrupado
                    contador_agrupaciones_pagina += 1

                # Contar subtotal y total general
                subtotal += 1
                conteo_campo_agrupacion[campo_agrupado] = conteo_campo_agrupacion.get(campo_agrupado, 0) + 1
                total_general += 1
                prev_reg = reg  # Guardamos el último registro PREVIO

                # Fila de detalle
                fila = construir_fila(reporte_criterios['modelo'], reg, encabezados)
                reporte_detalle.append(fila)
                fila_actual += 1

                # Paginación
                if len(reporte_detalle) >= 18:
                    #si no hay ningun separador en pagina gregamos uno el correpondiente a toda la pagina
                    if contador_agrupaciones_pagina == 0:
                        reporte_detalle.insert(1, [f'{formatear_valor_agrupado(reporte_criterios['modelo'],reporte_criterios["agrupacion"], reg)}'])
                        estiloPagina.append(('SPAN', (0, 1), (-1, 1)))
                        estiloPagina.append(('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.grey))
                        estiloPagina.append(('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey))
                        estiloPagina.append(('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'))
                        estiloPagina.append(('TOPPADDING', (0, 1), (-1, 1), 5))
                        estiloPagina.append(('BOTTOMPADDING', (0, 1), (-1, 1), 2))
                        estiloPagina.append(('LEFTPADDING', (0, 1), (-1, 1), 25))
                    paginas.append(copy.deepcopy(reporte_detalle))
                    estilosPaginas.append(copy.deepcopy(estiloPagina))
                    estiloPagina.clear()
                    reporte_detalle.clear()
                    reporte_detalle = [encabezados.copy()]
                    fila_actual = 1
                    contador_agrupaciones_pagina = 0  

            # Subtotal del último grupo
            if campo_agrupado_actual is not None:
                reporte_detalle.append([f'{formatear_valor_agrupado(reporte_criterios['modelo'],reporte_criterios["agrupacion"], prev_reg)} -- SUBTOTAL: {subtotal}'])
                estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.whitesmoke))
                estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                estiloPagina.append(('ALIGN', (0, fila_actual), (-1, fila_actual), 'RIGHT'))
                fila_actual += 1

            # Últimas páginas
            if len(reporte_detalle) >= 1:
                paginas.append(copy.deepcopy(reporte_detalle))
                estilosPaginas.append(copy.deepcopy(estiloPagina))
                estiloPagina.clear()

            if len(paginas) != len(estilosPaginas):
                log_error(
                    f"Desajuste páginas vs estilos en reporte detallado "
                    f"modelo {reporte_criterios.get('modelo')}",
                    app=LogApp.REPORTE
                )
                raise ValueError("Error interno generando páginas del reporte")


            for i, (pagina, estilos_dinamicos) in enumerate(zip(paginas, estilosPaginas)):
                ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
                dibujar_titulo_reporte(pdf, ancho, alto)

                #tabla
                tabla = Table(pagina, colWidths=anchos)

                # Estilos generales + dinámicos
                estilosTabla = estilosGenerales.copy()
                estilosTabla.extend(estilos_dinamicos)  # Aquí usamos directamente los estilos por página

                tabla.setStyle(TableStyle(estilosTabla))

                ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
                ubicacionYTabla1 = alto - 100 - alto_tabla - 70
                tabla.drawOn(pdf, 60, ubicacionYTabla1)

                # Pie de página con paginación y usuario
                fechaActual = timezone.now()
                ReportePdfBaseService.dibujar_pie_pagina_legal_horizontal(
                    pdf, alto, ancho,
                    formatear_fecha(fechaActual),
                    reporte_criterios['usuario'],
                    reporte_criterios['usuario_nombre'],
                    i + 1, len(paginas))
                
                #agregar el total no nos vamos a complicar i hay mas de 15 lineas se agrea el resumido en la sigueitne paina
                if i == len(paginas) - 1:
                    # calcular espacio requerido
                    lineas_total = math.ceil(len(conteo_campo_agrupacion) / 3) + 1
                    lineas_disponibles = 20 - len(pagina)

                    if lineas_total > lineas_disponibles:
                        # no cabe, nueva página
                        pdf.showPage()
                        ReportePdfBaseService.dibujar_encabezado(pdf, ancho, y)
                        dibujar_titulo_reporte(pdf, ancho, alto)
                        ReportePdfBaseService.dibujar_pie_pagina_legal_horizontal(
                                pdf, alto, ancho,
                                formatear_fecha(fechaActual),
                                reporte_criterios['usuario'],
                                reporte_criterios['usuario_nombre'],
                                i + 1, len(paginas))
                        y_inicio = alto - 160
                        columnas = 8 if lineas_total > 18 else 6
                        dibujar_resumido(pdf, y_inicio, ancho, alto, conteo_campo_agrupacion, total_general, columnas)
                    else:
                        # cabe, dibujar en la misma página
                        dibujar_resumido(pdf, ubicacionYTabla1, ancho, alto, conteo_campo_agrupacion, total_general)
                
                if i < len(paginas) - 1:
                        pdf.showPage()

            pdf.save()
            return response
        except ValueError:
            raise

        except Exception:
            log_error(
                f"Error generando PDF detallado modelo {reporte_criterios.get('modelo')} "
                f"agrupado por {reporte_criterios.get('agrupacion')}",
                app=LogApp.REPORTE
            )
            raise
