
from django.db.models.functions import ExtractYear
from agenda_medica.models import Periodo_laboral
from agenda_medica import validators as agenda_validator
from datetime import date, timedelta
from core.constants.choices_constants import EstadoRegistro
from django.core.exceptions import ValidationError


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

        return list(sorted(anios, reverse=True))
    
    @staticmethod
    def _analizarTipoSolapamiento(periodo, periodo_afectado):

        inicio_existente = periodo_afectado.fecha_inicio
        fin_existente = periodo_afectado.fecha_fin

        inicio_nuevo = periodo.fecha_inicio.date()
        fin_nuevo = periodo.fecha_final.date()

        # 1. Contención interna (fragmentación / mitosis)
        if (inicio_nuevo > inicio_existente and fin_nuevo < fin_existente):
            
            return {
                'accion': 'FRAGMENTACION_PERIODO',
                'titulo': 'Fragmentación de período',
                'mensajes': [
                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"está contenido dentro de un período existente."
                    ),
                    (
                        f"Los períodos resultantes serán:\n"
                        f"- {inicio_existente} - {(inicio_nuevo - timedelta(days=1))}\n"
                        f"- {inicio_nuevo} - {fin_nuevo}\n"
                        f"- {(fin_nuevo + timedelta(days=1))} - {fin_existente}"
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
                'mensajes': [
                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"afecta la parte final de un período existente."
                    ),
                    (
                        f"El período original quedará como:\n"
                        f"- {inicio_existente} - {(inicio_nuevo - timedelta(days=1))}"
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
                'mensajes': [
                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"afecta la parte inicial de un período existente."
                    ),
                    (
                        f"El período original quedará como:\n"
                        f"- {(fin_nuevo + timedelta(days=1))} - {fin_existente}"
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
                'mensajes': [
                    (
                        f"El nuevo período "
                        f"{inicio_nuevo} - {fin_nuevo} "
                        f"contiene completamente un período existente."
                    ),
                    (
                        f"El período resultante será:\n"
                        f"- {inicio_nuevo} - {fin_nuevo}"
                    ),
                    (
                        "La configuración existente será heredada."
                    )
                ]
            }

        return None


    @staticmethod
    def _analizarImpactoPeriodoLaboral(periodo, periodo_registro):

        def impactoEdicion():
            pass
        #1 si el registro viene es porque debemos modificar
        if periodo_registro and periodo.id:
            return impactoEdicion()
        
        else:#validar para adicion
            #1 - primero veamos si existe un periodo para los argumentos en adicion
            periodos_solapados_qs = Periodo_laboral.objects.filter(
                personal_salud__id=periodo.personal_id,
                jornada_laboral__id=periodo.jornada_id,
                estado=EstadoRegistro.ACTIVO,
                fecha_inicio__lte=periodo.fecha_final.date(),
                fecha_fin__gte=periodo.fecha_inicio.date()
            )

            conteo = periodos_solapados_qs.count()

            if conteo > 1:
                raise ValidationError(
                    "La operación afecta múltiples períodos laborales. "
                    "Actualmente este escenario debe resolverse manualmente."
                )
            
            if conteo == 1: # ahora vefircamos qeu tipo de solamiento
                periodo_afectado = periodos_solapados_qs.first()

                return PeriodoLaboralService._analizarTipoSolapamiento(
                    periodo,
                    periodo_afectado
                )
            

            return None



    @staticmethod
    def analizarImpactoPeriodoLaboral(periodo):
        #validacion critica
        periodo_registro = None
        if periodo.id:
            periodo_registro = (
                agenda_validator
                .validarReglasCriticasPeriodoLaboral(periodo)
            )

        resultado = PeriodoLaboralService._analizarImpactoPeriodoLaboral(periodo, periodo_registro)
        return resultado 

