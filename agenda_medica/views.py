from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from django.views.generic import TemplateView
from django.core.exceptions import ValidationError
from core.constants import permisos
from datetime import datetime, timedelta, time, date
from django.db.models import Value, CharField, F, Q, Case, When, Exists, OuterRef,  IntegerField, Subquery, Func
from django.db.models.functions import Concat, Coalesce, Cast
from django.http import JsonResponse
from django.utils import timezone
from core.constants. permisos import AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES
from agenda_medica.models import Periodo_laboral
from agenda_medica import validators as agenda_validators
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from usuario.permisos import verificar_permisos_usuario

from core.utils.utilidades_request import parse_json_request

# Create your views here.
class ListaPeriodoLaborales(UnidadRolRequiredMixin,TemplateView):
    template_name = "agenda_medica/agenda_medica_list.html"
    required_roles = AGENDA_MEDICA_EDITOR_ROLES
    required_unidades = AGENDA_MEDICA_EDITOR_UNIDADES

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user

        
        context['usuario'] = usuario
        anios = PeriodoLaboralService.anios_periodos()
        print(anios)
        context['anios'] = anios

        return context


def listarPeriodosLaboralesAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', "0"))
    order_direction = request.GET.get('order[0][dir]', 'desc')
    estado = (request.GET.get('estado') or '').strip()
    hoy = timezone.now().date()
    anio = hoy.year
    anio_filtro = request.GET.get('anio', str(anio)).strip()

    # Calcular rango de fechas 
    if not anio_filtro or not anio_filtro.isdigit():
        anio_filtro = str(hoy.year)
    fecha_inicio_desde = date(int(anio_filtro), 1, 1)
    fecha_inicio_hasta = date(int(anio_filtro), 12, 31)

    # Queryset base para conteo total 
    base_qs = Periodo_laboral.objects.filter(
        estado=1,
        fecha_inicio__range=(fecha_inicio_desde, fecha_inicio_hasta)
    )
    total_records = base_qs.count() 

    # Queryset principal con anotaciones 
    periodo_laboral_qs = base_qs.annotate(
        periodo=Concat(
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

    # Filtro por estado temporal (U, E, F)
    if estado and estado != "T":
        periodo_laboral_qs = periodo_laboral_qs.filter(estado_temporal=estado)

    # Busqueda por nombre completo o especialidad
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
            )
        ).filter(
            Q(nombre_completo_interno__icontains=search_value) |
            Q(personal_salud__especialidad__nombre_especialidad__icontains=search_value)
        )

    # Columnas para ordenamiento (deben coincidir con las columnas del DataTable)
    columns = [
        "personal_salud__empleado__primer_nombre",              # 0
        "personal_salud__especialidad__nombre_especialidad",    # 1
        "fecha_inicio",                                         # 2 
        "jornada_laboral__nombre_jornada_laboral",              # 3
        "estado_temporal",                                      # 4
    ]

    # Ordenamiento seguro
    if 0 <= order_column < len(columns):
        order_field = columns[order_column]
        if order_direction == 'desc':
            order_field = '-' + order_field
        periodo_laboral_qs = periodo_laboral_qs.order_by(order_field)

    # Conteo de registros después de filtros (búsqueda, estado temporal, etc.)
    filtered_records = periodo_laboral_qs.count()

    # Paginación y extracción de valores
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
        "data": periodos
    })
    


def guardarPeriodoLaboral(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    
    
    try:
        periodo = agenda_validators.validarArgumentosPeriodoLaboral(data, request.user.id)
    except ValueError as e:
        return JsonResponse(
            {'error': str(e)},
            status=400
        )

    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )



    try:
        #resultado = PacienteService.procesar_defuncion(defuncion)
        print(periodo)
        if True:
            return JsonResponse({'guardo': True}, status=200)
        else:
            return JsonResponse({'error': 'No se realizaron cambios'}, status=400)

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        return JsonResponse({'error': 'No se pudo procesar la defunción'}, status=500)


def validarImpactoPeriodoLaboral(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    
    
    try:
        periodo = agenda_validators.validarArgumentosPeriodoLaboral(data, request.user.id)


    except ValueError as e:
        return JsonResponse(
            {'error': str(e)},
            status=400
        )

    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )



    try:
        #resultado = PacienteService.procesar_defuncion(defuncion)
        print("////////////////////////////////")
        print(f"impacto {periodo}")

        resultado = PeriodoLaboralService.analizarImpactoPeriodoLaboral(periodo)
        
        return JsonResponse({'resultado': resultado}, status=200)



    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        print(e)
        return JsonResponse({'error': 'No se pudo procesar la defunción'}, status=500)

