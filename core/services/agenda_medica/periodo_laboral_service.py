

from agenda_medica.models import Periodo_laboral, Dia_laboral, Cupo_agenda, Configuracion_cupo, Dia_quirurgico

from cita.models import Historial_cita
from datetime import date, timedelta
from core.constants.choices_constants import EstadoRegistro, DiaSemana, EstadoCupoAgenda, TipoMovimientoCita
from django.core.exceptions import ValidationError
from core.constants.domain_constants import AccionImpactoPeriodoLaboral, TipoCambioFechaPeriodo
from django.db import transaction
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.utils.utilidades_fechas import obtener_fechas_por_dia_semana, filtro_rango_fecha
from types import SimpleNamespace
from django.db.models import Sum, Count, Value, Q, Prefetch
from django.db.models.functions import Coalesce, ExtractYear
from itertools import groupby
from operator import attrgetter
from django.utils import timezone



class PeriodoLaboralService :

    @staticmethod
    def anios_periodos():
        anios_inicio = Periodo_laboral.objects.annotate(
            year=ExtractYear('fecha_inicio')
        ).values_list('year', flat=True)

        anios_fin = Periodo_laboral.objects.annotate(
            year=ExtractYear('fecha_fin')
        ).values_list('year', flat=True)

        anios = set(anios_inicio.union(anios_fin))  

        anios.add(date.today().year)  

        return list(sorted(anios))
    

    @staticmethod
    def obtener_periodo_laboral(id, bloquear=False, enriquecer=False):
        """
        Obtiene el período laboral activo indicado.
        Permite bloquear el registro y enriquecer sus relaciones.
        """

        queryset = Periodo_laboral.objects.filter(
            id=id,
            estado=EstadoRegistro.ACTIVO
        )

        if bloquear:
            queryset = queryset.select_for_update()

        if enriquecer:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "dias_laborales",
                    queryset=Dia_laboral.objects.filter(
                        estado=EstadoRegistro.ACTIVO
                    ).prefetch_related(
                        Prefetch(
                            "configuraciones_cupo",
                            queryset=Configuracion_cupo.objects.filter(
                                estado=EstadoRegistro.ACTIVO
                            ).select_related("tipo_atencion"),
                            to_attr="configuraciones_activas"
                        ),
                        Prefetch(
                            "dia_quirurgico",
                            queryset=Dia_quirurgico.objects.filter(
                                estado=EstadoRegistro.ACTIVO
                            ),
                            to_attr="dia_quirurgico_activo"
                        )
                    ),
                    to_attr="dias_laborales_activos"
                )
            )
        return queryset.first()
        


    @staticmethod
    def obtener_calculo_cupos_periodo_ampliacion(periodo_laboral, fecha_inicio, fecha_fin):
        from core.services.agenda_medica.ausencia_service import AusenciaService
        
        dias_laborales = periodo_laboral.dias_laborales.filter(
            estado=EstadoRegistro.ACTIVO
        ).prefetch_related('configuraciones_cupo')

        calculo = []
        total_cupos_general = 0

        for dia in dias_laborales:
            fechas = obtener_fechas_por_dia_semana(
                fecha_inicio,
                fecha_fin,
                dia.dia_semana
            )

            fechas = AusenciaService.obtener_fechas_validas(
                fechas,
                periodo_laboral.personal_salud
            )

            configuraciones = dia.configuraciones_cupo.filter(
                estado=EstadoRegistro.ACTIVO
            )

            total_cupos = configuraciones.aggregate(
                total=Sum('cupos')
            )['total'] or 0

            total_cupos_dia = total_cupos * len(fechas)
            total_cupos_general += total_cupos_dia

            calculo.append({
                'dia': dia,
                'fechas': fechas,
                'total_cupos': total_cupos_dia
            })

        return  calculo, total_cupos_general


    @classmethod
    def obtener_cupos_historial_actual_periodo_reduccion(cls, periodo_laboral, rangos_reduccion):
        # Ejemplo de estructura de rangos_reduccion:
        #
        # [
        #     (fecha_inicio_reduccion, fecha_fin_reduccion),
        #     (fecha_inicio_reduccion, fecha_fin_reduccion)
        # ]
        filtro_rangos = Q()

        for fecha_inicio, fecha_fin in rangos_reduccion:
            filtro_rangos |= Q(
                **filtro_rango_fecha("fecha", fecha_inicio, fecha_fin)
            )

        return list(
            Cupo_agenda.objects.filter(
                configuracion_cupo__dia_laboral__periodo_laboral=periodo_laboral,
                estado__in=[
                    EstadoCupoAgenda.DISPONIBLE,
                    EstadoCupoAgenda.ASIGNADO,
                ]
            ).filter(
                filtro_rangos
            ).prefetch_related(
                Prefetch(
                    "historial_citas",
                    queryset=Historial_cita.objects.filter(
                        actual=True,
                        tipo_movimiento__in=[
                            TipoMovimientoCita.ASIGNACION,
                            TipoMovimientoCita.REPROGRAMACION,
                        ]
                    ),
                    to_attr="historial_actual"
                )
            ).order_by("fecha", "hora_inicio")
        )



    @staticmethod
    def analizar_impacto_reduccion_periodo(cupos):
        total_cupos = len(cupos)

        total_citas = sum(
            len(cupo.historial_actual)
            for cupo in cupos
        )

        return total_cupos, total_citas


    @staticmethod
    def _obtener_fechas_validas_rango_personal_salud(fecha_inicial, fecha_final, personal_salud, dia_semana):
        from core.services.agenda_medica.ausencia_service import AusenciaService

        fechas = obtener_fechas_por_dia_semana(
            fecha_inicial,
            fecha_final,
            dia_semana
        )

        fechas = AusenciaService.obtener_fechas_validas(
            fechas,
            personal_salud
        )

        return fechas



    @staticmethod
    def _determinar_accion_solapamiento(
        fecha_inicio_nueva,
        fecha_fin_nueva,
        fecha_inicio_existente,
        fecha_fin_existente
    ):
        # 1. Fragmentación / mitosis
        if (
            fecha_inicio_nueva > fecha_inicio_existente
            and fecha_fin_nueva < fecha_fin_existente
        ):
            return AccionImpactoPeriodoLaboral.FRAGMENTACION_PERIODO

        # 2. Reducción borde final
        elif (
            fecha_inicio_nueva > fecha_inicio_existente
            and fecha_fin_nueva >= fecha_fin_existente
        ):
            return AccionImpactoPeriodoLaboral.REDUCCION_FINAL

        # 3. Reducción borde inicial
        elif (
            fecha_inicio_nueva <= fecha_inicio_existente
            and fecha_fin_nueva < fecha_fin_existente
        ):
            return AccionImpactoPeriodoLaboral.REDUCCION_INICIAL

        # 4. Absorción completa
        elif (
            fecha_inicio_nueva <= fecha_inicio_existente
            and fecha_fin_nueva >= fecha_fin_existente
        ):
            return AccionImpactoPeriodoLaboral.ABSORSION_PERIODO

        return None


    @staticmethod
    def obtener_cantidad_dias_semana(periodo_laboral, dia_semana):
        fechas = PeriodoLaboralService._obtener_fechas_validas_rango_personal_salud(
            periodo_laboral.fecha_inicio,
            periodo_laboral.fecha_fin,
            periodo_laboral.personal_salud,
            dia_semana
        )

        return len(fechas)


    @staticmethod
    def obtener_fechas_validas_dia_laboral(periodo_laboral, dia_semana):
        return PeriodoLaboralService._obtener_fechas_validas_rango_personal_salud(
            periodo_laboral.fecha_inicio,
            periodo_laboral.fecha_fin,
            periodo_laboral.personal_salud,
            dia_semana
        )

 
    @staticmethod
    def obtener_dias_configurados(id_periodo):
        dias_laborales = (
            Dia_laboral.objects
            .filter(
                periodo_laboral_id=id_periodo,
                estado=EstadoRegistro.ACTIVO
            )
            .select_related(
                "dia_quirurgico"
            )
            .annotate(
                total_cupos_configurados=Coalesce(
                    Sum(
                        "configuraciones_cupo__cupos",
                        filter=Q(configuraciones_cupo__estado=EstadoRegistro.ACTIVO)
                    ),
                    Value(0)
                ),
                total_tipos=Coalesce(
                    Count(
                        "configuraciones_cupo",
                        filter=Q(configuraciones_cupo__estado=EstadoRegistro.ACTIVO)
                    ),
                    Value(0)
                )
            )
            .order_by("dia_semana")
        )
        return dias_laborales

    
    @staticmethod
    def obtener_configuraciones_para_rango(personal_id, fecha_inicio, fecha_final):

        periodos = (
            Periodo_laboral.objects
            .filter(
                personal_salud_id=personal_id,
                estado=EstadoRegistro.ACTIVO,
                fecha_inicio__lte=fecha_final,
                fecha_fin__gte=fecha_inicio,
            )
            .prefetch_related(
                Prefetch(
                    "dias_laborales",
                    queryset=Dia_laboral.objects.filter(
                        estado=EstadoRegistro.ACTIVO
                    ).prefetch_related(
                        "configuraciones_cupo"
                    )
                )
            )
            .order_by("fecha_inicio")
        )


        resultado = []

        for periodo in periodos:

            inicio = max(periodo.fecha_inicio, fecha_inicio)
            fin = min(periodo.fecha_fin, fecha_final)

            dias_configurados = {
                dia.dia_semana: dia
                for dia in periodo.dias_laborales.all()
            }

            fecha = inicio

            while fecha <= fin:
                dia_laboral = dias_configurados.get(fecha.weekday() + 1)

                if dia_laboral:
                    resultado.append({
                        "fecha": fecha,
                        "dia_laboral": dia_laboral,
                        "configuraciones": [
                            configuracion
                            for configuracion
                            in dia_laboral.configuraciones_cupo.all()
                            if configuracion.estado == EstadoRegistro.ACTIVO
                        ]
                    })

                fecha += timedelta(days=1)

        return resultado


    
    @staticmethod
    def obtener_cupos_agrupados_por_fecha(periodo_laboral, dia_numero):
        """
        Obtiene los cupos activos de un día laboral del período,
        agrupados por fecha.

        """
        historiales = (
                Historial_cita.objects
                .filter(
                    actual=True,
                    tipo_movimiento__in=[
                        TipoMovimientoCita.ASIGNACION,
                        TipoMovimientoCita.REPROGRAMACION,
                    ]
                )
                .select_related(
                    "cita"
                )
            )
        
        cupos = (
            Cupo_agenda.objects
            .filter(
                configuracion_cupo__dia_laboral__periodo_laboral=periodo_laboral,
                configuracion_cupo__dia_laboral__dia_semana=dia_numero,
                estado__in=[EstadoCupoAgenda.DISPONIBLE, EstadoCupoAgenda.ASIGNADO]
            )
            .select_related(
                "configuracion_cupo",
                "configuracion_cupo__dia_laboral",
            )
            .prefetch_related(
                Prefetch(
                    "historial_citas",
                    queryset=historiales,
                    to_attr="historial_actual"
                )

            )
            .order_by(
                "configuracion_cupo__dia_laboral__dia_semana",
                "fecha",
                "configuracion_cupo__orden",
                "id"
            )
        )

        return [
            list(grupo)
                for _, grupo in groupby(
                    cupos,
                    key=attrgetter("fecha")
                )
            ]
    

    @staticmethod
    def construir_dias_semana_ui(id_periodo):

        periodo = PeriodoLaboralService.obtener_periodo_laboral(id_periodo)
        dias_laborales_qs = PeriodoLaboralService.obtener_dias_configurados(id_periodo)
        # Convertir queryset a mapa:
        # {1: objeto_lunes, 5: objeto_viernes}
        dias_map = {
            dia.dia_semana: dia
            for dia in dias_laborales_qs
        }


        dias_semana = []

        for ndia, nombredia in DiaSemana.choices:

            fechas_dia = obtener_fechas_por_dia_semana(
                periodo.fecha_inicio,
                periodo.fecha_fin,
                ndia 
            )

            if not fechas_dia:
                continue

            dia = dias_map.get(ndia)

            if dia:
                dia_quirurgico = hasattr(
                    dia,
                    "dia_quirurgico"
                )

                dias_semana.append({
                    "numero_dia": ndia,
                    "id": dia.id,
                    "nombre_dia": nombredia,
                    "configurado": True,
                    "hora_inicio": dia.hora_inicio,
                    "hora_fin": dia.hora_fin,
                    "total_cupos": dia.total_cupos_configurados,
                    "total_tipos": dia.total_tipos,
                    "quirurgico": dia_quirurgico,
                })

            else:
                dias_semana.append({
                    "numero_dia": ndia,
                    "nombre_dia": nombredia,
                    "configurado": False,
                    "quirurgico": False,
                })

        return dias_semana


    @staticmethod
    def _construir_impacto_solapamiento(periodo, periodo_afectado):

        inicio_existente = periodo_afectado.fecha_inicio
        fin_existente = periodo_afectado.fecha_fin

        inicio_nuevo = periodo.fecha_inicio
        fin_nuevo = periodo.fecha_final

        accion = PeriodoLaboralService._determinar_accion_solapamiento(
            inicio_nuevo,
            fin_nuevo,
            inicio_existente,
            fin_existente
        )

        if accion is None:
            return None

        metadata_periodo = {
            'periodo_afectado_id': periodo_afectado.id,
            'fecha_modificado': (
                periodo_afectado.fecha_modificado.isoformat()
                if periodo_afectado.fecha_modificado
                else None
            )
        }

        mensajes_impacto = {

            AccionImpactoPeriodoLaboral.FRAGMENTACION_PERIODO: {
                'titulo': 'Fragmentación de período',
                'mensajes': [
                    (
                        f"El nuevo período {inicio_nuevo} - {fin_nuevo} "
                        "está <strong>contenido dentro de un período existente.</strong>"
                    ),
                    "<strong>Los períodos resultantes serán:</strong>",
                    f"- {inicio_existente} - {inicio_nuevo - timedelta(days=1)}",
                    f"- {inicio_nuevo} - {fin_nuevo}",
                    f"- {fin_nuevo + timedelta(days=1)} - {fin_existente}",
                    "Los nuevos períodos heredarán la configuración existente."
                ]
            },

            AccionImpactoPeriodoLaboral.REDUCCION_FINAL: {
                'titulo': 'Reducción de período',
                'mensajes': [
                    (
                        f"El nuevo período {inicio_nuevo} - {fin_nuevo} "
                        "afecta la <strong>parte final</strong> "
                        "de un período existente."
                    ),
                    "<strong>El período original quedará como:</strong>",
                    f"- {inicio_existente} - {inicio_nuevo - timedelta(days=1)}",
                    (
                        "El nuevo período heredará la configuración existente. "
                        "Los cupos y las citas programadas se conservarán sin cambios."
                    ),
                    "<strong>¿Desea continuar con la operación?</strong>"
                ]
            },

            AccionImpactoPeriodoLaboral.REDUCCION_INICIAL: {
                'titulo': 'Reducción de período',
                'mensajes': [
                    (
                        f"El nuevo período {inicio_nuevo} - {fin_nuevo} "
                        "afecta la <strong>parte inicial</strong> "
                        "de un período existente."
                    ),
                    "<strong>El período original quedará como:</strong>",
                    f"- {fin_nuevo + timedelta(days=1)} - {fin_existente}",
                    (
                        "El nuevo período heredará la configuración existente. "
                        "Los cupos y las citas programadas se conservarán sin cambios."
                    ),
                    "<strong>¿Desea continuar con la operación?</strong>"
                ]
            },

            AccionImpactoPeriodoLaboral.ABSORSION_PERIODO: {
                'titulo': 'Absorción de período',
                'mensajes': [
                    (
                        f"El nuevo período {inicio_nuevo} - {fin_nuevo} "
                        "contiene completamente un período existente."
                    ),
                    "<strong>El período resultante será:</strong>",
                    f"- {inicio_nuevo} - {fin_nuevo}",
                    (
                        "La configuración existente será heredada. "
                        "Los cupos y las citas programadas se conservarán sin cambios."
                    ),
                    "<strong>¿Desea continuar con la operación?</strong>"
                ]
            }
        }

        return {
            'accion': accion,
            **metadata_periodo,
            **mensajes_impacto[accion]
        }


    @staticmethod
    def _analizar_cambios_fechas_periodo(periodo_front, periodo_registro):

        def analizar_fecha_inicial():
            fecha_original = periodo_registro.fecha_inicio
            fecha_nueva = periodo_front.fecha_inicio

            if fecha_nueva == fecha_original:
                tipo = TipoCambioFechaPeriodo.SIN_CAMBIO
            elif fecha_nueva < fecha_original:
                tipo = TipoCambioFechaPeriodo.AMPLIACION
            else:
                tipo = TipoCambioFechaPeriodo.REDUCCION

            dias = abs((fecha_nueva - fecha_original).days)

            return {
                'tipo': tipo,
                'fecha_original': fecha_original,
                'fecha_nueva': fecha_nueva,
                'dias': dias
            }

        def analizar_fecha_final():
            fecha_original = periodo_registro.fecha_fin
            fecha_nueva = periodo_front.fecha_final

            if fecha_nueva == fecha_original:
                tipo = TipoCambioFechaPeriodo.SIN_CAMBIO
            elif fecha_nueva > fecha_original:
                tipo = TipoCambioFechaPeriodo.AMPLIACION
            else:
                tipo = TipoCambioFechaPeriodo.REDUCCION

            dias = abs((fecha_nueva - fecha_original).days)

            return {
                'tipo': tipo,
                'fecha_original': fecha_original,
                'fecha_nueva': fecha_nueva,
                'dias': dias
            }

        fecha_inicial = analizar_fecha_inicial()
        fecha_final = analizar_fecha_final()

        return {
            'fecha_inicial': fecha_inicial,
            'fecha_final': fecha_final
        }



    
    @staticmethod
    def _analizarImpactoEdicionPeriodoLaboral(periodo_front, periodo_registro):

        # notificar que desactvar un perido afecta citas 
        if  periodo_front.estado is False and periodo_registro.estado == EstadoRegistro.ACTIVO:
            
            rangos_reduccion = [
                (
                    periodo_registro.fecha_inicio,
                    periodo_registro.fecha_fin
                )
            ]

            cupos = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                periodo_registro,
                rangos_reduccion
            )

            cupos_afectados, citas_afectadas = (
                PeriodoLaboralService.analizar_impacto_reduccion_periodo(cupos)
            )

            return {
                'titulo': 'Desactivación de período',
                'mensajes': [
                    f"El período afectado {periodo_registro}",
                    (
                        f"Se desactivarán "
                        f"<strong>{cupos_afectados}</strong> cupos."
                    ),
                    (
                        f"Se encontraron "
                        f"<strong>{citas_afectadas}</strong> citas afectadas. "
                        f"Estas citas deberán ser reprogramadas."
                    ),
                    "<strong>¿Desea continuar con los cambios?</strong>",
                ]
            }

        #ahora validar las fechas por separadas para controlar amplaciones y reducciones por fecha
        fechas = PeriodoLaboralService._analizar_cambios_fechas_periodo(periodo_front, periodo_registro)
        fecha_inicial = fechas.get('fecha_inicial')
        fecha_final = fechas.get('fecha_final')

        #AMPLIACION 
        # verificamos si amplacion juntas, me refiero a ver si no choca las podemos validar jutnas entonce
        
        if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.AMPLIACION or fecha_final['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:
            #ahora si validamos el periodo completo con ORM
            conflicto = (
                Periodo_laboral.objects
                .filter(
                    personal_salud__id=periodo_front.personal_id,
                    jornada_laboral__id=periodo_front.jornada_id,
                    estado=EstadoRegistro.ACTIVO,
                    fecha_inicio__lte=periodo_front.fecha_final,
                    fecha_fin__gte=periodo_front.fecha_inicio
                )
                .exclude(id=periodo_front.id)
                .exists()
            )

            if conflicto:
                raise ValidationError(
                        "No es posible ampliar el período laboral "
                        "porque invade otro período existente."
                    )
            mensajes_ampliacion = []
            dias_ampliados  =0
            total_cupos = 0

            # Ampliación fecha inicial
            if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:

                _, cupos = PeriodoLaboralService.obtener_calculo_cupos_periodo_ampliacion(
                    periodo_laboral=periodo_registro,
                    fecha_inicio=fecha_inicial['fecha_nueva'],
                    fecha_fin=fecha_inicial['fecha_original'] - timedelta(days=1)
                )

                total_cupos += cupos
                dias_ampliados += int(fecha_inicial.get('dias', 0))

                mensajes_ampliacion.append(
                    f"La fecha inicial fue ampliada "
                    f"{fecha_inicial['dias']} días."
                )


            # Ampliación fecha final
            if fecha_final['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:

                _, cupos = PeriodoLaboralService.obtener_calculo_cupos_periodo_ampliacion(
                    periodo_laboral=periodo_registro,
                    fecha_inicio=fecha_final['fecha_original'] + timedelta(days=1),
                    fecha_fin=fecha_final['fecha_nueva']
                )

                total_cupos += cupos
                dias_ampliados += int(fecha_final.get('dias', 0))

                mensajes_ampliacion.append(
                    f"La fecha final fue ampliada "
                    f"{fecha_final['dias']} días."
                )


            return {
                'titulo': 'Ampliación de período',
                'mensajes': [
                    f"El período afectado {periodo_registro}",
                    *mensajes_ampliacion,
                    (
                        f"Total de ampliación: "
                        f"<strong>{dias_ampliados}</strong> días | "
                        f"<strong>{total_cupos}</strong> cupos adicionales"
                    ),
                    "<strong>¿Desea continuar con los cambios?</strong>",
                ]
            }
                    
            
            
        if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION or fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
            dias_reducidos = 0
            mensajes_reduccion = []
            rangos_reducidas =[]


            # reducción fecha inicial
            if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                dias_reducidos += int(fecha_inicial.get('dias', 0))
                rangos_reducidas.append((
                    fecha_inicial['fecha_original'],
                    fecha_inicial['fecha_nueva'] - timedelta(days=1)
                ))
                mensajes_reduccion.append(
                    (
                        f"La fecha inicial fue reducida "
                        f"{fecha_inicial['dias']} días."
                    )
                )

            # reducción fecha final
            if fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                dias_reducidos += int(fecha_final.get('dias', 0))
                rangos_reducidas.append((
                    fecha_final['fecha_nueva'] + timedelta(days=1),
                    fecha_final['fecha_original']
                ))
                mensajes_reduccion.append(
                    (
                        f"La fecha final fue reducida "
                        f"{fecha_final['dias']} días."
                    )
                )


            cupos = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(periodo_registro, rangos_reducidas)
            cupos_afectados, citas_afectadas=PeriodoLaboralService.analizar_impacto_reduccion_periodo(cupos)

            return {
                'titulo': 'Reducción de período',
                'mensajes': [
                    f"El período afectado {periodo_registro}",
                    *mensajes_reduccion,
                    (
                        f"Total de reducción: "
                        f"<strong>{dias_reducidos}</strong> días | "
                        f"<strong>{cupos_afectados}</strong> cupos afectados"
                    ),
                    (
                        f"Se encontraron <strong>{citas_afectadas}</strong> citas afectadas. "
                        f"Estas citas deberán ser reprogramadas."
                    ),
                    "<strong>¿Desea continuar con los cambios?</strong>",
                ]
            }
        
        return None


    @staticmethod
    def obtener_periodo_solapado(periodo, bloquear=False):
        periodos_solapados_qs = Periodo_laboral.objects.filter(
            personal_salud__id=periodo.personal_id,
            jornada_laboral__id=periodo.jornada_id,
            estado=EstadoRegistro.ACTIVO,
            fecha_inicio__lte=periodo.fecha_final,
            fecha_fin__gte=periodo.fecha_inicio
        )

      
        conteo = periodos_solapados_qs.count()

        if conteo > 1:
            raise ValidationError(
                "La operación afecta múltiples períodos laborales. "
                "Actualmente este escenario debe resolverse manualmente."
            )

        if conteo == 1:

            
            if bloquear:
                periodos_solapados_qs = periodos_solapados_qs.select_for_update()

            periodo_afectado = periodos_solapados_qs.prefetch_related(
                Prefetch(
                    "dias_laborales",
                    queryset=Dia_laboral.objects.filter(
                        estado=EstadoRegistro.ACTIVO
                    ).prefetch_related(
                        Prefetch(
                            "configuraciones_cupo",
                            queryset=Configuracion_cupo.objects.filter(
                                estado=EstadoRegistro.ACTIVO
                            ).select_related("tipo_atencion"),
                            to_attr="configuraciones_activas"
                        ),
                        Prefetch(
                            "dia_quirurgico",
                            queryset=Dia_quirurgico.objects.filter(
                                estado=EstadoRegistro.ACTIVO
                            ),
                            to_attr="dia_quirurgico_activo"
                        )
                    ),
                    to_attr="dias_laborales_activos"
                )
            ).first()



            if (
                periodo.fecha_inicio == periodo_afectado.fecha_inicio
                and periodo.fecha_final == periodo_afectado.fecha_fin
            ):
                raise ValidationError(
                    "Ya existe un período laboral "
                    "con el mismo rango de fechas."
                )

            return periodo_afectado

        return None


    @staticmethod
    def _analizarImpactoPeriodoLaboral(periodo, periodo_registro):
        #1 si el registro viene es porque debemos modificar
        if periodo_registro and periodo.id:
            return PeriodoLaboralService._analizarImpactoEdicionPeriodoLaboral(periodo, periodo_registro)
        
        else:#validar para adicion
            #1 - primero veamos si existe un periodo para los argumentos en adicion
            # Análisis de impacto: sin bloqueo
            periodo_afectado = PeriodoLaboralService.obtener_periodo_solapado(periodo)

            if periodo_afectado == None:
                return None

                
            return PeriodoLaboralService._construir_impacto_solapamiento(
                periodo,
                periodo_afectado
            )



    @staticmethod
    def analizarImpactoPeriodoLaboral(periodo):
        from agenda_medica.validators import PeriodoLaboralValidator
        #validacion critica
        periodo_registro = None
        if periodo.id:
            periodo_registro = (
                PeriodoLaboralValidator
                .validarReglasCriticasPeriodoLaboral(periodo)
            )
        resultado = PeriodoLaboralService._analizarImpactoPeriodoLaboral(periodo, periodo_registro)
        return resultado 


    @staticmethod
    def _replicar_estructura_periodo(periodo_origen, periodo_destino, usuario):
        from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
        from core.services.agenda_medica.dia_quirurgico_service import DiaQuirurgicoService

        # Obtener días laborales activos del periodo original.
        dias_configurados = periodo_origen.dias_laborales_activos

        estructura_dias = {}
        dias_nuevos_por_semana = {}


        # Replicar días laborales y días quirúrgicos.
        for dia in dias_configurados:
            fechas = obtener_fechas_por_dia_semana(
                periodo_destino.fecha_inicio,
                periodo_destino.fecha_fin,
                dia.dia_semana
            )

            if not fechas:
                continue

            dia_nuevo = ConfiguracionDiaService._crear_dia_laboral(
                periodo=periodo_destino,
                dia_numero=dia.dia_semana,
                hora_inicio=dia.hora_inicio,
                hora_fin=dia.hora_fin,
                usuario=usuario
            )

            dias_nuevos_por_semana[dia.dia_semana] = dia_nuevo

            if dia.dia_quirurgico_activo:
                DiaQuirurgicoService._crear_registro_dia_quirurgico(
                    dia_nuevo,
                    usuario
                )

            estructura_dias[dia.dia_semana] = dia.configuraciones_activas

        # Replicar configuraciones de cupos.
        configuraciones_nuevas = []

        for dia_semana, configuraciones in estructura_dias.items():
            dia_nuevo = dias_nuevos_por_semana[dia_semana]

            for configuracion in configuraciones:
                configuraciones_nuevas.append(
                    Configuracion_cupo(
                        dia_laboral=dia_nuevo,
                        tipo_atencion=configuracion.tipo_atencion,
                        cupos=configuracion.cupos,
                        duracion_minutos=configuracion.duracion_minutos,
                        orden=configuracion.orden,
                        estado=EstadoRegistro.ACTIVO,
                    )
                )

        Configuracion_cupo.objects.bulk_create(configuraciones_nuevas)

        # Recuperar configuraciones nuevas para reasignar los cupos.
        configuraciones_nuevas = Configuracion_cupo.objects.filter(
            dia_laboral__periodo_laboral=periodo_destino,
            dia_laboral__dia_semana__in=estructura_dias.keys(),
            estado=EstadoRegistro.ACTIVO
        ).select_related("dia_laboral", "tipo_atencion")

        return configuraciones_nuevas, dias_nuevos_por_semana


    def _reasignar_cupos_configuraciones(cupos_trasladar, configuraciones_nuevas):
        # Indexar configuraciones por día y tipo de atención.
        configuraciones_por_dia_tipo = {
            (dia.dia_laboral.dia_semana, dia.tipo_atencion_id): dia
            for dia in configuraciones_nuevas
        }

        # Reasignar cupos a sus nuevas configuraciones.
        cupos_actualizar = []

        for cupo in cupos_trasladar:
            dia_semana = cupo.fecha.isoweekday()

            configuracion_nueva = configuraciones_por_dia_tipo.get(
                (dia_semana, cupo.configuracion_cupo.tipo_atencion_id)
            )

            if not configuracion_nueva:
                raise ValidationError(
                    f"No se encontró configuración para el cupo del {cupo.fecha}."
                )

            cupo.configuracion_cupo = configuracion_nueva
            cupos_actualizar.append(cupo)

        Cupo_agenda.objects.bulk_update(
            cupos_actualizar,
            ["configuracion_cupo"]
        )


    @staticmethod
    def generar_cupos_dias_laborales(periodo,
        dias_laborales,
        fecha_inicio,
        fecha_fin,
        usuario
    ):
        from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
        
        for dia_semana, dia_laboral in dias_laborales.items():

            fechas_dias = PeriodoLaboralService._obtener_fechas_validas_rango_personal_salud(
                fecha_inicio,
                fecha_fin,
                periodo.personal_salud,
                dia_semana
            )

            configuraciones = dia_laboral.configuraciones_activas

            if configuraciones:
                ConfiguracionDiaService._crear_cupos_agenda(
                    dia_laboral,
                    configuraciones,
                    fechas_dias,
                    usuario
                )



    @staticmethod
    def procesarPeriodoLaboral(periodo_front, usuario):
        from agenda_medica.validators import PeriodoLaboralValidator
        from core.services.agenda_medica.configuracion_dia_service import ConfiguracionDiaService
        from core.services.cita.cita_service import CitaService
        from rrhh.models import PersonalSalud

        def aplicar_reduccion_inicial(periodo_afectado):

            # Guardar fecha inicial original.
            fecha_inicio_original = periodo_afectado.fecha_inicio

            # Ajustar fecha inicial del periodo original.
            nueva_fecha_inicio = periodo_front.fecha_final + timedelta(days=1)
            periodo_afectado.fecha_inicio = nueva_fecha_inicio
            periodo_afectado.modificado_por_id = usuario.id
            periodo_afectado.save()

            # Crear nuevo periodo.
            nuevo_periodo = crear_periodo_registro(periodo_front)

            # Replicar estructura del periodo.
            configuraciones_nuevas, dias_nuevos_por_semana = PeriodoLaboralService._replicar_estructura_periodo(
                periodo_origen=periodo_afectado,
                periodo_destino=nuevo_periodo,
                usuario=usuario
            )

            # Obtener cupos existentes dentro del nuevo periodo.
            rangos_reduccion = [
                (
                    nuevo_periodo.fecha_inicio,
                    nuevo_periodo.fecha_fin
                )
            ]
            print("////////")
            cupos_trasladar = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                periodo_afectado,
                rangos_reduccion
            )

            # Reasignar cupos a las nuevas configuraciones.
            PeriodoLaboralService._reasignar_cupos_configuraciones(
                cupos_trasladar=cupos_trasladar,
                configuraciones_nuevas=configuraciones_nuevas
            )

            # Generar cupos del tramo anterior al inicio original.
            fecha_fin_generacion = fecha_inicio_original - timedelta(days=1)

            
            PeriodoLaboralService.generar_cupos_dias_laborales(
                periodo=nuevo_periodo,
                dias_laborales=dias_nuevos_por_semana,
                fecha_inicio=nuevo_periodo.fecha_inicio,
                fecha_fin=fecha_fin_generacion,
                usuario=usuario
            )

            return True
            
        def aplicar_reduccion_final(periodo_afectado):
            # Guardar fecha inicial original.
            fecha_fin_original = periodo_afectado.fecha_fin

            # Ajustar fecha inicial del periodo original.
            nueva_fecha_final = (periodo_front.fecha_inicio - timedelta(days=1))
            periodo_afectado.fecha_fin = nueva_fecha_final
            periodo_afectado.modificado_por_id = usuario.id
            periodo_afectado.save()

            # Crear nuevo periodo.
            nuevo_periodo = crear_periodo_registro(periodo_front)


            # Replicar estructura del periodo.
            configuraciones_nuevas, dias_nuevos_por_semana = PeriodoLaboralService._replicar_estructura_periodo(
                periodo_origen=periodo_afectado,
                periodo_destino=nuevo_periodo,
                usuario=usuario
            )

            # Obtener cupos existentes dentro del nuevo periodo.
            rangos_reduccion = [
                (
                    nuevo_periodo.fecha_inicio,
                    nuevo_periodo.fecha_fin
                )
            ]

            cupos_trasladar = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                periodo_afectado,
                rangos_reduccion
            )

            # Reasignar cupos a las nuevas configuraciones.
            PeriodoLaboralService._reasignar_cupos_configuraciones(
                cupos_trasladar=cupos_trasladar,
                configuraciones_nuevas=configuraciones_nuevas
            )

            # Generar cupos del tramo posterior al inicio original.
            fecha_inicio_generacion = fecha_fin_original + timedelta(days=1)

            PeriodoLaboralService.generar_cupos_dias_laborales(
                periodo=nuevo_periodo,
                dias_laborales=dias_nuevos_por_semana,
                fecha_inicio=fecha_inicio_generacion,
                fecha_fin=nuevo_periodo.fecha_fin,
                usuario=usuario
            )


            return True
        
        def aplicar_fragmentacion(periodo_afectado):

                # Guardar fechas originales.
                fecha_fin_original = periodo_afectado.fecha_fin

                # el fragmenteo original sera el mas cercano a la fecha inicial
                nueva_fecha_final = (periodo_front.fecha_inicio - timedelta(days=1))
                periodo_afectado.fecha_fin = nueva_fecha_final
                periodo_afectado.modificado_por_id = usuario.id
                periodo_afectado.save()
                #hijo2
                nuevo_periodo = crear_periodo_registro(periodo_front)

                # Replicar estructura del periodo.
                configuraciones_nuevas, dias_nuevos_por_semana = PeriodoLaboralService._replicar_estructura_periodo(
                    periodo_origen=periodo_afectado,
                    periodo_destino=nuevo_periodo,
                    usuario=usuario
                )

                # Obtener cupos existentes dentro del nuevo periodo.
                rangos_fragmentacion = [
                    (
                        nuevo_periodo.fecha_inicio,
                        nuevo_periodo.fecha_fin
                    )
                ]
    
                cupos_trasladar = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                    periodo_afectado,
                    rangos_fragmentacion
                )
    
                # Reasignar cupos a las nuevas configuraciones.
                PeriodoLaboralService._reasignar_cupos_configuraciones(
                    cupos_trasladar=cupos_trasladar,
                    configuraciones_nuevas=configuraciones_nuevas
                )


                # Crear el periodo final o cola 
                fecha_inicial_cola = ( periodo_front.fecha_final + timedelta(days=1))

                periodo_cola = SimpleNamespace(
                    personal_id= periodo_front.personal_id,
                    jornada_id= periodo_front.jornada_id,
                    fecha_inicio= fecha_inicial_cola,
                    fecha_final= fecha_fin_original,

                )
                periodo_cola = crear_periodo_registro(periodo_cola)


                # Replicar estructura del periodo original.
                configuraciones_nuevas, dias_nuevos_por_semana = PeriodoLaboralService._replicar_estructura_periodo(
                    periodo_origen=periodo_afectado,
                    periodo_destino=periodo_cola,
                    usuario=usuario
                )

                # Obtener cupos existentes dentro periodo original.
                rangos_reduccion = [
                    (
                        periodo_cola.fecha_inicio,
                        periodo_cola.fecha_fin
                    )
                ]

                cupos_trasladar = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                    periodo_afectado,
                    rangos_reduccion
                )
    
                # Reasignar cupos a las nuevas configuraciones.
                PeriodoLaboralService._reasignar_cupos_configuraciones(
                    cupos_trasladar=cupos_trasladar,
                    configuraciones_nuevas=configuraciones_nuevas
                )

                return True
            
        def aplicar_absorcion(periodo_afectado):


                fecha_inicio_original = periodo_afectado.fecha_inicio
                fecha_fin_original = periodo_afectado.fecha_fin


                tramos_nuevos = []

                if periodo_front.fecha_inicio < fecha_inicio_original:
                    tramos_nuevos.append((
                        periodo_front.fecha_inicio,
                        fecha_inicio_original - timedelta(days=1)
                    ))

                if periodo_front.fecha_final > fecha_fin_original:
                    tramos_nuevos.append((
                        fecha_fin_original + timedelta(days=1),
                        periodo_front.fecha_final
                    ))

                periodo_afectado.fecha_inicio = periodo_front.fecha_inicio
                periodo_afectado.fecha_fin = periodo_front.fecha_final
                periodo_afectado.modificado_por_id = usuario.id
                periodo_afectado.save()

                dias_laborales = {
                    dia.dia_semana: dia
                    for dia in periodo_afectado.dias_laborales_activos
                }

                for fecha_inicio, fecha_fin in tramos_nuevos:
                    PeriodoLaboralService.generar_cupos_dias_laborales(
                        periodo=periodo_afectado,
                        dias_laborales=dias_laborales,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin,
                        usuario=usuario
                    )


                return True

        def desactivar_periodo(periodo_registro):

            #blouquear los cupos y cancelar las citas afectadas
            rangos_reduccion = [
                (
                    periodo_registro.fecha_inicio,
                    periodo_registro.fecha_fin
                )
            ]

            cupos = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                periodo_registro,
                rangos_reduccion
                                )


            historiales = [
                historial
                for cupo in cupos
                for historial in cupo.historial_actual
            ]

            if historiales:
                CitaService.cancelarRelacionCupo(
                    historiales,
                    usuario
                )

            
            ConfiguracionDiaService._inactivarCupos(cupos, usuario)

            #desactivar la configuracions correposndientes 
            configuraciones = [
                configuracion
                for dia in periodo_registro.dias_laborales_activos
                for configuracion in dia.configuraciones_activas 
            ]

            if configuraciones:
                ConfiguracionDiaService._inactivarConfiguraciones(
                    configuraciones,
                    usuario
                )


            #debemos desactivar dias laborales hijos del periodo afectado
            dias_laborales = periodo_registro.dias_laborales_activos or []


            #desactuivar los dias quirurgicos hijos del periodo afectado
            dias_quirurgicos = [
                dia.dia_quirurgico_activo
                for dia in dias_laborales
                if dia.dia_quirurgico_activo is not None
            ]

            if dias_quirurgicos:
                Dia_quirurgico.objects.filter(
                    id__in=[dia_qx.id for dia_qx in dias_quirurgicos]
                ).delete()


            for dia in dias_laborales:
                dia.estado = EstadoRegistro.INACTIVO
                dia.modificado_por = usuario

            Dia_laboral.objects.bulk_update(
                dias_laborales,
                ["estado", "modificado_por", "fecha_modificado"]
            )


            periodo_registro.estado = EstadoRegistro.INACTIVO
            periodo_registro.modificado_por = usuario
            periodo_registro.save()


            return True

        def crear_periodo_registro(periodoArg):
            kwargs = {
                "personal_salud_id": periodoArg.personal_id,
                "jornada_laboral_id": periodoArg.jornada_id,
                "fecha_inicio": periodoArg.fecha_inicio,
                "fecha_fin": periodoArg.fecha_final,
                "creado_por_id": usuario.id,
                "modificado_por_id": usuario.id,
                
            }

            periodo = Periodo_laboral.objects.create(**kwargs)
            return periodo
            

        # inicio del metodo
        periodo_registro = None


        periodo_registro = (
            PeriodoLaboralValidator
            .validarReglasCriticasPeriodoLaboral(periodo_front)
        )

        # CREACIÓN O ADICIÓN
        if not periodo_registro:
            periodo_afectado = PeriodoLaboralService.obtener_periodo_solapado(periodo_front)

            #para agregar periodo registro ser null
            resultado = None
            if periodo_afectado:
                resultado = PeriodoLaboralService._determinar_accion_solapamiento(
                    periodo_front.fecha_inicio,
                    periodo_front.fecha_final,
                    periodo_afectado.fecha_inicio,
                    periodo_afectado.fecha_fin
                )
                
        #pa crear
            if not resultado :
                with transaction.atomic():
                    personal = PersonalSalud.objects.select_for_update().get(
                        id=periodo_front.personal_id
                    )

                    # Verificar nuevamente los períodos solapados.
                    periodo_afectado = PeriodoLaboralService.obtener_periodo_solapado(
                        periodo_front,
                        bloquear=True
                    )

                    if periodo_afectado is None:
                        periodo = crear_periodo_registro(periodo_front)
                        return True if periodo else False

                    # El estado cambió mientras esperábamos el bloqueo.
                    raise ValidationError(
                        "El período laboral presenta conflictos con otro registro. "
                        "Actualice la información e intente nuevamente."
                    )
                    

            elif resultado: 
                #adicion con ajuste a regsitros previos 
                with transaction.atomic():
                    personal = PersonalSalud.objects.select_for_update().get(
                        id=periodo_front.personal_id
                    )

                    periodo_afectado = PeriodoLaboralService.obtener_periodo_solapado(
                        periodo_front,
                        bloquear=True,
                    )
                    if periodo_afectado is None:
                        raise ValidationError(
                            "El período afectado ya no existe o fue modificado. "
                            "Por favor, reinicie el proceso."
                        )

                    if not periodo_front.fecha_impacto:
                        raise ValidationError(
                            "No se pudo validar el período afectado."
                        )

                    fecha_registro = periodo_afectado.fecha_modificado.replace(microsecond=0)
                    fecha_validacion = periodo_front.fecha_impacto.replace(microsecond=0)
                    
                
                    if (fecha_registro != fecha_validacion):
                        raise ValidationError(
                                "El período afectado por la nueva adición "
                                "fue modificado por otro usuario. "
                                "Por favor, reinicie el proceso."
                            )

                    accion = PeriodoLaboralService._determinar_accion_solapamiento(
                        periodo_front.fecha_inicio,
                        periodo_front.fecha_final,
                        periodo_afectado.fecha_inicio,
                        periodo_afectado.fecha_fin
                    )
                                    
                    if accion == AccionImpactoPeriodoLaboral.REDUCCION_INICIAL:
                        return aplicar_reduccion_inicial(periodo_afectado)

                    elif accion == AccionImpactoPeriodoLaboral.REDUCCION_FINAL:
                        return aplicar_reduccion_final(periodo_afectado)

                    elif accion == AccionImpactoPeriodoLaboral.FRAGMENTACION_PERIODO:
                        return aplicar_fragmentacion(periodo_afectado)

                    elif accion == AccionImpactoPeriodoLaboral.ABSORSION_PERIODO:
                        return aplicar_absorcion(periodo_afectado)
                    else:
                        raise ValidationError(
                            "No se pudo determinar una operación válida para el solapamiento."
                        )
                    
        elif periodo_registro: #editar

            #bloyquemos el personal para evitar que otro usuario modifique el registro mientras se procesa la edición
            with transaction.atomic():
                personal = PersonalSalud.objects.select_for_update().get(
                    id=periodo_front.personal_id
                )

                periodo_registro = PeriodoLaboralService.obtener_periodo_laboral(periodo_front.id, bloquear=True, enriquecer=True)



                #compoirbar si  mientras el usaurios decidia el registro fue modificado 
                fecha_registro = (periodo_registro.fecha_modificado.replace(microsecond=0))
                fecha_validacion = (periodo_front.fecha_modificado.replace(microsecond=0))

                if (fecha_registro != fecha_validacion):
                    raise ValidationError(
                            "El período a editar fue modificado por otro usuario. "
                            "Por favor, reinicie el proceso."
                        )

                #validamos nuevamente con el personal ya bloqueado para evitar que otro usuario modifique el registro mientras se procesa la edición
                PeriodoLaboralValidator.validarReglasEdicionPeriodoLaboral(
                    periodo_front,
                    periodo_registro
                )

                # desactivar un periodo no requiere comprobar las fechas 
                if  periodo_front.estado is False and periodo_registro.estado == EstadoRegistro.ACTIVO:
                    return desactivar_periodo(periodo_registro)

                # TRABAJAR LOS CAMBIOS DE FECHAS
                #ahora validar las fechas por separadas para controlar amplaciones y reducciones por fecha
                fechas = PeriodoLaboralService._analizar_cambios_fechas_periodo(periodo_front, periodo_registro)
                fecha_inicial = fechas.get('fecha_inicial')
                fecha_final = fechas.get('fecha_final')

                dias_laborales = {
                        dia.dia_semana: dia
                        for dia in periodo_registro.dias_laborales_activos
                    }

                if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.AMPLIACION or fecha_final['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:
                    # Procesar ampliaciones
                    tramos_nuevos = []

                    if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:
                        tramos_nuevos.append((
                            fecha_inicial['fecha_nueva'],
                            fecha_inicial['fecha_original'] - timedelta(days=1)
                        ))

                    if fecha_final['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:
                        tramos_nuevos.append((
                            fecha_final['fecha_original'] + timedelta(days=1),
                            fecha_final['fecha_nueva']
                        ))

                    

                    for fecha_inicio, fecha_fin in tramos_nuevos:
                        PeriodoLaboralService.generar_cupos_dias_laborales(
                            periodo=periodo_registro,
                            dias_laborales=dias_laborales,
                            fecha_inicio=fecha_inicio,
                            fecha_fin=fecha_fin,
                            usuario=usuario
                        )


                if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION or fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                    # Procesar reducciones
                    rangos_reduccion = []

                    if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                        rangos_reduccion.append((
                            fecha_inicial['fecha_original'],
                            fecha_inicial['fecha_nueva'] - timedelta(days=1)
                        ))

                    if fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                        rangos_reduccion.append((
                            fecha_final['fecha_nueva'] + timedelta(days=1),
                            fecha_final['fecha_original']
                        ))

                    cupos = PeriodoLaboralService.obtener_cupos_historial_actual_periodo_reduccion(
                        periodo_registro,
                        rangos_reduccion
                    )

                    historiales = [
                        historial
                        for cupo in cupos
                        for historial in cupo.historial_actual
                    ]

                    if historiales:
                        CitaService.cancelarRelacionCupo(historiales, usuario)

                    ConfiguracionDiaService._inactivarCupos(cupos, usuario)


                    #DETECTAR SI QUEDAN DIAS LABORALES FUERA DDL RANGO
                    # esto solo ocurreco aunco un periodo es menor a 7 dias especilamente

                    dias_laborales_inactivar = []
                    configuraciones_inactivar = []
                    dias_quirurgicos_eliminar = []

                    for dia_semana, dia_laboral in dias_laborales.items():

                        fechas = obtener_fechas_por_dia_semana(
                            periodo_front.fecha_inicio,
                            periodo_front.fecha_final,
                            dia_semana 
                        )

                        if not fechas:
                            dias_laborales_inactivar.append(dia_laboral)

                            configuraciones_inactivar.extend(
                                dia_laboral.configuraciones_activas
                            )

                            if dia_laboral.dia_quirurgico_activo:
                                dias_quirurgicos_eliminar.append(
                                    dia_laboral.dia_quirurgico_activo
                                )


                    if configuraciones_inactivar:
                        ConfiguracionDiaService._inactivarConfiguraciones(
                            configuraciones_inactivar,
                            usuario
                        )

                    if dias_quirurgicos_eliminar:
                        Dia_quirurgico.objects.filter(
                            id__in=[dia.id for dia in dias_quirurgicos_eliminar]
                        ).delete()

                    if dias_laborales_inactivar:
                        fecha_actual = timezone.now()

                        for dia in dias_laborales:
                            dia.estado = EstadoRegistro.INACTIVO
                            dia.modificado_por = usuario
                            dia.fecha_modificado = fecha_actual

                        Dia_laboral.objects.bulk_update(
                            dias_laborales,
                            ["estado", "modificado_por", "fecha_modificado"]
                        )


                periodo_registro.fecha_inicio = periodo_front.fecha_inicio
                periodo_registro.fecha_fin = periodo_front.fecha_final
                periodo_registro.modificado_por = usuario
                periodo_registro.save()
                return True

                
            # return actualizar_periodo(periodo_registro, resultado)

        return False
