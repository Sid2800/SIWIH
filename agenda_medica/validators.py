from core.validators.main_validator import validar_entero_positivo, validar_booleano
from core.validators.fecha_validator import validar_fecha, validar_rango_fechas, validar_horario
from clinico.validators import validar_tipo_atencion_activo
from rrhh.validators import validar_personal_salud_activo
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from core.services.agenda_medica.ausencia_service import AusenciaService
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
from types import SimpleNamespace
from django.utils import timezone
from core.constants.choices_constants import EstadoRegistro, DiaSemana, TipoMovimientoCita, EstadoCupoAgenda, TipoAusencia
from core.constants.domain_constants import EstadoTemporalPeriodo, LogApp
from core.utils.utilidades_logging import log_error, log_info, log_warning
from core.utils.utilidades_fechas import parsear_fecha_iso, fechas_iguales, obtener_fechas_por_dia_semana
from agenda_medica.models import Periodo_laboral, Dia_laboral,Cupo_agenda, Configuracion_cupo, Ausencia
from django.db.models import Prefetch
from cita.models import Historial_cita

class PeriodoLaboralValidator:

    @classmethod
    def _validarExistenciaPeriodoLaboral(cls, id_periodo):
        periodo = PeriodoLaboralService.obtener_periodo_laboral(id_periodo)

        if not periodo:
            raise ValidationError(
                "El período laboral indicado no existe."
            )
        return periodo
    

    @classmethod
    def validarArgumentosPeriodoLaboral(cls,data, usuario):

        id_personal = validar_entero_positivo(data.get('personalSalud'), "Personal de salud" )
        id_jornada = validar_entero_positivo(data.get('jornadaLaboral'),"Jornada Laboral")
        id_periodo = (validar_entero_positivo(data.get('idPeriodo'),"idPeriodo")if data.get('idPeriodo')else None)
        fecha_modificado = data.get('fechaModificado')
        fecha_impacto = data.get('fechaModificadoImpacto')

        if fecha_modificado:
            fecha_modificado = parsear_fecha_iso(fecha_modificado)

        if fecha_impacto:
            fecha_impacto = parsear_fecha_iso(fecha_impacto)


        estado = data.get('estado')

        try:
            fecha_inicio = datetime.strptime(
                data.get('fechaInicio'),
                "%Y-%m-%d"
            ).date()

            fecha_final = datetime.strptime(
                data.get('fechaFinal'),
                "%Y-%m-%d"
            ).date()

        except ValueError:
            raise ValidationError(
                "Formato de fecha inválido"
            )

        periodo = None

        # Validación para edición
        if id_periodo:
            
            periodo = cls._validarExistenciaPeriodoLaboral(id_periodo)

            estado_temporal = periodo.estado_temporal
            # Período en ejecución
            if estado_temporal == EstadoTemporalPeriodo.EN_EJECUCION:
                validar_fecha( fecha_inicio,permitir_futuro=False, permitir_pasado=True)
                validar_fecha(fecha_final,permitir_futuro=True,permitir_pasado=True)
            # Período finalizado
            elif estado_temporal == EstadoTemporalPeriodo.FINALIZADO:
                validar_fecha(fecha_inicio, permitir_pasado=True)
                validar_fecha(fecha_final, permitir_pasado=True)
            # FUTURO
            else:
                validar_fecha(fecha_inicio, permitir_futuro=True, permitir_pasado=False)
                validar_fecha(fecha_final, permitir_futuro=True,permitir_pasado=False )


        # Validación para creación
        else:
            validar_fecha(fecha_inicio, permitir_futuro=True, permitir_pasado=False)
            validar_fecha(fecha_final, permitir_futuro=True, permitir_pasado=False)

        validar_rango_fechas(
            fecha_inicio,
            fecha_final,
            permitir_fin_igual_inicio=True
        )

        return SimpleNamespace(
            personal_id=int(id_personal),
            jornada_id=int(id_jornada),
            fecha_inicio=fecha_inicio,
            fecha_final=fecha_final,
            usuario_id=usuario,
            estado=estado,
            id=id_periodo,
            fecha_modificado=fecha_modificado,
            fecha_impacto=fecha_impacto
        )
        

    @classmethod
    def validarReglasCriticasPeriodoLaboral(cls, periodo):

        if not periodo:
            return None

        periodo_registro = None

        # Validar que el personal exista y esté activo
        personal_salud = validar_personal_salud_activo(periodo.personal_id)

        # Fase de modificación
        if periodo.id:

            # Validar que exista y esté activo
            periodo_registro = cls._validarExistenciaPeriodoLaboral(periodo.id)

            # Cambio de personal
            if personal_salud.id != periodo_registro.personal_salud.id:
                raise ValidationError(
                    "No se permite el cambio de personal en un período laboral."
                )

            # Cambio de jornada laboral
            if periodo.jornada_id != periodo_registro.jornada_laboral.id:
                raise ValidationError(
                    "No se permite el cambio de jornada en un período laboral."
                )

            # Estado real del período registrado
            estado = periodo_registro.estado_temporal

            # Validar según estado
            if estado == EstadoTemporalPeriodo.FINALIZADO:

                raise ValidationError(
                    "El período ha finalizado, no es posible modificarlo."
                )

            elif estado == EstadoTemporalPeriodo.EN_EJECUCION:

                hoy = timezone.localdate()

                if periodo.estado is False:
                    raise ValidationError(
                        "No se permite desactivar un periodo en ejecucion"
                    )

                # No permitir modificar fecha inicial
                if periodo.fecha_inicio != periodo_registro.fecha_inicio:
                    raise ValidationError(
                        "No se permite modificar la fecha inicial "
                        "de un período en ejecución."
                    )

                # Fecha final debe ser mayor a hoy
                if periodo.fecha_final <= hoy:
                    raise ValidationError(
                        "La fecha final de un período en ejecución "
                        "debe ser mayor a hoy."
                    )

        return periodo_registro
        


class DiaLaboralValidator:
    
    @classmethod
    def _validarPertenenciaDiaLaboral_PeriodoLaboral(cls, dia_id, periodo_id, dia_numero):
        dia_registro = Dia_laboral.objects.filter(
            id=dia_id,
            periodo_laboral_id=periodo_id,
            dia_semana=dia_numero,
            estado=EstadoRegistro.ACTIVO
        ).first()

        if dia_registro is None:
            raise ValidationError(
                "El día laboral no pertenece al período indicado."
            )
        
        return dia_registro
    
    @classmethod
    def _validarEstadoNoFuturo(cls, periodo):

        if periodo.estado_temporal != EstadoTemporalPeriodo.FUTURO:
            raise ValidationError(
                "El período indicado no permite cambios mientras esta en ejecucion"
            )

        
    # se usa en calidaror de quitar dia quirugico
    @classmethod
    def _validarDiaQuirurgico(cls, id_dia_laboral):

        return Dia_laboral.objects.filter(
            id=id_dia_laboral,
            estado=EstadoRegistro.ACTIVO,
            dia_quirurgico__estado=EstadoRegistro.ACTIVO
        ).first()


    @classmethod
    def _validarDiaNoQuirurgico(cls, id_periodo_laboral, dia_semana):

        return not Dia_laboral.objects.filter(
            periodo_laboral_id=id_periodo_laboral,
            dia_semana=dia_semana,
            estado=EstadoRegistro.ACTIVO,
            dia_quirurgico__estado=EstadoRegistro.ACTIVO
        ).exists()
        

    @classmethod
    def _validarSecuenciaOrdenConfiguraciones(cls, configuraciones):
        """
        Valida que las configuraciones activas tengan un orden
        consecutivo (1..N), sin duplicados y que las eliminadas
        tengan orden 0.
        """

        ordenes = []

        for config in configuraciones:

            if config.eliminado:
                if config.orden != 0:
                    raise ValidationError(
                        "El orden de una configuración eliminada es inválido."
                    )
                continue

            ordenes.append(config.orden)

        ordenes_ordenados = sorted(ordenes)
        esperado = list(range(1, len(ordenes_ordenados) + 1))

        if ordenes_ordenados != esperado:
            raise ValidationError(
                "La secuencia de órdenes de las configuraciones es inválida."
            )


    @classmethod
    def _validarConfiguracionesDuplicadas(cls, configuraciones):

        ids_recibidos = set()

        for config in configuraciones:

            if config.id is None:
                continue

            if config.id in ids_recibidos:
                raise ValidationError(
                    "Se recibieron configuraciones duplicadas."
                )

            ids_recibidos.add(config.id)


    @classmethod
    def _validarDiaDentroPeriodo(cls, periodo, dia_numero):

        fechas_dia = obtener_fechas_por_dia_semana(
            periodo.fecha_inicio,
            periodo.fecha_fin,
            dia_numero
        )

        if not fechas_dia:
            raise ValidationError(
                "El día seleccionado no existe dentro del período laboral."
            )


    @classmethod
    def validarPersistenciaDiaLaboral(cls, dia_laboral, fecha_validada):
        # valida que la decha de validacion  sea la ultima  editada
        if not fechas_iguales(
            dia_laboral.fecha_modificado,
            fecha_validada
        ):
            raise ValidationError(
                "El día laboral fue modificado por otro usuario. "
                "Por favor, reinicie el proceso."
            )



    @classmethod
    def validarArgumentosDiaLaboral(cls, data):

        configuraciones = data.get('configuraciones')
        numero_dia = data.get('diaNumero')
        periodo_id = data.get('periodoId')


        validar_entero_positivo(numero_dia, "Dia Semana")
        validar_entero_positivo(valor=periodo_id, nombre_campo="Id Periodo")

        fecha_modificado = data.get('fechaModificado')
        fecha_modificado = parsear_fecha_iso(fecha_modificado)


        if int(numero_dia) not in DiaSemana.values:
            raise ValidationError(
                "Día de semana inválido."
            )

        # validaciones generales agregar 

        # Validar lista
        if not isinstance(configuraciones, list):
            raise ValidationError(
                "Las configuraciones son inválidas."
            )

        # Validar no vacío
        if not configuraciones:
            raise ValidationError(
                "Debe agregar al menos una configuración."
            )

        # validar casa uno de los registros 
        configuraciones = [
            SimpleNamespace(**config)
            for config in configuraciones
        ]

        minutos_ocupados = 0

        for config in configuraciones:
            if config.id is not None:#Validamos solo si viene indicado que es edicion
                validar_entero_positivo(config.id,"Id configuración")

            #la llave eliminado debe existix
            if not isinstance(config.eliminado, bool):
                raise ValueError(
                    "El indicador de eliminación es inválido."
                )
            
            # Si es una configuración nueva eliminada,
            # nunca debió llegar al backend.
            if config.id is None and config.eliminado:
                raise ValidationError(
                    "La configuración enviada es inválida."
                )

        
            #si esta elimnado saltamos el resto de reglas
            if config.eliminado:
                continue

            # Validar orden siempre
            validar_entero_positivo(
                config.orden,
                "Orden"
            )

            validar_entero_positivo(config.id_tipo_atencion, "Id tipo atencion")
            validar_entero_positivo(config.cupos, "cupos")
            validar_entero_positivo(config.duracion, "duracion")
            # Calcular minutos ocupados
            minutos_ocupados += config.cupos * config.duracion

        cls._validarSecuenciaOrdenConfiguraciones(configuraciones)
        cls._validarConfiguracionesDuplicadas(configuraciones)



        # EL RESTO 
        hora_ini, hora_fin = validar_horario(data.get('horaInicio'), data.get('horaFin'))


        # Calcular minutos disponibles
        minutos_disponibles = (
            datetime.combine(date.min, hora_fin)
            -
            datetime.combine(date.min, hora_ini)
        ).seconds // 60


        # Validar capacidad horaria
        if minutos_ocupados > minutos_disponibles:
            raise ValidationError(
                "La configuración excede el tiempo disponible."
            )

        return SimpleNamespace(
            configuraciones=configuraciones,
            hora_ini=hora_ini,
            hora_fin=hora_fin,
            dia_id=data.get('diaID'),
            dia_numero = int(numero_dia),
            periodo_id = periodo_id,
            fecha_modificado=fecha_modificado
        )



    @classmethod
    def validarCreacionDiaLaboral(cls, dia_configuracion):
        # Validar que exista y esté activo
        periodo_registro = PeriodoLaboralValidator._validarExistenciaPeriodoLaboral(dia_configuracion.periodo_id)

        cls._validarEstadoNoFuturo(periodo_registro)


        # Validar que el día exista dentro del período

        cls._validarDiaDentroPeriodo(periodo_registro, dia_configuracion.dia_numero)


        # Validar que el día no sea quirúrgico
        if not cls._validarDiaNoQuirurgico(
            periodo_registro.id,
            dia_configuracion.dia_numero
        ):
            raise ValidationError(
                "No se puede configurar este día porque está definido como día quirúrgico."
            )

        existe = Dia_laboral.objects.filter(
                periodo_laboral=periodo_registro,
                dia_semana=dia_configuracion.dia_numero,
                estado=EstadoRegistro.ACTIVO
            ).exists()

        if existe:
            raise ValidationError(
                "Ya existe configuración para este día."
            )

        for config in dia_configuracion.configuraciones:
            validar_tipo_atencion_activo(config.id_tipo_atencion)


        return periodo_registro
    


    @classmethod
    def validarEdicionDiaLaboral(cls, dia_configuracion):

        dia_id = dia_configuracion.dia_id
        periodo_id = dia_configuracion.periodo_id
        n_dia = dia_configuracion.dia_numero

        # valido el id de dia porquie no lo verifico en argumentos
        dia_id = validar_entero_positivo(dia_id, "Dia Id")

        #primero que el periodo  exista 
        dia_configuracion.periodo_registro = PeriodoLaboralValidator._validarExistenciaPeriodoLaboral(periodo_id)

        #validar que periodo no se futuro
        cls._validarEstadoNoFuturo(dia_configuracion.periodo_registro )

        #validar que el dia exista dentro del periodo
        cls._validarDiaDentroPeriodo(dia_configuracion.periodo_registro, n_dia)

        #validar que dias labnorarl pertenezca al periodo indicado
        dia_configuracion.dia_registro = cls._validarPertenenciaDiaLaboral_PeriodoLaboral(dia_id, periodo_id, n_dia)

        # Configuraciones existentes del día
        dia_configuracion.configuraciones_registro = (
            dia_configuracion.dia_registro.configuraciones_cupo.filter(
                estado=EstadoRegistro.ACTIVO
            )
        )

        ids_configuraciones_bd = {
            config.id
            for config in dia_configuracion.configuraciones_registro
        }

        #validar la cantidad si no es la misma algo fallo 
        if len(dia_configuracion.configuraciones) < len(ids_configuraciones_bd):
            log_error(
                f"La cantidad de configuraciones del frontend ({len(dia_configuracion.configuraciones)}) "
                f"es menor que la registrada en la base de datos ({len(ids_configuraciones_bd)}).",
                LogApp.AGENDA
            )

            raise ValueError(
                "Inconsistencia en las configuraciones recibidas."
            )
        
        
        ids_recibidos = set()

        for config in dia_configuracion.configuraciones:

            # Solo validar las que ya existen en BD
            if config.id is None:
                continue

            # Validar ids duplicados
            if config.id in ids_recibidos:
                log_error(
                    f"La configuración {config.id} fue enviada más de una vez.",
                    LogApp.AGENDA
                )

                raise ValueError(
                    "Se recibieron configuraciones duplicadas."
                )

            ids_recibidos.add(config.id)

            # Validar pertenencia al día laboral
            if config.id not in ids_configuraciones_bd:
                log_error(
                    f"La configuración {config.id} no pertenece al día laboral {dia_configuracion.dia_registro.id}.",
                    LogApp.AGENDA
                )

                raise ValueError(
                    "La configuración recibida no pertenece al día laboral."
                )


    @classmethod
    def validarEliminarDiaLaboral(cls, data):

        dia_id = data.get("diaID")

        validar_entero_positivo(
            dia_id,
            "Id día laboral"
        )

        dia_laboral = (
            Dia_laboral.objects
            .filter(
                id=dia_id,
                estado=EstadoRegistro.ACTIVO
            )
            .prefetch_related(
                Prefetch(
                    "configuraciones_cupo",
                    queryset=Configuracion_cupo.objects.prefetch_related(
                        Prefetch(
                            "cupos_agenda",
                            queryset=(
                                Cupo_agenda.objects
                                .filter(
                                    estado__in=[
                                        EstadoCupoAgenda.DISPONIBLE,
                                        EstadoCupoAgenda.ASIGNADO
                                    ]
                                )
                                .prefetch_related(
                                    Prefetch(
                                        "historial_citas",
                                        queryset=Historial_cita.objects.filter(
                                            actual=True,
                                            tipo_movimiento__in=[
                                                TipoMovimientoCita.ASIGNACION,
                                                TipoMovimientoCita.REPROGRAMACION
                                            ]
                                        ),
                                        to_attr="historial_actual"
                                    )
                                )
                            ),
                            to_attr="cupos_registro"
                        )
                    ),
                    to_attr="configuraciones_registro"
                )
            )
            .first()
        )

        if dia_laboral is None:

            raise ValidationError(
                "El día laboral indicado no existe o ya no está activo."
            )


        if cls._validarDiaQuirurgico(dia_id):
            raise ValidationError(
                "No se puede eliminar un día quirúrgico desde este proceso."
            )

        return dia_laboral



class AgendaMedicaValidator:

    @staticmethod
    def validar_consulta(params):
        MAX_DIAS_AGENDA = 45
        medico = params.get("medico")
        fecha_inicio = params.get("fecha_inicio")
        fecha_fin = params.get("fecha_fin")

        validar_entero_positivo(medico, "Persnal de salud")

        if not fecha_inicio:
            raise ValidationError(
                "La fecha_inicio es requerida."
            )

        if not fecha_fin:
            raise ValidationError(
                "La fecha_fin es requerida."
            )

        try:
            fecha_inicio = datetime.strptime(
                fecha_inicio,
                "%Y-%m-%d"
            ).date()

            fecha_fin = datetime.strptime(
                fecha_fin,
                "%Y-%m-%d"
            ).date()

        except (TypeError, ValueError):
            raise ValidationError(
                "Las fechas deben tener formato YYYY-MM-DD."
            )

        validar_fecha(
            fecha_inicio,
            permitir_futuro=True
        )

        validar_fecha(
            fecha_fin,
            permitir_futuro=True
        )

        validar_rango_fechas(
            fecha_inicio,
            fecha_fin,
            permitir_fin_igual_inicio=True
        )

        if (fecha_fin - fecha_inicio).days > MAX_DIAS_AGENDA:
            raise ValidationError(
                f"El rango de fechas no puede superar los {MAX_DIAS_AGENDA} días."
            )

        return SimpleNamespace(
            medico=medico,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )


class DiaQuirurgicoValidator:

    @classmethod
    def validarDiaQuirurgico(cls, data):

        periodo_id = data.get('periodoId')
        dia_numero = data.get('diaNumero')

        validar_entero_positivo(
            periodo_id,
            "Id período"
        )

        validar_entero_positivo(
            dia_numero,
            "Día semana"
        )

        if int(dia_numero) not in DiaSemana.values:
            raise ValidationError(
                "Día de semana inválido."
            )

        periodo_registro = (
            PeriodoLaboralValidator
            ._validarExistenciaPeriodoLaboral(periodo_id)
        )

        existe_dia_laboral = Dia_laboral.objects.filter(
            periodo_laboral=periodo_registro,
            dia_semana=int(dia_numero),
            estado=EstadoRegistro.ACTIVO
        ).exists()

        if existe_dia_laboral:
            raise ValidationError(
                "El día seleccionado ya se encuentra configurado en este período."
            )

        return SimpleNamespace(
            periodo_registro=periodo_registro,
            dia_numero=int(dia_numero)
        )

    @classmethod
    def validarQuitarDiaQuirurgico(cls, data):

        dia_laboral_id = data.get("diaLaboralId")

        validar_entero_positivo(
            dia_laboral_id,
            "Id día laboral"
        )

        dia_laboral = DiaLaboralValidator._validarDiaQuirurgico(dia_laboral_id)

        if not dia_laboral:
            raise ValidationError(
                "El día laboral seleccionado no corresponde a un día quirúrgico."
            )

        return dia_laboral



class AusenciaValidator:


    @classmethod
    def _validarExistenciaAusencia(cls, id_ausencia):
        periodo = AusenciaService.obtener_ausencia(id_ausencia)

        if not periodo:
            raise ValidationError(
                "La ausencia indicada no existe."
            )
        return periodo


    @classmethod
    def _validarSolapamientoAusencia(cls, criterios):

        qs = Ausencia.objects.filter(
            personal_salud_id=criterios.personal_id,
            fecha_inicio__lte=criterios.fecha_final,
            fecha_fin__gte=criterios.fecha_inicio,
            estado=EstadoRegistro.ACTIVO,
        )


        if criterios.ausencia_id:
            qs = qs.exclude(id=criterios.ausencia_id)



        if qs.exists():
            raise ValidationError(
                "El período de ausencia se solapa con otra ausencia registrada "
                "para el mismo personal de salud."
            )

    @classmethod
    def validarPersistenciaAusencia(cls, ausencia, fecha_validada):
        # valida que la decha de validacion  sea la ultima  editada
        if not fechas_iguales(
            ausencia.fecha_modificado,
            fecha_validada
        ):
            raise ValidationError(
                "La ausencia fue modificado por otro usuario. "
                "Por favor, reinicie el proceso."
            )
        

    @classmethod
    def validarReglasCriticasAusencias(cls, criterios):
        """
        Validación de reglas de negocio para la creación y edición de ausencias.
        """

        if criterios.ausencia_id:
            # 1. Validar existencia de la ausencia en BD
            criterios.ausencia_db = cls._validarExistenciaAusencia(criterios.ausencia_id)

            # 2. Validar pertenencia de personal de salud
            if criterios.ausencia_db.personal_salud_id != criterios.personal_id:
                raise ValidationError(
                    "El personal de salud indicado no corresponde a la ausencia seleccionada."
                )

            estado_temporal = criterios.ausencia_db.estado_temporal

            # 3. Reglas según estado temporal

            # PERÍODO EN EJECUCIÓN:
            # Solo se permite modificar fecha final y observaciones.
            # La fecha inicial y el estado no se pueden modificar.
            if estado_temporal == EstadoTemporalPeriodo.EN_EJECUCION:
                validar_fecha(criterios.fecha_inicio, permitir_futuro=False, permitir_pasado=True)
                validar_fecha(criterios.fecha_final, permitir_futuro=True, permitir_pasado=False)

                # La fecha de inicio no se puede alterar si el proceso ya inició
                if criterios.fecha_inicio != criterios.ausencia_db.fecha_inicio:
                    raise ValidationError(
                        "No se permite modificar la fecha inicial de una ausencia en ejecución."
                    )

                if criterios.estado == EstadoRegistro.INACTIVO:
                    raise ValidationError(
                        "No es posible desactivar una ausencia en ejecucion."
                    )

            # PERÍODO FINALIZADO: Es inmutable (no se modifica rango ni se desactiva)
            elif estado_temporal == EstadoTemporalPeriodo.FINALIZADO:
                raise ValidationError(
                    "No se puede modificar una ausencia que ya ha finalizado."
                )

            # PERÍODO FUTURO: Se permite cambio de rango de fechas y desactivación
            elif estado_temporal == EstadoTemporalPeriodo.FUTURO:
                validar_fecha(criterios.fecha_inicio, permitir_futuro=True, permitir_pasado=False)
                validar_fecha(criterios.fecha_final, permitir_futuro=True, permitir_pasado=False)

                # Validar que el nuevo rango no traslade la ausencia.
                fecha_inicio_original = criterios.ausencia_db.fecha_inicio
                fecha_final_original = criterios.ausencia_db.fecha_fin

                fecha_inicio_nueva = criterios.fecha_inicio
                fecha_final_nueva = criterios.fecha_final

                # REDUCCIÓN:
                # El nuevo rango está contenido dentro del original.
                if (
                    fecha_inicio_nueva >= fecha_inicio_original
                    and fecha_final_nueva <= fecha_final_original
                ):
                    pass

                # AUMENTO:
                # El nuevo rango contiene al original.
                elif (
                    fecha_inicio_nueva <= fecha_inicio_original
                    and fecha_final_nueva >= fecha_final_original
                ):
                    pass

                # TRASLADO:
                # Los rangos se cruzan o están separados, pero
                # ninguno contiene completamente al otro.
                else:
                    raise ValidationError(
                        "Las nuevas fechas no pueden trasladar el período de ausencia. "
                        "Solo se permite reducir o ampliar el período original."
                    )

            else:
                raise ValidationError(
                    "Estado temporal de ausencia no válido."
                )

        # VALIDACIÓN PARA CREACIÓN
        else:
            criterios.ausencia_db = None
            validar_fecha(criterios.fecha_inicio, permitir_futuro=True, permitir_pasado=False)
            validar_fecha(criterios.fecha_final, permitir_futuro=True, permitir_pasado=False)

        # 4. Validar solapamiento con otras ausencias activas
        cls._validarSolapamientoAusencia(criterios)

        




    @classmethod
    def validarArgumentosAusencia(cls,data, usuario):
        #Agregar/Editar
        id_personal = validar_entero_positivo(data.get('personalSalud'), "Personal de salud" )
        tipo = validar_entero_positivo(data.get('tipo'),"Tipo de Ausencia")
        estado = validar_booleano(data.get('estado'), "Estado")
        observaciones = data.get('observaciones')

        if observaciones is not None:
            observaciones = observaciones.strip() or None

        #Editar
        id_ausencia = (validar_entero_positivo(data.get('ausenciaID'),"idAusencia")if data.get('ausenciaID')else None)
        fecha_modificado = data.get('fechaModificado')


        if fecha_modificado:
            fecha_modificado = parsear_fecha_iso(fecha_modificado)


        #Agregar/Editar
        try:
            fecha_inicio = datetime.strptime(
                data.get('fechaInicio'),
                "%Y-%m-%d"
            ).date()

            fecha_final = datetime.strptime(
                data.get('fechaFinal'),
                "%Y-%m-%d"
            ).date()

        except ValueError:
            raise ValidationError(
                "Formato de fecha inválido"
            )

    

        #Agregar/Editar
        validar_rango_fechas(
            fecha_inicio,
            fecha_final,
            permitir_fin_igual_inicio=True
        )

        TipoAusencia.validar(tipo)

        return SimpleNamespace(
            personal_id=id_personal,
            tipo_id=tipo,
            fecha_inicio=fecha_inicio,
            fecha_final=fecha_final,
            usuario_id=usuario,
            estado=EstadoRegistro.ACTIVO if estado else EstadoRegistro.INACTIVO,
            ausencia_id=id_ausencia,
            fecha_modificado=fecha_modificado,
            observaciones=observaciones,
        )

