from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.views import View
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time, date
from django.db.models import Value, CharField, F, Q, Case, When, Exists, OuterRef,  IntegerField, Subquery, Func, ExpressionWrapper, DurationField
from django.db.models.functions import Concat, Coalesce, Cast
from django.http import JsonResponse
from django.utils import timezone
from core.constants.permisos import AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES, AGENDA_MEDICA_VISUALIZACION_ROLES, AGENDA_MEDICA_VISUALIZACION_UNIDADES
from core.constants.domain_constants import LogApp
from core.constants.choices_constants import TipoAusencia
from django.views.decorators.http import require_GET
from django.urls import  reverse
from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy
from agenda_medica.models import Periodo_laboral,Ausencia
from agenda_medica.validators import DiaLaboralValidator, PeriodoLaboralValidator, AgendaMedicaValidator, AusenciaValidator
from core.services.agenda_medica.periodo_laboral_service import PeriodoLaboralService
from core.services.agenda_medica.configuracion_dia_service  import  ConfiguracionDiaService
from core.services.agenda_medica.agenda_medica_service import AgendaMedicaService
from core.services.agenda_medica.dia_quirurgico_service import DiaQuirurgicoService
from core.services.agenda_medica.ausencia_service import AusenciaService
from usuario.permisos import verificar_permisos_usuario
from core.utils.utilidades_textos import generar_slug
from core.utils.utilidades_logging import log_error
from core.utils.utilidades_request import parse_json_request
from django.views.decorators.http import require_POST, require_http_methods


# Create your views here.
class ListaPeriodoLaborales(UnidadRolRequiredMixin,TemplateView):
    template_name = "agenda_medica/agenda_medica_periodo_list.html"
    required_roles = AGENDA_MEDICA_EDITOR_ROLES
    required_unidades = AGENDA_MEDICA_EDITOR_UNIDADES

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        
        context['usuario'] = usuario
        anios = PeriodoLaboralService.anios_periodos()
        context['anios'] = anios

        return context


class ListaAusencias(UnidadRolRequiredMixin,TemplateView):
    template_name = "agenda_medica/agenda_medica_ausencia_list.html"
    required_roles = AGENDA_MEDICA_EDITOR_ROLES
    required_unidades = AGENDA_MEDICA_EDITOR_UNIDADES

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        
        context['usuario'] = usuario
        anios = AusenciaService.anios_ausencias()
        context['anios_ausencias'] = anios
        context['tipos_ausencia'] =  TipoAusencia.opciones()

        return context



class CalendarioPersonalSalud(UnidadRolRequiredMixin, TemplateView):

    template_name = "agenda_medica/calendario_personal_salud.html"

    required_roles = AGENDA_MEDICA_EDITOR_ROLES
    required_unidades = AGENDA_MEDICA_EDITOR_UNIDADES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["usuario"] = self.request.user
        idPersonal = kwargs.get("personal_salud_id",0)
        context["personal_salud_id"] = idPersonal



        return context
    
    

class ConfigurarPeriodo(UnidadRolRequiredMixin,DetailView):
    template_name = "agenda_medica/configurar_agenda.html"
    required_roles = AGENDA_MEDICA_EDITOR_ROLES
    required_unidades = AGENDA_MEDICA_EDITOR_UNIDADES
    model = Periodo_laboral
    context_object_name = 'periodo'

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        context['usuario'] = usuario
        id_periodo = self.kwargs["pk"]
        dias_configurados = (PeriodoLaboralService.construir_dias_semana_ui(id_periodo))

        print(dias_configurados)
        context['dias_configurados'] = dias_configurados
        return context
    


def listarPeriodosLaboralesAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', "0"))
    order_direction = request.GET.get('order[0][dir]', 'asc')
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
    
            periodo_laboral_qs = periodo_laboral_qs.order_by(order_field, 'fecha_inicio')


# Conteo de registros después de filtros (búsqueda, estado temporal, etc.)
    filtered_records = periodo_laboral_qs.count()

    # Paginación y extracción de valores
    periodos = list(periodo_laboral_qs[start:start + length].values(
        "personal_salud__empleado__primer_nombre",
        "personal_salud__empleado__segundo_nombre",
        "personal_salud__empleado__primer_apellido",
        "personal_salud__empleado__segundo_apellido",
        "personal_salud__especialidad__nombre_especialidad",
        "periodo",
        "jornada_laboral__nombre_jornada_laboral",
        "estado_temporal",
        "id",
    ))

    for periodo in periodos:
        periodo['url_configuracion'] = reverse(
            'configurar_periodo',
            kwargs={'pk': periodo['id'],
                'slug': generar_slug(periodo['personal_salud__empleado__primer_nombre']+" "+periodo['personal_salud__empleado__primer_apellido'])
                },
            
        )

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": periodos
    })
    

def listarAusenciasAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', "0"))
    order_direction = request.GET.get('order[0][dir]', 'asc')
    tipo = (request.GET.get('tipo') or '').strip()
    hoy = timezone.now().date()
    anio = hoy.year
    anio_filtro = request.GET.get('anio', str(anio)).strip()


    # Calcular rango de fechas 
    if not anio_filtro or not anio_filtro.isdigit():
        anio_filtro = str(hoy.year)

    fecha_inicio_desde = date(int(anio_filtro), 1, 1)
    fecha_inicio_hasta = date(int(anio_filtro), 12, 31)

    # Queryset base para conteo total 
    base_qs = Ausencia.objects.filter(
        estado=1,
        fecha_inicio__range=(fecha_inicio_desde, fecha_inicio_hasta)
    )
    total_records = base_qs.count() 

    # Queryset principal con anotaciones 
    ausencias_qs = base_qs.annotate(
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
            ),
            tipo_label=Case(
            *[
                When(tipo=valor, then=Value(label))
                for valor, label in TipoAusencia.choices
            ],
            output_field=CharField()
        )
    )

    # Filtro por tipo de ausencia
    if tipo and  not tipo == '0':
        ausencias_qs = ausencias_qs.filter(tipo=tipo)


    # Busqueda por nombre completo o especialidad
    if search_value:
        ausencias_qs = ausencias_qs.annotate(
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
        "dias",                                                 # 3 no ordenable solo esta para aumenrart el indice
        "tipo_label",                                           # 4
        "estado_temporal"                                       # 5
    ]


    
    # Ordenamiento seguro
    if 0 <= order_column < len(columns):
        order_field = columns[order_column]
        if order_direction == 'desc':
            order_field = '-' + order_field

        ausencias_qs = ausencias_qs.order_by(order_field, 'fecha_inicio')



    # Conteo de registros después de filtros (búsqueda, estado temporal, etc.)
    filtered_records = ausencias_qs.count()

    # Paginación y extracción de valores
    ausencias = list(ausencias_qs[start:start + length].values(
        "personal_salud__empleado__primer_nombre",
        "personal_salud__empleado__segundo_nombre",
        "personal_salud__empleado__primer_apellido",
        "personal_salud__empleado__segundo_apellido",
        "personal_salud__especialidad__nombre_especialidad",
        "fecha_inicio",
        "fecha_fin",
        "tipo",
        "tipo_label",
        "periodo",
        "estado_temporal",
        "id",
    ))

    for ausencia in ausencias:
        ausencia['dias'] = (
            ausencia['fecha_fin'] - ausencia['fecha_inicio']
        ).days + 1

        colores = AusenciaService.AGENDA_COLORES_TIPO_AUSENCIA.get(
            ausencia['tipo'],
            {
                "color": "rgba(0, 0, 0, 0.05)",
                "borderColor": "rgba(0, 0, 0, 0.5)",
            }
        )

        ausencia['colores_tipo'] = colores

    return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": ausencias
        })



class ListarTiposAusencias(View):
    def get(self, request):
        tipos_ausencia =  TipoAusencia.opciones()
        return JsonResponse(tipos_ausencia, safe=False)



@require_GET
def obtenerPeriodoLaboral(request):
    id = request.GET.get('id')
    if not id:
        return JsonResponse({'error': 'El parametro id es requerido'}, status=400)
    
    periodo = PeriodoLaboralService.obtener_periodo_laboral(id)

    if not periodo:
        return JsonResponse({"error": "No se encontró un período laboral habilitado."}, status=404)
    
    return JsonResponse({
    "id": periodo.id,
    "id_personal_clinico": periodo.personal_salud.id,
    "especialidad": getattr(periodo.personal_salud.especialidad, 'nombre_especialidad', None),
    "fecha_inicio":periodo.fecha_inicio,
    "fecha_final":periodo.fecha_fin,
    "id_jornada": periodo.jornada_laboral.id,
    "creado_por": periodo.creado_por.username, 
    "modificado_por": periodo.modificado_por.username, 
    "fecha_creado": periodo.fecha_creado, 
    "fecha_modificado": periodo.fecha_modificado,
    "estado": periodo.estado,
    "ejecucion": periodo.estado_temporal
    }, status=200)


def guardarPeriodoLaboral(request):
    
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    
    try:
        periodo = PeriodoLaboralValidator.validarArgumentosPeriodoLaboral(data, request.user.id)
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
        #PeriodoLaboralService.analizarImpactoPeriodoLaboral(periodo)
        resultadoGuardado = PeriodoLaboralService.procesarPeriodoLaboral(periodo,request.user)

        if resultadoGuardado:
            return JsonResponse({'guardo': True}, status=200)
        else:
            return JsonResponse({'guardo': False}, status=200)

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    except Exception as e:
        print(e)
        return JsonResponse({'error': 'No se pudo guardar el periodo'}, status=500)


def validarImpactoPeriodoLaboral(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    try:
        periodo = PeriodoLaboralValidator.validarArgumentosPeriodoLaboral(data, request.user.id)
    except ValueError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    try:
        resultado = PeriodoLaboralService.analizarImpactoPeriodoLaboral(periodo)

        return JsonResponse({'resultado': resultado}, status=200)
    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'No se pudo procesar el periodo'}, status=500)



def validarImpactoAusencia(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    try:
        ausencia = AusenciaValidator.validarArgumentosAusencia(data, request.user.id)
    except ValueError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )


    try:
        resultado = AusenciaService.analizarImpactoAusencia(ausencia)

        return JsonResponse({'resultado': resultado}, status=200)
    
    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'No se pudo procesar el periodo'}, status=500)




@require_POST
def guardarDiaLaboral(request):
    
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )
    
    try:
        diaLaboralConfigurado = DiaLaboralValidator.validarArgumentosDiaLaboral(data)
    except ValueError as e:
        return JsonResponse(
            {"error": "Error interno del servidor."},
            status=500
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    try:
        #PeriodoLaboralService.analizarImpactoPeriodoLaboral(periodo) al editar
        resultado = ConfiguracionDiaService.crear_dia_laboral(diaLaboralConfigurado,request.user)
        if resultado:
            return JsonResponse({'guardo': True}, status=200)
    

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    except Exception as e:
        log_error(
                f"[ConfiguracionDiaService]: crear_dia_laboral {e}",
                LogApp.AGENDA
            )
        return JsonResponse({'error': 'No se pudo guardar el periodo'}, status=500)
    


@require_POST
def guardarAusencia(request):
    
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )
    
    try:
        ausencia = AusenciaValidator.validarArgumentosAusencia(data, request.user.id)
    except ValueError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )


    try:
        resultado = AusenciaService.crearAusencia(ausencia,request.user)
        return JsonResponse({'resultado': resultado}, status=200)
            

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    except Exception as e:
        log_error(
                f"[ConfiguracionDiaService]: crear_dia_laboral {e}",
                LogApp.AGENDA
            )
        return JsonResponse({'error': 'No se pudo guardar el periodo'}, status=500)
    


@require_POST
def editarAusencia(request):
    
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )
    
    try:
        ausencia = AusenciaValidator.validarArgumentosAusencia(data, request.user.id)
    except ValueError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )


    try:

        
        resultado = AusenciaService.editarAusencia(ausencia,request.user)

        # print(ausencia)
        return JsonResponse({'resultado': resultado}, status=200)
            

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)

    except Exception as e:
        log_error(
                f"[ConfiguracionDiaService]: crear_dia_laboral {e}",
                LogApp.AGENDA
            )
        return JsonResponse({'error': 'No se pudo guardar el periodo'}, status=500)
    



@require_POST
def definirDiaQuirurgico(request):

    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
            return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )
    
    try:
        DiaQuirurgicoService.crear_dia_quirurgico(data, request.user)
        return JsonResponse({'guardo': True}, status=200)


    except ValueError as e:
        return JsonResponse(
            {"error": "Error interno del servidor."},
            status=500
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    except Exception as e:
        log_error(f"[DiaQuirurgicoService]: crear_dia_quirurgico {e}", LogApp.AGENDA)

        return JsonResponse(
            {'error': 'No se pudo configurar el día quirúrgico.'},status=500)




@require_http_methods(["DELETE"])
def quitarDiaQuirurgico(request):

    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
            return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )
    
    try:
        DiaQuirurgicoService.quitar_dia_quirurgico(data, request.user)

        return JsonResponse({'guardo': True}, status=200)


    except ValueError as e:
        return JsonResponse(
            {"error": "Error interno del servidor."},
            status=500
        )
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    except Exception as e:
        log_error(f"[DiaQuirurgicoService]: quitar_dia_quirurgico {e}", LogApp.AGENDA)

        return JsonResponse(
            {'error': 'No se pudo quitar el día quirurgico.'},status=500)



@require_GET
def obtenerDiaLaboral(request):
    id = request.GET.get('id')
    if not id:
        return JsonResponse({'error': 'El parametro id es requerido'}, status=400)
    
    detalle = ConfiguracionDiaService.obtener_dia_laboral_detallado(id)


    if not detalle:
        return JsonResponse(
            {"error": "No se encontró el día laboral."},
            status=404
        )
    
    return JsonResponse(detalle  , status=200)


@require_GET
def obtenerAusencia(request):
    id = request.GET.get('id')

    if not id:
        return JsonResponse({'error': 'El parametro id es requerido'}, status=400)
    
    ausencia = AusenciaService.obtener_ausencia(id)

    if not ausencia:
        return JsonResponse({"error": "No se encontró una ausencia habilitado."}, status=404)
    
    return JsonResponse({
            "id": ausencia.id,
            "id_personal_clinico": ausencia.personal_salud.id,
            "especialidad": getattr(ausencia.personal_salud.especialidad, 'nombre_especialidad', None),
            "fecha_inicio":ausencia.fecha_inicio,
            "fecha_final":ausencia.fecha_fin,
            "id_tipo": ausencia.tipo,
            "creado_por": ausencia.creado_por.username, 
            "modificado_por": ausencia.modificado_por.username, 
            "fecha_creado": ausencia.fecha_creado, 
            "fecha_modificado": ausencia.fecha_modificado,
            "estado": ausencia.estado,
            "ejecucion": ausencia.estado_temporal,
            "observaciones": ausencia.observaciones
        }, status=200)



def validarImpactoDiaLaboral(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({"error": "Error interno del servidor."}, status=500)
    

    try:
        dia_laboral = DiaLaboralValidator.validarArgumentosDiaLaboral(data)

    except ValueError as e:
        return JsonResponse({"error": "Error interno del servidor."}, status=500)
    
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    try:
        resultado, f_modificado= ConfiguracionDiaService.analizarImpactoEditarDiaLaboral(dia_laboral)

        
        if resultado:
            return JsonResponse({'conflictos': True, 'impactos':resultado, 'f_modificado':f_modificado}, status=200)
        else:
            return JsonResponse({'conflictos': False, 'impactos':None }, status=200)
        
    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'No se pudo procesar el periodo'}, status=500)



def editarDiaLaboral(request):
    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    
    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({"error": "Error interno del servidor."}, status=500)
    

    try:
        dia_laboral = DiaLaboralValidator.validarArgumentosDiaLaboral(data)

        

    except ValueError as e:
        return JsonResponse({"error": "Error interno del servidor."}, status=500)
    
    except ValidationError as e:
        return JsonResponse(
            {'error': e.messages[0]},
            status=400
        )

    try:
        resultado= ConfiguracionDiaService.editarDiaLaboral(dia_laboral, request.user)

        return JsonResponse(
                    {
                        "guarda": True,
                        "resultado": resultado
                    },
                    status=200
                )
    

    except ValidationError as e:
        return JsonResponse({'error': e.messages[0]}, status=400)
    except Exception as e:
        log_error(e, LogApp.AGENDA)

        return JsonResponse({'error': 'No se pudo procesar el periodo'}, status=500)



@require_http_methods(["DELETE"])
def eliminarDiaLaboral(request):

    if not verificar_permisos_usuario(request.user, AGENDA_MEDICA_EDITOR_ROLES, AGENDA_MEDICA_EDITOR_UNIDADES):
        return JsonResponse(
            {'error': 'No tienes permisos para realizar esta acción'},
            status=403
        )

    try:
        data = parse_json_request(request)

    except ValueError:
        return JsonResponse(
            {"error": "El cuerpo de la solicitud contiene un JSON inválido."},
            status=400
        )

    try:
        resultado = ConfiguracionDiaService.eliminarDiaLaboral(
            data,
            request.user
        )

        
        return JsonResponse({'success': True, 'resultado': resultado}, status=200)

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

    except Exception as e:

        log_error(
            f"[ConfiguracionDiaService]: eliminarDiaLaboral {e}",
            LogApp.AGENDA
        )

        return JsonResponse(
            {'error': 'No se pudo eliminar el día laboral.'},
            status=500
        )




class AgendaMedicaAPI(View):

    def dispatch(self, request, *args, **kwargs):
        usuario = request.user

        if not verificar_permisos_usuario(
            usuario,
            AGENDA_MEDICA_VISUALIZACION_ROLES,
            AGENDA_MEDICA_VISUALIZACION_UNIDADES
        ):
            return JsonResponse(
                {'error': 'No tienes permisos para realizar esta accion'},
                status=403
            )

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        try:
            criterios = AgendaMedicaValidator.validar_consulta(
                request.GET
            )

            datos = AgendaMedicaService.obtener_cupos(criterios)

            entries, dias_con_entries = AgendaMedicaService.transformar_cupos(datos)



            data = AusenciaService.obtener_ausencias(criterios)
            ausencias, dias_con_ausencias = AusenciaService.transformar_ausencias(data)

            entries = entries + ausencias
            dias_con_entries = sorted(
                set(dias_con_entries) | set(dias_con_ausencias)
            )


            return JsonResponse({
                "entries": entries,
                "workingDays": dias_con_entries,
            })

        except ValidationError as e:
            return JsonResponse(
                {'error': str(e)},
                status=400
            )
                