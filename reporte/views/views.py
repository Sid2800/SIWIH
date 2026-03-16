from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

from datetime import datetime, time, timedelta


from django.utils import timezone
from django.views import View

from reportlab.lib.units import inch, mm, cm
from reportlab.lib.colors import Color
from reportlab.platypus import Paragraph
from django.utils.translation import gettext as _
from django.http import HttpResponse
from django.conf import settings
import os
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
import copy
from django.views.generic import TemplateView
import json

from core.services.paciente_service import PacienteService
from core.services.reporte.PDF.reporte_generador_service import ReporteGeneradorService
from core.services.reporte.EXCEL.reporte_service_excel import ServiceExcel
from core.constants.stored_procedures import SP_CATALOGO_REFERENCIAS_RECIBIDAS, SP_CATALOGO_REFERENCIAS_ENVIADAS
from core.services.usuario_service import UsuarioService
from core.services.ubicacion_service import UbicacionService
from core.services.servicio_service import ServicioService
from core.services.ingreso.ingreso_service import IngresoService
from core.services.atencion_service import AtencionService
from core.services.imagenologia_service import EvaluacionService
from core.mixins import UnidadRolRequiredMixin

from core.services.recepcion_atenciones_service import RecepcionAtencionService
from core.utils.utilidades_textos import formatear_dni,formatear_expediente,formatear_nombre_completo 
from usuario.permisos import verificar_permisos_usuario
from core.utils.utilidades_fechas import formatear_fecha , formatear_fecha_dd_mm_yyyy_hh_mm, convertir_rango_fechas, formatear_fecha_dd_mm_yyyy
from core.utils.utilidades_request import cargar_json
from reporte.validators import validar_informe

class ReporteGeneradorView(UnidadRolRequiredMixin, TemplateView):
    template_name = "reporte/reportes_gen.html"
    required_roles = ['admin','digitador', 'auditor', 'Visitante']
    required_unidades = ['Admision', 'Referencia','Imagenologia', 'DIRECTIVOS']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        modelos = []

        informesRx = [
            (1,'ESTUDIOS IMPRESOS POR DEPENDENCIA'),
            (2,'GASTO DE MATERIAL POR DEPENDENCIA'),
            (3,'Pacientes atendidos diariamente por dependencia'),
            (4,'Estudios realizados por dependencia'),
        ]

        informesReferencia = [
            (1, 'REFERENCIAS A MAYOR COMPLEJIDAD SEGÚN ESPECIALIDAD'),
            (2, 'REFERENCIAS A MAYOR COMPLEJIDAD SEGUN INSTITUCIONES'),
            (3, 'REFERENCIAS A MAYOR COMPLEJIDAD SEGUN MOTIVO'),
            (4, 'SEGUIMIENTO A REFERENCIAS ENVIADAS A MAYOR COMPLEJIDAD'),
            (5, 'REFERENCIAS A MAYOR COMPLEJIDAD SEGUN AREA DE ENVIO'),
            (6, 'REFERENCIAS RECIBIDAS POR GESTOR- OTROS DEP- CLINICA PRIVADA'),
            (7, 'REFERENCIAS RECIBIDAS POR GESTOR- OTROS DEP- CLINICA PRIVADA. DETALLADO'),
            (8, 'REFERENCIAS RECIBIDAS SEGUN EVALUACION'),
            (9, 'RESPUESTAS RESUELTAS SEGUN AREAS ATENCION'),
            (10,'REFERENCIAS Y RESPUESTAS POR GESTOR- OTROS DEP- CLINICA PRIVADA'),
            (11,'REFERENCIAS ENVIADAS A PRIMER NIVEL DE ATENCION SEGUN GESTOR'),
        ]

        informesCatalogo = [
            (1, 'REFERENCIAS ENVIADAS'),
            (2, 'REFERENCIAS RECIBIDAS'),
        ]

        # SUPERUSUARIO o DIRECTIVOS => tienen acceso completo
        if self.request.user.is_superuser or \
        self.request.user.perfilunidad_set.filter(unidad__nombre_unidad='DIRECTIVOS').exists():

            modelos.extend([
                ('paciente', 'Paciente'),
                ('ingreso', 'Ingreso'),
                ('atencion', 'Atencion'),
                ('imagenologia', 'Evaluación RX'),
                ('estudio_rx', 'Estudio RX'),
            ])

            context['informesRx'] = informesRx
            context['informesReferencia'] = informesReferencia
            context['informesCatalogo'] = informesCatalogo
            context['modelos'] = modelos

        # --------- USUARIOS NORMALES ------------
        user_unidades = [pu.unidad.nombre_unidad for pu in self.request.user.perfilunidad_set.all()]

        # Paciente SIEMPRE disponible
        modelos.append(('paciente', 'Paciente'))

        # Admision
        if 'Admision' in user_unidades:
            modelos.append(('ingreso', 'Ingreso'))
            modelos.append(('atencion', 'Atencion'))

        # Imagenología
        if 'Imagenologia' in user_unidades:
            modelos.append(('imagenologia', 'Evaluación RX'))
            modelos.append(('estudio_rx', 'Estudio RX'))
            context.setdefault('informesRx', informesRx)  # evita pisar si ya existe

        # Referencia
        if 'Referencia' in user_unidades:
            context.setdefault('informesReferencia', informesReferencia)
            context.setdefault('informesCatalogo', informesCatalogo[:2])
                
                
        anio_actual = datetime.now().year
        anios = list(range(2000, anio_actual + 1))

        context['modelos'] = modelos
        context['anios'] = anios

        hoy = timezone.localdate()
        primer_dia_mes = hoy.replace(day=1)

        hoy = timezone.localdate()
        context["mes_actual"] = hoy.strftime("%m") 

        context['fecha_inicio'] = primer_dia_mes
        context['fecha_fin'] = hoy

        return context


class ObtenerInteraccionFiltroAgrupacion(View):
    def get(self, request, *args, **kwargs):
        modelo = request.GET.get('modelo')

        if not modelo:
            return JsonResponse({'error': 'Parámetro "modelo" es requerido.'}, status=400)

        try:
            if modelo == 'paciente':
                interacciones = {
                    'fecha_creado': 'Creacion',
                    'fecha_modificado': 'Actualizacion',
                    'fecha_nacimiento': 'Fecha Nacimiento',
                }
                agrupaciones = {
                    'creado_por_id': 'Usuario de creacion',
                    'modificado_por_id': 'Usuario de actualizacion',
                    'sexo': 'Sexo',
                    'sector__aldea__municipio_id': 'Municipio',
                    'sector__aldea__municipio__departamento_id': 'Departamento',
                    'estado':'Estado',
                    'tipo_id':'Tipo Identificacion',
                    'zona_id':'Zona'
                }
                filtros = agrupaciones.copy()  # En este caso, filtros y agrupaciones son iguales
                filtros['ninguno'] = 'Ninguno'
            
            
            elif modelo == 'ingreso':
                interacciones = {
                    'fecha_ingreso': 'Fecha Creacion',
                    'fecha_egreso': 'Fecha Egreso',
                    'fecha_recepcion_sdgi': 'Fecha Recepcion SDGI',
                    'fecha_modificado': 'Fecha Actualizacion',
                }
                agrupaciones = {
                    'sala__servicio_id': 'Servicio',
                    'sala_id': 'Sala',
                    'paciente__sector__aldea__municipio__departamento_id': 'Departamento',
                    'creado_por_id': 'Usuario de creacion',
                    'modificado_por_id': 'Usuario de actualizacion',
                }
                filtros = agrupaciones.copy()
                filtros['ninguno'] = 'Ninguno'


            elif modelo == 'atencion':
                interacciones = {
                    'fecha_atencion': 'Fecha Creacion',
                    'fecha_recepcion': 'Fecha Recepcion',
                    'fecha_modificado': 'Fecha Actualizacion',
                }
                agrupaciones = {
                    'especialidad__servicio_id': 'Servicio',
                    'especialidad_id': 'Especialidad',
                    'paciente__sector__aldea__municipio_id': 'Municipio',
                    'paciente__sector__aldea__municipio__departamento_id': 'Departamento',
                    'creado_por_id': 'Usuario de creacion',
                    'modificado_por_id': 'Usuario de actualizacion',
                }
                filtros = agrupaciones.copy()
                filtros['ninguno'] = 'Ninguno'


            elif modelo == 'imagenologia':
                interacciones = {
                    'fecha': 'Fecha Evaluacion',
                    'fecha_modificado': 'Fecha Actualizacion',
                }
                agrupaciones = {
                    'dependencia_id': 'Dependencia',
                    'maquinarx_id': 'Maquina RX',
                    'paciente__sector__aldea__municipio__departamento_id': 'Departamento',
                    'creado_por_id': 'Usuario de creacion',
                    'modificado_por_id': 'Usuario de actualizacion',
                }
                filtros = agrupaciones.copy()
                filtros['ninguno'] = 'Ninguno'

            elif modelo == 'estudio_rx':
                interacciones = {
                    'evaluacionRx__fecha': 'Fecha Evaluacion'
                }
                agrupaciones = {
                    'dependencia_id': 'Dependencia',
                    'evaluacionRx__maquinarx_id': 'Maquina RX',
                    'evaluacionRx__paciente__sector__aldea__municipio__departamento_id': 'Departamento',
                    'estudio_id': 'Estudio',
                    'evaluacion': 'Paciente', # solo para agrupar
                    'impreso': 'Impreso'
                }
                filtros = agrupaciones.copy()
                filtros['ninguno'] = 'Ninguno'
                if 'evaluacion' in filtros: 
                    del filtros['evaluacion']

            else:
                return JsonResponse({'error': f'Modelo no soportado: {modelo}'}, status=400)

            return JsonResponse({
                'interaccion': interacciones,
                'agrupacion': agrupaciones,
                'filtro': filtros,
            }, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class ObtenerOpcionesFiltro(View):
    def get(self, request, *args, **kwargs):
        campo = request.GET.get('campo')
        modelo = request.GET.get('modelo')

        if not modelo:
            return JsonResponse({'error': 'Parámetro "modelo" es requerido.'}, status=400)

        if not campo:
            return JsonResponse({'error': 'Parámetro "campo" es requerido.'}, status=400)

        try:
            if campo == 'ninguno':
                return JsonResponse({
                    'valores': [{'id': 0, 'valor': 'ninguno'}]
                }, status=200)

            elif campo in ['creado_por_id', 'modificado_por_id']:
                usuarios = UsuarioService.obtener_usuarios_activos()
                usuarios = [{'id': u['id'], 'valor': u['username']} for u in usuarios]
                return JsonResponse({'valores': usuarios}, status=200)

            elif campo == 'sector__aldea__municipio__departamento_id' or campo == 'paciente__sector__aldea__municipio__departamento_id' or campo == 'evaluacionRx__paciente__sector__aldea__municipio__departamento_id'  :
                    departamentos = UbicacionService.obtener_departamentos()
                    departamentos = [{'id': u['id'], 'valor': u['nombre_departamento']} for u in departamentos]
                    return JsonResponse({'valores': departamentos}, status=200)

            if campo == 'sala__servicio_id' or campo == 'especialidad__servicio_id':
                    servicios = ServicioService.obtener_servicios()
                    servicios = [{'id': u['id'], 'valor': f"{u['nombre_servicio']}"} for u in servicios]
                    return JsonResponse({'valores': servicios}, status=200)

            if campo == 'sala_id':
                    salas = ServicioService.obtener_salas_activas()
                    salas = [{'id': s['id'], 'valor': f"{s['nombre_sala']} | {s['servicio__nombre_corto']}"} for s in salas]
                    return JsonResponse({'valores': salas}, status=200)
            
            if campo == 'especialidad_id':
                    especialidades = ServicioService.obtener_especialidades_activas_servicio()
                    especialidades = [{'id': e['id'], 'valor': f"{e['nombre_especialidad']} | {e['servicio__nombre_corto']}"} for e in especialidades]
                    return JsonResponse({'valores': especialidades}, status=200)
            
            if campo == 'zona_id':
                    zonas = ServicioService.obtener_zonas()
                    zonas = [{'id': e['codigo'], 'valor': f"{e['nombre_zona']}"} for e in zonas]
                    return JsonResponse({'valores': zonas}, status=200)


            if campo == 'dependencia_id':
                    salas = ServicioService.obtener_salas_activas()
                    especialidades = ServicioService.obtener_especialidades_activas_servicio()
                    serv_aux = ServicioService.obtener_servicios_aux_activas()

                    salas = [{'id': f"S-{s['id']}", 'valor': f"{s['nombre_sala']} | {s['servicio__nombre_corto']}", 'tipo': 'sala'} for s in salas]
                    especialidades = [{'id': f"E-{e['id']}", 'valor': f"{e['nombre_especialidad']} | {e['servicio__nombre_corto']}", 'tipo': 'especialidad'} for e in especialidades]
                    serv_aux = [{'id': f"A-{a['id']}", 'valor': f"{a['nombre_servicio_a']} | SERV_AUX", 'tipo': 'servicio_auxiliar'} for a in serv_aux]
                    
                    valores_combinados = salas + especialidades + serv_aux
                    return JsonResponse({'valores': valores_combinados}, status=200)


            if campo == 'maquinarx_id' or campo == 'evaluacionRx__maquinarx_id':
                maquinas = EvaluacionService.obtener_maquinas_rx_activas()
                maquinas = [{'id': m['id'], 'valor': f"{m['descripcion_maquina']}"} for m in maquinas]
                return JsonResponse({'valores': maquinas}, status=200)

            if modelo == 'paciente':
                if campo == 'sector__aldea__municipio_id':
                    municipios = UbicacionService.obtener_municipios_por_departamento()
                    municipios = [{'id': u['id'], 'valor': u['nombre_municipio']} for u in municipios]
                    return JsonResponse({'valores': municipios}, status=200)
                
                elif campo == 'sexo':
                    return JsonResponse({
                        'valores': [
                            {'id': 'H', 'valor': 'HOMBRE'},
                            {'id': 'M', 'valor': 'MUJER'},
                        ]
                    }, status=200)
                elif campo == 'estado':
                    return JsonResponse({
                        'valores': [
                            {'id': 'A', 'valor': 'ACTIVO'},
                            {'id': 'P', 'valor': 'PASIVO'},
                            {'id': 'I', 'valor': 'INACTIVO'},
                        ]
                    }, status=200)
                elif campo == 'tipo_id':
                    tipos = PacienteService.obtener_tipos()
                    tipos = [{'id': u['id'], 'valor': u['descripcion_tipo']} for u in tipos]
                    return JsonResponse({'valores': tipos}, status=200)      
            elif modelo == 'estudio_rx':
                if campo == 'estudio_id':
                    estudios = EvaluacionService.obtener_estudios()
                    estudios = [{'id': e['id'], 'valor': f"{e['codigo']} | {e['descripcion_estudio']}"} for e in estudios]
                    return JsonResponse({'valores': estudios}, status=200)
                elif campo == 'impreso':
                    return JsonResponse({
                        'valores': [
                            {'id': '1', 'valor': 'SI'},
                            {'id': '0', 'valor': 'NO'},
                        ]
                    }, status=200)
            return JsonResponse({'error': f'Campo no soportado: {campo} para modelo: {modelo}'}, status=400)

        except Exception as e:
            print(f"Error al obtener opciones de filtro: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class ReporteGenerador(View):
    def post(self, request, *args, **kwargs):
        usuario = request.user
        data, error = cargar_json(request)
        if error:
            return error


        reporte_criterios = {
            'modelo': data.get('modelo'),
            'fechaIni': data.get('fechaIni'),
            'fechaFin': data.get('fechaFin'),
            'interaccion': data.get('interaccion'),
            'agrupacion': data.get('agrupacion'),
            'campoFiltro': data.get('campoFiltro'),
            'valorFiltro': data.get('valorFiltro'),
            'detalles': data.get('detalles'),
            'campoValorTexto': data.get('campoValorTexto'),
            'campoFiltroTexto': data.get('campoFiltroTexto')
        }


        missing = [k for k, v in reporte_criterios.items() if v in (None, '')]
        if missing:
            return JsonResponse({'error': f'Faltan parámetros: {", ".join(missing)}'}, status=400)


        try:
            fecha_ini, fecha_fin = convertir_rango_fechas(
                reporte_criterios['fechaIni'],
                reporte_criterios['fechaFin']
            )
            reporte_criterios['fechaIni'] = fecha_ini
            reporte_criterios['fechaFin'] = fecha_fin
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)


        # Convertir 'detalles' a entero 0 o 1
        try:
            reporte_criterios['detalles'] = int(reporte_criterios['detalles'])
        except (ValueError, TypeError):
            reporte_criterios['detalles'] = 0

        if reporte_criterios['modelo'] == 'paciente':

            if reporte_criterios['detalles'] == 1: 
                
                data = PacienteService.GenerarDataPaciente(reporte_criterios,'detallado')

                if data:
                    if len(data['data']) == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']             
                    reporte = ReporteGeneradorService.GenerarReporteDetallado(data['data'], reporte_criterios)
                    return reporte
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)
            else: 
                data = PacienteService.GenerarDataPaciente(reporte_criterios,'resumido')
                if data:
                    if data['total'] == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['resumen'] = data['resumen']
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['total'] = data['total']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    #ahora si a generar el reporte
                    reporte = ReporteGeneradorService.GenerarReporteResumido(reporte_criterios)
                    return reporte
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)
        elif reporte_criterios['modelo'] == 'ingreso':

            if reporte_criterios['detalles'] == 1:
                data = IngresoService.GenerarDataIngreso(reporte_criterios, 'detallado')

                if data:
                    if len(data['data']) == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']    

                    reporte = ReporteGeneradorService.GenerarReporteDetallado(data['data'], reporte_criterios)
                    return reporte
                    #return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)

            else:

                data = IngresoService.GenerarDataIngreso(reporte_criterios)
                if data:
                    if data['total'] == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['resumen'] = data['resumen']
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['total'] = data['total']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    #ahora si a generar el reporte
                    reporte = ReporteGeneradorService.GenerarReporteResumido(reporte_criterios)
                    return reporte
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)
        elif reporte_criterios['modelo'] == 'atencion':
            if reporte_criterios['detalles'] == 1:
                data = AtencionService.GenerarDataAtencion(reporte_criterios, 'detallado')

                if data:
                    if len(data['data']) == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']    
                    reporte = ReporteGeneradorService.GenerarReporteDetallado(data['data'], reporte_criterios)
                    return reporte
                    #return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
            else:
                data = AtencionService.GenerarDataAtencion(reporte_criterios) 
                if data:
                    if data['total'] == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)
                    reporte_criterios['resumen'] = data['resumen']
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['total'] = data['total']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    #ahora si a generar el reporte
                    reporte = ReporteGeneradorService.GenerarReporteResumido(reporte_criterios)
                    return reporte
                    #return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)
                
        elif reporte_criterios['modelo'] == 'imagenologia':
            if reporte_criterios['detalles'] == 1:
                return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
            else:
                data = EvaluacionService.generarDataEvaluacionRx(reporte_criterios)

                if data:
                    if data['total'] == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)

                    reporte_criterios['resumen'] = data['resumen']
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['total'] = data['total']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    #ahora si a generar el reporte
                    reporte = ReporteGeneradorService.GenerarReporteResumido(reporte_criterios)
                    return reporte
                #   return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)
        elif reporte_criterios['modelo'] == 'estudio_rx':
            if reporte_criterios['detalles'] == 1:
                return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
            else:
                data = EvaluacionService.generarDataEstudioDetalleRx(reporte_criterios)

                if data:
                    if data['total'] == 0:
                        return JsonResponse({'error': 'No hay datos para generar el reporte'}, status=400)

                    reporte_criterios['resumen'] = data['resumen']
                    reporte_criterios['etiqueta'] = data['etiqueta']
                    reporte_criterios['total'] = data['total']
                    reporte_criterios['campo_agrupado'] = data['campo_agrupado']
                    reporte_criterios['usuario'] = usuario.username
                    reporte_criterios['usuario_nombre'] = f"{usuario.first_name}-{usuario.last_name}"
                    #ahora si a generar el reporte
                    reporte = ReporteGeneradorService.GenerarReporteResumido(reporte_criterios)
                    return reporte
                    #return JsonResponse({'error': 'Reporte en desarrollo'}, status=400)
                else:
                    return JsonResponse({'error': 'No logramos construir informacion para este reporte'}, status=400)


        else:
            return JsonResponse({'error': 'Los otros modelos para repote aun estan desarrollo'}, status=400)



class reporte_detalle_recepcion_atenciones(View):

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
            recepcion = RecepcionAtencionService.definir_recepcion_atencion(recepcion_id)
            
            if not recepcion:
                return JsonResponse({"error": "No se encontró la recepción con ese ID."}, status=404)

            # Crear el servicio de recepción
            service = RecepcionAtencionService(recepcion)

            # Obtener los detalles de la recepción
            detalles = service.obtener_detalles()


            if not detalles:
                return JsonResponse({"error": "No se encontraron detalles para esta recepción."}, status=404)

            
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Recepcion-{recepcion.id}.pdf"'
            pdf = canvas.Canvas(response, pagesize=letter)
            pdf.setTitle(f"Recepcion Atenciones-{recepcion.id}")
            ancho, alto = letter

            y = alto - 30  # Margen superior


            def dibujar_titulo_detalle_recepcion(pdf, ancho, alto):
                # Título
                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawCentredString(ancho / 2, alto - 100, f"DETALLE DE RECEPCION DE ATENCIONES #{recepcion_id}")
                

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
            encabezado = [["Fecha Atencion", "Expediente", "DNI", "Nombre"]]
            data = encabezado.copy() # Encabezado
            fila_actual = 1
            sala_actual = None
            paginas = []
            estilosPaginas = []
            estiloPagina = []


            for reg in detalles:
                if reg["atencion__especialidad__servicio__nombre_servicio"] != sala_actual:
                    data.append(
                    [f"{reg['atencion__especialidad__servicio__nombre_servicio']}", "", "", ""]) # fila de sala
                    estiloPagina.append(('SPAN', (0, fila_actual), (-1, fila_actual)))
                    estiloPagina.append(('LINEBELOW', (0, fila_actual), (-1, fila_actual), 0.5, colors.grey))
                    estiloPagina.append(('BACKGROUND', (0, fila_actual), (-1, fila_actual), colors.lightgrey))
                    estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                    estiloPagina.append(('FONTNAME', (0, fila_actual), (-1, fila_actual), 'Helvetica-Bold'))
                    estiloPagina.append(('TOPPADDING', (0, fila_actual), (-1, fila_actual), 6))
                    estiloPagina.append(('BOTTOMPADDING', (0, fila_actual), (-1, fila_actual), 3))

                    estiloPagina.append(('LEFTPADDING', (0, fila_actual), (-1, fila_actual), 35))
                    fila_actual += 1
                    sala_actual = reg["atencion__especialidad__servicio__nombre_servicio"]
                
                #subtotales
                sala = reg["atencion__especialidad__servicio__nombre_servicio"]
                conteo_por_sala[sala] = conteo_por_sala.get(sala, 0) + 1
                total_general += 1
                data.append([
                        formatear_fecha_dd_mm_yyyy_hh_mm(reg["atencion__fecha_atencion"]), 
                        formatear_expediente(reg["expediente_numero"]), 
                        formatear_dni(reg["atencion__paciente__dni"]), 
                        formatear_nombre_completo(
                            reg["atencion__paciente__primer_nombre"],
                            reg["atencion__paciente__segundo_nombre"],
                            reg["atencion__paciente__primer_apellido"],
                            reg["atencion__paciente__segundo_apellido"],
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


    pdf.drawImage(aside, x=0, y=-55, width=105, height=900, preserveAspectRatio=True, mask='auto')
    pdf.drawImage(logo1, x=60, y=y-45, width=75, height=55, preserveAspectRatio=True, mask='auto')
    pdf.drawImage(logo2, x=ancho-175, y=y-50, width=90, height=65, preserveAspectRatio=True, mask='auto')
    pdf.drawImage(logo3, x=ancho-105, y=y-50, width=90, height=65, preserveAspectRatio=True, mask='auto')


#/*     informes Catologos         */
class InformesCatalogo(View):

    # ======= CONSTANTES LOCALES DE LA CLASE =======
    INFORMES_TITULOS = {
        1: "CATALOGO DE REFERENCIAS ENVIADAS :",
        2: "CATALOGO DE REFERECNIAS RECIBIDAS :",
    }


    # Grupos lógicos de informes
    CATOLOGOS_REFERENCIA = {1, 2}

    def post(self, request, *args, **kwargs):
        usuario = request.user

        # --- Cargar JSON ---
        data, error = cargar_json(request)
        if error:
            return error
        

        reporte_criterios = {
            'fechaIni': data.get('fechaIni'),
            'fechaFin': data.get('fechaFin'),
            'catalogo': data.get('catalogo'),
        }

        missing = [k for k, v in reporte_criterios.items() if v in (None, '')]
        if missing:
            return JsonResponse({'error': f'Faltan parámetros: {", ".join(missing)}'}, status=400)

        try: # VALIDADO Y CON BUENOS RANGUITOS
            fecha_ini, fecha_fin = convertir_rango_fechas(
                reporte_criterios['fechaIni'],
                reporte_criterios['fechaFin']
            )
            reporte_criterios['fechaIni'] = fecha_ini
            reporte_criterios['fechaFin'] = fecha_fin
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

        catalogo = 0
        try:
            catalogo = validar_informe(reporte_criterios['catalogo'], [1,2])
            reporte_criterios.update({'catalogo': catalogo})
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        ##ahora si genramos la data 
        if catalogo in self.CATOLOGOS_REFERENCIA: #{1, 2} REFERENCIA 
            if catalogo == 1:
                sp = SP_CATALOGO_REFERENCIAS_ENVIADAS
            else:
                sp = SP_CATALOGO_REFERENCIAS_RECIBIDAS

            titulos, data = ServiceExcel.obtener_data_catalogo(sp, fecha_ini, fecha_fin)

            if len(data) == 0:
                return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)
        
            titulo = f"{self.INFORMES_TITULOS.get(catalogo, "CATÁLOGO SIN TÍTULO DEFINIDO")} ENTRE {formatear_fecha_dd_mm_yyyy(fecha_ini)} y {formatear_fecha_dd_mm_yyyy(fecha_fin)}"

            return ServiceExcel.GenerarExcelCatalogo(titulos, data, titulo)
        else:
            return JsonResponse({'error': 'Informe no reconocido.'}, status=400)


