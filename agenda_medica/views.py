from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from django.views.generic import TemplateView
from core.constants import permisos
from datetime import datetime, timedelta, time
from django.db.models import Value, CharField, F, Q, Case, When, Exists, OuterRef,  IntegerField, Subquery, Func
from django.db.models.functions import Concat, Coalesce, Cast
from django.http import JsonResponse
from django.utils import timezone
from core.constants import permisos
from agenda_medica.models import Periodo_laboral
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService

# Create your views here.
class ListaAgendaMedica(UnidadRolRequiredMixin,TemplateView):
    template_name = "agenda_medica/agenda_medica_list.html"
    required_roles = permisos.ATENCION_VISUALIZACION_ROLES
    required_unidades = permisos.ATENCION_VISUALIZACION_UNIDADES

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        
        context['usuario'] = usuario
        anios = PeriodoLaboralService.anios_periodos()
        print(anios)
        context['anios'] = anios



        return context



def listarAgendaMedicaAPI(request):

    for key, value in request.GET.items():
        print(key, value)
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', "0"))

    order_direction = request.GET.get('order[0][dir]', 'desc')
    
    search_column = request.GET.get('search_column')

    estado = (request.GET.get('estado') or '').strip()

    hoy = timezone.now().date()
    anio = hoy.year

    anio_filtro = request.GET.get('anio')
    anio_filtro = (request.GET.get('anio') or str(anio)).strip()




    periodo_laboral_qs = (
        Periodo_laboral.objects
        .filter(
            estado=1,
            fecha_inicio__year=int(anio_filtro)
        ).annotate(
            periodo = Concat(
                Func(
                    F('fecha_inicio'),
                    Value('%d/%m/%Y'),
                    function='DATE_FORMAT',
                    output_field=CharField()
                ),
                Value(' al '),
                Func(
                    F('fecha_fin'),
                    Value('%d/%m/%Y'),
                    function='DATE_FORMAT',
                    output_field=CharField()
                )
            ),
            estado_temporal=Case(
                When(fecha_inicio__gt=hoy, then=Value("U")),
                When(fecha_inicio__lte=hoy, fecha_fin__gte=hoy, then=Value("E")),
                default=Value("F"),
                output_field=CharField()
            )
        )
    )
    
    if estado and estado != "T":
        periodo_laboral_qs = periodo_laboral_qs.filter(
            estado_temporal=estado
        )
            

    
    # Si se requiere búsqueda por nombre completo
    if search_value:
        periodo_laboral_qs = periodo_laboral_qs.annotate(
            nombre_completo_interno=Concat(
                F("personal_salud__empleado__primer_nombre"),
                Case(
                    When(personal_salud__empleado__segundo_nombre__isnull=False, personal_salud__empleado__segundo_nombre__exact="", then=Value("")),
                    When(personal_salud__empleado__segundo_nombre__isnull=False, then=Concat(Value(" "), F("personal_salud__empleado__segundo_nombre"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                Value(" "),
                F("personal_salud__empleado__primer_apellido"),
                Case(
                    When(personal_salud__empleado__segundo_apellido__isnull=False, personal_salud__empleado__segundo_apellido__exact="", then=Value("")),
                    When(personal_salud__empleado__segundo_apellido__isnull=False, then=Concat(Value(" "), F("personal_salud__empleado__segundo_apellido"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                output_field=CharField()
            ),
            
        ).filter(
            Q(nombre_completo_interno__icontains=search_value) |
            Q(personal_salud__especialidad__nombre_especialidad__icontains=search_value)
        )
    



    
    # Columnas para ordenamiento (deben coincidir con las columnas del DataTable)
    columns = [
        "personal_salud__empleado__primer_nombre",              # 0
        "personal_salud__especialidad__nombre_especialidad",    # 1
        "periodo",                                              # 2
        "jornada_laboral__nombre_jornada_laboral",              # 3 
        "estado_temporal",                                      # 5

    ]
    
    # Mapea columnas que necesitan coalesce para evitar null en orden
    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            periodo_laboral_qs = periodo_laboral_qs.order_by(order_column_name)
        else:
            periodo_laboral_qs = periodo_laboral_qs.order_by('-' + order_column_name)
    

    # Conteo
    total_records = Periodo_laboral.objects.count()
    filtered_records = periodo_laboral_qs.count()
    
    periodos = list(periodo_laboral_qs[start:start + length].values(
        "id",
        "personal_salud__empleado__primer_nombre",
        "personal_salud__empleado__segundo_nombre",
        "personal_salud__empleado__primer_apellido",
        "personal_salud__empleado__segundo_apellido",
        "personal_salud__especialidad__nombre_especialidad",
        "periodo",
        "jornada_laboral__nombre_jornada_laboral",
        "estado_temporal"

    ))
    
    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": periodos #evaluaciones
    })
    
