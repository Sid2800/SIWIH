from django.http import HttpResponse, JsonResponse
from core.services.referencia.referencia_service import ReferenciaService
from core.services.referencia.referencia_informes_service import RefInformeService
from core.services.reporte.PDF.reporte_referencia_service import ReporteReferenciaService
from core.services.reporte.EXCEL.reporte_service_excel import ServiceExcel
from core.validators.fecha_validator import validar_anio, validar_mes
from usuario.permisos import verificar_permisos_usuario
from reporte.validators import validar_informe
from core.utils.utilidades_request import cargar_json
from core.constants import permisos 
from django.views import View
import datetime
import json



class InformesReferencia(View):

    # ======= CONSTANTES LOCALES DE LA CLASE =======
    INFORMES_TITULOS = {
        1: "REFERENCIAS A MAYOR COMPLEJIDAD SEGUN ESPECIALIDAD",
        2: "REFERENCIAS A MAYOR COMPLEJIDAD SEGUN INSTITUCIONES",
        3: "REFERENCIAS A MAYOR COMPLEJIDAD SEGUN MOTIVO",
        4: "SEGUIMIENTO A REFERENCIAS ENVIADAS A MAYOR COMPLEJIDAD",
        5: "REFERENCIAS A MAYOR COMPLEJIDAD SEGUN AREA DE ENVIO",
        6: "REFERENCIAS RECIBIDAS POR GESTOR / DEPTO. / PRIVADA",
        7: "REFERENCIAS RECIBIDAS POR GESTOR / DEPTO. / PRIVADA. DETALLADO",
        8: "REFERENCIAS RECIBIDAS SEGUN EVALUACION",
        9: "RESPUESTAS RESUELTAS SEGUN AREA ATENCION",
        10:"REFERENCIAS Y RESPUESTAS POR GESTOR- OTROS DEP- CLINICA PRIVADA",
        11:"REFERENCIAS ENVIADAS A PRIMER NIVEL DE ATENCION SEGUN GESTOR",
    }

    OBSERVACIONES = {
        8: "Unicamente se incluyen las referencias recibidas, de instuciones que pertenecen a la Secretaria de Salud",
        9: "Se consideran todas las respuestas dadas en el mes seleccionado, incluyendo aquellas que corresponden a referencias recibidas en meses anteriores.",
        10: (
            "Las respuestas brindadas se consideran únicamente si corresponden a referencias recibidas en el mes seleccionado. "
            "No se incluyen respuestas registradas en el mes seleccionado cuya referencia fue recibida en un periodo distinto. "
            "El porcentaje de derivaciones se calcula en función de las respuestas registradas."
        ),
    }

    # Grupos lógicos de informes
    INFORMES_CLASICOS = {1, 2, 3, 5, 8}
    INFORME_SEGUIMIENTO = 4
    INFORMES_RECIBIDAS = {6, 7, 10, 11}
    INFORME_RESPUESTAS = 9


    def _validar_data(self, dataReporte):
        # Validar que exista y que tenga tabla
        if not dataReporte or not dataReporte.get("tabla"):
            return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)

        # Validar total numérico
        try:
            total = int(dataReporte.get("total", 0))
            if total <= 0:
                return JsonResponse({'error': 'No hay datos disponibles para generar el informe.'}, status=404)
        except:
            return JsonResponse({'error': 'Error en formato de datos del informe.'}, status=400)

        return None

    def _agregar_observacion(self, informe, criterios):
        obs = self.OBSERVACIONES.get(informe)
        if obs:
            criterios["observacion"] = obs

    def _agregar_datos_reporte(self, criterios, dataReporte, informe):
        """
        Agrega al diccionario de criterios
        """
        criterios.update({
            'data': dataReporte.get('tabla'),
            'total': dataReporte.get('total'),
            'etiqueta': dataReporte.get('etiqueta'),
            'informe': informe
        })


    def post(self, request, *args, **kwargs):
        usuario = request.user

        # --- Cargar JSON ---
        data, error = cargar_json(request)
        if error:
            return error

        # --- Obtener parámetros ---
        anio = data.get("anio")
        mes = data.get("mes")
        informe = data.get("informe")
        tipo_documento = data.get("tipoDoc")

        # --- Validar que existan ---
        if not all([anio, mes, informe]):
            return JsonResponse({"error": "Debe proporcionar año, mes e informe."}, status=400)

        informe= int(informe)

        titulo_informe = self.INFORMES_TITULOS.get(informe, "INFORME DESCONOCIDO")

        try:
            anio = validar_anio(anio)                
            mes = validar_mes(mes)
            informe = validar_informe(informe, [1,2,3,4,5,6,7,8,9,10,11]) 
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        # Datos base del reporte
        criterios = {
            'mes': mes,
            'anio': anio,
            'usuario': usuario,
            'usuario_nombre': f"{usuario.first_name} {usuario.last_name}",
            'informe': informe,
            'informe_titulo': titulo_informe
        }


        if int(informe) in self.INFORMES_CLASICOS: #[1,2,3,5,8]
            dataReporte = RefInformeService.generarDataInformeReferencia(mes,anio, informe
                                                                        , True if int(informe) !=8 else False)# mayor complejidad
            
            if "error" in dataReporte:
                return JsonResponse({'error': dataReporte['error']}, status=400)
            
            error = self._validar_data(dataReporte)
            if error:
                return error

            self._agregar_datos_reporte(criterios, dataReporte, informe)

            top3 =  dataReporte.get('top3',None)

            self._agregar_observacion(informe,criterios)


            if top3:
                detalle = RefInformeService.generarDetalleInforme1ReferenciaEspecialidad(mes, anio, top3)
                criterios.update({
                    'detalle_informe_1': detalle
                })
                
            if tipo_documento == 1 :
                return ServiceExcel.GenerarExcelReferenciaBase(criterios)
            else:
                return ReporteReferenciaService.GenerarInformeReferencia(criterios)
        elif informe == self.INFORME_SEGUIMIENTO:#4:
            dataReporte = RefInformeService.generarDataInformeSeguimientoTIC(mes,anio)

            if "error" in dataReporte:
                return JsonResponse({'error': dataReporte['error']}, status=400)

            error = self._validar_data(dataReporte)
            if error:
                return error

            self._agregar_datos_reporte(criterios, dataReporte, informe)

            if tipo_documento == 1 :
                return ServiceExcel.GenerarExcelReferenciaBase(criterios)
            else:
                return ReporteReferenciaService.GenerarInformeReferencia(criterios)
        
        elif informe in self.INFORMES_RECIBIDAS:#[6,7,10,11]: #REFERENCIAS RECIBIDAS POR GESTOR   // 6 resumido // detallado / con repuestas
            
            dataReporte = RefInformeService.generarDataInformeRefRecibidasGestor(mes,anio,informe, 1 if informe == 11 else 0)

            if "error" in dataReporte:
                return JsonResponse({'error': dataReporte['error']}, status=400)

            error = self._validar_data(dataReporte)
            if error:
                return error
        
            self._agregar_datos_reporte(criterios, dataReporte, informe)

            self._agregar_observacion(informe,criterios)

            if informe in [6,7]:
                if tipo_documento == 1 :
                    return ServiceExcel.GenerarExcelReferenciaBase(criterios)
                else:
                    return ReporteReferenciaService.GenerarInformeReferencia(criterios)
            else:


                if tipo_documento == 1 :
                    return ServiceExcel.GenerarExcelReferenciaBase(criterios)
                else:
                    return ReporteReferenciaService.GenerarInformeReferenciaColumnas(criterios)
        
            

        elif informe == 9:
            dataReporte = RefInformeService.generarDataInformeRespuesta(mes,anio,1) 

            error = self._validar_data(dataReporte)
            if error:
                return error
            
            self._agregar_datos_reporte(criterios, dataReporte, informe)

            self._agregar_observacion(informe,criterios)


            if tipo_documento == 1 :
                return ServiceExcel.GenerarExcelReferenciaBase(criterios)
            else:
                return ReporteReferenciaService.GenerarInformeReferencia(criterios)
            

        return JsonResponse({'error': 'Informe no reconocido.'}, status=400)


class FormatoReferencia(View):
    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario, permisos.REFERENCIA_VISUALIZACION_ROLES, permisos.REFERENCIA_VISUALIZACION_UNIDADES):
            return JsonResponse({"error": "No tiene permisos para ver este reporte"})
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, referencia_id):
        usuario = request.user

        if not referencia_id:
            return JsonResponse({"error": "El ID de la referencia es requerido."}, status=400)

        try:
            referencia, paciente = RefInformeService.generarDataFormatoReferencia(referencia_id)
            formato = ReporteReferenciaService.GenerarFormatoRefencia(referencia, paciente, usuario)
            return formato
        except Exception as e:
            return JsonResponse({'error': f'Tenemos problema en generar la información del reporte. {e}'}, status=400)
        

class FormatoRespuesta(View):
    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario, permisos.REFERENCIA_VISUALIZACION_ROLES, permisos.REFERENCIA_VISUALIZACION_UNIDADES):
            return JsonResponse({"error": "No tiene permisos para ver este reporte"})
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, respuesta_id):
        usuario = request.user

        if not respuesta_id:
            return JsonResponse({"error": "El ID de la respuesta es requerido."}, status=400)

        try:
            respuesta, paciente = RefInformeService.generarDataFormatoRespuesta(respuesta_id)
            formato = ReporteReferenciaService.GenerarFormatoRespuesta(respuesta, paciente, usuario)
            return formato
        except Exception as e:
            return JsonResponse({'error': f'Tenemos problema en generar la información del reporte. {e}'}, status=400)

