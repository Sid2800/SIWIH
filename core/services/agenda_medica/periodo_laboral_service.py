
from django.db.models.functions import ExtractYear
from agenda_medica.models import Periodo_laboral, Dia_laboral, Cupo_agenda

from datetime import date, timedelta
from core.constants.choices_constants import EstadoRegistro, DiaSemana, EstadoCupoAgenda
from django.core.exceptions import ValidationError
from core.constants.domain_constants import AccionImpactoPeriodoLaboral, TipoCambioFechaPeriodo
from django.db import transaction
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from core.utils.utilidades_fechas import obtener_fechas_por_dia_semana
from types import SimpleNamespace
from django.db.models import Sum, Count, Value, Q
from django.db.models.functions import Coalesce
from itertools import groupby
from operator import attrgetter

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
    def obtener_periodo_laboral(id):
        """
        Obtiene la informacion del paciente esterno del dni recibido
        """
        try:
            periodo = Periodo_laboral.objects.get(id=id, estado=EstadoRegistro.ACTIVO)
            return periodo  
        except Periodo_laboral.DoesNotExist:
            return None
    

    @staticmethod
    def obtener_cantidad_dias_semana( periodo_laboral, dia_semana):
        return len(
            obtener_fechas_por_dia_semana(
                periodo_laboral.fecha_inicio,
                periodo_laboral.fecha_fin,
                dia_semana
            )
        )

    @staticmethod
    def obtener_dias_configurados(id_periodo):
        dias_laborales = (
            Dia_laboral.objects
            .filter(
                periodo_laboral_id=id_periodo,
                estado=EstadoRegistro.ACTIVO
            )
            .annotate(
                total_cupos_configurados=Coalesce(
                    Sum(
                        "cupos__cupos",
                        filter=~Q(cupos__estado=EstadoCupoAgenda.INACTIVO)
                    ),
                    Value(0)
                ),
                total_tipos=Coalesce(
                    Count(
                        "cupos",
                        filter=Q(cupos__estado=EstadoRegistro.ACTIVO)
                    ),
                    Value(0)
                )
            )
            .order_by("dia_semana")
        )
        return dias_laborales
    

    
    @staticmethod
    def obtener_cupos_agrupados_por_fecha(periodo_laboral, dia_numero):
        """
        Obtiene los cupos activos de un día laboral del período,
        agrupados por fecha.

        """
        cupos = (
            Cupo_agenda.objects
            .filter(
                configuracion_cupo__dia_laboral__periodo_laboral=periodo_laboral,
                configuracion_cupo__dia_laboral__dia_semana=dia_numero,
                estado=EstadoCupoAgenda.DISPONIBLE
            )
            .select_related(
                "configuracion_cupo",
                "configuracion_cupo__dia_laboral",
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


        dias_laborales_qs = PeriodoLaboralService.obtener_dias_configurados(id_periodo)
        # Convertir queryset a mapa:
        # {1: objeto_lunes, 5: objeto_viernes}
        dias_map = {
            dia.dia_semana: dia
            for dia in dias_laborales_qs
        }


        dias_semana = []

        for ndia, nombredia in DiaSemana.choices:
            dia = dias_map.get(ndia)
            if dia:
                dias_semana.append({
                "numero_dia": ndia,
                "id":dia.id,
                "nombre_dia": nombredia,
                "configurado": True,
                "hora_inicio": dia.hora_inicio,
                "hora_fin": dia.hora_fin,
                "total_cupos": dia.total_cupos_configurados,
                "total_tipos": dia.total_tipos,
            })
                
            else:
                dias_semana.append({
                "numero_dia": ndia,
                "nombre_dia": nombredia,
                "configurado": False,
            })
        return dias_semana


    @staticmethod
    def _analizarTipoSolapamiento(periodo, periodo_afectado):

        inicio_existente = periodo_afectado.fecha_inicio
        fin_existente = periodo_afectado.fecha_fin

        inicio_nuevo = periodo.fecha_inicio
        fin_nuevo = periodo.fecha_final

        metadata_periodo = {
            'periodo_afectado_id': periodo_afectado.id,
            'fecha_modificado': (
                periodo_afectado.fecha_modificado.isoformat()
                if periodo_afectado.fecha_modificado
                else None
            )
        }

        # 1. Contención interna (fragmentación / mitosis)
        if (inicio_nuevo > inicio_existente and fin_nuevo < fin_existente):
            
            return {
                'accion': AccionImpactoPeriodoLaboral.FRAGMENTACION_PERIODO,
                'titulo': 'Fragmentación de período',
                **metadata_periodo,
                'mensajes': [

                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"está <strong>contenido dentro de un período existente.</strong>"
                    ),

                    "<strong>Los períodos resultantes serán:</strong>",

                    (
                        f"- {inicio_existente} - "
                        f"{(inicio_nuevo - timedelta(days=1))}"
                    ),

                    (
                        f"- {inicio_nuevo} - {fin_nuevo}"
                    ),

                    (
                        f"- {(fin_nuevo + timedelta(days=1))} - "
                        f"{fin_existente}"
                    ),

                    (
                        "Los nuevos períodos heredarán "
                        "la configuración existente."
                    )
                ]
            }


        # 2. Reducción borde final
        elif (inicio_nuevo > inicio_existente and fin_nuevo >= fin_existente):

            return {
                'accion': 'REDUCCION_FINAL',
                'titulo': 'Reducción de período',
                **metadata_periodo,
                'mensajes': [

                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"afecta la <strong>parte final</strong> "
                        f"de un período existente."
                    ),

                    "<strong>El período original quedará como:</strong>",

                    (
                        f"- {inicio_existente} - "
                        f"{(inicio_nuevo - timedelta(days=1))}"
                    ),

                    (
                        "El nuevo período heredará "
                        "la configuración existente."
                    )

                ]       
            }   


        # 3. Reducción borde inicial
        elif (inicio_nuevo <= inicio_existente and fin_nuevo < fin_existente):
            return {
                'accion': 'REDUCCION_INICIAL',
                'titulo': 'Reducción de período',
                **metadata_periodo,
                'mensajes': [

                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"afecta la <strong>parte inicial</strong> "
                        f"de un período existente."
                    ),

                    "<strong>El período original quedará como:</strong>",

                    (
                        f"- {(fin_nuevo + timedelta(days=1))} - "
                        f"{fin_existente}"
                    ),

                    (
                        "El nuevo período heredará "
                        "la configuración existente."
                    )
                ]
            }


        # 4. El nuevo contiene completamente el existente
        elif (inicio_nuevo <= inicio_existente and fin_nuevo >= fin_existente):
            return {
                'accion': 'ABSORSION_PERIODO',
                'titulo': 'Absorción de período',
                **metadata_periodo,
                'mensajes': [

                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"contiene completamente un período existente."
                    ),

                    "<strong>El período resultante será:</strong>",

                    (
                        f"- {inicio_nuevo} - {fin_nuevo}"
                    ),

                    (
                        "La configuración existente será heredada."
                    )
                ]
            }
        return None
    

    def _analizarImpactoEdicionPeriodoLaboral(periodo, periodo_registro):

        def analizarFechaInicial():

            fecha_original = periodo_registro.fecha_inicio
            fecha_nueva = periodo.fecha_inicio

            # SIN CAMBIO
            if fecha_nueva == fecha_original:
                return {
                    'tipo': TipoCambioFechaPeriodo.SIN_CAMBIO,
                    'fecha_original': fecha_original,
                    'fecha_nueva': fecha_nueva,
                    'dias': 0
                }

            # AMPLIACION
            # la fecha nueva va más atrás
            if fecha_nueva < fecha_original:

                dias = (
                    fecha_original - fecha_nueva
                ).days

                return {
                    'tipo': TipoCambioFechaPeriodo.AMPLIACION,
                    'fecha_original': fecha_original,
                    'fecha_nueva': fecha_nueva,
                    'dias': dias
                }

            # REDUCCION
            # la fecha nueva avanza hacia adelante
            dias = (
                fecha_nueva - fecha_original
            ).days

            return {
                'tipo': TipoCambioFechaPeriodo.REDUCCION,
                'fecha_original': fecha_original,
                'fecha_nueva': fecha_nueva,
                'dias': dias
            }

        def analizarFechaFinal():
            fecha_original = periodo_registro.fecha_fin
            fecha_nueva = periodo.fecha_final

            # SIN CAMBIO
            if fecha_nueva == fecha_original:

                return {
                    'tipo': TipoCambioFechaPeriodo.SIN_CAMBIO,
                    'fecha_original': fecha_original,
                    'fecha_nueva': fecha_nueva,
                    'dias': 0
                }

            # AMPLIACION
            # la fecha final se mueve hacia adelante
            if fecha_nueva > fecha_original:

                dias = (
                    fecha_nueva - fecha_original
                ).days

                return {
                    'tipo': TipoCambioFechaPeriodo.AMPLIACION,
                    'fecha_original': fecha_original,
                    'fecha_nueva': fecha_nueva,
                    'dias': dias
                }

            # REDUCCION
            # la fecha final retrocede
            dias = (
                fecha_original - fecha_nueva
            ).days

            return {
                'tipo': TipoCambioFechaPeriodo.REDUCCION,
                'fecha_original': fecha_original,
                'fecha_nueva': fecha_nueva,
                'dias': dias
            }
        
        # notificar que desactvar un perido afecta citas 
        if  periodo.estado is False and periodo_registro.estado == EstadoRegistro.ACTIVO:
            
            #encontrar el impacto en citas  y colocarlo en el mensaje
            citas = 999999
        
            return {
                'titulo': 'Desactivar periodo',
                'mensajes': [
                    (
                        f"El período afectado "
                        f"{periodo_registro}"
                    ),
                    (
                        f"Se encontraron {citas} citas afectadas, estas citas deberan ser reprogramadas"
                    ),

                    "<strong>¿Desea continuar con los cambios?</strong>",
                ]
            }

        #ahora validar las fechas por separadas para controlar amplaciones y reducciones por fecha
        fecha_inicial = analizarFechaInicial()
        fecha_final = analizarFechaFinal()

        #AMPLIACION 
        # verificamos si amplacion juntas, me refiero a ver si no choca las podemos validar jutnas entonce
        
        if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.AMPLIACION or fecha_final['tipo'] == TipoCambioFechaPeriodo.AMPLIACION:
            #ahora si validamos el periodo completo con ORM
            conflicto = (
                Periodo_laboral.objects
                .filter(
                    personal_salud__id=periodo.personal_id,
                    jornada_laboral__id=periodo.jornada_id,
                    estado=EstadoRegistro.ACTIVO,
                    fecha_inicio__lte=periodo.fecha_final,
                    fecha_fin__gte=periodo.fecha_inicio
                )
                .exclude(id=periodo.id)
                .exists()
            )

            if conflicto:
                raise ValidationError(
                        "No es posible ampliar el período laboral "
                        "porque invade otro período existente."
                    )
            
        if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION or fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
            dias_reducidos = 0
            mensajes_reduccion = []

            # reducción fecha inicial
            if fecha_inicial['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                dias_reducidos += int(fecha_inicial.get('dias', 0))
                mensajes_reduccion.append(
                    (
                        f"La fecha inicial fue reducida "
                        f"{fecha_inicial['dias']} días."
                    )
                )

            # reducción fecha final
            if fecha_final['tipo'] == TipoCambioFechaPeriodo.REDUCCION:
                dias_reducidos += int(fecha_final.get('dias', 0))
                mensajes_reduccion.append(
                    (
                        f"La fecha final fue reducida "
                        f"{fecha_final['dias']} días."
                    )
                )

            # encontrar impacto citas
            citas = 999999

            return {
                'titulo': 'Reducción de período',
                'mensajes': [
                    (
                        f"El período afectado "
                        f"{periodo_registro}"
                    ),
                    *mensajes_reduccion,
                    (
                        f"Total de días afectados por reducción: "
                        f"{dias_reducidos}"
                    ),
                    (
                        f"Se encontraron {citas} citas afectadas, "
                        f"estas citas deberán ser reprogramadas."
                    ),
                    "<strong>¿Desea continuar con los cambios?</strong>",
                ]
            }
        
        return None


    @staticmethod
    def _analizarImpactoPeriodoLaboral(periodo, periodo_registro):
        #1 si el registro viene es porque debemos modificar
        if periodo_registro and periodo.id:
            return PeriodoLaboralService._analizarImpactoEdicionPeriodoLaboral(periodo, periodo_registro)
        
        else:#validar para adicion
            #1 - primero veamos si existe un periodo para los argumentos en adicion
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
            
            if conteo == 1: # ahora vefircamos qeu tipo de solamiento
                periodo_afectado = periodos_solapados_qs.first()
                
                if (periodo.fecha_inicio == periodo_afectado.fecha_inicio
                and
                periodo.fecha_final == periodo_afectado.fecha_fin):
                    raise ValidationError(
                        "Ya existe un período laboral "
                        "con el mismo rango de fechas."
                    )

                
                return PeriodoLaboralService._analizarTipoSolapamiento(
                    periodo,
                    periodo_afectado
                )
            return None


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
    def procesarPeriodoLaboral(periodo, usuario):
        from agenda_medica.validators import PeriodoLaboralValidator

        def aplicar_reduccion_inicial(periodo_afectado):
            with transaction.atomic():
                nueva_fecha_inicio = (
                    periodo.fecha_final
                    + timedelta(days=1)
                )
                periodo_afectado.fecha_inicio = (
                    nueva_fecha_inicio
                )
                periodo_afectado.modificado_por_id = (
                    usuario.id
                )
                periodo_afectado.save()
                crear_periodo(periodo)
                return True
            
        def aplicar_reduccion_final(periodo_afectado):
            with transaction.atomic():
                nueva_fecha_final = (
                    periodo.fecha_inicio
                    - timedelta(days=1)
                )
                periodo_afectado.fecha_fin = nueva_fecha_final
                periodo_afectado.modificado_por_id = usuario.id
                periodo_afectado.save()
                crear_periodo(periodo) 
                return True
        
        def aplicar_fragmentacion(periodo_afectado):
            with transaction.atomic():
                # el fragmenteo original sera el mas cercano a la fecha inicial
                nueva_fecha_final = (
                    periodo.fecha_inicio
                    - timedelta(days=1)
                )
                fecha_final_original = periodo_afectado.fecha_fin
                periodo_afectado.fecha_fin = nueva_fecha_final
                periodo_afectado.modificado_por_id = usuario.id

                periodo_afectado.save()
                #hijo2
                crear_periodo(periodo) 

                fecha_inicial_cola = (
                    periodo.fecha_final
                    + timedelta(days=1)
                )

                periodo_cola = SimpleNamespace(
                    personal_id= periodo.personal_id,
                    jornada_id= periodo.jornada_id,
                    fecha_inicio= fecha_inicial_cola,
                    fecha_final= fecha_final_original,
                )
                crear_periodo(periodo_cola)
                return True
            
        def aplicar_absorcion(periodo_afectado):
            with transaction.atomic():
                periodo_afectado.fecha_inicio = periodo.fecha_inicio
                periodo_afectado.fecha_fin = periodo.fecha_final
                periodo_afectado.modificado_por_id = usuario.id
                periodo_afectado.save()
                return True

        def actualizar_periodo(periodoR):
            """Actualiza los datos del periodo solo si han cambiado."""
            cambios = False
            try:

                if periodoR.fecha_inicio != periodo.fecha_inicio:
                    periodoR.fecha_inicio = periodo.fecha_inicio
                    cambios = True

                if periodoR.fecha_fin != periodo.fecha_final:
                    periodoR.fecha_fin = periodo.fecha_final
                    cambios = True

                if periodoR.estado != periodo.estado:
                    periodoR.estado = periodo.estado
                    cambios = True

                if cambios:
                    periodoR.modificado_por_id = usuario.id

                if not cambios:
                    return False

                periodoR.save()
                return True
            
            except Exception as e:
                log_error(
                    f"[FALLO_ACTUALIZAR_PERIODO_LABORAL] id={periodoR.id} detalle={str(e)}",
                    app=LogApp.PACIENTE
                )
                raise
        
        def crear_periodo(periodoArg):
            kwargs = {
                "personal_salud_id": periodoArg.personal_id,
                "jornada_laboral_id": periodoArg.jornada_id,
                "fecha_inicio": periodoArg.fecha_inicio,
                "fecha_fin": periodoArg.fecha_final,
                "creado_por_id": usuario.id,
                "modificado_por_id": usuario.id,
                
            }

            Periodo_laboral.objects.create(**kwargs)
            return True
            

        # inicio del metodo
        periodo_registro = None
        if periodo.id:
            periodo_registro = (
                PeriodoLaboralValidator
                .validarReglasCriticasPeriodoLaboral(periodo)
            )

        resultado = PeriodoLaboralService._analizarImpactoPeriodoLaboral(periodo, periodo_registro)
        

        #pa crear
        if not resultado and not periodo_registro : #guardamos porque no hay conflictos ni un registro previo
            #guaradar de una
            with transaction.atomic():
                return crear_periodo(periodo)

        elif resultado and not periodo_registro: 
            #adicion con ajuste a regsitros previos 
            accion = resultado.get('accion')
            id_periodo_ajustar = resultado.get('periodo_afectado_id')

            periodo_afectado = Periodo_laboral.objects.get(
                id=id_periodo_ajustar
            )

            if not periodo.fecha_impacto:
                raise ValidationError(
                    "No se pudo validar el período afectado."
                )

            fecha_registro = periodo_afectado.fecha_modificado.replace(microsecond=0)
            fecha_validacion = periodo.fecha_impacto.replace(microsecond=0)
            
        
            if (fecha_registro != fecha_validacion):
                raise ValidationError(
                        "El período afectado por la nueva adición "
                        "fue modificado por otro usuario. "
                        "Por favor, reinicie el proceso."
                    )
                                

            if accion == AccionImpactoPeriodoLaboral.REDUCCION_INICIAL.value:
                return aplicar_reduccion_inicial(periodo_afectado)

            elif accion == AccionImpactoPeriodoLaboral.REDUCCION_FINAL.value:
                return aplicar_reduccion_final(periodo_afectado)

            elif accion == AccionImpactoPeriodoLaboral.FRAGMENTACION_PERIODO.value: 
                return aplicar_fragmentacion(periodo_afectado)

            elif accion == AccionImpactoPeriodoLaboral.ABSORSION_PERIODO.value:
                return aplicar_absorcion(periodo_afectado)
            
        elif periodo_registro: #editar

            #compoirbar si  mientras el usaurios decidia el registro fue modificado 
            fecha_registro = (periodo_registro.fecha_modificado.replace(microsecond=0))
            fecha_validacion = (periodo.fecha_modificado.replace(microsecond=0))

            if (fecha_registro != fecha_validacion):
                raise ValidationError(
                        "El período a editar fue modificado por otro usuario. "
                        "Por favor, reinicie el proceso."
                    )
            
            return actualizar_periodo(periodo_registro)

        return False
