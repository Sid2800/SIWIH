
from django.db.models.functions import ExtractYear
from agenda_medica.models import Periodo_laboral
from datetime import date

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