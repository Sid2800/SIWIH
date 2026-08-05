from core.validators.main_validator import validar_entero_positivo
from core.validators.fecha_validator import validar_fecha, validar_rango_fechas, validar_horario
from clinico.validators import validar_tipo_atencion_activo
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
from types import SimpleNamespace
from django.utils import timezone
from core.constants.choices_constants import EstadoRegistro, DiaSemana
from core.constants.domain_constants import EstadoTemporalPeriodo, LogApp
from core.utils.utilidades_logging import log_error, log_info, log_warning
from core.utils.utilidades_fechas import parsear_fecha_iso, fechas_iguales
from agenda_medica.models import Periodo_laboral, Dia_laboral


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

        # Fase de modificación
        if periodo.id:

            # Validar que exista y esté activo
            periodo_registro = cls._validarExistenciaPeriodoLaboral(periodo.id)


            # Cambio de personal
            if periodo.personal_id != periodo_registro.personal_salud.id:
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
    def validarReglasCriticasDiaLaboralCupoAtencion(cls, dia_configuracion):
        # Validar que exista y esté activo
        periodo_registro = PeriodoLaboralValidator._validarExistenciaPeriodoLaboral(dia_configuracion.periodo_id)

        cls._validarEstadoNoFuturo(periodo_registro)

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
    def validarReglasCriticasDiaLaboral(cls, dia_configuracion):

        dia_id = dia_configuracion.dia_id
        periodo_id = dia_configuracion.periodo_id
        n_dia = dia_configuracion.dia_numero

        # valido el id de dia porquie no lo verifico en argumentos
        dia_id = validar_entero_positivo(dia_id, "Dia Id")

        #primero que el periodo  exista 
        dia_configuracion.periodo_registro = PeriodoLaboralValidator._validarExistenciaPeriodoLaboral(periodo_id)

        #validar que periodo no se futuro
        cls._validarEstadoNoFuturo(dia_configuracion.periodo_registro )

        #validar que dias labnorarl pertenezca al periodo indicado
        dia_configuracion.dia_registro = cls._validarPertenenciaDiaLaboral_PeriodoLaboral(dia_id, periodo_id, n_dia)

        # Configuraciones existentes del día
        dia_configuracion.configuraciones_registro = (
            dia_configuracion.dia_registro.cupos.filter(
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

            
        




