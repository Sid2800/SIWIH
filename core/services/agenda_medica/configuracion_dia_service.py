from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db import transaction
from core.constants.choices_constants import EstadoRegistro, EstadoCupoAgenda
from core.utils.utilidades_fechas import obtener_fechas_por_dia_semana
from agenda_medica.models import Dia_laboral, Configuracion_cupo, Cupo_agenda
from agenda_medica.validators import validarReglasCriticasDiaLaboralCupoAtencion as validarDia
from datetime import datetime, timedelta, date

class ConfiguracionDiaService:

    @staticmethod
    def generar_cupos_agenda(dia_laboral, usuario):
        periodo_laboral = dia_laboral.periodo_laboral
        configuraciones = (
            Configuracion_cupo.objects
            .select_related(
                "tipo_atencion",
                "dia_laboral__periodo_laboral__personal_salud"
            )
            .filter(
                dia_laboral=dia_laboral,
                estado=EstadoRegistro.ACTIVO
            )
        )

        fechas_dias = obtener_fechas_por_dia_semana(
            periodo_laboral.fecha_inicio,
            periodo_laboral.fecha_fin,
            dia_laboral.dia_semana
        )

        cupos_crear = []

        for fecha_dia in fechas_dias:
            hora_actual = dia_laboral.hora_inicio
            for config in configuraciones:
                for _ in range(config.cupos):
                    hora_fin = (
                        datetime.combine(date.today(), hora_actual)
                        +
                        timedelta(minutes=config.duracion_minutos)
                    ).time()
                    cupos_crear.append(
                        Cupo_agenda(
                            personal_salud=config.dia_laboral.periodo_laboral.personal_salud,
                            configuracion_cupo=config,
                            tipo_atencion=config.tipo_atencion,
                            fecha=fecha_dia,
                            hora_inicio=hora_actual,
                            hora_fin=hora_fin,
                            estado=EstadoCupoAgenda.DISPONIBLE,
                            creado_por=usuario,
                            modificado_por=usuario
                        )
                    )

                    hora_actual = hora_fin

        Cupo_agenda.objects.bulk_create(cupos_crear)


    @staticmethod
    def crear_dia_laboral(dia_configuracion, usuario):
        try:
            with transaction.atomic():
                periodo = validarDia(dia_configuracion)
                dia_laboral = Dia_laboral.objects.create(
                    periodo_laboral=periodo,
                    dia_semana=dia_configuracion.dia_numero,
                    hora_inicio=dia_configuracion.hora_ini,
                    hora_fin=dia_configuracion.hora_fin,
                    estado=EstadoRegistro.ACTIVO,
                    creado_por=usuario,
                    modificado_por=usuario,
                )

                configuraciones_crear = []

                for config in dia_configuracion.configuraciones:
                    configuraciones_crear.append(
                        Configuracion_cupo(
                            dia_laboral=dia_laboral,
                            tipo_atencion_id=config.id,
                            cupos=config.cupos,
                            duracion_minutos=config.duracion,
                            estado=EstadoRegistro.ACTIVO,
                        )
                    )

                Configuracion_cupo.objects.bulk_create(configuraciones_crear)
                ConfiguracionDiaService.generar_cupos_agenda(dia_laboral, usuario )

            return True

        except IntegrityError:
            raise ValidationError(
                "Uno de los tipos de atención no existe."
            )