from imagenologia.models import Estudio, MaquinaRX
from imagenologia.models import EvaluacionRxDetalle, EvaluacionRx, PacienteExterno
from core.services.server_image.media_service import MediaService
from core.constants.domain_constants import AccionEstudio
from django.core.exceptions import ValidationError
from core.exceptions import EvaluacionDominioError
from django.db import transaction
from django.db.models import Q, F, Case, When, Value, CharField, Count, Sum, IntegerField
from django.db.models.functions import Concat, ExtractDay
from datetime import date,datetime
from django.utils import timezone
import calendar
from collections import defaultdict
from core.utils.utilidades_mensajes import mostrar_resultado_media
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.validators.main_validator import validar_entero_positivo
from django.core.exceptions import ObjectDoesNotExist


class EvaluacionService:

    @staticmethod
    def validar_evaluacion_paciente(evaluacion_id, paciente_id):
        return EvaluacionRx.objects.filter(
            id=evaluacion_id,
            paciente_id=paciente_id
        ).exists()


    @staticmethod
    def obtener_estudios():
        estudios = Estudio.objects.filter(estado=1).values(
            'id',
            'codigo',
            'descripcion_estudio'
            )  
        
        return list(estudios)
    

    @staticmethod
    def obtener_maquinas_rx_activas():
        maquinas = MaquinaRX.objects.filter(estado=1).values(
            'id',
            'descripcion_maquina'
            )  
        
        return list(maquinas)
    
    
    @staticmethod
    def crear_evaluacionrx_estudio_detalle(id_evaluacionrx, id_estudio, impreso=False):

        id_estudio = validar_entero_positivo(id_estudio, "estudio_id")
        id_evaluacionrx = validar_entero_positivo(id_evaluacionrx, "evaluacion_id")

        try:
            detalle = EvaluacionRxDetalle.objects.create(
                evaluacionRx_id=id_evaluacionrx,
                estudio_id=id_estudio,
                impreso=impreso
            )

            return detalle.id

        except Exception as e:
            raise RuntimeError(
                f"No se pudo crear detalle evaluacion={id_evaluacionrx} estudio={id_estudio} detalle={str(e)}"
            )



    @staticmethod
    def procesar_estudios_evaluacion(evaluacion_id, estudios):

        if not estudios:
            log_warning(
                f"[SIN_ESTUDIOS] evaluacion={evaluacion_id}",
                app=LogApp.RX
            )
            raise EvaluacionDominioError("No se enviaron estudios.")

        id_map = {}
        try:
            with transaction.atomic():

                for estudio in estudios:

                    frontend_id = estudio.get('frontendId')
                    estudio_id = estudio.get('id')
                    detalle_id = estudio.get('idDetalle', 0)
                    impreso = estudio.get('impreso', False)
                    accion = estudio.get('accionEstudio')

                    try:
                        _ = AccionEstudio(accion)
                    except ValueError:
                        log_warning(
                            f"[ACCION_INVALIDA] evaluacion={evaluacion_id} accion={accion}",
                            app=LogApp.RX
                        )
                        raise EvaluacionDominioError("Acción de estudio inválida")

                    if not estudio_id:
                        log_warning(
                                f"[ID_INVALIDO] evaluacion={evaluacion_id} frontend_id={frontend_id}",
                                app=LogApp.RX
                            )
                        raise EvaluacionDominioError("ID de estudio inválido")

                    if detalle_id != 0:

                        try:
                            estudioDetalle = (
                                EvaluacionRxDetalle.objects
                                .select_for_update()
                                .get(id=detalle_id, evaluacionRx_id=evaluacion_id)
                            )
                        except ObjectDoesNotExist:
                            log_error(
                                f"[DETALLE_NO_EXISTE] evaluacion={evaluacion_id} detalle_id={detalle_id}",
                                app=LogApp.RX
                            )
                            raise

                        if accion == AccionEstudio.DELETE:
                            if estudioDetalle.activo:  # evitar update innecesario
                                estudioDetalle.activo = False
                                estudioDetalle.save(update_fields=["activo"])
                            else:
                                log_warning(
                                    f"[YA_INACTIVO] evaluacion={evaluacion_id} detalle_id={detalle_id}",
                                    app=LogApp.RX
                                )
                            continue

                        fields_to_update = []

                        if estudioDetalle.impreso != impreso:
                            estudioDetalle.impreso = impreso
                            fields_to_update.append("impreso")

                        if estudioDetalle.estudio_id != estudio_id:
                            estudioDetalle.estudio_id = estudio_id
                            fields_to_update.append("estudio_id")

                        if fields_to_update:
                            estudioDetalle.save(update_fields=fields_to_update)

                    else:

                        if accion == AccionEstudio.DELETE:
                            continue

                        nuevo_id = EvaluacionService.crear_evaluacionrx_estudio_detalle(
                            evaluacion_id,
                            estudio_id,
                            impreso
                        )

                        id_map[frontend_id] = nuevo_id

            return id_map
        except Exception as e:
            log_error(
                f"[FALLO_PROCESO] evaluacion={evaluacion_id} detalle={str(e)}",
                app=LogApp.RX
            ) 
            raise


    @staticmethod
    def obtener_estudios_evaluacion(evaluacion_id, paciente_id):
        """
        Obtiene los estudios asociados a una evaluación.
        """
        estudios = EvaluacionRxDetalle.objects.filter(
            evaluacionRx_id=evaluacion_id, 
            evaluacionRx__paciente_id=paciente_id,
            activo=True
        ).values(
            'id',
            'estudio__id',
            'estudio__codigo',
            'estudio__descripcion_estudio',
            'impreso'
        )
        
        return list(estudios)


    @staticmethod  
    def obtener_paciente_externo_DNI(dni_e):
        """
        Obtiene la informacion del paciente esterno del dni recibido
        """
        try:
            paciente_externo = PacienteExterno.objects.get(dni=dni_e, activo=1)
            return paciente_externo  
        except PacienteExterno.DoesNotExist:
            return None


    @staticmethod
    def cambiar_referencia_evaluacion_externo_interno(idPaciente, idExterno):

        if not idPaciente or not idExterno:
            log_warning(
                f"[ID_INVALIDO] paciente={idPaciente} externo={idExterno}",
                app=LogApp.RX
            )
            raise EvaluacionDominioError("IDs inválidos para cambio de referencia.")

        try:
            with transaction.atomic():

                evaluaciones = EvaluacionRx.objects.filter(
                    paciente_externo_id=idExterno
                )

                actualizadas = evaluaciones.update(
                    paciente_id=idPaciente,
                    paciente_externo_id=None
                )

                if actualizadas == 0:
                    log_warning(
                        f"[SIN_EVALUACIONES] externo={idExterno}",
                        app=LogApp.RX
                    )

            return actualizadas

        except Exception as e:
            log_error(
                f"[FALLO_CAMBIO_REFERENCIA] paciente={idPaciente} externo={idExterno} detalle={str(e)}",
                app=LogApp.RX
            )
            raise


    @staticmethod
    def procesar_paciente_externo(externo, usuario):
        """Asigna un padre/madre a un paciente, creando o actualizando registros."""
        try:
            # Extraer valores de 'externo' de forma segura
            ext_id = externo.get('id')
            ext_dni = externo.get('dni')
            ext_nombre1 = externo.get('nombre1')
            ext_nombre2 = externo.get('nombre2')
            ext_apellido1 = externo.get('apellido1')
            ext_apellido2 = externo.get('apellido2')
            ext_fecha_nac = externo.get('fechaNacimiento')
            ext_sexo = externo.get('sexo')


            def actualizar_datos_externo(paciente_externo):
                """Actualiza los datos del padre/madre solo si han cambiado."""
                cambios = False
                if paciente_externo.dni != ext_dni:
                    paciente_externo.dni = ext_dni
                    cambios = True
                if paciente_externo.primer_nombre != ext_nombre1:
                    paciente_externo.primer_nombre = ext_nombre1
                    cambios = True
                if paciente_externo.segundo_nombre != ext_nombre2:
                    paciente_externo.segundo_nombre = ext_nombre2
                    cambios = True
                if paciente_externo.primer_apellido != ext_apellido1:
                    paciente_externo.primer_apellido = ext_apellido1
                    cambios = True
                if paciente_externo.segundo_apellido != ext_apellido2:
                    paciente_externo.segundo_apellido = ext_apellido2
                    cambios = True
                if paciente_externo.fecha_nacimiento != ext_fecha_nac:
                    paciente_externo.fecha_nacimiento = ext_fecha_nac
                    cambios = True
                if paciente_externo.sexo != ext_sexo:
                    paciente_externo.sexo = ext_sexo
                    cambios = True

                if cambios:
                    paciente_externo.modificado_por = usuario
                    paciente_externo.save()

                return paciente_externo

            def crear():
                """Crea un paciente externo si no existe."""
                if not ext_nombre1 or not ext_apellido1:
                    log_warning(
                        f"[DATOS_INSUFICIENTES] intento crear externo sin nombre/apellido dni={ext_dni}",
                        app=LogApp.RX
                    )
                    raise ValidationError("No se puede crear paciente externo sin nombre1 y apellido1.")
                paciente_nuevo = PacienteExterno.objects.create(
                    dni=ext_dni if ext_dni else None,
                    primer_nombre=ext_nombre1.upper() if ext_nombre1 else None,
                    segundo_nombre=ext_nombre2 if ext_nombre2 else None,
                    primer_apellido=ext_apellido1.upper() if ext_apellido1 else None,
                    segundo_apellido=ext_apellido2 if ext_apellido2 else None,
                    fecha_nacimiento=ext_fecha_nac,
                    sexo=ext_sexo,
                    creado_por=usuario,
                    modificado_por=usuario
                )
                return paciente_nuevo

            # 1. Buscar por ID
            if ext_id:
                try:
                    paciente_externo = PacienteExterno.objects.get(id=ext_id)
                    return actualizar_datos_externo(paciente_externo)
                except PacienteExterno.DoesNotExist:
                    log_warning(
                        f"[NO_EXISTE] externo_id={ext_id}",
                        app=LogApp.RX
                    )
                    raise ValidationError(f"No existe paciente externo con id {ext_id}")

            # 2. Buscar por DNI
            if ext_dni:
                try:
                    paciente_externo = PacienteExterno.objects.get(dni=ext_dni)
                    return actualizar_datos_externo(paciente_externo)
                except PacienteExterno.DoesNotExist:
                    return crear()

            # 3. Crear si hay nombres y apellidos
            if ext_nombre1 and ext_apellido1:
                return crear()

            # 4. Sin datos clave, error
            log_warning(
                f"[SIN_DATOS] no se pudo identificar externo id={ext_id} dni={ext_dni}",
                app=LogApp.RX
            )
            raise ValidationError("Datos insuficientes para crear o actualizar paciente externo.") 
        
        except Exception as e:
            log_error(
                f"[FALLO_PROCESO] externo_id={ext_id} dni={ext_dni} detalle={str(e)}",
                app=LogApp.RX
            )
            raise      
    


    @staticmethod
    def inactivar_paciente_externo(id):

        try:
            paciente_e = PacienteExterno.objects.get(id=id, activo=True)
            paciente_e.activo = False
            paciente_e.save(update_fields=["activo"])

        except PacienteExterno.DoesNotExist:
            log_warning(
                f"[NO_EXISTE_O_INACTIVO] externo_id={id}",
                app=LogApp.RX
            )
            return False

        except Exception as e:
            log_error(
                f"[FALLO_INACTIVAR] externo_id={id} detalle={str(e)}",
                app=LogApp.RX
            )
            raise

        return True


    @staticmethod
    def inactivar_evaluacion_rx(evaluacionId, usuario):
        detalles_ids = []
        try:
            with transaction.atomic():
                evaluacion = EvaluacionRx.objects.filter(
                    id=evaluacionId,
                    estado=1
                ).first()

                if not evaluacion:
                    log_warning(
                        f"[NO_EXISTE_O_INACTIVA] evaluacion={evaluacionId}",
                        app=LogApp.RX
                    )
                    return False
                
                evaluacion.estado = 2
                evaluacion.save(update_fields=["estado"])

                # Obtener ids antes de actualizar
                detalles_ids = list(
                    EvaluacionRxDetalle.objects.filter(
                        evaluacionRx=evaluacionId,
                        activo=1
                    ).values_list("id", flat=True)
                )

                EvaluacionRxDetalle.objects.filter(
                    id__in=detalles_ids
                ).update(activo=0)

            if detalles_ids:
                try:
                    paciente_tipo, paciente_id = evaluacion.obtener_tipo_y_paciente_id()

                    media_result = MediaService.desactivar_imagenes_evaluacion(
                        detalles_ids=detalles_ids,
                        paciente_tipo=paciente_tipo,
                        paciente_id=paciente_id,
                        usuario=usuario
                    )

                except Exception as e:
                    log_error(
                        f"[FALLO_MEDIA] evaluacion={evaluacionId} detalle={str(e)}",
                        app=LogApp.MEDIA
                    )
                

            return True , media_result
        except Exception as e:
            log_error(
                f"[FALLO_INACTIVAR] evaluacion={evaluacionId} detalle={str(e)}",
                app=LogApp.RX
            )
            raise


    @staticmethod
    def listar_evaluaciones_por_paciente(id_paciente):
        try:
            evaluaciones_qs = EvaluacionRx.objects.filter(
                paciente_id=id_paciente,
                estado=1
            ).annotate(
                total_estudios=Count('detalles', filter=Q(detalles__activo=True)),
                nombre_dependencia=Case(
                    When(sala__isnull=False, then=F('sala__nombre_sala')),
                    When(especialidad__isnull=False, then=F('especialidad__nombre_especialidad')),
                    When(servicio_auxiliar__isnull=False, then=F('servicio_auxiliar__nombre_servicio_a')),
                    default=Value('Desconocido'),
                    output_field=CharField()
                ),
                tipo_dependencia=Case(
                    When(sala__isnull=False, then=Value('HOSP')),
                    When(especialidad__isnull=False, then=Value('CEXT')),
                    When(servicio_auxiliar__isnull=False, then=Value('SVAUX')),
                    default=Value('DESC'),
                    output_field=CharField()
                )
            )

            evaluaciones = list(evaluaciones_qs.values(
                "id",
                "fecha",
                "nombre_dependencia",
                "tipo_dependencia",
                "maquinarx__descripcion_maquina",
                "total_estudios",
                "modificado_por__username",
                "fecha_modificado"
            ))

            return evaluaciones

        except Exception as e:
            return []


    #Informes
    @staticmethod
    def generarDataEvaluacionRx(reporte_criterios):
        """
        Filtra y agrupa datos de ingresos según criterios, calculando totales y porcentajes para resúmenes.
        Retorna la data procesada lista para la generación de reportes.
        """
        try:
            qs = EvaluacionRx.objects.all()
            qs = qs.filter(estado=1)

            # Filtro por campo específico
            if 'campoFiltro' in reporte_criterios and 'valorFiltro' in reporte_criterios:
                campo_original = reporte_criterios['campoFiltro']
                valor_original = str(reporte_criterios['valorFiltro'])

                if campo_original == 'dependencia_id' and '-' in valor_original:
                    indicador, valor_id = valor_original.split('-', 1)

                    dependencia_map = {
                        'A': 'servicio_auxiliar_id',
                        'E': 'especialidad_id',
                        'S': 'sala_id',
                    }

                    campo = dependencia_map.get(indicador)
                    if campo:
                        qs = qs.filter(**{campo: valor_id})
                elif campo_original != 'ninguno':
                    qs = qs.filter(**{campo_original: valor_original})
                

            # Filtro por fecha de inicio
            if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

            # Filtro por fecha de fin
            if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})


            if reporte_criterios.get('agrupacion') == 'dependencia_id':
                qs_dependencia = qs.annotate(
                    dependencia_nombre=Case(
                        When(sala__isnull=False, then=Concat(F('sala__nombre_sala'), Value(' | HOSP'))),
                        When(especialidad__isnull=False, then=Concat(F('especialidad__nombre_especialidad'), Value(' | CEXT'))),
                        When(servicio_auxiliar__isnull=False, then=Concat(F('servicio_auxiliar__nombre_servicio_a'), Value(' | SAUX'))),
                        default=Value('Sin asignar'),
                        output_field=CharField()
                    )
                )
                resumen_raw = qs_dependencia.values('dependencia_nombre').annotate(
                    total=Count('id')
                ).order_by('-total')

                nombre_amigable = "Dependencia"
                campo_agrupado = 'dependencia_nombre'
            else:
                # Diccionario con campos posibles para agrupación
                agrupacion_campos = {
                    'creado_por_id': ('creado_por__username', 'usuario creador'),
                    'modificado_por_id': ('modificado_por__username', 'usuario editor'),
                    'paciente__sector__aldea__municipio__departamento_id': (
                        'paciente__sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'
                    ),
                    'maquinarx_id': ('maquinarx__descripcion_maquina', 'Máquina RX'),
                }

                agrupacion_key = reporte_criterios['agrupacion']

                campo_agrupado, nombre_amigable = agrupacion_campos.get(
                    agrupacion_key,
                    (agrupacion_key, agrupacion_key)
                )

                resumen_raw = qs.values(campo_agrupado).annotate(
                    total=Count('id')
                ).order_by('-total')

            total = qs.count()
            resumen = []


            for item in resumen_raw:
                porcentaje = (item['total'] / total) * 100 if total > 0 else 0
                resumen.append({
                    campo_agrupado: item[campo_agrupado],
                    'total': item['total'],
                    'porcentaje': round(porcentaje, 2)
                })

            return {
                'campo_agrupado': campo_agrupado,
                'etiqueta': nombre_amigable,
                'total': total,
                'resumen': resumen
            }
        

        except Exception as e:
            log_error(
                f"[FALLO_REPORTE_RX] criterios={reporte_criterios} detalle={str(e)}",
                app=LogApp.RX
            )
            return None
        

    @staticmethod
    def generarDataEstudioDetalleRx(reporte_criterios):
        """
        Filtra y agrupa datos de ingresos según criterios, calculando totales y porcentajes para resúmenes.
        Retorna la data procesada lista para la generación de reportes.
        """
        try:
            qs = EvaluacionRxDetalle.objects.all()
            qs = qs.filter(activo=1)

            
            # Filtro por campo específico
            if 'campoFiltro' in reporte_criterios and 'valorFiltro' in reporte_criterios:
                campo_original = reporte_criterios['campoFiltro']
                valor_original = str(reporte_criterios['valorFiltro'])

                if campo_original == 'dependencia_id' and '-' in valor_original:
                    indicador, valor_id = valor_original.split('-', 1)

                    dependencia_map = {
                        'A': 'evaluacionRx__servicio_auxiliar_id',
                        'E': 'evaluacionRx__especialidad_id',
                        'S': 'evaluacionRx__sala_id',
                    }

                    campo = dependencia_map.get(indicador)
                    if campo:
                        qs = qs.filter(**{campo: valor_id})
                elif campo_original != 'ninguno':
                    qs = qs.filter(**{campo_original: valor_original})
                

            # Filtro por fecha de inicio
            if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                campo_fecha = reporte_criterios.get('interaccion')
                qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

            # Filtro por fecha de fin
            if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                campo_fecha = reporte_criterios.get('interaccion')
                qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})


            if reporte_criterios.get('agrupacion') == 'dependencia_id':
                qs_dependencia = qs.annotate(
                    dependencia_nombre=Case(
                        When(
                            evaluacionRx__sala__isnull=False,
                            then=Concat(F('evaluacionRx__sala__nombre_sala'), Value(' | HOSP'))
                        ),
                        When(
                            evaluacionRx__especialidad__isnull=False,
                            then=Concat(F('evaluacionRx__especialidad__nombre_especialidad'), Value(' | CEXT'))
                        ),
                        When(
                            evaluacionRx__servicio_auxiliar__isnull=False,
                            then=Concat(F('evaluacionRx__servicio_auxiliar__nombre_servicio_a'), Value(' | SAUX'))
                        ),
                        default=Value('Sin asignar'),
                        output_field=CharField()
                    )
                )

                resumen_raw = qs_dependencia.values('dependencia_nombre').annotate(
                    total=Count('id')
                ).order_by('-total')

                nombre_amigable = "Dependencia"
                campo_agrupado = 'dependencia_nombre'
            elif reporte_criterios.get('agrupacion') == 'evaluacion':
                qs_dependencia = qs.annotate(
                    evaluacion_paciente = Concat(F('evaluacionRx__paciente__dni'), Value(' | '), F('evaluacionRx__paciente__primer_nombre'), Value(' '),F('evaluacionRx__paciente__primer_apellido'),)
                )

                resumen_raw = qs_dependencia.values('evaluacion_paciente').annotate(
                    total=Count('id')
                ).order_by('-total')

                nombre_amigable = "Paciente"
                campo_agrupado = 'evaluacion_paciente'
                
            else:
                # Diccionario con campos posibles para agrupación
                agrupacion_campos = {
                    'evaluacionRx__paciente__sector__aldea__municipio__departamento_id': (
                        'evaluacionRx__paciente__sector__aldea__municipio__departamento__nombre_departamento', 'Departamento'
                    ),
                    'evaluacionRx__maquinarx_id': ('evaluacionRx__maquinarx__descripcion_maquina', 'Maquina RX'),
                    'estudio_id': ('estudio__descripcion_estudio', 'Estudio'),
                    
                }

                agrupacion_key = reporte_criterios['agrupacion']

                campo_agrupado, nombre_amigable = agrupacion_campos.get(
                    agrupacion_key,
                    (agrupacion_key, agrupacion_key)
                )

                resumen_raw = qs.values(campo_agrupado).annotate(
                    total=Count('id')
                ).order_by('-total')

            total = qs.count()
            resumen = []


            for item in resumen_raw:
                valor_agrupado = item[campo_agrupado]

                # Convertir True/False a "Sí"/"No" si el campo es 'impreso'
                if campo_agrupado == 'impreso':
                    valor_agrupado = "SI" if valor_agrupado else "NO"
                porcentaje = (item['total'] / total) * 100 if total > 0 else 0

                resumen.append({
                    campo_agrupado: valor_agrupado, # Usar el valor transformado
                    'total': item['total'],
                    'porcentaje': round(porcentaje, 2)
                })


            return {
                'campo_agrupado': campo_agrupado,
                'etiqueta': nombre_amigable,
                'total': total,
                'resumen': resumen
            }
        

        except Exception as e:
            log_error(
                f"[FALLO_REPORTE_ESTUDIO_RX] criterios={reporte_criterios} detalle={str(e)}",
                app=LogApp.RX
            )
            return None
        

    @staticmethod
    def generarDataInformeGastoCostoPelicula(mes, anio, indice =1):
        """
        Filtra y agrupa datos de ingresos según criterios, calculando totales y porcentajes para resúmenes.
        Retorna la data procesada lista para la generación de reportes.
        """
        try:
            if anio is None:
                anio = date.today().year

            qs = EvaluacionRxDetalle.objects.filter(activo=1,impreso=1).select_related(
                'evaluacionRx',
                'estudio',
                'evaluacionRx__sala',
                'evaluacionRx__especialidad',
                'evaluacionRx__servicio_auxiliar'
            )

            #filtro
            if mes and anio:
                qs = qs.filter(
                    evaluacionRx__fecha__year =anio,
                    evaluacionRx__fecha__month =mes,
                )

            # Anotar dependencia y día
            qs = qs.annotate(
                dia=ExtractDay('evaluacionRx__fecha'),
                dependencia_nombre=Case(
                    When(evaluacionRx__sala__isnull=False, then=Concat(Value('HOSP | '), F('evaluacionRx__sala__nombre_sala'))),
                    When(evaluacionRx__especialidad__isnull=False, then=Concat(Value('CEXT | '), F('evaluacionRx__especialidad__nombre_especialidad'))),
                    When(evaluacionRx__servicio_auxiliar__isnull=False, then=Concat(Value('SAUX | '),F('evaluacionRx__servicio_auxiliar__nombre_servicio_a'))),
                    default=Value('Sin asignar'),
                    output_field=CharField()
                )
            )

            # Agrupar por dependencia y día
            if indice == 1:
                resumen_raw = qs.values('dependencia_nombre', 'dia').annotate(
                    conteo=Count('id')
                ).order_by('dia','dependencia_nombre')
            elif indice == 2:
                resumen_raw = qs.values('dependencia_nombre', 'dia').annotate(
                    conteo=Sum('estudio__coste_impresion')
                ).order_by('dia','dependencia_nombre')
                

            # Conteo total (opcional)
            total = qs.count()

            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe

            # recorremos cada registro de resumen_raw
            for item in resumen_raw:
                dependencia = item['dependencia_nombre'][:38]    # nombre de la dependencia
                if dependencia == 'CEXT | EMERGENCIA GENERAL':
                    dependencia = 'EMER | EMERGENCIA GENERAL'
                dia = item['dia']                           # número del día
                conteo = item['conteo']                     # cantidad de registros

                # llenamos el diccionario: si no existe la clave, se crea automáticamente
                tabla[dependencia][dia] = conteo

            # Calcular último día del mes dinámicamente
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dias_mes = range(1, ultimo_dia + 1)

            #tabla final
            tabla_final = []
            
            for dependencia in sorted(tabla.keys()):
                dias_data = tabla[dependencia]
                fila = [dependencia]  # primera columna: nombre de la dependencia
                total_fila = 0 

                for dia in dias_mes:
                    conteo = dias_data.get(dia, 0)  # se asegura de que si no hay valor sea 0
                    fila.append(conteo)
                    total_fila += conteo

                fila.append(total_fila)  # agregamos el total al final de la fila
                tabla_final.append(tuple(fila))

            # Ahora calculamos el total por columna
            totales_columna = ['TOTAL']  # primera columna con etiqueta
            num_columnas_dias = len(dias_mes)

            for i in range(1,num_columnas_dias + 2): #+1 para sumar la ultima columna agregada o mejro dicho el total de fila
                # sumamos ese día en todas las filas
                suma_columna = 0
                for fila in tabla_final:
                    suma_columna += fila[i]
                # agregamos esta suma a la lista de totales por columna
                totales_columna.append(suma_columna)

            tabla_final.append(tuple(totales_columna))

            return {
                    'total': total,
                    'tabla': tabla_final,
                    'dias': dias_mes
                }
            
        except Exception as e:
            log_error(
                f"[FALLO_REPORTE_GASTO_PELICULA] mes={mes} anio={anio} indice={indice} detalle={str(e)}",
                app=LogApp.RX
            )
            return None


    @staticmethod
    def generarDataInformePacienteSala(mes, anio):
        """
        Filtra y agrupa datos de ingresos según criterios, calculando totales y porcentajes para resúmenes.
        Retorna la data procesada lista para la generación de reportes.
        """
        try:
            if anio is None:
                anio = date.today().year

            qs = EvaluacionRx.objects.filter(estado=1).select_related(
                'sala',
                'especialidad',
                'servicio_auxiliar'
            )

            #filtro
            if mes and anio:
                qs = qs.filter(
                    fecha__year  = anio,
                    fecha__month = mes,
                )

            # Anotar dependencia y día
            qs = qs.annotate(
                dia=ExtractDay('fecha'),
                dependencia_nombre=Case(
                    When(sala__isnull=False, then=Concat(Value('HOSP | '), F('sala__nombre_sala'))),
                    When(especialidad__isnull=False, then=Concat(Value('CEXT | '), F('especialidad__nombre_especialidad'))),
                    When(servicio_auxiliar__isnull=False, then=Concat(Value('SAUX | '),F('servicio_auxiliar__nombre_servicio_a'))),
                    default=Value('Sin asignar'),
                    output_field=CharField()
                )
            )

            # Agrupar por dependencia y día
            resumen_raw = qs.values('dependencia_nombre', 'dia').annotate(
                conteo=Count('id')
            ).order_by('dia','dependencia_nombre')

                
            # Conteo total (opcional)
            total = qs.count()

            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe

            # recorremos cada registro de resumen_raw
            for item in resumen_raw:
                dependencia = item['dependencia_nombre'][:38]    # nombre de la dependencia
                if dependencia == 'CEXT | EMERGENCIA GENERAL':
                    dependencia = 'EMER | EMERGENCIA GENERAL'          
                dia = item['dia']                           # número del día
                conteo = item['conteo']                     # cantidad de registros

                # llenamos el diccionario: si no existe la clave, se crea automáticamente
                tabla[dependencia][dia] = conteo

            # Calcular último día del mes dinámicamente
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dias_mes = range(1, ultimo_dia + 1)

            #tabla final
            tabla_final = []
            
            for dependencia in sorted(tabla.keys()):
                dias_data = tabla[dependencia]
                fila = [dependencia]  # primera columna: nombre de la dependencia
                total_fila = 0 

                for dia in dias_mes:
                    conteo = dias_data.get(dia, 0)  # se asegura de que si no hay valor sea 0
                    fila.append(conteo)
                    total_fila += conteo

                fila.append(total_fila)  # agregamos el total al final de la fila
                tabla_final.append(tuple(fila))

            # Ahora calculamos el total por columna
            totales_columna = ['TOTAL']  # primera columna con etiqueta
            num_columnas_dias = len(dias_mes)

            for i in range(1,num_columnas_dias + 2): #+1 para sumar la ultima columna agregada o mejro dicho el total de fila
                # sumamos ese día en todas las filas
                suma_columna = 0
                for fila in tabla_final:
                    suma_columna += fila[i]
                # agregamos esta suma a la lista de totales por columna
                totales_columna.append(suma_columna)

            tabla_final.append(tuple(totales_columna))

            return {
                    'total': total,
                    'tabla': tabla_final,
                    'dias': dias_mes
                }
            
        except Exception as e:
            log_error(
                f"[FALLO_REPORTE_PACIENTE_SALA] mes={mes} anio={anio} detalle={str(e)}",
                app=LogApp.RX
            )
            return None
                

    @staticmethod
    def generarDataInformeEstudioDependecia(mes, anio):
        try:
            if anio is None:
                anio = date.today().year

            qs = EvaluacionRxDetalle.objects.filter(activo=1)

            #filtro
            if mes and anio:
                qs = qs.filter(
                    evaluacionRx__fecha__year =anio,
                    evaluacionRx__fecha__month =mes,

                )

            # Anotar dependencia y día intercambiar el truo flase de impreso
            qs = qs.annotate(
                dependencia_nombre=Case(
                    When(evaluacionRx__sala__isnull=False, then=Concat(Value('HP-'), F('evaluacionRx__sala__nombre_corto_sala'))),
                    When(evaluacionRx__especialidad__isnull=False, then=Concat(Value('CE-'), F('evaluacionRx__especialidad__nombre_corto_especialidad'))),
                    When(evaluacionRx__servicio_auxiliar__isnull=False, then=Concat(Value('SA-'),F('evaluacionRx__servicio_auxiliar__nombre_corto_servicio_a'))),
                    default=Value('Sin asignar'),
                    output_field=CharField()
                ),
                impreso_int=Case(
                    When(impreso=True, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )

            # Agrupar por dependencia y día
            resumen_raw = qs.values('dependencia_nombre','estudio__descripcion_estudio').annotate(
                conteo=Count('id'),
                impresas=Sum('impreso_int')
            ).order_by('dependencia_nombre')

            

            # Conteo total (opcional)
            total = qs.count()
            
            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe
            tabla_impresas = defaultdict(lambda: defaultdict(int))
            #tabla final
            tabla_final = []

            for item in resumen_raw:
                estudio = item['estudio__descripcion_estudio'][:23]
                dependencia = item['dependencia_nombre'][:12]
                if dependencia == 'CE-EME-GEN':
                    dependencia = '-EMER-GEN' 
                conteo = item['conteo']
                tabla[estudio][dependencia] = conteo
                tabla_impresas[estudio][dependencia] = int(item['impresas'] or 0)  

            # Encabezados: "ESTUDIO" + dependencias + "TOTAL"
            dependencias_set = set()
            for item in resumen_raw:
                dependencia = item['dependencia_nombre'][:12]  # recortamos
                if dependencia == 'CE-EME-GEN':
                    dependencia = '-EMER-GEN'  # reemplazo específico
                dependencias_set.add(dependencia)

            # Luego ordenar
            dependencias = sorted(dependencias_set)

            tabla_final = [["ESTUDIO"] + dependencias + ["TOTAL"]]
            total_columnas = len(dependencias) 
            # Llenar filas por estudio
            for estudio in sorted(tabla.keys()):
                fila = [estudio]
                total_fila = 0
                for dep in dependencias:
                    conteo = tabla[estudio].get(dep, 0)
                    fila.append(conteo)
                    total_fila += conteo
                fila.append(total_fila)
                tabla_final.append(fila)


            
            # Inicializamos la fila de totales
            totales_columnas = ["TOTAL"] + [0] * (len(dependencias) + 1)  # +1 para la columna TOTAL

            # Recorremos las filas de datos (omitimos la primera fila que es encabezado de fila)
            for fila in tabla_final[1:]:
                for i in range(1, len(fila)):  # desde la columna 1 (dep1) hasta TOTAL
                    totales_columnas[i] += fila[i]

            # Agregamos la fila de totales
            tabla_final.append(totales_columnas)

            # Fila de impresas por columna
            fila_impresas = ["IMPRESAS"]
            for dep in dependencias:
                suma_impresas = sum(tabla_impresas[estudio].get(dep, 0) for estudio in tabla_impresas)
                fila_impresas.append(suma_impresas)
            fila_impresas.append(sum(fila_impresas[1:]))  # total general de impresas
            tabla_final.append(fila_impresas)



            return {
                    'total': total,
                    'tabla': tabla_final,
                    'columnas': total_columnas
                }

        except Exception as e:
            log_error(
                f"[FALLO_REPORTE_ESTUDIO_DEPENDENCIA] mes={mes} anio={anio} detalle={str(e)}",
                app=LogApp.RX
            )
            return None
                    