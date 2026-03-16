
from .models import Expediente, PacienteAsignacion
from core.services.expediente_service import ExpedienteService
from core.services.ingreso.ingreso_service import IngresoService
from core.services.paciente_service import PacienteService
from core.services.expediente_service import ExpedienteService
from core.utils.utilidades_textos import formatear_nombre_completo, formatear_ubicacion_completo
from core.utils.utilidades_fechas import formatear_fecha_simple, calcular_edad_texto
from core.mixins import UnidadRolRequiredMixin
from core.constants  import permisos
from expediente import forms 

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import  CreateView
from django.views.generic.detail import DetailView
from django.views.generic import TemplateView
from django.db.models import OuterRef, Subquery, When, Value, Case,Q
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.shortcuts import render


class ExpedienteAddView(UnidadRolRequiredMixin, CreateView):
    model=Expediente

    required_roles = ['admin']
    required_unidades = ['Admision']
    form_class = forms.ExpedienteCreateForm
    success_url = reverse_lazy('listar_expedientes')

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                print(self.request, f"{field.capitalize()}: {error}")
                messages.error(self.request, f"{field.capitalize()}: {error}")
        return super().form_invalid(form)

    def get_form(self, form_class = None):
        form = super(CreateView, self ).get_form()
        #form.fields['numero'].widget = forms.TextInput({'class':'formularioCampo-text', 'placeholder':'Numero'})
        form.fields['numero'].widget.attrs.update({'class': 'formularioCampo-text','placeholder':'Numero'})
        form.fields['localizacion'].widget.attrs.update({'class': 'formularioCampo-select'})
        form.fields['estado'].widget.attrs.update({'class': 'formularioCampo-select'})
        return form

class ExpedienteDetailView(DetailView):
    model=Expediente

#Funcion que sirve la api para Frontend del expedietne libre econtrado
def traer_expediente_libre(request):
    usuario_id = request.user.id
    expediente = ExpedienteService.obtener_expediente_libre(usuario_id)

    if expediente:
        data = {
        "expediente_numero": expediente.numero if expediente.numero else None,
        "localizacion": expediente.localizacion.descripcion_localizacion if expediente.localizacion and expediente.localizacion else "Desconocida",
        "estado": expediente.estado if expediente.estado else "Desconocido"
        }
    return JsonResponse(data)

# Este API retorna datos de pacientes aptos para ingresos por número de expediente.
def obtenerPacienteIngresoExpediente(request):
    numero = request.GET.get('numero')

    if not numero:
        return JsonResponse({"error": "El parámetro 'numero' es requerido."}, status=400)

    # Buscar paciente con expediente activo por medio del número
    pacienteA = ExpedienteService.obtener_paciente_propietario(numero)

    if not pacienteA:
        return JsonResponse({"mensaje": "No se encontró un paciente habilitado con este número de expediente."}, status=200)

    # Verificar si el paciente ya tiene un ingreso activo
    if IngresoService.tiene_ingreso_activo(pacienteA.paciente.id):
        return JsonResponse({"mensaje": "El paciente ya cuenta con un ingreso activo."}, status=200)

    # Verificar si el paciente está registrado como fallecido
    if PacienteService.comprobar_defuncion(pacienteA.paciente):
        return JsonResponse({"mensaje": "El paciente está registrado como fallecido y no puede ser ingresado."}, status=200)

    # Respuesta con los datos del paciente apto
    return JsonResponse({
        "id": pacienteA.paciente.id,
        "dni": pacienteA.paciente.dni,
        "numeroExp": pacienteA.expediente.numero,
        "nombreCompleto": formatear_nombre_completo(
            pacienteA.paciente.primer_nombre,
            pacienteA.paciente.segundo_nombre,
            pacienteA.paciente.primer_apellido,
            pacienteA.paciente.segundo_apellido
        ),
        "fechaNacimiento": formatear_fecha_simple(pacienteA.paciente.fecha_nacimiento),
        "edad": calcular_edad_texto(str(pacienteA.paciente.fecha_nacimiento)),
        "sexo": pacienteA.paciente.get_sexo_display(),
        "telefono": pacienteA.paciente.telefono,
        "direccion": formatear_ubicacion_completo(
            pacienteA.paciente.sector.aldea.municipio.departamento.nombre_departamento,
            pacienteA.paciente.sector.aldea.municipio.nombre_municipio,
            pacienteA.paciente.sector.nombre_sector
        ),
        "extrajero": pacienteA.paciente.get_extranjeroPasaporte()
    })


# Este API retorna datos de pacientes aptos para regsitro por número de expediente.
def obtenerPacienteRegistroExpediente(request):
    numero = request.GET.get('numero')

    if not numero:
        return JsonResponse({"error": "El parámetro 'numero' es requerido."}, status=400)

    # Buscar paciente con expediente activo por medio del número
    pacienteA = ExpedienteService.obtener_paciente_propietario(numero)

    if not pacienteA:
        return JsonResponse({"mensaje": "No se encontró un paciente habilitado con este número de expediente."}, status=200)

    # Verificar si el paciente está registrado como fallecido
    if PacienteService.comprobar_defuncion(pacienteA.paciente):
        return JsonResponse({"mensaje": "El paciente está registrado como fallecido y no puede ser ingresado."}, status=200)

    # Respuesta con los datos del paciente apto
    return JsonResponse({
        "id": pacienteA.paciente.id,
        "dni": pacienteA.paciente.dni,
        "numeroExp": pacienteA.expediente.numero,
        "nombreCompleto": formatear_nombre_completo(
            pacienteA.paciente.primer_nombre,
            pacienteA.paciente.segundo_nombre,
            pacienteA.paciente.primer_apellido,
            pacienteA.paciente.segundo_apellido
        ),
        "fechaNacimiento": formatear_fecha_simple(pacienteA.paciente.fecha_nacimiento),
        "edad": calcular_edad_texto(str(pacienteA.paciente.fecha_nacimiento)),
        "sexo": pacienteA.paciente.get_sexo_display(),
        "telefono": pacienteA.paciente.telefono,
        "direccion": formatear_ubicacion_completo(
            pacienteA.paciente.sector.aldea.municipio.departamento.nombre_departamento,
            pacienteA.paciente.sector.aldea.municipio.nombre_municipio,
            pacienteA.paciente.sector.nombre_sector
        ),
        "extrajero": pacienteA.paciente.get_extranjeroPasaporte()
    })


def listarExpedientesAPI(request):
    # Obtén parámetros de paginación y búsqueda de la solicitud
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))  # Índice de inicio
    length = int(request.GET.get('length', 20))  # Número de registros a devolver
    search_value = request.GET.get('search[value]', '').strip()  # Valor de búsqueda
    order_column = int(request.GET.get('order[0][column]', 7))  # Índice de columna para ordenar
    order_direction = request.GET.get('order[0][dir]', 'desc')  # Dirección de orden
    search_column = request.GET.get('search_column')
    
    
    # Subconsulta para obtener el estado del paciente asignado
    estado_subquery = PacienteAsignacion.objects.filter(
        expediente=OuterRef('id')
    ).order_by('-id').values('estado')[:1]


    # Subconsulta para obtener el DNI del paciente asignado
    dni_subquery = PacienteAsignacion.objects.filter(
        expediente=OuterRef('id')
    ).order_by('-id').annotate(
        dni=Case(
            When(estado=0, then=Value("No asignado")),  # Si estado=2, mostrar "No asignado"
            default='paciente__dni'
        )
    ).values('dni')[:1]


    # Subconsulta para obtener los nombres (primer y segundo nombre)
    nombres_subquery = PacienteAsignacion.objects.filter(
        expediente=OuterRef('id')
    ).order_by('-id').annotate(
        nombres=Case(
            When(estado=0, then=Value("No asignado")),
            default=Concat('paciente__primer_nombre', Value(' '), 'paciente__segundo_nombre')
        )
    ).values('nombres')[:1]

    # Subconsulta para obtener los apellidos (primer y segundo apellido)
    apellidos_subquery = PacienteAsignacion.objects.filter(
        expediente=OuterRef('id')
    ).order_by('-id').annotate(
        apellidos= Case(
            When(estado=0, then=Value("No asignado")),
        default=Concat('paciente__primer_apellido', Value(' '), 'paciente__segundo_apellido')
        )
    ).values('apellidos')[:1]

    # Consulta principal con subconsultas
    expediente_qs = Expediente.objects.annotate(
        asignacion_estado=Subquery(estado_subquery),
        propietario_dni=Subquery(dni_subquery),
        propietario_nombres=Subquery(nombres_subquery),
        propietario_apellidos=Subquery(apellidos_subquery)
    ).values(
        "numero",
        "localizacion__descripcion_localizacion",
        "estado",
        "modificado_por__username",
        "fecha_modificado",
        "asignacion_estado",
        "propietario_dni",
        "propietario_nombres",
        "propietario_apellidos",
        "id"
    )


    if search_column and search_value:
        # Búsqueda específica por columna con filtros aplicados de inmediato
        if search_column == '0':  # Expediente
            try:
                numero = int(search_value.lstrip("0"))  # Elimina ceros a la izquierda
                expediente_qs = expediente_qs.filter(numero=numero)
            except ValueError:
                expediente_qs = expediente_qs.none()
        elif search_column == '1':  # DNI
            dni_limpio = search_value.replace("-", "").strip()
            expediente_qs = expediente_qs.filter(propietario_dni__iexact=dni_limpio)
        elif search_column == '2':  # DNI
            expediente_qs = expediente_qs.filter(propietario_nombres__icontains=search_value)
        elif search_column == '3':  # DNI
            expediente_qs = expediente_qs.filter(propietario_apellidos__icontains=search_value)


    # Mapear las columnas en el mismo orden que aparecen en el DataTable
    columns = [
        "numero",#0
        "localizacion__descripcion_localizacion",#1
        "estado",#2
        "propietario_dni",#3
        "propietario_nombres",#4
        "propietario_apellidos",#5 
        "asignacion_estado",#6
        "fecha_modificado",#7
    ]


    # Aplica el ordenamiento antes de la paginación menos a la ultima fila pues son los botones
    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            expediente_qs = expediente_qs.order_by(order_column_name)
        else:
            expediente_qs = expediente_qs.order_by('-' + order_column_name)

    # Contar registros totales y filtrados
    total_records = Expediente.objects.count()
    filtered_records = expediente_qs.count()

    # Aplica paginación
    expedientes = list(expediente_qs[start:start + length])

    # Crea la respuesta JSON que DataTables espera
    data = {
        "draw": draw,  # Se devuelve el mismo draw recibido
        "recordsTotal": total_records,  # Total de registros sin filtrar
        "recordsFiltered": filtered_records,  # Total de registros filtrados
        "data": expedientes  # Lista de los pacientes para mostrar en la página actual
    }

    return JsonResponse(data)


def listarPropietariosExpedienteAPI(request):
    id_expediente = request.GET.get('id_expediente')

    if not id_expediente:
        return JsonResponse({
            "data": []
        })

    queryset = PacienteAsignacion.objects.annotate(
        nombre_completo=Concat(
            "paciente__primer_nombre", Value(" "), 
            "paciente__segundo_nombre", Value(" "), 
            "paciente__primer_apellido", Value(" "), 
            "paciente__segundo_apellido"
        )
    ).filter(expediente__id=id_expediente).values(
        "id",
        "estado",
        "fecha_asignacion",
        "fecha_liberacion",
        "expediente__numero",
        "paciente__id",
        "paciente__dni",
        "nombre_completo",
    )

    return JsonResponse({"data": list(queryset)})


class listarExpedientes(UnidadRolRequiredMixin,TemplateView):
    template_name = 'expediente/expediente_list.html'
    required_roles = permisos.EXPEDIENTE_VISUALIZACION_ROLES
    required_unidades = permisos.EXPEDIENTE_VISUALIZACION_UNIDADES
