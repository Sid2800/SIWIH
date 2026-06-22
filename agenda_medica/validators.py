from core.validators.main_validator import validar_entero_positivo
from core.validators.fecha_validator import validar_fecha, validar_rango_fechas, validar_horario
from clinico.validators import validar_tipo_atencion_activo
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
from types import SimpleNamespace
from django.utils import timezone
from core.constants.choices_constants import EstadoRegistro, DiaSemana
from core.constants.domain_constants import EstadoTemporalPeriodo

from agenda_medica.models import Periodo_laboral, Dia_laboral


def validarArgumentosPeriodoLaboral(data, usuario):

    id_personal = validar_entero_positivo(data.get('personalSalud'), "Personal de salud" )
    id_jornada = validar_entero_positivo(data.get('jornadaLaboral'),"Jornada Laboral")
    id_periodo = (validar_entero_positivo(data.get('idPeriodo'),"idPeriodo")if data.get('idPeriodo')else None)
    fecha_modificado = data.get('fechaModificado')
    fecha_impacto = data.get('fechaModificadoImpacto')

    if fecha_modificado:
        fecha_modificado = datetime.fromisoformat(
            fecha_modificado.replace("Z", "+00:00")
        )

    if fecha_impacto:
        fecha_impacto = datetime.fromisoformat(
            fecha_impacto.replace("Z", "+00:00")
        )

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
        periodo = PeriodoLaboralService.obtener_periodo_laboral(id_periodo)

        if not periodo:
            raise ValidationError(
                "El período laboral indicado no existe."
            )

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
    

    
def validarReglasCriticasPeriodoLaboral(periodo):

    if not periodo:
        return None 

    periodo_registro = None

    # Fase de modificación
    if periodo.id:

        # Validar que exista y esté activo
        periodo_registro = PeriodoLaboralService.obtener_periodo_laboral(periodo.id)

        if not periodo_registro:
            raise ValidationError(
                "El período indicado no existe o está desactivado."
            )

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
    


def validarArgumentosDiaLaboral(data, usuario):
    configuraciones = data.get('configuraciones')
    numero_dia = data.get('diaNumero')
    periodo_id = data.get('periodoId')


    validar_entero_positivo(numero_dia)
    validar_entero_positivo(periodo_id)



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

    for config in configuraciones:
        validar_entero_positivo(config.id, "Id tipo atencion")
        validar_entero_positivo(config.cupos, "cupos")
        validar_entero_positivo(config.duracion, "duracion")

    # EL RESTO 
    hora_ini, hora_fin = validar_horario(data.get('horaInicio'), data.get('horaFin'))
    

    # Calcular minutos disponibles
    minutos_disponibles = (
        datetime.combine(date.min, hora_fin)
        -
        datetime.combine(date.min, hora_ini)
    ).seconds // 60

    # Calcular minutos ocupados
    minutos_ocupados = sum(
        config.cupos * config.duracion
        for config in configuraciones
    )

    # Validar capacidad horaria
    if minutos_ocupados > minutos_disponibles:
        raise ValidationError(
            "La configuración excede el tiempo disponible."
        )

    #alidaciones para editar
    return SimpleNamespace(
        configuraciones=configuraciones,
        hora_ini=hora_ini,
        hora_fin=hora_fin,
        dia_id=data.get('diaID'),
        dia_numero= numero_dia,
        periodo_id = periodo_id
    )

    

def validarReglasCriticasDiaLaboralCupoAtencion(dia_configuracion):
    # Validar que exista y esté activo
    periodo_registro = PeriodoLaboralService.obtener_periodo_laboral(dia_configuracion.periodo_id)

    if not periodo_registro:
        raise ValidationError(
            "El período indicado no existe o está desactivado."
        )
    
    if periodo_registro.estado_temporal != EstadoTemporalPeriodo.FUTURO:
        raise ValidationError(
            "El período indicado no permite cambios miestra esta en ejecucion"
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
        validar_tipo_atencion_activo(config.id)


    return periodo_registro
        
    