from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from django.utils import timezone
from django.views import View
from reportlab.lib.units import inch, mm, cm
from reportlab.lib.colors import Color
from reportlab.platypus import Paragraph
from django.utils.translation import gettext as _
from django.http import HttpResponse

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
import copy
from django.views.generic import TemplateView

from core.services.recepcion_ingresos_service import RecepcionIngresoServiceSala, RecepcionIngresoServiceSDGI
from core.utils.utilidades_fechas import formatear_fecha, formatear_fecha_dd_mm_yyyy_hh_mm
from core.utils.utilidades_textos import  formatear_dni, formatear_expediente, formatear_nombre_completo
from usuario.permisos import verificar_permisos_usuario
from .views import dibujar_encabezado, dibujar_pie_pagina_carta




class reporte_detalle_recepcion_ingresos_sala(View):

    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos del usuario antes de continuar con la lógica de la vista
        usuario = request.user
        if not verificar_permisos_usuario(usuario, ['admin', 'digitador'], ['Admision']):
            return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

        return super().dispatch(request, *args, **kwargs)


    def get(self, request, recepcion_id):
        usuario = request.user


        if not recepcion_id:
            return JsonResponse({"error": "El ID de recepción es requerido."}, status=400)
    

        try:
            # Intentamos obtener la recepción
            recepcion = RecepcionIngresoServiceSala.definir_recepcion_ingreso_sala(recepcion_id)
            
            if not recepcion:
                return JsonResponse({"error": "No se encontró la recepción con ese ID."}, status=404)

            # Crear el servicio de recepción
            service = RecepcionIngresoServiceSala(recepcion)

            # Obtener los detalles de la recepción
            detalles = service.obtener_detalles_sala()

            if not detalles:
                return JsonResponse({"error": "No se encontraron detalles para esta recepción."}, status=404)

            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Recepcion-{recepcion.id}.pdf"'
            pdf = canvas.Canvas(response, pagesize=letter)
            pdf.setTitle(f"Recepcion Ingreso Sala-{recepcion.id}")
            ancho, alto = letter

            y = alto - 30  # Margen superior



            def dibujar_titulo_detalle_recepcion(pdf, ancho, alto):
                # Título
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawCentredString(ancho / 2, alto - 100, f"DETALLE DE RECEPCION DE EGRESO #{recepcion_id} (SALA)")
                

                # Línea gris suave
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 105, 584, alto - 105)

                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawRightString(112, alto - 130, f"NUMERO")
                pdf.drawRightString(190, alto - 130, f"FECHA")
                pdf.drawRightString(480, alto - 130, f"RESPONSABLE")

                
                # Dibuja fondo negro para los datos
                x = 60
                gris_claro = Color(0.8, 0.8, 0.8)
                pdf.setFillColor(colors.black)
                pdf.rect(x, alto - 160, 525, 25, fill=1, stroke=0)

                # Información de la recepción
                pdf.setFont("Helvetica", 11)
                pdf.setFillColor(colors.white)

                # Dibujar los datos de la recepción
                pdf.drawString(70, alto - 152, f"{recepcion_id}")
                pdf.drawString(150, alto - 152, f"{formatear_fecha(recepcion.fecha_recepcion).upper()}")
                usuario = f"{recepcion.recibido_por.username.upper()} - {recepcion.recibido_por.first_name.upper()} {recepcion.recibido_por.last_name.upper()}"
                pdf.drawString(390, alto - 152, usuario[:25])


                # Línea de separación
                pdf.line(60, alto - 175, 584, alto - 175)

            def dibujar_observaciones_y_subtotales(pdf, ubicacionYTabla1, alto_tabla, ancho, alto, conteo_por_sala, total_general):
                pdf.setFont("Helvetica-Bold", 12)
                pdf.setFillColor(colors.black)
                pdf.drawRightString(215, ubicacionYTabla1 - 30, "OBSERVACIONES")

                pdf.setFillColor(colors.lightgrey)
                pdf.rect(110, ubicacionYTabla1 - 95, 255, 60, fill=1, stroke=0)

                estilo_blanco = ParagraphStyle(
                    name='Blanco',
                    fontName='Helvetica',
                    fontSize=10,
                    textColor=colors.black,
                    alignment=TA_JUSTIFY,
                )

                if recepcion.observaciones:
                    texto = recepcion.observaciones
                else:
                    texto = "Sin observaciones"

                p = Paragraph(texto, estilo_blanco)
                width, height = p.wrap(230, 100)
                p.drawOn(pdf, 120, ubicacionYTabla1 - height - 40)

                # TABLA DE SUBTOTALES
                data_subtotal = []
                for sala, cantidad in conteo_por_sala.items():
                    data_subtotal.append([sala[:23], str(cantidad)])
                data_subtotal.append(["TOTAL", str(total_general)])

                tablaSubtotal = Table(data_subtotal, colWidths=[160, 40])
                tablaSubtotal.setStyle(TableStyle([
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ]))

                ancho_tabla2, alto_tabla2 = tablaSubtotal.wrapOn(pdf, ancho, alto)
                ubicacionYTabla2 = ubicacionYTabla1 - alto_tabla2 -20
                tablaSubtotal.drawOn(pdf, ancho - ancho_tabla2 - 30, ubicacionYTabla2)


            #Trabajar la data antes para ver cuantas paginas seran requeridas       
            estilosGenerales = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

                # Encabezado: fondo negro, texto blanco
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

                # Líneas verticales internas
                
                ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.grey),
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.grey),

                # Pie
                ('LINEBELOW', (0, -1), (-1, -1), 4, colors.black),  # línea inferior gruesa

                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]

            
            conteo_por_sala = {}
            total_general = 0
            encabezado = [["Fecha Ingreso", "Expediente", "DNI", "Nombre"]]
            data = encabezado.copy() # Encabezado
            fila_actual = 1
            sala_actual = None
            paginas = []
            estilosPaginas = []
            estiloPagina = []


            for reg in detalles:
                if reg["ingreso__sala__nombre_sala"] != sala_actual:
                    data.append(
                    [f"{reg['ingreso__sala__nombre_sala']} | {reg['ingreso__sala__servicio__nombre_corto']}", "", "", ""]) # fila de sala
                    estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                    estiloPagina.append(('LINEBELOW', (0, fila_actual), (-1, fila_actual), 0.5, colors.grey))
                    estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.lightgrey))
                    estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                    estiloPagina.append(('TOPPADDING', (0, fila_actual), (-1, fila_actual), 6))
                    estiloPagina.append(('BOTTOMPADDING', (0, fila_actual), (-1, fila_actual), 3))

                    estiloPagina.append(('LEFTPADDING', (0, fila_actual), (-1, fila_actual), 35))
                    fila_actual += 1
                    sala_actual = reg["ingreso__sala__nombre_sala"]
                
                #subtotales
                sala = reg["ingreso__sala__nombre_sala"]
                conteo_por_sala[sala] = conteo_por_sala.get(sala, 0) + 1
                total_general += 1
                data.append([
                        formatear_fecha_dd_mm_yyyy_hh_mm(reg["ingreso__fecha_ingreso"]), 
                        formatear_expediente(reg["expediente_numero"]), 
                        formatear_dni(reg["ingreso__paciente__dni"]), 
                        formatear_nombre_completo(
                            reg["ingreso__paciente__primer_nombre"],
                            reg["ingreso__paciente__segundo_nombre"],
                            reg["ingreso__paciente__primer_apellido"],
                            reg["ingreso__paciente__segundo_apellido"],
                        )
                        
                        ])
                fila_actual += 1
                if len(data) >= 18:
                    paginas.append(copy.deepcopy(data)) #la data      
                    estilosPaginas.append(copy.deepcopy(estiloPagina))
                    estiloPagina.clear()
                    data.clear()
                    data = encabezado.copy()
                    fila_actual = 1
                    
            
            if len(data) >= 1:
                paginas.append(copy.deepcopy(data))
                data.clear()
                estilosPaginas.append(copy.deepcopy(estiloPagina))#ojo aca puede ser que no tenga pues alberga los estilos unicamente para las salas
                estiloPagina.clear()


            if len(paginas) != len(estilosPaginas):
                raise ValueError(f"Desajuste: páginas={len(paginas)} y estilosPaginas={len(estilosPaginas)} no coinciden")


            for i, (pagina, estilos_dinamicos) in enumerate(zip(paginas, estilosPaginas)):

                # Dibujar encabezado
                dibujar_encabezado(pdf, ancho, y)        

                # Título
                dibujar_titulo_detalle_recepcion(
                    pdf, ancho, alto
                )

                # TABLA DE DETALLES 
                tabla = Table(pagina, colWidths=[3.5 * cm, 3 * cm, 3.5 * cm, 8.5 * cm])

                # Estilos generales + dinámicos
                estilosTabla = estilosGenerales.copy()
                estilosTabla.extend(estilos_dinamicos)  # Aquí usamos directamente los estilos por página

                tabla.setStyle(TableStyle(estilosTabla))

                ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
                ubicacionYTabla1 = alto - 100 - alto_tabla - 80
                tabla.drawOn(pdf, 60, ubicacionYTabla1)

                pdf.line(60, ubicacionYTabla1 -10, 584, ubicacionYTabla1 -10)

                if i == len(paginas) - 1:
                    pdf.setFillColor(colors.black)
                    dibujar_observaciones_y_subtotales(pdf,ubicacionYTabla1,ancho_tabla,ancho,alto,conteo_por_sala,total_general)
                
                fechaActual = timezone.now()
                dibujar_pie_pagina_carta(pdf, alto, ancho, formatear_fecha(fechaActual), usuario.username.upper(), f"{usuario.first_name.upper()} {usuario.last_name.upper()}", i + 1, len(paginas))

                if i < len(paginas) - 1:
                    pdf.showPage()
                    

            pdf.save()
            return response
            
        except Exception as e:
            # Capturar cualquier error inesperado
            return JsonResponse({"error": f"Hubo un error inesperado: {str(e)}"}, status=500)


class reporte_detalle_recepcion_ingresos_SDGI(View):

    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos del usuario antes de continuar con la lógica de la vista
        usuario = request.user
        if not verificar_permisos_usuario(usuario, ['admin', 'digitador'], ['Admision']):
            return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

        return super().dispatch(request, *args, **kwargs)


    def get(self, request, recepcion_id):
        usuario = request.user


        if not recepcion_id:
            return JsonResponse({"error": "El ID de recepción es requerido."}, status=400)
    

        try:
            # Intentamos obtener la recepción
            recepcion = RecepcionIngresoServiceSDGI.definir_recepcion_ingreso_sdgi(recepcion_id)
            
            if not recepcion:
                return JsonResponse({"error": "No se encontró la recepción con ese ID."}, status=404)

            # Crear el servicio de recepción
            service = RecepcionIngresoServiceSDGI(recepcion)

            # Obtener los detalles de la recepción
            detalles = service.obtener_detalles_sdgi()

            if not detalles:
                return JsonResponse({"error": "No se encontraron detalles para esta recepción."}, status=404)

            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Recepcion-{recepcion.id}.pdf"'
            pdf = canvas.Canvas(response, pagesize=letter)
            pdf.setTitle(f"Recepcion Ingreso SDGI-{recepcion.id}")
            ancho, alto = letter

            y = alto - 30  # Margen superior


            def dibujar_titulo_detalle_recepcion(pdf, ancho, alto):
                # Título
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawCentredString(ancho / 2, alto - 100, f"DETALLE DE RECEPCION DE EGRESO #{recepcion_id} (SDGI)")

                # Línea gris suave
                pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
                pdf.line(60, alto - 105, 584, alto - 105)

                pdf.setFont("Helvetica-Bold", 12)
                pdf.drawRightString(112, alto - 130, f"NUMERO")
                pdf.drawRightString(190, alto - 130, f"FECHA")
                pdf.drawRightString(480, alto - 130, f"RESPONSABLE")

                
                # Dibuja fondo negro para los datos
                x = 60
                gris_claro = Color(0.8, 0.8, 0.8)
                pdf.setFillColor(colors.black)
                pdf.rect(x, alto - 160, 525, 25, fill=1, stroke=0)

                # Información de la recepción
                pdf.setFont("Helvetica", 11)
                pdf.setFillColor(colors.white)

                # Dibujar los datos de la recepción
                pdf.drawString(70, alto - 152, f"{recepcion_id}")
                pdf.drawString(150, alto - 152, f"{formatear_fecha(recepcion.fecha_recepcion).upper()}")
                usuario = f"{recepcion.recibido_por.username.upper()} - {recepcion.recibido_por.first_name.upper()} {recepcion.recibido_por.last_name.upper()}"
                pdf.drawString(390, alto - 152, usuario[:25])


                # Línea de separación
                pdf.line(60, alto - 175, 584, alto - 175)

            def dibujar_observaciones_y_subtotales(pdf, ubicacionYTabla1, alto_tabla, ancho, alto, conteo_por_sala, total_general):
                pdf.setFont("Helvetica-Bold", 12)
                pdf.setFillColor(colors.black)
                pdf.drawRightString(215, ubicacionYTabla1 - 30, "OBSERVACIONES")

                pdf.setFillColor(colors.lightgrey)
                pdf.rect(110, ubicacionYTabla1 - 95, 255, 60, fill=1, stroke=0)

                estilo_blanco = ParagraphStyle(
                    name='Blanco',
                    fontName='Helvetica',
                    fontSize=10,
                    textColor=colors.black,
                    alignment=TA_JUSTIFY,
                )

                if recepcion.observaciones:
                    texto = recepcion.observaciones
                else:
                    texto = "Sin observaciones"

                p = Paragraph(texto, estilo_blanco)
                width, height = p.wrap(230, 100)
                p.drawOn(pdf, 120, ubicacionYTabla1 - height - 40)

                # TABLA DE SUBTOTALES
                data_subtotal = []
                for sala, cantidad in conteo_por_sala.items():
                    data_subtotal.append([sala[:23], str(cantidad)])
                data_subtotal.append(["TOTAL", str(total_general)])

                tablaSubtotal = Table(data_subtotal, colWidths=[160, 40])
                tablaSubtotal.setStyle(TableStyle([
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ]))

                ancho_tabla2, alto_tabla2 = tablaSubtotal.wrapOn(pdf, ancho, alto)
                ubicacionYTabla2 = ubicacionYTabla1 - alto_tabla2 -20
                tablaSubtotal.drawOn(pdf, ancho - ancho_tabla2 - 30, ubicacionYTabla2)


            #Trabajar la data antes para ver cuantas paginas seran requeridas       
            estilosGenerales = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

                # Encabezado: fondo negro, texto blanco
                ('BACKGROUND', (0, 0), (-1, 0), colors.black),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

                # Líneas verticales internas
                ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.grey),
                ('LINEAFTER', (0, 0), (-2, -1), 0.5, colors.grey),

                # Pie
                ('LINEBELOW', (0, -1), (-1, -1), 4, colors.black),  # línea inferior gruesa

                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]

            
            conteo_por_sala = {}
            total_general = 0
            encabezado = [["Fecha Ingreso","Fecha Egreso", "Exp #", "DNI", "Nombre"]]
            data = encabezado.copy() # Encabezado
            fila_actual = 1
            sala_actual = None
            paginas = []
            estilosPaginas = []
            estiloPagina = []


            for reg in detalles:
                if reg["ingreso__sala__nombre_sala"] != sala_actual:
                    data.append(
                    [f"{reg['ingreso__sala__nombre_sala']} | {reg['ingreso__sala__servicio__nombre_corto']}", "", "", "", ""]) # fila de sala
                    estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                    estiloPagina.append(('LINEBELOW', (0, fila_actual), (-1, fila_actual), 0.5, colors.grey))
                    estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.lightgrey))
                    estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                    estiloPagina.append(('TOPPADDING', (0, fila_actual), (-1, fila_actual), 6))
                    estiloPagina.append(('BOTTOMPADDING', (0, fila_actual), (-1, fila_actual), 3))
                    estiloPagina.append(('LEFTPADDING', (0, fila_actual), (-1, fila_actual), 35))
                    fila_actual += 1
                    sala_actual = reg["ingreso__sala__nombre_sala"]
                
                #subtotales
                sala = reg["ingreso__sala__nombre_sala"]
                conteo_por_sala[sala] = conteo_por_sala.get(sala, 0) + 1
                total_general += 1
                data.append([
                        formatear_fecha_dd_mm_yyyy_hh_mm(reg["ingreso__fecha_ingreso"]), 
                        formatear_fecha_dd_mm_yyyy_hh_mm(reg["ingreso__fecha_egreso"]), 
                        formatear_expediente(reg["expediente_numero"]), 
                        formatear_dni(reg["ingreso__paciente__dni"]), 
                        formatear_nombre_completo(
                            reg["ingreso__paciente__primer_nombre"],
                            reg["ingreso__paciente__segundo_nombre"],
                            reg["ingreso__paciente__primer_apellido"],
                            reg["ingreso__paciente__segundo_apellido"],
                        )[:33]
                        
                        ])
                fila_actual += 1

                if len(data) >= 18:
                    paginas.append(copy.deepcopy(data)) #la data      
                    estilosPaginas.append(copy.deepcopy(estiloPagina))
                    estiloPagina.clear()
                    data.clear()
                    data = encabezado.copy()
                    fila_actual = 1

                    
            if len(data) >= 1:
                paginas.append(copy.deepcopy(data))
                data.clear()
                estilosPaginas.append(copy.deepcopy(estiloPagina))#ojo aca puede ser que no tenga pues alberga los estilos unicamente para las salas
                estiloPagina.clear()

            if len(paginas) != len(estilosPaginas):
                raise ValueError(f"Desajuste: páginas={len(paginas)} y estilosPaginas={len(estilosPaginas)} no coinciden")


            for i, (pagina, estilos_dinamicos) in enumerate(zip(paginas, estilosPaginas)):

                # Dibujar encabezado
                dibujar_encabezado(pdf, ancho, y)        

                # Título
                dibujar_titulo_detalle_recepcion(
                    pdf, ancho, alto
                )

                # TABLA DE DETALLES 
                tabla = Table(pagina, colWidths=[3.2 * cm,3.2 * cm, 1.7 * cm, 3.2 * cm, 7.2 * cm])

                # Estilos generales + dinámicos
                estilosTabla = estilosGenerales.copy()
                estilosTabla.extend(estilos_dinamicos)  # Aquí usamos directamente los estilos por página

                tabla.setStyle(TableStyle(estilosTabla))

                ancho_tabla, alto_tabla = tabla.wrapOn(pdf, ancho, alto)
                ubicacionYTabla1 = alto - 100 - alto_tabla - 80
                tabla.drawOn(pdf, 60, ubicacionYTabla1)

                pdf.line(60, ubicacionYTabla1 -10, 584, ubicacionYTabla1 -10)

                if i == len(paginas) - 1:
                    pdf.setFillColor(colors.black)
                    dibujar_observaciones_y_subtotales(pdf,ubicacionYTabla1,ancho_tabla,ancho,alto,conteo_por_sala,total_general)
                
                fechaActual = timezone.now()
                dibujar_pie_pagina_carta(pdf, alto, ancho, formatear_fecha(fechaActual), usuario.username.upper(), f"{usuario.first_name.upper()} {usuario.last_name.upper()}", i + 1, len(paginas))

                if i < len(paginas) - 1:
                    pdf.showPage()
                    

            pdf.save()
            return response
        
        except Exception as e:
            # Capturar cualquier error inesperado
            return JsonResponse({"error": f"Hubo un error inesperado: {str(e)}"}, status=500)

