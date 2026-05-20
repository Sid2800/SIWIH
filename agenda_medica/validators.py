from core.validators.main_validator import validar_entero_positivo
from core.validators.fecha_validator import validar_fecha, validar_rango_fechas
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
from types import SimpleNamespace
from django.utils import timezone
from core.constants.choices_constants import EstadoRegistro
from core.constants.domain_constants import EstadoTemporalPeriodo

from agenda_medica.models import Periodo_laboral


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
    