from core.validators.main_validator import validar_entero_positivo
from core.validators.fecha_validator import validar_fecha, validar_rango_fechas
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

    try:
        fecha_inicio = datetime.strptime(
            data.get('fechaInicio'),
            "%Y-%m-%d"
        )

        fecha_final = datetime.strptime(
            data.get('fechaFinal'),
            "%Y-%m-%d"
        )

    except ValueError:
        raise ValidationError(
            "Formato de fecha inválido"
        )

    validar_fecha(fecha_final, permitir_futuro=True)
    validar_fecha(fecha_inicio, permitir_futuro=True)

    validar_rango_fechas(
        fecha_inicio,
        fecha_final,
        permitir_inicio_hoy=False,
        permitir_fin_igual_inicio=True
    )

    return SimpleNamespace(
        personal_id=int(id_personal),
        jornada_id=int(id_jornada),
        fecha_inicio=fecha_inicio,
        fecha_final=fecha_final,
        usuario_id=usuario,
        id=int(id_periodo) if id_periodo else None,
    )
    

    
def validarReglasCriticasPeriodoLaboral(periodo):

    if not periodo:
        return None

    periodo_registro = None

    # Fase de modificación
    if periodo.id:

        # Validar que exista y esté activo
        periodo_registro = Periodo_laboral.objects.filter(
            id=periodo.id,
            estado=EstadoRegistro.ACTIVO
        ).first()

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

            # No permitir modificar fecha inicial
            if periodo.fecha_inicio.date() != periodo_registro.fecha_inicio:
                raise ValidationError(
                    "No se permite modificar la fecha inicial "
                    "de un período en ejecución."
                )

            # Fecha final debe ser mayor a hoy
            if not periodo.fecha_final.date() > hoy:
                raise ValidationError(
                    "La fecha final de un período en ejecución "
                    "debe ser mayor a hoy."
                )

    return SimpleNamespace(
        periodo_registro=periodo_registro
    )