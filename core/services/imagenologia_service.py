from imagenologia.models import Estudio, MaquinaRX
from imagenologia.models import EvaluacionRxDetalle, EvaluacionRx, PacienteExterno
from core.services.server_image.media_service import MediaService
from core.constants.domain_constants import AccionEstudio
from django.core.exceptions import ValidationError
from core.exceptions import EvaluacionDominioError
from django.db import transaction
from django.db.models import Q, F, Case, When, Value, CharField, Count, Sum, IntegerField
from django.db.models.functions import Concat, ExtractDay, Substr
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
            evaluaciones = EvaluacionRx.objects.filter(
                paciente_id=id_paciente,
                estado=1
            ).select_related(
                'unidad_clinica__sala',
                'unidad_clinica__area_atencion',
                'unidad_clinica__servicio_aux',
                'unidad_clinica__establecimiento_ext'
            ).annotate(
                total_estudios=Count('detalles', filter=Q(detalles__activo=True)),
                unidad_clinica_descripcion=Case(
                    When(
                        unidad_clinica__sala__isnull=False,
                        then=Concat(
                            Value('HOSP- '),
                            F('unidad_clinica__sala__nombre_sala')
                        )
                    ),
                    When(
                        unidad_clinica__area_atencion__isnull=False,
                        then=Concat(
                            Value('AREA- '),
                            F('unidad_clinica__area_atencion__nombre_area_atencion')
                        )
                    ),
                    When(
                        unidad_clinica__servicio_aux__isnull=False,
                        then=Concat(
                            Value('AUX- '),
                            F('unidad_clinica__servicio_aux__nombre_servicio_a')
                        )
                    ),
                    When(
                        unidad_clinica__establecimiento_ext__isnull=False,
                        then=Concat(
                            Value('EXT- '),
                            F('unidad_clinica__establecimiento_ext__nombre_institucion_salud')
                        )
                    ),
                    default=Value('DESC - Desconocido'),
                    output_field=CharField()
                )
            )

            evaluaciones = list(evaluaciones.values(
                "id",
                "fecha",
                "unidad_clinica_descripcion",
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
                campo = reporte_criterios['campoFiltro']
                valor = str(reporte_criterios['valorFiltro'])

                if campo == 'unidad_clinica_id':
                    qs = qs.filter(unidad_clinica_id=valor)

  
                elif campo != 'ninguno':
                    qs = qs.filter(**{campo: valor})
                

            # Filtro por fecha de inicio
            if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

            # Filtro por fecha de fin
            if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                campo_fecha = reporte_criterios.get('interaccion', 'fecha_creado')
                qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})


            if reporte_criterios.get('agrupacion') == 'unidad_clinica_id':
                qs_unidad_clinica = qs.annotate(
                    unidad_clinica_descripcion=Case(
                        When(
                            unidad_clinica__sala__isnull=False,
                            then=Concat(
                                F('unidad_clinica__sala__nombre_sala'),
                                Value(' | HOSP')
                            )
                        ),
                        When(
                            unidad_clinica__area_atencion__isnull=False,
                            then=Concat(
                                F('unidad_clinica__area_atencion__nombre_area_atencion'),
                                Value(' | AREA')
                            )
                        ),
                        When(
                            unidad_clinica__servicio_aux__isnull=False,
                            then=Concat(
                                F('unidad_clinica__servicio_aux__nombre_servicio_a'),
                                Value(' | AUX')
                            )
                        ),
                        When(
                            unidad_clinica__establecimiento_ext__isnull=False,
                            then=Concat(
                                F('unidad_clinica__establecimiento_ext__nivel_complejidad_institucional__siglas'),
                                Value(' '),
                                F('unidad_clinica__establecimiento_ext__nombre_institucion_salud'),
                                Value(' | EXT')
                            )
                        ),
                        default=Value('Sin asignar'),
                        output_field=CharField()
                    )
                )

                resumen_raw = qs_unidad_clinica.values('unidad_clinica_descripcion').annotate(
                    total=Count('id')
                ).order_by('-total')

                nombre_amigable = "Unidad Clinica"
                campo_agrupado = 'unidad_clinica_descripcion'
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
                campo = reporte_criterios['campoFiltro']
                valor = str(reporte_criterios['valorFiltro'])

                if campo == 'unidad_clinica_id':
                    qs = qs.filter(unidad_clinica_id=valor)


                elif campo != 'ninguno':
                    qs = qs.filter(**{campo: valor})

            # Filtro por fecha de inicio
            if 'fechaIni' in reporte_criterios and reporte_criterios['fechaIni']:
                campo_fecha = reporte_criterios.get('interaccion')
                qs = qs.filter(**{f"{campo_fecha}__gte": reporte_criterios['fechaIni']})

            # Filtro por fecha de fin
            if 'fechaFin' in reporte_criterios and reporte_criterios['fechaFin']:
                campo_fecha = reporte_criterios.get('interaccion')
                qs = qs.filter(**{f"{campo_fecha}__lte": reporte_criterios['fechaFin']})


            if reporte_criterios.get('agrupacion') == 'unidad_clinica_id':
                qs_unidad_clinica = qs.annotate(
                    unidad_clinica_descripcion=Case(
                        When(
                            evaluacionRx__unidad_clinica__sala__isnull=False,
                            then=Concat(
                                F('evaluacionRx__unidad_clinica__sala__nombre_sala'),
                                Value(' | HOSP')
                            )
                        ),
                        When(
                            evaluacionRx__unidad_clinica__area_atencion__isnull=False,
                            then=Concat(
                                F('evaluacionRx__unidad_clinica__area_atencion__nombre_area_atencion'),
                                Value(' | AREA')
                            )
                        ),
                        When(
                            evaluacionRx__unidad_clinica__servicio_aux__isnull=False,
                            then=Concat(
                                F('evaluacionRx__unidad_clinica__servicio_aux__nombre_servicio_a'),
                                Value(' | AUX')
                            )
                        ),
                        When(
                            evaluacionRx__unidad_clinica__establecimiento_ext__isnull=False,
                            then=Concat(
                                F('evaluacionRx__unidad_clinica__establecimiento_ext__nivel_complejidad_institucional__siglas'),
                                Value(' '),
                                F('evaluacionRx__unidad_clinica__establecimiento_ext__nombre_institucion_salud'),
                                Value(' | EXT')
                            )
                        ),
                        default=Value('Sin asignar'),
                        output_field=CharField()
                    )
                )

                resumen_raw = qs_unidad_clinica.values('unidad_clinica_descripcion').annotate(
                    total=Count('id')
                ).order_by('-total')

                nombre_amigable = "Unidad Clinica"
                campo_agrupado = 'unidad_clinica_descripcion'

            elif reporte_criterios.get('agrupacion') == 'evaluacion':
                qs_unidad = qs.annotate(
                    evaluacion_paciente = Concat(F('evaluacionRx__paciente__dni'), Value(' | '), F('evaluacionRx__paciente__primer_nombre'), Value(' '),F('evaluacionRx__paciente__primer_apellido'),)
                )

                resumen_raw = qs_unidad.values('evaluacion_paciente').annotate(
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
                'evaluacionRx__unidad_clinica__sala',
                'evaluacionRx__unidad_clinica__area_atencion',
                'evaluacionRx__unidad_clinica__servicio_auxiliar'
                'evaluacionRx__unidad_clinica__establecimiento_ext'

            )

            #filtro
            if mes and anio:
                qs = qs.filter(
                    evaluacionRx__fecha__year =anio,
                    evaluacionRx__fecha__month =mes,
                )

            # Anotar unidad y día
            qs = qs.annotate(
                dia=ExtractDay('evaluacionRx__fecha'),
                unidad_nombre=Case(
                                    When(
                        evaluacionRx__unidad_clinica__sala__isnull=False,
                        then=Concat(
                            Value('HOSP | '),
                            F('evaluacionRx__unidad_clinica__sala__nombre_sala')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__area_atencion__isnull=False,
                        then=Concat(
                            Value('CEXT | '),
                            F('evaluacionRx__unidad_clinica__area_atencion__nombre_area_atencion')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__servicio_aux__isnull=False,
                        then=Concat(
                            Value('AUX | '),
                            F('evaluacionRx__unidad_clinica__servicio_aux__nombre_servicio_a')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__establecimiento_ext__isnull=False,
                        then=Concat(
                            Value('EXTE | '),
                            F('evaluacionRx__unidad_clinica__establecimiento_ext__nivel_complejidad_institucional__siglas'),
                            Value(' '),
                            F('evaluacionRx__unidad_clinica__establecimiento_ext__nombre_institucion_salud')
                        )
                    ),
                    default=Value('Sin asignar'),
                    output_field=CharField()
                )
                    
            )
            

            # Agrupar por unidad_nombre y día
            if indice == 1:
                resumen_raw = qs.values('unidad_nombre', 'dia').annotate(
                    conteo=Count('id')
                ).order_by('dia','unidad_nombre')
            elif indice == 2:
                resumen_raw = qs.values('unidad_nombre', 'dia').annotate(
                    conteo=Sum('estudio__coste_impresion')
                ).order_by('dia','unidad_nombre')
                

            # Conteo total (opcional)
            total = qs.count()

            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe

            # recorremos cada registro de resumen_raw
            for item in resumen_raw:
                unidad_clinica = item['unidad_nombre'][:38]    # nombre de la unidad
                if unidad_clinica == 'CEXT | EMERGENCIA GENERAL':
                    unidad_clinica = 'EMER | EMERGENCIA GENERAL'
                dia = item['dia']                           # número del día
                conteo = item['conteo']                     # cantidad de registros

                # llenamos el diccionario: si no existe la clave, se crea automáticamente
                tabla[unidad_clinica][dia] = conteo

            # Calcular último día del mes dinámicamente
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dias_mes = range(1, ultimo_dia + 1)

            #tabla final
            tabla_final = []
            
            for uc in sorted(tabla.keys()):
                dias_data = tabla[uc]
                fila = [uc]  # primera columna: nombre de la unida
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
                'unidad_clinica__sala',
                'unidad_clinica__area_atencion',
                'unidad_clinica__servicio_auxiliar'
                'unidad_clinica__establecimiento_ext'
            )

            #filtro
            if mes and anio:
                qs = qs.filter(
                    fecha__year  = anio,
                    fecha__month = mes,
                )

            # Anotar unidad y día
            qs = qs.annotate(
                dia=ExtractDay('fecha'),
                unidad_nombre=Case(
                                    When(
                        unidad_clinica__sala__isnull=False,
                        then=Concat(
                            Value('HOSP | '),
                            F('unidad_clinica__sala__nombre_sala')
                        )
                    ),
                    When(
                        unidad_clinica__area_atencion__isnull=False,
                        then=Concat(
                            Value('CEXT | '),
                            F('unidad_clinica__area_atencion__nombre_area_atencion')
                        )
                    ),
                    When(
                        unidad_clinica__servicio_aux__isnull=False,
                        then=Concat(
                            Value('AUX | '),
                            F('unidad_clinica__servicio_aux__nombre_servicio_a')
                        )
                    ),
                    When(
                        unidad_clinica__establecimiento_ext__isnull=False,
                        then=Concat(
                            Value('EXTE | '),
                            F('unidad_clinica__establecimiento_ext__nivel_complejidad_institucional__siglas'),
                            Value(' '),
                            F('unidad_clinica__establecimiento_ext__nombre_institucion_salud')
                        )
                    ),
                    default=Value('Sin asignar'),
                    output_field=CharField()
                )
            )

            # Agrupar por unidad clinica y día
            resumen_raw = qs.values('unidad_nombre', 'dia').annotate(
                conteo=Count('id')
            ).order_by('dia','unidad_nombre')

                
            # Conteo total (opcional)
            total = qs.count()

            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe

            # recorremos cada registro de resumen_raw
            for item in resumen_raw:
                unidad_clinica = item['unidad_nombre'][:38]    # nombre de la unidad
                if unidad_clinica == 'CEXT | EMERGENCIA GENERAL':
                    unidad_clinica = 'EMER | EMERGENCIA GENERAL'          
                dia = item['dia']                           # número del día
                conteo = item['conteo']                     # cantidad de registros

                # llenamos el diccionario: si no existe la clave, se crea automáticamente
                tabla[unidad_clinica][dia] = conteo

            # Calcular último día del mes dinámicamente
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dias_mes = range(1, ultimo_dia + 1)

            #tabla final
            tabla_final = []
            
            for unidad_clinica in sorted(tabla.keys()):
                dias_data = tabla[unidad_clinica]
                fila = [unidad_clinica]  # primera columna: nombre de la unidad
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

            qs = EvaluacionRxDetalle.objects.filter(activo=1).select_related(
                'evaluacionRx',
                'estudio',
                'evaluacionRx__unidad_clinica__sala',
                'evaluacionRx__unidad_clinica__area_atencion',
                'evaluacionRx__unidad_clinica__servicio_auxiliar'
                'evaluacionRx__unidad_clinica__establecimiento_ext'

            )

            #filtro
            if mes and anio:
                qs = qs.filter(
                    evaluacionRx__fecha__year =anio,
                    evaluacionRx__fecha__month =mes,

                )

            
            # Anotar unidad y día intercambiar el truo flase de impreso
            qs = qs.annotate(
                unidad_clinica_descripcion=Case(
                    When(
                        evaluacionRx__unidad_clinica__sala__isnull=False,
                        then=Concat(
                            Value('HP-'),
                            F('evaluacionRx__unidad_clinica__sala__nombre_corto_sala')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__area_atencion__isnull=False,
                        then=Concat(
                            Value('CE-'),
                            F('evaluacionRx__unidad_clinica__area_atencion__nombre_corto_area_atencion')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__servicio_aux__isnull=False,
                        then=Concat(
                            Value('AU-'),
                            F('evaluacionRx__unidad_clinica__servicio_aux__nombre_corto_servicio_a')
                        )
                    ),
                    When(
                        evaluacionRx__unidad_clinica__establecimiento_ext__isnull=False,
                        then=Concat(
                            Value('EX-'),
                            F('evaluacionRx__unidad_clinica__establecimiento_ext__nivel_complejidad_institucional__siglas'),
                            Value(' '),
                            Substr(
                                F('evaluacionRx__unidad_clinica__establecimiento_ext__nombre_institucion_salud'),
                                1, 10
                            )
                        )
                    ),
                    default=Value('DESC - Desconocido'),
                    output_field=CharField()
                ),
                impreso_int=Case(
                    When(impreso=True, then=1),
                    default=0,
                    output_field=IntegerField()
                )
            )

            # Agrupar por unidad y día
            resumen_raw = qs.values('unidad_clinica_descripcion','estudio__descripcion_estudio').annotate(
                conteo=Count('id'),
                impresas=Sum('impreso_int')
            ).order_by('unidad_clinica_descripcion')

            # Conteo total (opcional)
            total = qs.count()
            
            # mapear 
            tabla = defaultdict(lambda: defaultdict(int)) # esta vacia retorna 0 si un indice no existe
            tabla_impresas = defaultdict(lambda: defaultdict(int))
            #tabla final
            tabla_final = []

            for item in resumen_raw:
                estudio = item['estudio__descripcion_estudio'][:23]
                unidad_c = item['unidad_clinica_descripcion'][:14]
                if unidad_c == 'CE-EME-GEN':
                    unidad_c = '-EMER-GEN' 
                conteo = item['conteo']
                tabla[estudio][unidad_c] = conteo
                tabla_impresas[estudio][unidad_c] = int(item['impresas'] or 0)  
            



            # Encabezados: "ESTUDIO" + unidades + "TOTAL"
            unidad_set = set()
            for item in resumen_raw:
                unidad_c = item['unidad_clinica_descripcion'][:14]  # recortamos
                if unidad_c == 'CE-EME-GEN':
                    unidad_c = '-EMER-GEN'  # reemplazo específico
                unidad_set.add(unidad_c)


            # Luego ordenar
            unidades = sorted(unidad_set)

            tabla_final = [["ESTUDIO"] + unidades + ["TOTAL"]]
            total_columnas = len(unidades) 
            # Llenar filas por estudio
            for estudio in sorted(tabla.keys()):
                fila = [estudio]
                total_fila = 0
                for dep in unidades:
                    conteo = tabla[estudio].get(dep, 0)
                    fila.append(conteo)
                    total_fila += conteo
                fila.append(total_fila)
                tabla_final.append(fila)
            
            # Inicializamos la fila de totales
            totales_columnas = ["TOTAL"] + [0] * (len(unidades) + 1)  # +1 para la columna TOTAL

            # Recorremos las filas de datos (omitimos la primera fila que es encabezado de fila)
            for fila in tabla_final[1:]:
                for i in range(1, len(fila)):  # desde la columna 1 (dep1) hasta TOTAL
                    totales_columnas[i] += fila[i]

            # Agregamos la fila de totales
            tabla_final.append(totales_columnas)

            # Fila de impresas por columna
            fila_impresas = ["IMPRESAS"]
            for dep in unidades:
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
                f"[FALLO_REPORTE_ESTUDIO_UNIDAD_CLINICA] mes={mes} anio={anio} detalle={str(e)}",
                app=LogApp.RX
            )
            return None
                    