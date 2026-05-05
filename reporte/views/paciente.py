
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from ingreso.models import Ingreso
from paciente.models import Paciente
from django.contrib import messages
from django.utils import timezone
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch, mm, cm
from reportlab.platypus import Paragraph
from django.utils.translation import gettext as _
from core.services.expediente_service import ExpedienteService
from core.services.reporte.PDF.reporte_paciente_service import ReportePacienteService
from core.services.paciente_service import PacienteService
from core.utils.utilidades_textos import  formatear_dni ,formatear_nombre_completo, formatear_expediente
from core.utils.utilidades_fechas import formatear_fecha, formatear_hora, formatear_fecha_simple, obtener_edad_con_indicador
from usuario.permisos import verificar_permisos_usuario 
from .views import dibujar_encabezado, dibujar_pie_pagina_carta
from core.services.ingreso.ingreso_formatos_service import IngresoFormatosService
from usuario.permisos import verificar_permisos_usuario
from core.constants import permisos 
from django.http import HttpResponse


from django.views import View
from django.conf import settings
import os
import json


def reporte_hospitalizacion(request, ingreso_id):
    
    def obtener_nombre_completo(obj, campos):
        """Retorna el nombre completo combinando los campos especificados."""
        return " ".join(filter(None, [getattr(obj, campo, "") for campo in campos])).strip()

    def validar_extranjero_o_hondureno_con_pasaporte(tipo, nacionalidad):
        """
        Retorna True si es extranjero o si es hondureño con pasaporte.
        Retorna False si es hondureño con identificación válida (no pasaporte).
        
        tipo: int (ej. 2 = pasaporte)
        nacionalidad: int (1 = hondureño, otro = extranjero)
        """
        if nacionalidad != 1:
            return True  # Es extranjero
        if nacionalidad == 1 and tipo == 2:
            return True  # Hondureño usando pasaporte (inválido)
        return False  # Hondureño con documento válido

    try:
        ingreso_obj = Ingreso.objects.select_related(
            "acompaniante",
            "acompaniante__sector__aldea__municipio__departamento", 
            "sala__servicio", 
            "cama__sala__servicio", 
            "paciente__padre", 
            "paciente__madre",
            "paciente__sector__aldea__municipio__departamento",
            "creado_por",
            "modificado_por",
        ).get(id=ingreso_id)

        # ////// INFORMACIÓN DINÁMICA DEL INGRESO //////

        # --- Datos del paciente ---
        usuario = ingreso_obj.creado_por.username.upper() if ingreso_obj.creado_por else ""
        expediente = (
            str(ExpedienteService.obtener_expediente_activo_paciente(ingreso_obj.paciente.id).numero).zfill(7)
            if ingreso_obj.paciente else "0000000"
        )

        if ingreso_obj.paciente:
            tipo= ingreso_obj.paciente.tipo.id
            nacionalidad= ingreso_obj.paciente.nacionalidad.id
            nombres = obtener_nombre_completo(ingreso_obj.paciente, ["primer_nombre", "segundo_nombre"])
            apellidos = obtener_nombre_completo(ingreso_obj.paciente, ["primer_apellido", "segundo_apellido"])
            dni = ingreso_obj.paciente.dni or ""
            fechaNac = ingreso_obj.paciente.fecha_nacimiento
            mesNac = f"{fechaNac.month:02d}" if fechaNac else ""
            diaNac = f"{fechaNac.day:02d}" if fechaNac else ""

            orden_gemelar = ingreso_obj.paciente.orden_gemelar
            edad, edadT = obtener_edad_con_indicador(str(fechaNac))

            sexo = "1" if ingreso_obj.paciente.sexo == "H" else "2"

            estCivil = ingreso_obj.paciente.estado_civil.id if ingreso_obj.paciente.estado_civil else ""
            ocupacion = ingreso_obj.paciente.ocupacion.id if ingreso_obj.paciente.ocupacion else ""
            telefono_paciente = ingreso_obj.paciente.telefono or ""

            if ingreso_obj.paciente.sector:
                depto = ingreso_obj.paciente.sector.aldea.municipio.departamento.nombre_departamento
                muni = ingreso_obj.paciente.sector.aldea.municipio.nombre_municipio
                ubicacion = ingreso_obj.paciente.sector.nombre_sector
            else:
                depto, muni, ubicacion = "", "", ""
        else:
            tipo, nombres, apellidos, dni, fechaNac, mesNac, diaNac, edad, edadT = "","", "", "", "", "", "", "00", ""
            sexo, estCivil, ocupacion, telefono_paciente, depto, muni, ubicacion = "", "", "", "", "", "", ""


        # --- Datos del acompañante ---
        if ingreso_obj.acompaniante:
            nombre_contacto = obtener_nombre_completo(
                ingreso_obj.acompaniante, ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"]
            )
            telefono_contacto = ingreso_obj.acompaniante.telefono or ""

            if ingreso_obj.acompaniante.sector:
                direccion_contacto = (
                    f"{getattr(ingreso_obj.acompaniante.sector.aldea.municipio.departamento, 'nombre_departamento', '')} "
                    f"{getattr(ingreso_obj.acompaniante.sector.aldea.municipio, 'nombre_municipio', '')} "
                    f"{getattr(ingreso_obj.acompaniante.sector, 'nombre_sector', '')}"
                )[:38].strip()
            else:
                direccion_contacto = ""
        else:
            nombre_contacto, telefono_contacto, direccion_contacto = "", "", ""

        # --- Datos de los padres ---
        if ingreso_obj.paciente and ingreso_obj.paciente.padre:
            if ingreso_obj.paciente.padre.paciente_ref:
                padre = Paciente.objects.get(id=ingreso_obj.paciente.padre.paciente_ref_id)
                nombrePadre = obtener_nombre_completo(padre, ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"])
            else:
                padre =  ingreso_obj.paciente.padre
                nombrePadre = obtener_nombre_completo(padre, ["nombre1", "nombre2", "apellido1", "apellido2"])
            dniPadre = formatear_dni(padre.dni) or ""
        else:
            nombrePadre, dniPadre = "", ""

        if ingreso_obj.paciente and ingreso_obj.paciente.madre:
            if ingreso_obj.paciente.madre.paciente_ref:
                madre = Paciente.objects.get(id=ingreso_obj.paciente.madre.paciente_ref_id)
                nombreMadre = obtener_nombre_completo(madre, ["primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido"])
            else: 
                madre =  ingreso_obj.paciente.madre
                nombreMadre = obtener_nombre_completo(madre, ["nombre1", "nombre2", "apellido1", "apellido2"])
            dniMadre = formatear_dni(madre.dni) or ""
        else:
            nombreMadre, dniMadre = "", ""

        # --- Información del ingreso ---
        
        zonaIngreso = ingreso_obj.zona.codigo if ingreso_obj.zona else ""
        if zonaIngreso == 4: # permutamos la zona labor y parto a Emgernecia 
            zonaIngreso = 2

        


        sala = ingreso_obj.sala.nombre_sala if ingreso_obj.sala else ""
        servicio = (
            ingreso_obj.cama.sala.servicio.nombre_servicio if ingreso_obj.cama else
            ingreso_obj.sala.servicio.nombre_servicio if ingreso_obj.sala else ""
        )
        idservicio = (
            ingreso_obj.cama.sala.servicio_id if ingreso_obj.cama else
            ingreso_obj.sala.servicio_id if ingreso_obj.sala else ""
        )


        fechaIngreso = timezone.localtime(ingreso_obj.fecha_ingreso) or ""

        
        
        cama = str(ingreso_obj.cama.numero_cama) if ingreso_obj.cama else ""
        mesIngreso = f"{fechaIngreso.month:02d}" if fechaIngreso else ""
        diaIngreso = f"{fechaIngreso.day:02d}" if fechaIngreso else ""
        horaIngreso = f"{formatear_hora(fechaIngreso)}" if fechaIngreso else ""
        


        # data del reporte
        updated_local = timezone.localtime(timezone.now())
        fechaInpre = formatear_fecha(updated_local)
            
    except Exception as e:
        print(f"errror {str(e)}")
        messages.error(request, f"Se produjo un error al procesar el expediente: {str(e)}")
    


    if fechaIngreso:
        fecha_ingreso_str = fechaIngreso.strftime("%Y-%m-%d")
    nombre_paciente = f"{nombres} {apellidos}".strip().replace(" ", "_") 
    nombre_archivo = f"reporte_ingreso_{nombre_paciente}_{fecha_ingreso_str}.pdf"


    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'

    pdf = canvas.Canvas(response, pagesize=letter)
    pdf.setTitle(f"Reporte de Hospitalización - {nombre_paciente}")
    ancho, alto = letter
    inicioIzquierda = 30
    espacioColumna = 8.5

    # Título centrado
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(ancho / 2, alto - 30, "HOJA DE HOSPITALIZACIÓN")

    # Tres líneas de texto pequeñas a la izquierda
    pdf.setFont("Helvetica-Bold", 6)
    pdf.drawString(inicioIzquierda, alto - 22, "SECRETARÍA DE SALUD")
    pdf.drawString(inicioIzquierda, alto - 29, "DEPARTAMENTO DE ESTADÍSTICA")
    pdf.drawString(inicioIzquierda, alto - 36, "HONDURAS, C.A") 

    #codigo del formato
    # Dibujar el cuadrado
    x = ancho - 450  # Coordenada x del cuadrado
    y = alto - 36   # Coordenada y del cuadrado

    pdf.setFillColorRGB(0, 0, 0)  # Color amarillo
    pdf.rect(x, y, 32, 12, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(ancho-449,alto-33,"HH-2005")

    # Genera 64 filas vacías con 66 columnas
    datos = [[""] * 66 for _ in range(63)]

    colWidths = [7] + [espacioColumna] * 64 + [7]

    rowHeights = [
    12, 10, 10,   # Bloque 1
    12, 10, 10,   # Bloque 2
    13, 11, 11, 12,  # Bloque 3
    12, 10, 10,   # Bloque 4
    12, 10, 10,   # Bloque 5
    13, 10, 10,   # Bloque 6
    12, 11, 11, 5,   # Bloque 7
    4, 12, 14, 4,  # Bloque 8
    11, 11, 11, 11, 11, 5,  # Bloque 9
    12, 11, 12,   # Bloque 10
    12, 13, 13, 13, 13, 10, 12, 13, 13, 13, 13,  # Bloque 11
    12, 11, 11, 7,   # Bloque 12
    12, 12, 11, 11, 12, 12, 12, 12, 12, 12, 12, 10  # Bloque 13
    ]

    tabla = Table(datos, colWidths=colWidths, rowHeights=rowHeights)



    estilo = [
        #quitamos el borde de la tabla
        ('GRID', (0, 0), (-1, -1), .1, colors.Color(1, 1, 1)),
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),                # Fuente para toda la tabla
        ('FONTSIZE', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Centra el texto horizontalmente
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Centra el texto verticalmente

        #primerra fila historia clinica
        #bordes externos de la primera fila
        ('LINEAFTER', (65, 0), (65, 63), .1, colors.black), 
        ('LINEBEFORE', (0, 0), (0, 63), .1, colors.black),

        #primera fila
        ('LINEABOVE', (0, 0), (65, 0), .1, colors.black),
        ('LINEBELOW', (0, 2), (65, 2), .1, colors.black),  

        #combinar las celdas para la numeracion de historia clinica
        ('SPAN', (63, 1), (64, 2)),
        ('SPAN', (61, 1), (62, 2)),
        ('SPAN', (59, 1), (60, 2)),
        ('SPAN', (57, 1), (58, 2)),
        ('SPAN', (55, 1), (56, 2)),
        ('SPAN', (53, 1), (54, 2)),
        ('SPAN', (51, 1), (52, 2)),
        ('SPAN', (49, 1), (50, 2)),
        ('SPAN', (47, 1), (48, 2)),
        ('SPAN', (45, 1), (46, 2)),
        ('SPAN', (43, 1), (44, 2)),
        ('SPAN', (41, 1), (42, 2)),     
        ('GRID', (41, 1), (64, 2), .2, colors.black),  

        #segunda fila 
        ('LINEBELOW', (0, 5), (65, 5), .1, colors.black), 
    ]

    # reglas condicionales
    if not validar_extranjero_o_hondureno_con_pasaporte(tipo, nacionalidad):
        estilo += [
            ('SPAN', (37, 4), (38, 5)),
            ('SPAN', (39, 4), (40, 5)),
            ('SPAN', (41, 4), (42, 5)),
            ('SPAN', (43, 4), (44, 5)),
            ('SPAN', (45, 4), (45, 5)),  # guion
            ('SPAN', (46, 4), (47, 5)),
            ('SPAN', (48, 4), (49, 5)),
            ('SPAN', (50, 4), (51, 5)),
            ('SPAN', (52, 4), (53, 5)),
            ('SPAN', (54, 4), (54, 5)),  # guion
            ('SPAN', (55, 4), (56, 5)),
            ('SPAN', (57, 4), (58, 5)),
            ('SPAN', (59, 4), (60, 5)),
            ('SPAN', (61, 4), (62, 5)),
            ('SPAN', (63, 4), (64, 5)),
            ('GRID', (37, 4), (64, 5), .2, colors.black),
        ]
    else:
        estilo += [
            ('SPAN', (37, 4), (64, 5)),  # EN CASO QUE SEA EXTRANJERO O NACIONAL CON PASAPORTE
            ('GRID', (37, 4), (64, 5), .2, colors.black),
        ]


    estilo += [
        #TERCERA FILA
        ('LINEBELOW', (0, 9), (65, 9), .2, colors.black),  
        ('SPAN', (1, 7), (3, 8)),
        ('GRID', (1, 7), (3, 8), .1, colors.black),
        ('SPAN', (5, 7), (7, 8)),
        ('GRID', (5, 7), (7, 8), .1, colors.black),

        ('SPAN', (9, 7), (12, 8)),
        ('GRID', (9, 7), (12, 8), .1, colors.black),

        ('SPAN', (14, 7), (16, 8)),
        ('GRID', (14, 7), (16, 8), .1, colors.black),

        ('SPAN', (18, 7), (19, 8)),
        ('GRID', (18, 7), (19, 8), .1, colors.black),

        ('SPAN', (26, 7), (27, 8)),
        ('GRID', (26, 7), (27, 8), .1, colors.black),

        ('SPAN', (35, 7), (36, 8)),
        ('GRID', (35, 7), (36, 8), .1, colors.black),

        ('SPAN', (50, 7), (51, 8)),
        ('GRID', (50, 7), (51, 8), .1, colors.black),


        #CUARTA BLOQUE
        ('SPAN', (0, 10), (18, 12)),
        ('SPAN', (19, 10), (36, 12)),
        ('SPAN', (37, 10), (-1, 12)),


        #QUINTA BLOQUE
        ('SPAN', (0, 13), (19, 15)),
        ('SPAN', (20, 13), (50, 15)),
        ('SPAN', (51, 13), (-1, 15)),


        #sexta BLOQUE
        ('SPAN', (0, 16), (32, 18)),
        ('SPAN', (33, 16), (-1, 18)),
        ('GRID', (0, 10), (-1, 18), .1, colors.black),


        #SIETE BLOQUE
        ('LINEBELOW', (0, 22), (-1, 22), .2, colors.black), 
        
        ('SPAN', (1, 20), (2, 21)),
        ('GRID', (1, 20), (2, 21), .1, colors.black), 

        ('SPAN', (13, 19), (37, 19)),
        

        ('SPAN', (13, 20), (23, 20)),
        ('SPAN', (24, 20), (37, 20)),

        ('SPAN', (13, 21), (23, 22)),
        ('SPAN', (24, 21), (37, 22)),
        ('GRID', (13, 19), (37, 22), .1, colors.black),


        ('SPAN', (40, 20), (42, 21)),
        ('GRID', (40, 20), (42, 21), .1, colors.black),

        ('SPAN', (46, 20), (48, 21)),
        ('GRID', (46, 20), (48, 21), .1, colors.black),

        ('SPAN', (52, 20), (55, 21)),
        ('GRID', (52, 20), (55, 21), .1, colors.black),

        ('SPAN', (60, 20), (64, 21)),
        ('GRID', (60, 20), (64, 21), .1, colors.black),


        #OCHO BLOQUE


        ('SPAN', (10, 24), (56, 24)),
        ('SPAN', (10, 25), (56, 25)),
        ('LINEBELOW', (10, 24), (56, 25), .1, colors.black),



        ('SPAN', (58, 23), (59, 24)),
        ('SPAN', (60, 23), (61, 24)),
        ('SPAN', (62, 23), (63, 24)),
        ('SPAN', (64, 23), (65, 24)),

        ('SPAN', (58, 25), (59, 26)),
        ('SPAN', (60, 25), (61, 26)),
        ('SPAN', (62, 25), (63, 26)),
        ('SPAN', (64, 25), (65, 26)),

        ('GRID', (58, 23), (65, 26), .1, colors.black),


        #nueve bloque
        ('SPAN', (0, 27), (37, 32)),
        
        ('SPAN', (38, 27), (-1, 32)),

        ('GRID', (0, 27), (-1, 32), .1, colors.black),


        #diez bloque
        ('SPAN', (0, 33), (20, 33)),

        ('SPAN', (0, 34), (10, 34)),
        ('SPAN', (0, 35), (10, 35)),

        ('SPAN', (11, 34), (20, 34)),
        ('SPAN', (11, 35), (20, 35)),


        ('SPAN', (21, 33), (32, 33)),

        ('SPAN', (21, 34), (24, 34)),
        ('SPAN', (25, 34), (28, 34)),
        ('SPAN', (29, 34), (32, 34)),

        ('SPAN', (21, 35), (24, 35)),
        ('SPAN', (25, 35), (28, 35)),
        ('SPAN', (29, 35), (32, 35)),


        ('SPAN', (33, 33), (53, 33)),

        ('SPAN', (33, 34), (43, 34)),
        ('SPAN', (33, 35), (43, 35)),

        ('SPAN', (44, 34), (53, 34)),
        ('SPAN', (44, 35), (53, 35)),
        

        ('SPAN', (54, 33), (-1, 33)),

        ('SPAN', (54, 34), (57, 34)),
        ('SPAN', (58, 34), (61, 34)),
        ('SPAN', (62, 34), (-1, 34)),

        ('SPAN', (54, 35), (57, 35)),
        ('SPAN', (58, 35), (61, 35)),
        ('SPAN', (62, 35), (-1, 35)),

        ('GRID', (0, 33), (-1, 35), .1, colors.black),


        #once bloque 
        ('SPAN', (7, 37), (54, 37)),
        ('LINEBELOW', (7, 37), (54, 37), .1, colors.black),

        ('SPAN', (3, 38), (54, 38)), 
        ('SPAN', (3, 39), (54, 39)), 
        ('SPAN', (3, 40), (54, 40)), 
        ('LINEBELOW', (3, 38), (54, 40), .1, colors.black),

        
        ('SPAN', (55, 36), (64, 36)),

        ('SPAN', (55, 37), (56, 37)),
        ('SPAN', (57, 37), (58, 37)),
        ('SPAN', (59, 37), (60, 37)),
        ('SPAN', (61, 37), (62, 37)),
        ('SPAN', (63, 37), (64, 37)),

        ('SPAN', (55, 38), (56, 38)),
        ('SPAN', (57, 38), (58, 38)),
        ('SPAN', (59, 38), (60, 38)),
        ('SPAN', (61, 38), (62, 38)),
        ('SPAN', (63, 38), (64, 38)),

        ('SPAN', (55, 39), (56, 39)),
        ('SPAN', (57, 39), (58, 39)),
        ('SPAN', (59, 39), (60, 39)),
        ('SPAN', (61, 39), (62, 39)),
        ('SPAN', (63, 39), (64, 39)),

        ('SPAN', (55, 40), (56, 40)),
        ('SPAN', (57, 40), (58, 40)),
        ('SPAN', (59, 40), (60, 40)),
        ('SPAN', (61, 40), (62, 40)),
        ('SPAN', (63, 40), (64, 40)),

        ('GRID', (55, 36), (64, 40), .1, colors.black),

        ('SPAN', (7, 43), (43, 43)),
        ('LINEBELOW', (7, 43), (43, 43), .1, colors.black),

        ('SPAN', (3, 44), (43, 44)), 
        ('SPAN', (3, 45), (43, 45)), 
        ('SPAN', (3, 46), (43, 46)), 
        ('LINEBELOW', (3, 44), (43, 46), .1, colors.black),


        ('SPAN', (46, 42), (48, 42)),
        ('SPAN', (49, 42), (51, 42)),
        ('SPAN', (52, 42), (54, 42)),

        ('SPAN', (46, 43), (48, 43)),
        ('SPAN', (49, 43), (51, 43)),
        ('SPAN', (52, 43), (54, 43)),

        ('SPAN', (46, 44), (48, 44)),
        ('SPAN', (49, 44), (51, 44)),
        ('SPAN', (52, 44), (54, 44)),

        ('SPAN', (46, 45), (48, 45)),
        ('SPAN', (49, 45), (51, 45)),
        ('SPAN', (52, 45), (54, 45)),

        ('SPAN', (46, 46), (48, 46)),
        ('SPAN', (49, 46), (51, 46)),
        ('SPAN', (52, 46), (54, 46)),

        ('GRID', (46, 42), (54, 46), .1, colors.black),


        ('SPAN', (57, 42), (64, 42)),
        ('SPAN', (57, 43), (58, 43)),
        ('SPAN', (59, 43), (60, 43)),
        ('SPAN', (61, 43), (62, 43)),
        ('SPAN', (63, 43), (64, 43)),

        ('SPAN', (57, 44), (58, 44)),
        ('SPAN', (59, 44), (60, 44)),
        ('SPAN', (61, 44), (62, 44)),
        ('SPAN', (63, 44), (64, 44)),

        ('SPAN', (57, 45), (58, 45)),
        ('SPAN', (59, 45), (60, 45)),
        ('SPAN', (61, 45), (62, 45)),
        ('SPAN', (63, 45), (64, 45)),

        ('SPAN', (57, 46), (58, 46)),
        ('SPAN', (59, 46), (60, 46)),
        ('SPAN', (61, 46), (62, 46)),
        ('SPAN', (63, 46), (64, 46)),

        ('GRID', (57, 42), (64, 46), .1, colors.black),

        ('LINEBELOW', (0, 46), (-1, 46), .1, colors.black),


        #doce bloque 
        ('SPAN', (3, 48), (5, 49)),
        ('GRID', (3, 48), (5, 49), .1, colors.black),

        ('SPAN', (22, 48), (24, 49)),
        ('GRID', (22, 48), (24, 49), .1, colors.black),
        #REFERIDO A
        ('SPAN', (41, 47), (57, 47)),
        ('SPAN', (41, 48), (57, 48)),
        ('SPAN', (41, 49), (57, 49)),
        ('LINEBELOW', (41, 47), (57, 49), .1, colors.black),
        #AUTOPSIA
        ('SPAN', (59, 47), (64, 47)),
        ('SPAN', (59, 48), (64, 48)),
        ('SPAN', (59, 49), (61, 49)),
        ('SPAN', (62, 49), (64, 49)),
        ('GRID', (59, 47), (64, 49), .1, colors.black),

        ('LINEBELOW', (0, 50), (-1, 50), .1, colors.black),

        #trece bloque  final
        ('SPAN', (0, 51), (-1, 51)),
        ('SPAN', (0, 52), (24, 56)),
        ('GRID', (0, 52), (24, 56), .1, colors.black),

        ('SPAN', (25, 52), (-1, 52)),
        ('SPAN', (25, 53), (26, 54)),

        ('SPAN', (27, 53), (42, 53)),
        ('SPAN', (43, 53), (58, 53)),

        ('SPAN', (59, 53), (-1, 54)),

        ('SPAN', (27, 54), (34, 54)),
        ('SPAN', (35, 54), (42, 54)),

        ('SPAN', (43, 54), (50, 54)),
        ('SPAN', (51, 54), (58, 54)),

        #-----
        ('SPAN', (25,55), (26, 56)),
        ('SPAN', (27,55), (34, 56)),
        ('SPAN', (35,55), (42, 56)),
        ('SPAN', (43,55), (50, 56)),
        ('SPAN', (51,55), (58, 56)),
        ('SPAN', (59,55), (65, 56)),

        #-----
        ('SPAN', (25,57), (26, 58)),
        ('SPAN', (27,57), (34, 58)),
        ('SPAN', (35,57), (42, 58)),
        ('SPAN', (43,57), (50, 58)),
        ('SPAN', (51,57), (58, 58)),
        ('SPAN', (59,57), (65, 58)),

        #-----
        ('SPAN', (25,59), (26, 60)),
        ('SPAN', (27,59), (34, 60)),
        ('SPAN', (35,59), (42, 60)),
        ('SPAN', (43,59), (50, 60)),
        ('SPAN', (51,59), (58, 60)),
        ('SPAN', (59,59), (65, 60)),

        ('SPAN', (25,61), (26, 62)),
        ('SPAN', (27,61), (34, 62)),
        ('SPAN', (35,61), (42, 62)),
        ('SPAN', (43,61), (50, 62)),
        ('SPAN', (51,61), (58, 62)),
        ('SPAN', (59,61), (65, 62)),

        ('GRID', (25, 52), (65, 62), .1, colors.black),

        ('SPAN', (19,58), (23, 58)),
        ('SPAN', (19,59), (23, 59)),
        ('SPAN', (19,60), (23, 60)),
        ('SPAN', (19,61), (23, 61)),
        ('GRID', (19, 58), (23, 61), .1, colors.black),

        ('LINEBELOW', (0, 62), (24, 62), .1, colors.black),

    ]


    
    # Estilo de la tabla
    # luego, crear el estilo de tabla
    table_style = TableStyle(estilo)
    
    tabla.setStyle(table_style)

    # Posicionar la tabla
    tabla.wrapOn(pdf, ancho, alto)
    tabla.drawOn(pdf, inicioIzquierda, alto - 734)



    # Dibujar las titulos de celdas manualmente
    pdf.setFont("Helvetica", 8)
    
    #ubicaciones generales
    LonXprimerEle = inicioIzquierda + 7

    # bloque1 
    Altbloq1 = alto - 48
    pdf.drawString(LonXprimerEle, Altbloq1, "ESTABLECIMIENTO")
    pdf.drawString(LonXprimerEle + espacioColumna*30 ,Altbloq1, "CODIGO")
    pdf.drawString(LonXprimerEle + espacioColumna*47,Altbloq1, "N° DE HISTORIA CLÍNICA")

    # bloque2
    Altbloq2 = alto - 81
    pdf.drawString(LonXprimerEle, Altbloq2, "PRIMER APELLIDO")
    pdf.drawString(LonXprimerEle + espacioColumna*9+6, Altbloq2, "SEGUNDO APELLIDO")
    pdf.drawString(LonXprimerEle + espacioColumna*25, Altbloq2, "NOMBRES")

    if not (validar_extranjero_o_hondureno_con_pasaporte(tipo,nacionalidad)):
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(LonXprimerEle + espacioColumna*44+2, Altbloq2 -15, "-")
        pdf.drawString(LonXprimerEle + espacioColumna*53+2, Altbloq2 -15, "-")

    pdf.setFont("Helvetica", 8)
    # bloque3
    Altbloq3 = alto - 112
    #ETIQUETAS SUPERARIORES
    pdf.drawString(LonXprimerEle, Altbloq3, "FECHA DE NACIMIENTO")
    pdf.drawString(LonXprimerEle + espacioColumna*13, Altbloq3, "EDAD")
    pdf.drawString(LonXprimerEle + espacioColumna*25, Altbloq3, "SEXO")
    pdf.drawString(LonXprimerEle + espacioColumna*34, Altbloq3, "ESTADO CIVIL")
    pdf.drawString(LonXprimerEle + espacioColumna*49, Altbloq3, "OCUPACIÓN")

    #ETIQUETAS INFERIORES
    pdf.drawString(LonXprimerEle+6, Altbloq3 - 35, "DIA")
    pdf.drawString(LonXprimerEle+38, Altbloq3 -35, "MES")
    pdf.drawString(LonXprimerEle+76, Altbloq3 -35, "AÑO")

    #OPCIONES NUMERADAS 
    #bloque3
    coorXListaNumerada = LonXprimerEle + espacioColumna*20+2
    coorYListaNumerada = Altbloq3 - 2
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(coorXListaNumerada, coorYListaNumerada, "1. HORAS")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -9 , "2. DIAS")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -18 , "3. MESES")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada-27 , "4. AÑOS")

    coorXListaNumerada = LonXprimerEle + espacioColumna*28
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -9, "1. HOMBRE")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -18, "2. MUJER")

    coorXListaNumerada = LonXprimerEle + espacioColumna*41
    coorYListaNumerada = Altbloq3 
    pdf.setFont("Helvetica", 6)
    pdf.drawString(coorXListaNumerada, coorYListaNumerada, "1. CASADO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -7, "2. SOLTERO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -14, "3. VIUDO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -21, "4. UNIÓN LIBRE")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -28, "5. DESCONOCIDO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -35, "6. NO APLICA")


    coorXListaNumerada = LonXprimerEle + espacioColumna*55
    coorYListaNumerada = Altbloq3 +1
    pdf.setFont("Helvetica", 6)
    pdf.drawString(coorXListaNumerada, coorYListaNumerada, "1. EMPLEADO PUBLICO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -7, "2. EMPLEADO PRIVADO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -14,"3. EMPLADO DOMESTICO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -21, "4. DESEMPLEADO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -28, "5. NEGOCIO PROPIO SOCIO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -35, "6. NO APLICA")

    #BLOQUE 4
    Altbloq4 = alto - 159
    pdf.setFont("Helvetica", 8)

    pdf.drawString(LonXprimerEle, Altbloq4, "RESIDENCIA")
    pdf.drawString(LonXprimerEle + espacioColumna*9, Altbloq4, "DEPARTAMENTO")
    pdf.drawString(LonXprimerEle + espacioColumna*19, Altbloq4, "MUNICIPIO")
    pdf.drawString(LonXprimerEle + espacioColumna*37-4, Altbloq4, "LOCALIDAD: (BARRIO O COLONIA NÚMERO DE CASA)")

    #BLOQUE 5
    Altbloq5 = alto - 191
    pdf.drawString(LonXprimerEle, Altbloq5, "EN CASO DE EMERGENCIA LLAMAR A:")
    pdf.drawString(LonXprimerEle + espacioColumna*20, Altbloq5, "DIRECCIÓN EXACTA")
    pdf.drawString(LonXprimerEle + espacioColumna*51, Altbloq5, "TELEFONO")
    pdf.drawString(LonXprimerEle + espacioColumna*58, Altbloq5, "TEL -PTE")

    #BLOQUE 6
    Altbloq6 = alto - 223
    pdf.drawString(LonXprimerEle, Altbloq6, "NOMBRE DEL PADRE:")
    pdf.drawString(LonXprimerEle+ espacioColumna*33, Altbloq6, "NOMBRE DE LA MADRE:")

    #BLOQUE 7
    Altbloq7 = alto - 256
    pdf.drawString(LonXprimerEle, Altbloq7, "INGRESO POR:")

    #LISTA NUMERADA
    pdf.setFont("Helvetica", 6.2)
    coorXListaNumerada = LonXprimerEle + espacioColumna*2.5
    coorYListaNumerada = Altbloq7 - 2
    pdf.drawString(coorXListaNumerada, coorYListaNumerada-7, "1. CONSULTA  EXTERNA")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -15 , "2. EMERGENCIA")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -23 , "3. NACIMIENTO")
    
    pdf.setFont("Helvetica", 8)
    pdf.drawString(LonXprimerEle+ espacioColumna*21-4, Altbloq7, "INGRESO A:")
    pdf.drawString(LonXprimerEle+ espacioColumna*31, Altbloq7-1, "CAMA:")
    pdf.drawString(LonXprimerEle+ espacioColumna*15, Altbloq7 -12, "SERVICIO")
    pdf.drawString(LonXprimerEle+ espacioColumna*29, Altbloq7 -12, "SALA")

    pdf.drawString(LonXprimerEle+ espacioColumna*46, Altbloq7, "FECHA DE INGRESO:")
    pdf.drawString(LonXprimerEle+ espacioColumna*37+1, Altbloq7-24, "DIA:")
    pdf.drawString(LonXprimerEle+ espacioColumna*43-4, Altbloq7-24, "MES:")
    pdf.drawString(LonXprimerEle+ espacioColumna*49-4, Altbloq7-24, "AÑO:")
    pdf.drawString(LonXprimerEle+ espacioColumna*56-2, Altbloq7-24, "HORA:")

    #BLOQUE 8
    Altbloq8 = alto - 301
    pdf.drawString(LonXprimerEle, Altbloq8, "DIAGNOSTICO")
    pdf.drawString(LonXprimerEle, Altbloq8-11, "DE INGRESO:")

    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(LonXprimerEle+ espacioColumna*8, Altbloq8-1, "1) ")
    pdf.drawString(LonXprimerEle+ espacioColumna*8, Altbloq8-14, "2) ")

    #BLOQUE 9
    pdf.setFont("Helvetica", 8)
    Altbloq9 = alto - 330

    pdf.drawString(LonXprimerEle, Altbloq9, "CAUSA DE ACCIDENTE O VIOLENCIA:")
    pdf.drawString(LonXprimerEle+ espacioColumna*38, Altbloq9, "LUGAR DE ACCIDENTE O VIOLENCIA:")
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(LonXprimerEle, Altbloq9 - 10, "(   )  VEHÍCULO MOTORIZADO")
    pdf.drawString(LonXprimerEle, Altbloq9 - 19, "(   )  OTRO TRANSPORTE")
    pdf.drawString(LonXprimerEle, Altbloq9 - 27, "(   )  CAIDA")
    pdf.drawString(LonXprimerEle, Altbloq9 - 36, "(   )  MAQUINARIA")
    pdf.drawString(LonXprimerEle, Altbloq9 - 45, "(   )  INCENDIO O EXPLOSIÓN")

    pdf.drawString(LonXprimerEle + espacioColumna*15, Altbloq9 - 10, "(   )  FENOMENO NATURAL   (  ) OTROS ____________")
    pdf.drawString(LonXprimerEle + espacioColumna*15, Altbloq9 - 19, "(   )  ASALTO / AGRESIÓN")
    pdf.drawString(LonXprimerEle + espacioColumna*15, Altbloq9 - 27, "(   )  INTENTO DE SUICIDIO  ______________________")
    pdf.drawString(LonXprimerEle + espacioColumna*15, Altbloq9 - 36, "(   )  EXPOSICIÓN A SUSTANCIAS NOCIVAS")

    pdf.drawString(LonXprimerEle + espacioColumna*38, Altbloq9 - 10, "(   )  TRABAJO")
    pdf.drawString(LonXprimerEle + espacioColumna*38, Altbloq9 - 19, "(   )  VIVIENDA")
    pdf.drawString(LonXprimerEle + espacioColumna*38, Altbloq9 - 27, "(   )  CENTRO ESTUDIOS")
    pdf.drawString(LonXprimerEle + espacioColumna*38, Altbloq9 - 36, "(   )  CENTRO MÉDICO _______________________________________")
    pdf.drawString(LonXprimerEle + espacioColumna*38, Altbloq9 - 45, "(   )  DEPORTE O DIVERSIÓN")

    pdf.drawString(LonXprimerEle + espacioColumna*52, Altbloq9 - 10, "(   )  VÍA PUBLICA")
    pdf.drawString(LonXprimerEle + espacioColumna*52, Altbloq9 - 19, "(   )  DESCONOCIDO")
    pdf.drawString(LonXprimerEle + espacioColumna*52, Altbloq9 - 27, "(   )  OTROS _______________")

    #BLOQUE 10
    pdf.setFont("Helvetica", 8)
    Altbloq10 = alto - 389
    pdf.drawString(LonXprimerEle + espacioColumna*7, Altbloq10, "TRASLADO A:")
    pdf.drawString(LonXprimerEle + espacioColumna*2, Altbloq10-12, "SERVICIO")
    pdf.drawString(LonXprimerEle + espacioColumna*14, Altbloq10-12, "SALA")

    pdf.drawString(LonXprimerEle + espacioColumna*21, Altbloq10, "FECHA DE TRASLADO")
    pdf.drawString(LonXprimerEle + espacioColumna*21 +2, Altbloq10-12, "DIA")
    pdf.drawString(LonXprimerEle + espacioColumna*25, Altbloq10-12, "MES")
    pdf.drawString(LonXprimerEle + espacioColumna*29, Altbloq10-12, "AÑO")

    pdf.drawString(LonXprimerEle + espacioColumna*40, Altbloq10, "EGRESO DE:")
    pdf.drawString(LonXprimerEle + espacioColumna*35, Altbloq10-12, "SERVICIO")
    pdf.drawString(LonXprimerEle + espacioColumna*46+4, Altbloq10-12, "SALA")

    pdf.drawString(LonXprimerEle + espacioColumna*54, Altbloq10, "FECHA DE TRASLADO")
    pdf.drawString(LonXprimerEle + espacioColumna*54+3, Altbloq10-12, "DIA")
    pdf.drawString(LonXprimerEle + espacioColumna*58, Altbloq10-12, "MES")
    pdf.drawString(LonXprimerEle + espacioColumna*62, Altbloq10-12, "AÑO")

    #bloque 11
    Altbloq11 = alto - 425
    pdf.drawString(LonXprimerEle, Altbloq11, "DIAGNÓSTICO DE EGRESO:")
    pdf.drawString(LonXprimerEle, Altbloq11-72, "OPERACIONES:")

    pdf.drawString(LonXprimerEle + espacioColumna*57, Altbloq11, "CÓDIGO")


    pdf.setFont("Helvetica", 7)
    pdf.drawString(LonXprimerEle, Altbloq11 - 14, "PRINCIPAL  1)")
    pdf.drawString(LonXprimerEle, Altbloq11 - 27, " 2)")
    pdf.drawString(LonXprimerEle, Altbloq11 - 40, " 3)")
    pdf.drawString(LonXprimerEle, Altbloq11 - 53, " 4)")

    pdf.drawString(LonXprimerEle, Altbloq11 - 89, "PRINCIPAL  1)")
    pdf.drawString(LonXprimerEle, Altbloq11 - 102, " 2)")
    pdf.drawString(LonXprimerEle, Altbloq11 - 115, " 3)")


    pdf.setFont("Helvetica", 8)
    pdf.drawString(LonXprimerEle + espacioColumna*58, Altbloq11-73, "CÓDIGO")

    pdf.drawString(LonXprimerEle+ espacioColumna*46-3, Altbloq11-73, "DIA")
    pdf.drawString(LonXprimerEle+ espacioColumna*49-4, Altbloq11-73, "MES")
    pdf.drawString(LonXprimerEle+ espacioColumna*52-4, Altbloq11-73, "AÑO")

    #BLOQUE 12
    Altbloq12 = alto - 563
    pdf.drawString(LonXprimerEle, Altbloq12, "CONDICIÓN DE EGRESO")
    pdf.drawString(LonXprimerEle+ espacioColumna*20, Altbloq12, "RAZON DE EGRESO")
    pdf.drawString(LonXprimerEle+ espacioColumna*36, Altbloq12, "REFERIDO A:")

    pdf.setFont("Helvetica", 6.2)
    coorXListaNumerada = LonXprimerEle + espacioColumna*11+4
    coorYListaNumerada = Altbloq12 - 2
    pdf.drawString(coorXListaNumerada, coorYListaNumerada, "1. IGUAL CONDICIÓN")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -7 , "2. MEJORADO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -15 , "3. CURADO")
    pdf.drawString(coorXListaNumerada, coorYListaNumerada -23 , "4. FALLECIDO")

    pdf.drawString(coorXListaNumerada+ espacioColumna*18, coorYListaNumerada + 5, "1. ALTA MÉDICA")
    pdf.drawString(coorXListaNumerada+ espacioColumna*18, coorYListaNumerada -2 , "2. ALTA EXIGIDA")
    pdf.drawString(coorXListaNumerada+ espacioColumna*18, coorYListaNumerada -10 , "3. FUGA")
    pdf.drawString(coorXListaNumerada+ espacioColumna*18, coorYListaNumerada -18 , "4. REFERIDO")
    pdf.drawString(coorXListaNumerada+ espacioColumna*18, coorYListaNumerada -26 , "5. FALLECIDO")

    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(LonXprimerEle + espacioColumna*59, Altbloq12, "AUTOPSIA")
    pdf.drawString(LonXprimerEle + espacioColumna*59, Altbloq12-11, "SI")
    pdf.drawString(LonXprimerEle + espacioColumna*62, Altbloq12-11, "NO")

    #BLOQUE 13
    pdf.setFont("Helvetica-Bold", 10)
    Altbloq13 = alto - 604

    pdf.drawCentredString(ancho / 2, Altbloq13, "PARTO O ABORTO")
    
    pdf.setFont("Helvetica", 8)
    pdf.drawString(LonXprimerEle, Altbloq13  - 12, "PERSONAL QUE ATENDIO EL PARTO:")
    

    pdf.setFont("Helvetica", 6.6)
    pdf.drawString(LonXprimerEle, Altbloq13 - 24, "(   )  ESTUDIANTE")
    pdf.drawString(LonXprimerEle, Altbloq13 - 34, "(   )  MÉDICO GENERAL")
    pdf.drawString(LonXprimerEle, Altbloq13 - 44, "(   )  RESIDENTE")

    pdf.drawString(LonXprimerEle + espacioColumna*10+3, Altbloq13 - 24, "(   )  MÉDICO ESPECIALISTA")
    pdf.drawString(LonXprimerEle+ espacioColumna*10+3, Altbloq13 - 34, "(   )  AUXILIAR DE ENFERMERIA")
    pdf.drawString(LonXprimerEle+ espacioColumna*10+3, Altbloq13 - 44, "(   )  ENFERMERIA PROFESIONAL")
    pdf.drawString(LonXprimerEle+ espacioColumna*10+3, Altbloq13 - 54, "(   )  EXTRAHOSPITALARIO")

    pdf.setFont("Helvetica", 8)
    pdf.drawString(LonXprimerEle + espacioColumna*39, Altbloq13 -11, "CONDICIÓN DE EGRESO")
    pdf.drawString(LonXprimerEle + espacioColumna*24+3, Altbloq13 -28, "No.")
    pdf.drawString(LonXprimerEle + espacioColumna*24+6, Altbloq13 -52, "1")
    pdf.drawString(LonXprimerEle + espacioColumna*24+6, Altbloq13 -76, "2")
    pdf.drawString(LonXprimerEle + espacioColumna*24+6, Altbloq13 -99, "3")
    pdf.drawString(LonXprimerEle + espacioColumna*24+6, Altbloq13 -123, "4")


    pdf.drawString(LonXprimerEle + espacioColumna*32+4, Altbloq13 -22.5, "SEXO")
    pdf.drawString(LonXprimerEle + espacioColumna*45, Altbloq13 -22.5, "CONDICION AL NACER")

    pdf.drawString(LonXprimerEle + espacioColumna*28-2, Altbloq13 -34, "HOMBRE")
    pdf.drawString(LonXprimerEle + espacioColumna*36+2, Altbloq13 -34, "MUJER")

    pdf.drawString(LonXprimerEle + espacioColumna*45, Altbloq13 -34, "VIVO")
    pdf.drawString(LonXprimerEle + espacioColumna*52, Altbloq13 -34, "MUERTO")

    pdf.setFont("Helvetica", 6.7)
    pdf.drawString(LonXprimerEle + espacioColumna*58+2, Altbloq13 -24, "PESO AL NACER")
    pdf.drawString(LonXprimerEle + espacioColumna*59, Altbloq13 -33, "EN GRAMOS")

    pdf.setFont("Helvetica", 7)
    pdf.drawString(LonXprimerEle, Altbloq13  - 80, "Número de embarazos incluyendo éste:")
    pdf.drawString(LonXprimerEle, Altbloq13  - 93, "Período de gestación: (en semanas)")
    pdf.drawString(LonXprimerEle, Altbloq13  - 106, "Total número de consultas prenatales")
    pdf.drawString(LonXprimerEle, Altbloq13  - 119, "Consultas prenatales por médico:")

    #firmas
    pdf.drawString(LonXprimerEle+40, Altbloq13  - 164, "__________________________________________")
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(LonXprimerEle+53, Altbloq13  - 172, "FIRMA JEFE O RESPONSABLE DE LA SALA")

    pdf.drawString(LonXprimerEle+350, Altbloq13  - 164, "__________________________________________")
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(LonXprimerEle+395, Altbloq13  - 172, "FECHA DE LA FIRMA")

    #//////  INFORMACION ESTATICA
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LonXprimerEle, Altbloq1 -16, "HOSPITAL DR. ENRIQUE AGUILAR CERRATO")
    pdf.drawString(LonXprimerEle + espacioColumna*31, Altbloq1 -16, "8753")


    #//////  INFORMACION DINAMICA DEL INGRESP


    #usurario
    pdf.setFont("Helvetica", 7)
    pdf.drawString(LonXprimerEle+ espacioColumna*51, alto-35, f"Registrado: {usuario}")
    #infodelreporte
    pdf.drawString(LonXprimerEle, Altbloq13  - 138, f"Impreso el: {fechaInpre}")
    # CAMA NUMERO 
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(LonXprimerEle+ espacioColumna*51, alto-24, f"CAMA {str(cama)}")


    pdf.setFont("Helvetica", 7)
    #parte para mostrar si es gemelo  
    if tipo in [3,4]:
        if orden_gemelar:
            pdf.setFont("Helvetica-Bold", 10) 
            pdf.drawString(LonXprimerEle+ espacioColumna*51, alto-25, f"Gemelo #: {orden_gemelar}")


    #bloque 1   
    pdf.setFont("Helvetica-Bold", 14)
    charExpe = list(str(expediente))
    ejeX = LonXprimerEle+ espacioColumna*44+5
    for numero in charExpe:
        pdf.drawString(ejeX, Altbloq1 -18, numero)
        ejeX+=17

    #bloque 2
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LonXprimerEle, Altbloq2 -16, apellidos)
    #pdf.drawString(LonXprimerEle+ espacioColumna*10, Altbloq2 -16, apellido2)
    
    pdf.drawString(LonXprimerEle+ espacioColumna*21-5, Altbloq2 -16, nombres[0:19])

    pdf.setFont("Helvetica-Bold", 14)
    ejeX = LonXprimerEle+ espacioColumna*36+5
    if not validar_extranjero_o_hondureno_con_pasaporte(tipo,nacionalidad):
        for i,numero in enumerate(dni):
            pdf.drawString(ejeX, Altbloq2-17, numero)
            if i == 3 or i == 7 :
                ejeX+=25
            else: 
                ejeX+=17
    else:
        pdf.drawString(ejeX, Altbloq2-17, dni[:24])


    #bloque 3
    pdf.drawString(LonXprimerEle+5, Altbloq3-20, str(diaNac))
    pdf.drawString(LonXprimerEle+38, Altbloq3-20, str(mesNac))
    pdf.drawString(LonXprimerEle+69, Altbloq3-20, str(fechaNac.year))
    pdf.drawString(LonXprimerEle + espacioColumna*13+5, Altbloq3-20, edad)
    pdf.drawString(LonXprimerEle + espacioColumna*17+5, Altbloq3-20, edadT)
    pdf.drawString(LonXprimerEle + espacioColumna*25+4, Altbloq3-20, sexo)
    pdf.drawString(LonXprimerEle + espacioColumna*34+5, Altbloq3-20, str(estCivil))
    pdf.drawString(LonXprimerEle + espacioColumna*49+5, Altbloq3-20, str(ocupacion))

    #bloque 4
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LonXprimerEle, Altbloq4 -16, depto)
    pdf.drawString(LonXprimerEle + espacioColumna*19, Altbloq4 -16, muni[0:21])
    pdf.drawString(LonXprimerEle + espacioColumna*37-4, Altbloq4 -16, ubicacion[0:35])

    #bloque 5
    pdf.drawString(LonXprimerEle, Altbloq5 -16, nombre_contacto[:22])
    pdf.drawString(LonXprimerEle+ espacioColumna*20, Altbloq5 -16, direccion_contacto)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(LonXprimerEle+ espacioColumna*51, Altbloq5 -16, telefono_contacto)
    pdf.drawString(LonXprimerEle+ espacioColumna*58, Altbloq5 -16, telefono_paciente)

    #BLOQUE 6
    pdf.drawString(LonXprimerEle, Altbloq6 -19, nombrePadre)
    pdf.drawString(LonXprimerEle + espacioColumna*33, Altbloq6 -19, nombreMadre)

    pdf.setFont("Helvetica-Bold", 9.5)
    pdf.drawString(LonXprimerEle+ espacioColumna*11, Altbloq6-2 , dniPadre)
    pdf.drawString(LonXprimerEle+ espacioColumna*45, Altbloq6-2 , dniMadre)

    #BLOQUE 7
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(LonXprimerEle+4.5, Altbloq7 - 19, str(zonaIngreso))

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(LonXprimerEle+espacioColumna*12+4, Altbloq7 -26, servicio)
    
    pdf.drawString(LonXprimerEle+espacioColumna*35-3, Altbloq7, cama)
    


    if cama or idservicio != 700: # regla de obstetricia que si no se define la cama no aparece la sala 

        pdf.drawString(LonXprimerEle + espacioColumna * 24 - 4, Altbloq7 - 26, sala[:20])

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(LonXprimerEle+espacioColumna*39+4.5, Altbloq7 -19, diaIngreso)
    pdf.drawString(LonXprimerEle+espacioColumna*45+4.5, Altbloq7 -19, mesIngreso)
    pdf.drawString(LonXprimerEle+espacioColumna*51+1.5, Altbloq7 -19, str(fechaIngreso.year))

    pdf.drawString(LonXprimerEle+espacioColumna*59+3, Altbloq7 -20, horaIngreso)
    

    
    #pagina 2
    pdf.showPage()
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(ancho / 2, alto - 50, "AUTORIZACIÓN")
    pdf.drawCentredString(ancho / 2, alto - 330, "SALIDA EXIGIDA")
    pdf.drawCentredString(ancho / 2, alto - 565, "AUTORIZACIÓN RETIRO DEL PACIENTE")



    #pagina 2
    # Configuración de estilos
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.alignment = 4  # Justificado
    style.leading = 16  # Espaciado entre líneas

    # Variables de posición
    inicioPagina2 = inch - 20
    ancho_max = 7 * inch  # Ajusta según sea necesario
    altoP2 = alto

    # --- PÁRRAFOS PRINCIPALES ---

    texto = ("Por la presente autorizo al personal médico del hospital para que, durante mi hospitalización, "
            "se me practiquen los procedimientos clínicos de gabinete, laboratorio, quirúrgicos o anatomopatológicos "
            "que sean útiles para el diagnóstico, tratamiento y recuperación de mi salud.")

    p = Paragraph(texto, style)
    p.wrapOn(pdf, ancho_max, 100)
    p.drawOn(pdf, inicioPagina2, altoP2 - 110)

    texto = ("Del mismo modo autorizo a la institución para que se lleve a cabo los procedimientos completados "
            "en las leyes nacionales, que sean necesarias para el reconocimiento de mi enfermedad a fin de evitar "
            "riesgos de contagio y facilitar la protección futura a la salud de mis familiares y allegados.")

    p = Paragraph(texto, style)
    p.wrapOn(pdf, ancho_max, 100)
    p.drawOn(pdf, inicioPagina2, altoP2 - 165)

    texto = ("Exonero de toda responsabilidad a los médicos tratantes, porque en contra de las indicaciones médicas "
            "he exigido la salida de mi ____________________________________________________ (PARENTESCO), quien se encuentra "
            "internado en este hospital. Al tomar tal actitud, asumo por completo la responsabilidad por los riesgos "
            "que me han sido advertidos.")

    p = Paragraph(texto, style)
    p.wrapOn(pdf, ancho_max, 100)
    p.drawOn(pdf, inicioPagina2, altoP2 - 410)

    # --- FIRMA VOLUNTARIA ---
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(ancho / 2, altoP2 - 190,
                        "Firmo voluntariamente a los _________ días del mes de _____________________________ del 20______")

    # --- FIRMAS ---
    pdf.setFont("Helvetica", 10)

    # Firma del paciente
    pdf.drawString(inicioPagina2, altoP2 - 225, "__________________________________________")
    pdf.drawString(inicioPagina2 + 80, altoP2 - 237, "Nombre y apellidos")

    pdf.drawString(inicioPagina2 + 350, altoP2 - 225, "___________________________")
    pdf.drawString(inicioPagina2 + 410, altoP2 - 237, "Firma")

    # Firma del testigo
    pdf.drawString(inicioPagina2, altoP2 - 270, "__________________________________________")
    pdf.drawString(inicioPagina2 + 105, altoP2 - 283, "Testigo")

    pdf.drawString(inicioPagina2 + 350, altoP2 - 270, "___________________________")
    pdf.drawString(inicioPagina2 + 410, altoP2 - 283, "Firma")

    # --- INFORMACIÓN ADICIONAL ---
    pdf.setFont("Helvetica", 10.5)

    pdf.drawCentredString(ancho / 2, altoP2 - 430,
                        "Nombre: _________________________________________  Cédula de Identidad N° __________________")

    pdf.drawCentredString(ancho / 2, altoP2 - 460,
                        "Fecha: _______________________________________                      Firma: _________________________")

    pdf.drawCentredString(ancho / 2, altoP2 - 490,
                        "Testigo: ______________________________  Firma: ________________  Cédula N°__________________")

    pdf.drawCentredString(ancho / 2, alto - 595,
                        "Yo, ________________________________________  Cédula N° __________________  Domicilio Exacto:")

    pdf.drawCentredString(ancho / 2, alto - 620,
                        "_____________________________________________________________________________________")

    pdf.drawCentredString(ancho / 2, alto - 650,
                        "He retirado en esta fecha a mi ________________________________________  (relación con el paciente)")

    pdf.drawCentredString(ancho / 2, alto - 680,
                        "Del servicio de _____________________________________  con la autorización médica correspondiente.")

    pdf.drawCentredString(ancho / 2, altoP2 - 730,
                        "Fecha: _________________________                Firma: _________________________")


    #Datos DInamicos segunda pagina diaIngreso
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(ancho-405, altoP2 - 187, diaIngreso)

    mes = _(fechaIngreso.strftime("%B")).capitalize()
    pdf.drawString(ancho-225, altoP2 - 187, mes)

    pdf.drawString(ancho-80, altoP2 - 187, str(fechaIngreso.year)[-2:])


    #regla de negocio, si es un recien nacido o hijo de de, usar el nombre la madre para firmar como testigo el paciente nos e puestras porque es un rn

    nombre_completo = f"{nombres} {apellidos}"#mismmo paciente
    if tipo in [3, 4]:# madre del hijo o del rn
        pdf.drawString(inicioPagina2, altoP2 - 265, nombreMadre)

    else:
        pdf.drawString(inicioPagina2, altoP2 - 220, nombre_completo)
        pdf.drawString(inicioPagina2, altoP2 - 265, nombre_contacto)


    #pagina 3
    pdf.showPage()
    dibujar_encabezado_epicrisis(pdf, ancho, 755)
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


    #---------->>>>>>>>>    DATOS DINAMICOS 
    pdf.setFont("Helvetica-Bold", 11)

    pdf.drawString(235,alto-alturaTabla-65, nombres[0:19])
    pdf.drawString(50,alto-alturaTabla-65, apellidos)


    #----- MAPEAR LA EDAD
    if edadT:
        if edadT == "4":
            medida = "AÑOS"
        elif edadT == "3":
            medida = "MESES"
        elif edadT == "2":
            medida = "DIAS"
        elif edadT == "1":
            medida = "HORAS"

    pdf.drawString(354,alto-alturaTabla-59, edad)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(349,alto-alturaTabla-70, medida)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(448,alto-alturaTabla-60, sexo)

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(480,alto-alturaTabla-58, expediente)
    pdf.drawString(480,alto-alturaTabla-69, formatear_dni(dni))

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(60,alto-alturaTabla-95, servicio)
    pdf.drawString(265,alto-alturaTabla-95, sala)
    pdf.drawString(496,alto-alturaTabla-95, f"# {cama}")
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(70,alto-alturaTabla-127, str(zonaIngreso))

    pdf.drawString(275,alto-alturaTabla-130, diaIngreso)
    pdf.drawString(330,alto-alturaTabla-130, mesIngreso)
    pdf.drawString(380,alto-alturaTabla-130, str(fechaIngreso.year))
    # Finalizar el PDF
    pdf.save()

    return response



class reporte_hospitalizacion_2026(View):

    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario, permisos.INGRESO_VISUALIZACION_ROLES, permisos.INGRESO_VISUALIZACION_UNIDADES):
            return JsonResponse({"error": "No tiene permisos para ver este reporte"})
        return super().dispatch(request, *args, **kwargs)
    

    def get(self, request, ingreso_id):

        usuario = request.user

        if not ingreso_id:
            return JsonResponse({"error": "El ID del ingreso es requerido."}, status=400)
    
        try:
            data = IngresoFormatosService.construir_data_hoja_hospitalizacion(ingreso_id)
            formato = ReportePacienteService.GenerarFormatoHojaHospitalizacion2026(data, usuario)
            return formato
            
        except Exception as e:
            return JsonResponse({'error': f'Tenemos problema en generar la información del reporte. {e}'}, status=400)
        


def dibujar_encabezado_epicrisis(pdf, ancho, y):
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



class reporte_entrega_cadaver(View):
    def dispatch(self, request, *args, **kwargs):
        # Verificar permisos del usuario antes de continuar con la lógica de la vista
        usuario = request.user
        if not verificar_permisos_usuario(usuario, ['admin', 'digitador'], ['Admision']):
            return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

        return super().dispatch(request, *args, **kwargs)


    def get(self, request, defuncion_id):
        usuario = request.user

        if not defuncion_id:
            return JsonResponse({"error": "El ID de defuncion es requerido."}, status=400)
    

        try:
            # Intentamos obtener la recepción
            defuncion = PacienteService.obtener_defuncion_id(defuncion_id)
            if not defuncion:
                return JsonResponse({"error": "No se encontró la defuncion con ese ID."}, status=404)
            #expediente
            expediente_activo = ExpedienteService.obtener_expediente_activo_paciente(defuncion.paciente.id)
            paciente = defuncion.paciente

            # Determinar el valor del expediente
            if paciente.dni:
                expediente = formatear_dni(paciente.dni)
            elif expediente_activo and expediente_activo.numero:
                expediente = formatear_expediente(str(expediente_activo.numero))
            else:
                dniMadre = formatear_dni(paciente.madre.dni) if paciente.madre and paciente.madre.dni else None
                expediente = dniMadre if dniMadre else "N/A"

            pdf = ReportePacienteService.generar_entrega_cadaver_pdf(defuncion, expediente, usuario)

            return pdf
            
    
        except Exception as e:
            # Capturar cualquier error inesperado
            return JsonResponse({"error": f"Hubo un error inesperado: {str(e)}"}, status=500)


class reporte_obito(View):

    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario, ['admin', 'digitador'], ['Admision']):
            return JsonResponse({'error': 'No tienes permisos'}, status=403)

        return super().dispatch(request, *args, **kwargs)


    def get(self, request, obito_id):
        usuario = request.user
        if not obito_id:
            return JsonResponse({"error": "El ID de óbito es requerido."}, status=400)

        try:
            obito = PacienteService.obtener_obito_id(obito_id)

            if not obito:
                return JsonResponse({"error": "No se encontró el óbito"}, status=404)

            expediente_activo = ExpedienteService.obtener_expediente_activo_paciente(obito.paciente.id)
            paciente = obito.paciente

            if paciente.dni:
                expediente = formatear_dni(paciente.dni)
            elif expediente_activo and expediente_activo.numero:
                expediente = formatear_expediente(str(expediente_activo.numero))
            else:
                expediente = "N/A"

            pdf = ReportePacienteService.generar_obito_pdf(obito, expediente, usuario)

            return pdf

        except Exception as e:
            return JsonResponse({"error": f"Error inesperado: {str(e)}"}, status=500)