from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db import transaction
from core.constants.choices_constants import EstadoRegistro, EstadoCupoAgenda
from core.constants.domain_constants import LogApp
from core.utils.utilidades_fechas import obtener_fechas_por_dia_semana
from core.utils.utilidades_logging import log_error, log_info

from agenda_medica.models import Dia_laboral, Configuracion_cupo, Cupo_agenda
from agenda_medica.validators import DiaLaboralValidator, PeriodoLaboralService
from datetime import datetime, timedelta, date, time
from types import SimpleNamespace
from django.db.models import Prefetch

class ConfiguracionDiaService:


    @classmethod
    def _crear_cupos_agenda(cls, dia_laboral, configuraciones, fechas_dias, usuario):

        cupos_crear = []

        for fecha_dia in fechas_dias:
            hora_actual = dia_laboral.hora_inicio

            for config in configuraciones:
                for _ in range(config.cupos):

                    hora_fin = (
                        datetime.combine(date.today(), hora_actual)
                        + timedelta(minutes=config.duracion_minutos)
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


    @classmethod
    def generar_cupos_agenda(cls, dia_laboral, usuario):

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

        cls._crear_cupos_agenda(
            dia_laboral,
            configuraciones,
            fechas_dias,
            usuario
        )


    @classmethod
    def obtener_dia_laboral_detallado(cls, id):
        dia_laboral = (
            Dia_laboral.objects
            .select_related(
                "periodo_laboral",
                "creado_por",
                "modificado_por"
            )
            .prefetch_related(
                Prefetch(
                    "cupos",
                    queryset=Configuracion_cupo.objects
                        .select_related("tipo_atencion")
                        .filter(estado=EstadoRegistro.ACTIVO)
                        .order_by("orden")
                )
            )
            .filter(
                id=id,
                estado=EstadoRegistro.ACTIVO
            )
            .first()
        )

        if not dia_laboral:
            return None

        configuraciones = []
        total_cupos = 0

        for config in dia_laboral.cupos.all():
            configuraciones.append({
                "id": config.id,
                "tipoAtencionId": config.tipo_atencion.id,
                "tipoAtencion": config.tipo_atencion.nombre_tipo_atencion,
                "cupos": config.cupos,
                "duracion": config.duracion_minutos,
                "eliminado": False,
            })
            total_cupos += config.cupos


        return {
            "id": dia_laboral.id,
            "periodo_id": dia_laboral.periodo_laboral.id,
            "dia_numero": dia_laboral.dia_semana,
            "dia_nombre": dia_laboral.get_dia_semana_display(),
            "hora_inicio": dia_laboral.hora_inicio,
            "hora_fin": dia_laboral.hora_fin,
            "fecha_modificado": dia_laboral.fecha_modificado,
            "total_cupos": total_cupos,
            "configuraciones": configuraciones,
        }
                

    @classmethod
    def  crear_dia_laboral(cls, dia_configuracion, usuario):
        with transaction.atomic():
            periodo = DiaLaboralValidator.validarReglasCriticasDiaLaboralCupoAtencion(dia_configuracion)

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
                        tipo_atencion_id=config.id_tipo_atencion,
                        cupos=config.cupos,
                        duracion_minutos=config.duracion,
                        orden=config.orden,
                        estado=EstadoRegistro.ACTIVO,
                    )
                )


            Configuracion_cupo.objects.bulk_create(configuraciones_crear)
            cls.generar_cupos_agenda(dia_laboral, usuario )

        return True


    @classmethod
    def _determinarImpactoEliminacionConfiguracionDia(cls, diaConfiguracion):
        
        return {
                "tipoAtencion": diaConfiguracion.tipo_atencion.nombre_tipo_atencion,
                "cupos": diaConfiguracion.total_cupos,
                "citas": 999,
                }


    @classmethod
    def _determinarImpactoEdicionConfiguracionDia(cls, diaConfiguracion, periodo_laboral, cantidad_dias):
        conf_dia_base = diaConfiguracion.configuracion_bd
        conf_dia_front = diaConfiguracion.configuracion_front
        mensajes= []

        # Cambio en la cantidad de cupos
        if conf_dia_front.cuposCambio:

            diferencia = conf_dia_base.cupos - conf_dia_front.cupos

            # Reducción de cupos
            if diferencia > 0:

                cupos_afectados = cantidad_dias * diferencia

                mensajes.append(
                    {
                        "tipoAtencion": conf_dia_base.tipo_atencion.nombre_tipo_atencion,
                        "tipoCambio": "REDUCCION_CUPOS",
                        "cupos": cupos_afectados,
                        "citas": 999,
                    }
                )
            
        # Cambio en la duración
        if conf_dia_front.duracionCambio:

            mensajes.append(
                {
                    "tipoAtencion": conf_dia_base.tipo_atencion.nombre_tipo_atencion,
                    "tipoCambio": "DURACION",
                    "cupos": conf_dia_base.dia_laboral.total_cupos,
                    "citas": 999,
                }
            )

        return mensajes

    @classmethod
    def _obtenerCambiosEditarDiaLaboral(cls, dia_laboral):

        cambios = SimpleNamespace(
                hora_inicio=False,
                hora_fin=False,
                secuencia=False,
                configuraciones_agregar=[],
                configuraciones_editar=[],
                configuraciones_eliminar=[]
            )
        
        # Comparar horario.
        if dia_laboral.dia_registro.hora_inicio != dia_laboral.hora_ini:
            cambios.hora_inicio = True

        if dia_laboral.dia_registro.hora_fin != dia_laboral.hora_fin:
            cambios.hora_fin = True

        # Crear índice de las configuraciones enviadas por el frontend
        configuraciones_front = {
            config.id: config
            for config in dia_laboral.configuraciones
            if config.id is not None
        }

        # Recorrer las configuraciones existentes en BD
        
        #     Detectar tipos eliminados.
        #     Detectar cambios de cupos.
        #     Detectar cambios de duración.
        for config_bd in dia_laboral.configuraciones_registro:

            config_front = configuraciones_front.get(config_bd.id)

            # El validator garantiza que siempre existirá
            if config_front is None:
                continue

            #si se elimina no requiere mas 
            if config_front.eliminado:
                if config_front.id is not None: # solo si id existe de agrega para eliminar
                    cambios.secuencia=True
                    cambios.configuraciones_eliminar.append(config_bd)

                continue

            atencionCambio = False
            cuposCambio = False
            duracionCambio = False


            if config_bd.orden != config_front.orden:
                cambios.secuencia = True

            if config_bd.tipo_atencion_id != config_front.id_tipo_atencion:
                atencionCambio = True

            if config_bd.cupos != config_front.cupos:
                cambios.secuencia=True
                cuposCambio = True

            if config_bd.duracion_minutos != config_front.duracion:
                cambios.secuencia=True
                duracionCambio = True
            
            config_front.atencionCambio = atencionCambio
            config_front.cuposCambio = cuposCambio
            config_front.duracionCambio = duracionCambio

            if (
                config_front.atencionCambio
                or config_front.cuposCambio
                or config_front.duracionCambio
            ):
                cambios.configuraciones_editar.append(
                    SimpleNamespace(
                        configuracion_bd=config_bd,
                        configuracion_front=config_front
                    )
                )

            #obtener los resgitros que requieren adicion en base
            cambios.configuraciones_agregar = [
                config
                for config in dia_laboral.configuraciones
                if config.id is None
            ]

            if cambios.configuraciones_agregar:
                cambios.secuencia = True

        return cambios


    @classmethod
    def analizarImpactoEditarDiaLaboral(cls, dia_laboral):
        try:
            #validator
                # Validar que el día laboral exista.
                # Validar que pertenezca al período indicado.
                # Validar que el período exista.
                # Validar que el período esté en estado FUTURO.
            DiaLaboralValidator.validarReglasCriticasDiaLaboral(dia_laboral)


            cambios = cls._obtenerCambiosEditarDiaLaboral(dia_laboral)
            #retornon none si no cambio el dia, y las configuracion no se editan ni eliminan
            #     Si no hubo cambios → retornar None.
            if (
                not cambios.hora_inicio
                and not cambios.hora_fin
                and not cambios.configuraciones_editar
                and not cambios.configuraciones_eliminar
                and not cambios.secuencia 
            ):
                return None, dia_laboral.dia_registro.fecha_modificado
            

            
            impactos = {
                "eliminar": [],
                "editar": [],
                "general": [],

            } 

            print(f"//////////{dia_laboral.dia_registro.id}////a")




            #ver impacto en eliminacion
            periodo_laboral = dia_laboral.periodo_registro
            cantidad_dias = PeriodoLaboralService.obtener_cantidad_dias_semana(
                periodo_laboral,
                dia_laboral.dia_numero
            )

            #     Construir el objeto de impacto que verá el usuario.
            for config in cambios.configuraciones_eliminar:
                impactos["eliminar"].append(
                    cls._determinarImpactoEliminacionConfiguracionDia(config))
                #     Si hubo cambios → consultar citas
            for config in cambios.configuraciones_editar:
                impactos["editar"].extend(cls._determinarImpactoEdicionConfiguracionDia(config, periodo_laboral, cantidad_dias,))

            if cambios.secuencia:
                impactos["general"].append(
                    {
                        "tipo": "RECALCULO_SECUENCIA",
                        "mensaje": (
                            f"La secuencia de horarios de {dia_laboral.dia_registro.total_cupos}  cupos será recalculada"
                        )
                    }
                )


            

            return impactos, dia_laboral.dia_registro.fecha_modificado
        except Exception as e:
            log_error(
                "[ConfiguracionDiaService]: analizarImpactoEditarDiaLaboral",
                LogApp.AGENDA
            )
            raise

        #     Determinar qué citas quedan huérfanas.


    def _incrementarCupos(configuracion, cantidad_cupos, fechas_dias, usuario):

        hora_dummy = time(0, 0)
        cupos_agregar= []

        for fecha in fechas_dias:
            for _ in range(cantidad_cupos):

                cupos_agregar.append(
                Cupo_agenda(
                    personal_salud=configuracion.dia_laboral.periodo_laboral.personal_salud,
                    configuracion_cupo=configuracion,
                    tipo_atencion= configuracion.tipo_atencion,
                    fecha=fecha,
                    hora_inicio=hora_dummy,
                    hora_fin=hora_dummy,
                    estado=EstadoCupoAgenda.DISPONIBLE,
                    creado_por=usuario,
                    modificado_por=usuario,
                )
            )
                

        if cupos_agregar:
            Cupo_agenda.objects.bulk_create(cupos_agregar)

        return cupos_agregar 
    

    @classmethod
    def _reducirCupos(cls, configuracion, cantidad_cupos, fechas_dias, usuario):

        cupos_actualizar = []
        for fecha in fechas_dias:
            cupos = list(
                Cupo_agenda.objects
                .filter(
                    configuracion_cupo=configuracion,
                    fecha=fecha,
                )
                .exclude(estado=EstadoCupoAgenda.INACTIVO)
                .order_by("-hora_inicio")[:cantidad_cupos]
            )
            for cupo in cupos:
                cupo.estado = EstadoCupoAgenda.INACTIVO
                cupo.modificado_por = usuario

            cupos_actualizar.extend(cupos)

        if cupos_actualizar:
            Cupo_agenda.objects.bulk_update(
                cupos_actualizar,
                ["estado", "modificado_por", "fecha_modificado"]
            )

        return cupos_actualizar


    @classmethod
    def _actualizarConfiguracionCupo(cls, conf, fechas_dias, usuario):
        configuracion_bd = conf.configuracion_bd
        configuracion_front = conf.configuracion_front

        cupos_actuales = configuracion_bd.cupos
        cupos_nuevos = configuracion_front.cupos

    
        if cupos_nuevos > cupos_actuales:
            cantidad_cupos = cupos_nuevos - cupos_actuales
            cls._incrementarCupos(configuracion_bd, cantidad_cupos, fechas_dias, usuario)

        elif cupos_nuevos < cupos_actuales:
            cantidad_cupos = cupos_actuales - cupos_nuevos
            cls._reducirCupos(configuracion_bd, cantidad_cupos, fechas_dias, usuario)

        configuracion_bd.cupos = cupos_nuevos
        configuracion_bd.save(update_fields=["cupos"])



    @classmethod
    def _actualizarConfiguracionDuracion(cls, conf):

        configuracion_bd = conf.configuracion_bd
        configuracion_front = conf.configuracion_front

        configuracion_bd.duracion_minutos = configuracion_front.duracion

        configuracion_bd.save(update_fields=["duracion_minutos"])


    @classmethod
    def _crearConfiguracionCupo(cls, dia_laboral, configuracion_front, fechas_dias, usuario):
        configuracion = Configuracion_cupo.objects.create(
            dia_laboral=dia_laboral,
            tipo_atencion_id=configuracion_front.id_tipo_atencion,
            cupos=configuracion_front.cupos,
            duracion_minutos=configuracion_front.duracion,
            orden=configuracion_front.orden,
            estado=EstadoRegistro.ACTIVO,
        )

        cls._crear_cupos_agenda(
            dia_laboral,
            [configuracion],
            fechas_dias,
            usuario
        )

        return configuracion


    @classmethod
    def _actualizarOrdenConfiguraciones(cls, configuraciones_registro, configuraciones_front,usuario):
        configuraciones_actualizar = []

        configuraciones_front = {
            config.id: config
            for config in configuraciones_front
            if config.id is not None and not config.eliminado
        }

        for configuracion_bd in configuraciones_registro:

            configuracion_front = configuraciones_front.get(configuracion_bd.id)

            # Puede ser None si fue eliminada
            if configuracion_front is None:
                continue

            if configuracion_bd.orden != configuracion_front.orden:
                configuracion_bd.orden = configuracion_front.orden
                configuraciones_actualizar.append(configuracion_bd)

        if configuraciones_actualizar:
            Configuracion_cupo.objects.bulk_update(
                configuraciones_actualizar,
                ["orden"]
            )


    @classmethod
    def _recalcularHorarios(cls, dia_laboral, usuario):
        """
        Recalcula la secuencia de horarios de todos los CupoAgenda activos
        del día laboral, respetando el orden de las configuraciones.
        """
        cupos_agrupados = PeriodoLaboralService.obtener_cupos_agrupados_por_fecha(dia_laboral.periodo_registro, dia_laboral.dia_numero)

        cupos_actualizar = []

        for cupos_dia in cupos_agrupados:
            hora_actual = dia_laboral.dia_registro.hora_inicio
            for cupo in cupos_dia:
                cupo.hora_inicio = hora_actual
                hora_actual = (
                    datetime.combine(date.today(), hora_actual)
                    + timedelta(minutes=cupo.configuracion_cupo.duracion_minutos)
                ).time()

                cupo.hora_fin = hora_actual
                cupo.modificado_por = usuario
                cupos_actualizar.append(cupo)

        if cupos_actualizar:
            Cupo_agenda.objects.bulk_update(
                cupos_actualizar,
                [
                    "hora_inicio",
                    "hora_fin",
                    "modificado_por",
                    "fecha_modificado",
                ]
            )


    @classmethod
    def editarDiaLaboral(cls, dia_laboral, usuario):
        try:
            DiaLaboralValidator.validarReglasCriticasDiaLaboral(dia_laboral)  
            DiaLaboralValidator.validarPersistenciaDiaLaboral(dia_laboral.dia_registro, dia_laboral.fecha_modificado)

            cambios = cls._obtenerCambiosEditarDiaLaboral(dia_laboral)

            PeriodoLaboralService.obtener_cupos_agrupados_por_fecha(dia_laboral.periodo_registro, dia_laboral.dia_numero)

            with transaction.atomic():
            # 1. Actualizar Día Laboral (si cambió horario)
                update_fields = []

                if cambios.hora_inicio:
                    dia_laboral.dia_registro.hora_inicio = dia_laboral.hora_ini
                    update_fields.append("hora_inicio")

                if cambios.hora_fin:
                    dia_laboral.dia_registro.hora_fin = dia_laboral.hora_fin
                    update_fields.append("hora_fin")

                                
            # 2. Eliminar configuraciones
                ids = [
                    configuracion.id
                    for configuracion in cambios.configuraciones_eliminar
                ]

                if ids:
                    cupos = Cupo_agenda.objects.filter(
                        configuracion_cupo_id__in=ids
                    )

                    # TODO: Cuando exista el módulo de citas,
                    # buscar las citas asociadas a estos cupos y
                    # dejarlas huérfanas (cupo_agenda = NULL).

                    #INACTIVAMOS LOS CUPOS
                    cupos.update(
                        estado=EstadoCupoAgenda.INACTIVO,
                        modificado_por=usuario,
                    )

                    #INACTIVAMOS LA CONFIGURACION CUPO
                    Configuracion_cupo.objects.filter(
                        id__in=ids
                    ).update(
                        estado=EstadoRegistro.INACTIVO)
                    

            # 3. Editar configuraciones
                periodo = dia_laboral.periodo_registro
                fechas_dias = obtener_fechas_por_dia_semana(
                    periodo.fecha_inicio,
                    periodo.fecha_fin,
                    dia_laboral.dia_numero
                )

                for conf in cambios.configuraciones_editar:
                    datos = conf.configuracion_front

                    if datos.cuposCambio: 
                        cls._actualizarConfiguracionCupo(conf, fechas_dias, usuario)

                    if datos.duracionCambio: 
                        cls._actualizarConfiguracionDuracion(conf)


            # 4. Crear configuraciones nuevas
                for conf in cambios.configuraciones_agregar:
                    cls._crearConfiguracionCupo(
                            dia_laboral.dia_registro,
                            conf,
                            fechas_dias,
                            usuario
                        )

            # 5  reordenar si amerita
                if cambios.secuencia:
                    cls._actualizarOrdenConfiguraciones(
                        dia_laboral.configuraciones_registro,
                        dia_laboral.configuraciones,
                        usuario
                    )
            # 6. Recalcular secuencia y horarios
                cls._recalcularHorarios(dia_laboral, usuario)


            # 7. Actualizar/Reprogramar cupos y citas afectadas

            # 8 marcar que dia laboral se  modifico
                update_fields.extend([
                    "fecha_modificado",
                    "modificado_por",
                ])
                dia_laboral.dia_registro.modificado_por = usuario
                dia_laboral.dia_registro.save(update_fields=update_fields)



        except Exception as e:
            log_error(
                "[ConfiguracionDiaService]: analizarImpactoEditarDiaLaboral",
                LogApp.AGENDA
            )
            raise