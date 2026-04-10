from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from django.views.generic.edit import UpdateView, CreateView
from django.views.generic import DetailView
from django.views.decorators.http import require_GET
from core.services.externals import obtener_dispensacion_mysql
from django.core.exceptions import ValidationError
from .models import Paciente, Padre
from ingreso.models import Acompanante
from .forms import PacienteCreateForm, PacienteEditForm
from core.validators.paciente import buscar_duplicidad_paciente 
from core.services.paciente_service import PacienteService
from core.services.padre_service import PadreService
from core.services.expediente_service import ExpedienteService
from core.services.ubicacion_service import UbicacionService
from core.services.ingreso.ingreso_service import IngresoService
from core.services.imagenologia_service import EvaluacionService 
from core.services.servicio_service import ServicioService
from core.services.usuario_service import UsuarioService
from core.services.server_image.media_service import MediaService
from usuario.permisos import verificar_permisos_usuario, verificar_permisos_dispensacion
from core.utils.utilidades_fechas import formatear_fecha, formatear_fecha_simple, calcular_edad_texto
from core.utils.utilidades_textos import generar_slug,formatear_nombre_completo, formatear_ubicacion_completo, formatear_expediente, formatear_dni
from core.utils.utilidades_request import parse_json_request
from core.validators.main_validator import validar_entero_positivo
from core.validators.fecha_validator import validar_fecha
# permisos
from core.constants.permisos import (
    PACIENTE_EDITOR_ROLES,
    PACIENTE_EDITOR_UNIDADES,
    PACIENTE_VISUALIZACION_ROLES,
    PACIENTE_VISUALIZACION_UNIDADES,
    PACIENTE_DISPENSACION_ROLES,
    PACIENTE_DISPENSACION_UNIDADES,
)
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


from usuario.models import PerfilUnidad
from dal import autocomplete
from types import SimpleNamespace

import json
from pprint import pprint
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db import connections, transaction
from django.http.response import JsonResponse
from django import forms
from datetime import datetime
from django.db.utils import OperationalError
from django.db.models import Q, F, Value, OuterRef, Subquery, CharField,Case, When, BooleanField
from django.db.models.functions import Coalesce, Concat
from django.shortcuts import get_object_or_404, redirect
#from expediente.c import comprobar_libre
#asignar_expediente_paciente



# Create your views here.
class PacienteAddView(UnidadRolRequiredMixin, CreateView):
    model=Paciente
    required_roles = PACIENTE_EDITOR_ROLES
    required_unidades = PACIENTE_EDITOR_UNIDADES
    form_class = PacienteCreateForm
    success_url = reverse_lazy('listar_pacientes') 

    #si el registro validado pero antes de guardar
    def form_valid(self, form):
        cleaned_data = form.cleaned_data

        zona_codigo = self.request.session.get("zona_codigo")
        usuario_id = self.request.user.id
        paciente = form.instance
        #orden_gemelar = self.request.POST.get("orden_gemelar")
        try:
            id_externo = int(self.request.POST.get("idExterno", 0))
        except ValueError:
            id_externo = None

        if zona_codigo:
            form.instance.zona_id = zona_codigo
        if usuario_id:
            form.instance.creado_por_id = usuario_id
            form.instance.modificado_por_id = usuario_id

        datos_madre = self.extraer_datos_padre(cleaned_data, "madre")
        datos_padre = self.extraer_datos_padre(cleaned_data, "padre")

        try:
            with transaction.atomic():

                madre = PadreService.procesar_padre_o_madre(**datos_madre)
                padre = PadreService.procesar_padre_o_madre(**datos_padre)

                if paciente.tipo in [3, 4] and not madre:
                    return JsonResponse({
                        "success": False,
                        "errors": {
                            "madre": ["Debe registrar la madre para este paciente."]
                        }
                    }, status=400)

                paciente.madre = madre
                paciente.padre = padre
                response = super().form_valid(form)

                self.liberar_si_es_paciente(self.object)
                
                paciente_interno_id = self.object.id

                # Diccionario de mensajes
                messages = {
                    "paciente": "Paciente registrado correctamente"
                }
                if id_externo:
                    # Lógica para convertir el paciente externo
                    EvaluacionService.cambiar_referencia_evaluacion_externo_interno(
                        paciente_interno_id,
                        id_externo
                    )

                    imagenes_migradas = MediaService.cambiar_imagenes_referencia(
                        paciente_interno_id=paciente_interno_id,
                        paciente_externo_id=id_externo
                    )

                    EvaluacionService.inactivar_paciente_externo(id_externo) 

                    messages["externo"] = (
                        f"Paciente externo convertido correctamente "
                        f"({imagenes_migradas} imágenes migradas)."
                    )      
                
                
                expediente_numero = self.request.POST.get("expediente_numero", "").strip()
                if expediente_numero:
                    expediente = ExpedienteService.comprobar_y_asignar(expediente_numero, paciente.id, usuario_id)
                    if expediente:
                        messages["expediente"] = f"Expediente numero {expediente.numero} asignado correctamente al paciente."
                        # Actualizar el campo expediente_numero en el paciente
                        paciente.expediente_numero = expediente.numero
                        paciente.save(update_fields=["expediente_numero"])
                    else:
                        messages["expediente"] = "No se pudo asignar el expediente al paciente."
                
                return JsonResponse({
                    "success": True,
                    "messages": messages,
                    "redirect_url": reverse_lazy('listar_pacientes')
                })

        except Exception as e:
            return JsonResponse({
                "success": False,
                "errors": {
                    "non_field_errors": [f"Hubo un error al registrar el paciente: {str(e)}"]
                }
            }, status=400)
            
        
    def extraer_datos_padre(self, cleaned_data, tipo):
        """Extrae datos del formulario segÃºn el tipo (madre/padre)."""
        return {
        "id": cleaned_data.get(f"{tipo}Id", None),
        "dni": cleaned_data.get(f"{tipo}Dni", None),
        "nombre1": cleaned_data.get(f"{tipo}Nombre1", "").strip(),
        "nombre2": cleaned_data.get(f"{tipo}Nombre2", "").strip(),
        "apellido1": cleaned_data.get(f"{tipo}Apellido1", "").strip(),
        "apellido2": cleaned_data.get(f"{tipo}Apellido2", "").strip(),
        "direccion": cleaned_data.get(f"domicilio_{tipo}", "").strip(),
        "tipo": "02" if tipo == "madre" else "01",
    }

    def liberar_si_es_paciente(self, paciente):
        """Si el padre/madre es paciente, limpia sus datos en la tabla Padre."""
        for tipo, dni in [("madre", paciente.dni), ("padre", paciente.dni)]:
            if dni:
                try:
                    padre_obj = Padre.objects.get(dni=dni)
                    PadreService.liberar_campos_padre(paciente,padre_obj)
                except Padre.DoesNotExist:
                    pass  # Si no existe, no hacer nada

    def form_invalid(self, form):
        # form.errors es un dict {campo: [errores]}
        return JsonResponse({
            'success': False,
            'errors': form.errors  # esto serÃ¡ un dict JSON serializable
        }, status=400)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Agregar Paciente'
        context['subtitulo'] = 'Agregando'
        context['MD'] = 1
        context['readonly_mode'] = 0
        return context


# vista para editar
class PacienteEditView(UpdateView):
    model = Paciente
    form_class = PacienteEditForm
    success_url = reverse_lazy('listar_pacientes') 



    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        #kwargs['user'] = self.request.user  # Pasar el usuario actual
        return kwargs

    def form_valid(self, form):
        cleaned_data = form.cleaned_data
        paciente = form.instance
        usuario = self.request.user
        try:
            id_externo = int(self.request.POST.get("idExterno", 0))
        except ValueError:
            id_externo = None



        if not verificar_permisos_usuario(
            usuario,
            PACIENTE_EDITOR_ROLES,
            PACIENTE_EDITOR_UNIDADES):
            return JsonResponse({"success": False, "error": f"No tiene permiso para editar el paciente"})



        if usuario:
            form.instance.modificado_por_id = usuario.id

        madre_data = self.extraer_datos_padre(cleaned_data, "madre")
        padre_data = self.extraer_datos_padre(cleaned_data, "padre")
    
        expedienteNumero = self.request.POST.get("expediente_numero", "").strip()
        estado = self.request.POST.get("estado", "").strip()


        messages_dict = {}

        try:
            with transaction.atomic():
                # Procesar madre
                if any([madre_data.get("id"), madre_data.get("dni"), madre_data.get("nombre1")]):
                    madre = PadreService.procesar_padre_o_madre(**madre_data)
                    if madre:
                        paciente.madre = madre
                else:
                    if paciente.madre:
                        madre = paciente.madre
                        paciente.madre = None
                        if not Paciente.objects.filter(madre=madre).exclude(id=paciente.id).exists():
                            madre.delete()

                # Procesar padre
                if any([padre_data.get("id"), padre_data.get("dni"), padre_data.get("nombre1")]):
                    padre = PadreService.procesar_padre_o_madre(**padre_data)
                    if padre:
                        paciente.padre = padre
                else:
                    if paciente.padre:
                        padre = paciente.padre
                        paciente.padre = None
                        if not Paciente.objects.filter(padre=padre).exclude(id=paciente.id).exists():
                            padre.delete()

                # Procesar expediente
                if not expedienteNumero and estado == "I":
                    expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
                    if expediente:
                        pacienteAsignacion = ExpedienteService.obtener_paciente_asignacion(expediente.id)
                        if pacienteAsignacion:
                            pacienteAsignacion.estado = "0"
                            pacienteAsignacion.fecha_liberacion = datetime.now()
                            pacienteAsignacion.save()
                        expediente.estado = 2
                        expediente.save()

                        # Quitar nÃºmero de expediente del paciente
                        paciente.expediente_numero = None

                        messages_dict["expediente"] = f"Expediente {'sin numero' if not expediente.numero else expediente.numero} liberado correctamente."
                elif expedienteNumero:
                    if not ExpedienteService.comprobar_propietario(expedienteNumero, paciente.id):
                        expediente = ExpedienteService.comprobar_y_asignar(expedienteNumero, paciente.id, usuario.id)
                        if expediente:
                            # Asignar nÃºmero de expediente al paciente
                            paciente.expediente_numero = expediente.numero
                            messages_dict["expediente"] = f"Expediente nÃºmero {expediente.numero} asignado correctamente al paciente."
                        else:
                            messages_dict["expediente"] = "No se pudo asignar el expediente al paciente."

                # Guardar el paciente
                response = super().form_valid(form)

                # Mensaje de Exito
                messages_dict["paciente"] = f"Paciente {paciente.primer_nombre} {paciente.primer_apellido} editado correctamente."
                
                if id_externo:
                    # Lógica para convertir el paciente externo
                    inactivo =EvaluacionService.inactivar_paciente_externo(id_externo)
                    if inactivo:
                        cambio_referencia = EvaluacionService.cambiar_referencia_evaluacion_externo_interno(paciente.id,id_externo)
                        if cambio_referencia:
                            messages_dict["externo"] = "Se redefinio correctamente el paciente externo"


                

                return JsonResponse({
                    "success": True,
                    "messages": messages_dict,
                    "redirect_url": reverse_lazy('listar_pacientes')
                })

        except Exception as e:
            return JsonResponse({
            "success": False,
            "errors": {
            "non_field_errors": [f"Error en la actualizacion del paciente: {str(e)}"]
            }
        }, status=400)


    def form_invalid(self, form):
        # form.errors es un dict {campo: [errores]}
        return JsonResponse({
            'success': False,
            'errors': form.errors  # esto serÃ¡ un dict JSON serializable
        }, status=400)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Paciente'
        context['subtitulo'] = 'Editando'
        context['MD'] = 2

        # datos del registro
        paciente = self.object  # paciente actual usando self.object
        # Crear el diccionario con los datos 
        info_registro = {
            'creado_por':paciente.creado_por,
            'modificado_por':paciente.modificado_por,
            'fecha_creado': formatear_fecha(str(paciente.fecha_creado)),
            'fecha_modificado': formatear_fecha(str(paciente.fecha_modificado)),
        }
        context['info_registro'] = info_registro

        #datos del expediente 
        expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
        if expediente:
            info_expediente = {
                'numero': expediente.numero,
                'estado': expediente.estado,  # AsegÃºrate de que 'estado' sea en minÃºsculas
                'ubicacion': expediente.localizacion.descripcion_localizacion  # AsegÃºrate de que 'ubicacion' estÃ© en minÃºsculas
            }
            context['info_expediente'] = json.dumps(info_expediente)



        #datos de la ubicacionb completa
        ubicacion = UbicacionService.obtener_detalles_domicilio(paciente.sector_id) 
        context['info_ubicacion'] = json.dumps(ubicacion)

        #padres
        def obtener_info_padre(padre_id):
            return PadreService.obtener_detalles_padre(padre_id) if padre_id else None

        context['info_madre'] = json.dumps(obtener_info_padre(paciente.madre_id))
        context['info_padre'] = json.dumps(obtener_info_padre(paciente.padre_id))      

        #defuncion
        context['defuncion'] = PacienteService.comprobar_defuncion(paciente)
        context['apto_obito'] = PacienteService.esMujerEdadFertil(paciente)
        #permisos 

        
        #validamos los grupos requeridos con los del usuairo y mandamos un true o false, atravez del diccionario de contexto
        permiso =  not verificar_permisos_usuario(self.request.user,  ['admin', 'digitador'], ['Admision'])
        context['readonly_mode'] = 1 if permiso else 0

        #enlace construido desde elbckend historialpaciente
        context['url_historial'] = reverse('historial_paciente', kwargs={
        'pk': paciente.pk,
        'slug': generar_slug(paciente.primer_nombre+" "+paciente.primer_apellido)
        })
        #enlace construido desde elbckend historialpaciente
        context['url_ingreso'] = reverse('ingreso_agregar', kwargs={
        'pk': paciente.pk,
        'slug': generar_slug(paciente.primer_nombre+" "+paciente.primer_apellido)    })
        
        return context



    def extraer_datos_padre(self, cleaned_data, tipo):
        return {
            "id": cleaned_data.get(f"{tipo}Id", None),
            "dni": cleaned_data.get(f"{tipo}Dni", None),
            "nombre1": cleaned_data.get(f"{tipo}Nombre1", "").strip(),
            "nombre2": cleaned_data.get(f"{tipo}Nombre2", "").strip(),
            "apellido1": cleaned_data.get(f"{tipo}Apellido1", "").strip(),
            "apellido2": cleaned_data.get(f"{tipo}Apellido2", "").strip(),
            "direccion": cleaned_data.get(f"domicilio_{tipo}", "").strip(),
            "tipo": "02" if tipo == "madre" else "01",
        }


#vista que lista los pcientes # disponibles a todos lo suaurios y unidades
def listarPacientes(request):
    usuario = request.user

    # Si es superusuario, darle acceso completo
    if usuario.is_superuser:
        context = {
            "botones": ["todos"]
        }
        return render(request, 'paciente/paciente_list.html', context)
    
    permisos_por_unidad = {
        1: ["crear_paciente", "editar_paciente", "crear_ingreso", "crear_atencion"],  # Admisión
        2: ["crear_evaluacionrx"],  # Imagenología
        4: ["editar_paciente"], # directivos
        6: ["crear_referencia"]  # Imagenología

    }

    perfiles = PerfilUnidad.objects.filter(usuario=usuario).values_list('servicio_unidad_id', flat=True)

    botones = []
    for unidad_id in perfiles:
        permisos = permisos_por_unidad.get(unidad_id, [])
        for p in permisos:
            if p not in botones:  # Evita duplicados y preserva orden
                botones.append(p)

    context = {
        "botones": json.dumps(botones)  # Se manda ya en el orden original
    }
        
    return render(request, 'paciente/paciente_list.html', context)


# Retorna el JSON que alimenta el DataTables de Pacientes
def listarPacientesAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()
    order_column = int(request.GET.get('order[0][column]', 9))
    order_direction = request.GET.get('order[0][dir]', 'desc')
    search_column = request.GET.get('search_column')
    activos_inactivos = request.GET.get('activos_inactivos', "0")
    defunciones = request.GET.get('defunciones', "0")
    sai = request.GET.get('sai', "0")
    adolescente = request.GET.get('adolecente', "0")

    # Caso especial: bÃºsqueda por nombre completo
    if search_value and search_column == '2':
        pacientes_qs = Paciente.objects.annotate(   
        nombre_completo=Concat(
            F("primer_nombre"),
            Case(
                When(
                    ~Q(segundo_nombre='') & ~Q(segundo_nombre__isnull=True),
                    then=Concat(Value(" "), F("segundo_nombre"))
                ),
                default=Value(""),
                output_field=CharField(),
            ),
            Case(
                When(
                    ~Q(primer_apellido='') & ~Q(primer_apellido__isnull=True),
                    then=Concat(Value(" "), F("primer_apellido"))
                ),
                default=Value(""),
                output_field=CharField(),
            ),
            Case(
                When(
                    ~Q(segundo_apellido='') & ~Q(segundo_apellido__isnull=True),
                    then=Concat(Value(" "), F("segundo_apellido"))
                ),
                default=Value(""),
                output_field=CharField(),
            ),
            output_field=CharField(),
            )
        ).filter(nombre_completo__icontains=search_value)
    else:
        pacientes_qs = Paciente.objects.all()

    # Aplicar filtros por estado
    if activos_inactivos == "1":
        pacientes_qs = pacientes_qs.filter(estado="I")
    elif defunciones == "1":
        pacientes_qs = pacientes_qs.filter(defuncion__isnull=False)
    elif sai == "1":
        pacientes_qs = pacientes_qs.filter(sai=True)
    elif adolescente == "1":
        pacientes_qs = pacientes_qs.filter(adolescente=True)
    else:
        pacientes_qs = pacientes_qs.exclude(estado="I").filter(
            defuncion__isnull=True,
        )

    # Filtro por columna especÃ­fica (excepto nombre completo ya manejado)
    if search_column and search_value:
        if search_column == '0':
            try:
                numero = int(search_value.lstrip("0"))  # Elimina ceros a la izquierda
                pacientes_qs = pacientes_qs.filter(expediente_numero__iexact=numero)
            except ValueError:
                pacientes_qs = pacientes_qs.none()
        elif search_column == '1':
            dni_limpio = search_value.replace("-", "").strip()
            pacientes_qs = pacientes_qs.filter(dni__icontains=dni_limpio)

    # Columnas para ordenamiento (sin nacionalidad)
    columns = [
        "expediente_numero",                                # 0
        "dni",                                              # 1
        "tipo_id",                                          # 2
        "primer_nombre",                                    # 3
        "primer_apellido",                                  # 4
        "fecha_nacimiento",                                 # 5
        "sexo",                                             # 6
        "sector__aldea__municipio__nombre_municipio",      # 7
        "clasificacion_id",        # 8
        "fecha_modificado",                                 # 9
    ]

    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            pacientes_qs = pacientes_qs.order_by(order_column_name)
        else:
            pacientes_qs = pacientes_qs.order_by('-' + order_column_name)

    filtered_records = pacientes_qs.count()

    pacientes_qs = pacientes_qs.select_related(
        "sector__aldea__municipio", "modificado_por"
    )

    pacientes = list(pacientes_qs[start:start+length].values(
        "expediente_numero",
        "tipo_id",
        "id",
        "dni",
        "primer_nombre",
        "segundo_nombre",
        "primer_apellido",
        "segundo_apellido",
        "fecha_nacimiento",
        "sexo",
        "sector__aldea__municipio__nombre_municipio",
        "sector__nombre_sector",
        "clasificacion_id",
        "fecha_modificado",
        "modificado_por__username"
    ))

    data = {
        "draw": draw,
        "recordsTotal": 0,  # como pediste, sin cÃ¡lculo para rendimiento
        "recordsFiltered": filtered_records,
        "data": pacientes
    }
    return JsonResponse(data)


#encontrar paciente en el censo, al mismo tiempo notificar si ya esta ligado un paicente a esa identidad
def obtener_paciente_censo(request):
    dni = request.GET.get('parametro')
    respuesta = PacienteService.obtener_paciente_censo(dni)
    return JsonResponse(respuesta, status=200 if "data" in respuesta else 400)


#enrega un json con la data de un paciente segun si dni o numero de expediente siempre y cuando este actrivo 
def obtener_paciente_activo(request):
    dni = request.GET.get('DNI')

    if not dni:
        return JsonResponse({"error": "El parametro 'DNI' es requerido."}, status=400)

    # Buscar paciente con expediente activo por medio del DNI
    pacienteA = PacienteService.obtener_paciente_propietario(dni)

    if not pacienteA:
        return JsonResponse({"mensaje": "No se encontro un paciente habilitado con este numero."}, status=200)

    # Verificar si el paciente ya tiene un ingreso activo
    if IngresoService.tiene_ingreso_activo(pacienteA.paciente.id):
        return JsonResponse({"mensaje": "El paciente ya cuenta con un ingreso activo."}, status=200)

    # Verificar si el paciente estÃ¡ registrado como fallecido
    if PacienteService.comprobar_defuncion(pacienteA.paciente):
        return JsonResponse({"mensaje": "El paciente esta registrado como fallecido y no puede ser ingresado."}, status=200)

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
        )
    })



#tratar de asistir, encontrando un padre existente
# , o su nombre en su defecto del censo
def obtener_padre(request):
    dni = request.GET.get('dni', None)
    rol = request.GET.get('rol', None)

    if not dni or not rol:
        return JsonResponse({'error': "Se requiere un parametro 'dni' y 'rol'."}, status=400)
    response = PadreService.obtener_padre_por_dni(dni, rol)
    return JsonResponse(response)


def busqueda_censo(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    order_column = int(request.GET.get('order[0][column]', 1))
    order_direction = request.GET.get('order[0][dir]', 'desc')

    params = {
        'search_sexo': request.GET.get('search_sexo'),
        'search_nombre1': request.GET.get('search_nombre1'),
        'search_nombre2': request.GET.get('search_nombre2'),
        'search_apellido1': request.GET.get('search_apellido1'),
        'search_apellido2': request.GET.get('search_apellido2'),
    }

    # Validaciones antes de llamar al servicio
    if len(params) == 0:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
        })

    elif len([v for v in params.values() if v]) < 3:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'Myerror': "Se requieren al menos tres criterios de buqueda."
        })

    datos, total_filtered = PacienteService.listar_personas_censo(params, start, length, order_column, order_direction)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': 6082107,  # Numero total de registros fijos o consulta real
        'recordsFiltered': total_filtered,
        'data': datos
    })    


class PacienteAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        query = self.q
        qs = PacienteService.obtener_pacientes(query)
        return qs
    
    def get_result_label(self, result):
        return f"{result.nombre_completo} {result.dni}"


# Este API retorna datos de pacientes aptos para ingresos o cita mÃ©dica.
def obtenerPacienteIngresoDNI(request):
    dni = request.GET.get('DNI')

    if not dni:
        return JsonResponse({"error": "El parÃ¡metro 'DNI' es requerido."}, status=400)

    # Buscar paciente con expediente activo por medio del DNI
    pacienteA = PacienteService.obtener_paciente_propietario(dni)

    if not pacienteA:
        return JsonResponse({"mensaje": "No se encontro un paciente habilitado con este numero."}, status=200)

    # Verificar si el paciente ya tiene un ingreso activo
    if IngresoService.tiene_ingreso_activo(pacienteA.paciente.id):
        return JsonResponse({"mensaje": "El paciente ya cuenta con un ingreso activo."}, status=200)

    # Verificar si el paciente estÃ¡ registrado como fallecido
    if PacienteService.comprobar_defuncion(pacienteA.paciente):
        return JsonResponse({"mensaje": "El paciente esta registrado como fallecido y no puede ser ingresado."}, status=200)

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
        )
    })


# Este API retorna datos de pacientes aptos para evalucion rx
def obtenerPacienteRegistroDNI(request):
    dni = request.GET.get('DNI')

    if not dni:
        return JsonResponse({"error": "El parametro 'DNI' es requerido."}, status=400)

    # Buscar paciente con expediente activo por medio del DNI
    pacienteA = PacienteService.obtener_paciente_propietario(dni)

    if not pacienteA:
        return JsonResponse({"mensaje": "No se encontro un paciente habilitado con este numero."}, status=200)

    # Verificar si el paciente estÃ¡ registrado como fallecido
    if PacienteService.comprobar_defuncion(pacienteA.paciente):
        return JsonResponse({"mensaje": "El paciente esta registrado como fallecido y no puede ser evaluado."}, status=200)

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


def busquedaPacientesAPI(request): # sirve al modala de busqueda
    # ObtÃ©n parÃ¡metros de paginaciÃ³n y bÃºsqueda de la solicitud
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))  # Ãndice de inicio
    length = int(request.GET.get('length', 10))  # NÃºmero de registros a devolver
    search_value = request.GET.get('search[value]', '').strip()  # Valor de bÃºsqueda
    order_column = int(request.GET.get('order[0][column]', 9))  # Ãndice de columna para ordenar
    order_direction = request.GET.get('order[0][dir]', 'desc')  # DirecciÃ³n de orden
    search_column = request.GET.get('search_column')
    
    pacientes_qs = Paciente.objects.annotate(
    es_extranjero_pasaporte=Case(
        When(~Q(nacionalidad_id=1), then=Value(True)),
        When(Q(nacionalidad_id=1) & Q(tipo_id=2), then=Value(True)),
        default=Value(False),
        output_field=BooleanField()
        )
    )

    if search_value and search_column == '2':
        pacientes_qs = pacientes_qs.annotate(
            nombre_completo=Concat(
                F("primer_nombre"),
                Case(
                    When(segundo_nombre__isnull=False, then=Concat(Value(" "), F("segundo_nombre"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                Value(" "),
                F("primer_apellido"),
                Case(
                    When(segundo_apellido__isnull=False, then=Concat(Value(" "), F("segundo_apellido"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                output_field=CharField()
            )
        ).filter(nombre_completo__icontains=search_value)
    
    pacientes_qs = pacientes_qs.exclude(Q(estado="I") | Q(defuncion__isnull=False))

    if search_column and search_value:
        if search_column == '0':
            try:
                numero = int(search_value.lstrip("0"))  # Elimina ceros a la izquierda
                pacientes_qs = pacientes_qs.filter(expediente_numero__iexact=numero)
            except ValueError:
                pacientes_qs = pacientes_qs.none()
        elif search_column == '1':
            dni_limpio = search_value.replace("-", "").strip()
            pacientes_qs = pacientes_qs.filter(dni__iexact=dni_limpio)

        # Columnas para ordenamiento 
    columns = [
        "expediente_numero",                                # 0
        "dni",                                              # 1
        "tipo_id",                                          # 2
        "primer_nombre",                                    # 3
        "primer_apellido",                                  # 4
        "sexo",                                             # 5
        "fecha_nacimiento",                                 # 6
        "telefono",                                         # 7
        "sector__aldea__municipio__nombre_municipio",       # 8
        "fecha_modificado"                                  # 9
    ]


    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            pacientes_qs = pacientes_qs.order_by(order_column_name)
        else:
            pacientes_qs = pacientes_qs.order_by('-' + order_column_name)


    filtered_records = pacientes_qs.count()


    pacientes_qs = pacientes_qs.select_related(
        "sector__aldea__municipio", "modificado_por"
    )

    pacientes = list(pacientes_qs[start:start+length].values(
        "expediente_numero",
        "dni",
        "tipo_id",
        "primer_nombre",
        "segundo_nombre",
        "primer_apellido",
        "segundo_apellido",
        "fecha_nacimiento",
        "sexo",
        "sector__aldea__municipio__nombre_municipio",
        "sector__nombre_sector",
        "telefono",
        "id",
    ))

    
    # Crea la respuesta JSON que DataTables espera
    data = {
        "draw": draw,
        "recordsTotal": 0,  # sin calculo para evitar sobre cargar
        "recordsFiltered": filtered_records,
        "data": pacientes
    }


    return JsonResponse(data)


def busquedaAvanzada(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    order_column = int(request.GET.get('order[0][column]', "1"))
    order_direction = request.GET.get('order[0][dir]', 'desc')

    search_base = int(request.GET.get('search_base', 0))
    search_sexo = request.GET.get('search_sexo', "H")
    search_nombre1 = request.GET.get('search_nombre1', '').strip()
    search_nombre2 = request.GET.get('search_nombre2', '').strip()
    search_apellido1 = request.GET.get('search_apellido1', '').strip()
    search_apellido2 = request.GET.get('search_apellido2', '').strip()

    campos = [search_nombre1, search_nombre2, search_apellido1, search_apellido2]
    campos_no_vacios = [campo for campo in campos if campo]

    if len(campos_no_vacios) == 0:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
        })

    if len(campos_no_vacios) < 2:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'Myerror': "Se requieren al menos dos criterios de bÃºsqueda.",
        })
    
    acompaniante_qs = Acompanante.objects.none()
    padre_qs =  Padre.objects.none()
    pacientes_qs = Paciente.objects.none()

    if search_base == 0:
        acompaniante_qs = Acompanante.objects.annotate(
            origen=Value("Acompanante"),
            codigo=F('id'),
        ).values(
            "codigo",
            "dni",
            "primer_nombre",
            "segundo_nombre",
            "primer_apellido",
            "segundo_apellido",
            "telefono",
            "sector__aldea__municipio__nombre_municipio",
            "sector__aldea__municipio__id",
            "sector__aldea__municipio__departamento__nombre_departamento",
            "sector__aldea__municipio__departamento__id",
            "sector__nombre_sector",
            "sector__id",
            "origen",  
        )

        padre_qs = Padre.objects.annotate(
            primer_nombre=F('nombre1'),
            segundo_nombre=F('nombre2'),
            primer_apellido=F('apellido1'),
            segundo_apellido=F('apellido2'),
            sector__aldea__municipio__nombre_municipio=F('direccion__aldea__municipio__nombre_municipio'),
            sector__aldea__municipio__departamento__nombre_departamento=F('direccion__aldea__municipio__departamento__nombre_departamento'),
            sector__nombre_sector=F('direccion__nombre_sector'),
            sector__aldea__municipio__id=F('direccion__aldea__municipio__id'),
            sector__aldea__municipio__departamento__id=F('direccion__aldea__municipio__departamento__id'),

            sector__id=F('direccion__id'),
            telefono=Value("", output_field=CharField()),
            codigo=Value("", output_field=CharField()),
            origen=Value("Padre")
        ).values(
            "codigo",
            "dni", 
            "primer_nombre",
            "segundo_nombre",
            "primer_apellido",
            "segundo_apellido",
            "telefono",
            "sector__aldea__municipio__nombre_municipio",
            "sector__aldea__municipio__id",
            "sector__aldea__municipio__departamento__nombre_departamento",
            "sector__aldea__municipio__departamento__id",
            "sector__nombre_sector",
            "sector__id",
            "origen"
        )

        paciente_qs = Paciente.objects.annotate(
            origen=Value("Paciente"),
            codigo=Value("", output_field=CharField()),

        ).values(
            "codigo",
            "dni",
            "primer_nombre",
            "segundo_nombre",
            "primer_apellido",
            "segundo_apellido",
            "telefono",
            "sector__aldea__municipio__nombre_municipio",
            "sector__aldea__municipio__id",
            "sector__aldea__municipio__departamento__nombre_departamento",
            "sector__aldea__municipio__departamento__id",
            "sector__nombre_sector",
            "sector__id",
            "origen",  
        ).exclude(Q(tipo=4) | Q(tipo=3))

        

        filtros = Q()
        if search_nombre1:
            filtros &= Q(primer_nombre__icontains=search_nombre1)
        if search_nombre2:
            filtros &= Q(segundo_nombre__icontains=search_nombre2)
        if search_apellido1:
            filtros &= Q(primer_apellido__icontains=search_apellido1)
        if search_apellido2:
            filtros &= Q(segundo_apellido__icontains=search_apellido2)

        if acompaniante_qs:
            acompaniante_qs = acompaniante_qs.filter(filtros)
        if padre_qs:
            if search_sexo:  
                rol = "01" if search_sexo == 'H' else "02"
                padre_qs = padre_qs.filter(filtros & Q(tipo=rol))
            else:
                padre_qs = padre_qs.filter(filtros)
        if paciente_qs:
            if search_sexo:  
                paciente_qs = paciente_qs.filter(filtros & Q(sexo=search_sexo))
            else:
                paciente_qs = paciente_qs.filter(filtros)


        columns = [
        "dni",#0
        "primer_nombre",#2
        "segundo_nombre",#3
        "primer_apellido",#4
        "segundo_apellido",#5
        "telefono",#6
        "sector__aldea__municipio__departamento__nombre_departamento",#7
        ]

        if order_column < len(columns): 
            order_column_name = columns[order_column]

            if order_direction == 'asc':
                acompaniante_qs = acompaniante_qs.order_by(order_column_name)
                padre_qs = padre_qs.order_by(order_column_name)
                pacientes_qs = pacientes_qs.order_by(order_column_name)
            else:
                acompaniante_qs = acompaniante_qs.order_by('-' + order_column_name)
                padre_qs = padre_qs.order_by('-' + order_column_name)
                pacientes_qs = pacientes_qs.order_by('-' + order_column_name)



        total_records = 200
        personas = list(acompaniante_qs) + list(padre_qs) + list(paciente_qs)
        filtered_records = len(personas)
        personas = list(personas[start:start + length])

        return JsonResponse({
            "draw": draw,
            "recordsTotal": total_records,
            "recordsFiltered": filtered_records,
            "data": personas
        })
    elif search_base == 1:# censo
        
        params = {
        'search_sexo': 1 if  search_sexo == 'H' else 2,
        'search_nombre1': search_nombre1,
        'search_nombre2': search_nombre2,
        'search_apellido1': search_apellido1,
        'search_apellido2': search_apellido2,
        } 

        
        
        datos, total_filtered = PacienteService.listar_personas_censo_avanzada(params, start, length, order_column, order_direction)
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 6082107,  # NÃºmero total de registros fijos o consulta real
            'recordsFiltered': total_filtered,
            'data': datos
        })


def guardarDefuncion(request):
    if not verificar_permisos_usuario(request.user, PACIENTE_EDITOR_ROLES, PACIENTE_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    try:
        id_paciente = validar_entero_positivo(data.get('idPaciente'), "idPaciente")
        id_defuncion = validar_entero_positivo(data.get('idDefuncion'), "idDefuncion") if data.get('idDefuncion') else None
        tipo = validar_entero_positivo(data.get('tipo'), "tipo")
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)
    
    fecha = data.get('fecha')
    motivo = data.get('motivo')

    dependencia_raw = data.get('dependencia')

    dependencia = None
    tipo_dependencia = None

    if dependencia_raw:
        try:
            dependencia, tipo_dependencia = ServicioService.obtener_dependencia_y_campo(dependencia_raw)
        except ValidationError:
            return JsonResponse({'error': 'La dependencia no es válida'}, status=400)
    

    if not fecha or not id_paciente or not tipo:
        return JsonResponse({'error': 'Datos incompletos'}, status=400)
    

    try:
        fecha = datetime.strptime(fecha, "%Y-%m-%d")
        validar_fecha(fecha,False)
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)
    except ValidationError as e:
        return JsonResponse({'error': 'La fecha enviada no es aceptable '}, status=400)


    defuncion = SimpleNamespace(
        fecha=fecha,
        tipo_dependencia=tipo_dependencia,
        dependencia=dependencia,
        motivo=motivo,
        paciente_id=int(id_paciente),
        id=int(id_defuncion) if id_defuncion else None,
        tipo=int(tipo),
        usuario_id=request.user.id
    )


    try:
        resultado = PacienteService.procesar_defuncion(defuncion)

        if resultado:
            return JsonResponse({'guardo': True}, status=200)
        else:
            return JsonResponse({'error': 'No se realizaron cambios'}, status=400)

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        return JsonResponse({'error': 'No se pudo procesar la defunción'}, status=500)


def guardarObito(request):

    if not verificar_permisos_usuario(request.user, PACIENTE_EDITOR_ROLES, PACIENTE_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)
    

    try:
        data = parse_json_request(request)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    try:
        id_paciente = validar_entero_positivo(data.get('idPaciente'), "idPaciente")
        id_obito = validar_entero_positivo(data.get('idObito'), "idObito") if data.get('idObito') else None
        tipo = validar_entero_positivo(data.get('tipo'), "tipo")
    except ValidationError as e:
        return JsonResponse({'error': e.message_dict}, status=400)

    
    fecha = data.get('fecha')
    dni_responsable = data.get('dniResponsable')
    nombre_responsable = data.get('nombreResponsable')

    dependencia_raw = data.get('dependencia')

    dependencia = None
    tipo_dependencia = None

    if dependencia_raw:
        try:
            dependencia, tipo_dependencia = ServicioService.obtener_dependencia_y_campo(dependencia_raw)
        except ValidationError:
            return JsonResponse({'error': 'La dependencia no es válida'}, status=400)


    # Validación básica
    if not fecha or not id_paciente or not tipo:
        return JsonResponse({'error': 'Datos incompletos'}, status=400)

    try:
        fecha = datetime.strptime(fecha, "%Y-%m-%d")
        validar_fecha(fecha, False)
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)
    except ValidationError:
        return JsonResponse({'error': 'La fecha enviada no es aceptable'}, status=400)


    obito = SimpleNamespace(
        fecha=fecha,
        tipo_dependencia=tipo_dependencia,
        dependencia=dependencia,
        paciente_id= int(id_paciente),  # madre
        id=int(id_obito) if id_obito else None,
        tipo=int(tipo),
        dni_responsable=dni_responsable,
        nombre_responsable=nombre_responsable.upper() if nombre_responsable else None,
        usuario_id=request.user.id
    )

    try:
        resultado, id_obito= PacienteService.procesar_obito(obito)

        if resultado and id_obito:
            pdf_url = reverse("entrega_cadaver_obito", kwargs={"obito_id": id_obito})

            return JsonResponse({
                'guardo': True,
                'pdf_url': pdf_url
            }, status=200)
        
        else:
            return JsonResponse({'error': 'No se realizaron cambios'}, status=400)

    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    except Exception as e:
        print(e)
        return JsonResponse({'error': 'No se pudo procesar el óbito'}, status=500)
    


def obtener_defuncion_paciente(request):
    idPaciente = request.GET.get('id')

    if not idPaciente:  # Verifica si el parÃ¡metro no estÃ¡ presente o estÃ¡ vacÃ­o
        return JsonResponse({"error": "El parametro 'idPaciente' es requerido."}, status=400)

    defuncion = PacienteService.obtener_defuncion(idPaciente)

    if not defuncion:
        return JsonResponse({"mensaje": "no defuncion"}, status=200)
    
    if defuncion.sala or defuncion.servicio_auxiliar or defuncion.especialidad:
        info = ServicioService.encontrar_dependencia_en_instance(defuncion)
        if info:
            dependencia_codigo = info["clave"]
            dependencia_label = f"{info['nombre']} ({info['tipo']})"
    else:
        dependencia_codigo = None
        dependencia_label = ""


    # Construir la respuesta con los datos del paciente
    return JsonResponse({
        "id": defuncion.id,
        "dependencia_codigo": dependencia_codigo,
        "dependencia_label": dependencia_label,
        "fecha_defuncion": defuncion.fecha_defuncion.strftime("%Y-%m-%d"),
        "motivo": defuncion.motivo,
        "fechaAdicion": defuncion.fecha_registro,
        "registrado": defuncion.registrado_por.username,
        "fecha_entrega": defuncion.fecha_entrega.strftime("%Y-%m-%d") if defuncion.fecha_entrega else None,
        "reponsable_nombre": defuncion.reponsable_nombre if defuncion.reponsable_nombre else "",
        "reponsable_dni": defuncion.reponsable_dni if defuncion.reponsable_dni else "",
        "tipo_defuncion": defuncion.tipo_defuncion,
        "tipo_defuncion_display": defuncion.get_tipo_defuncion_display()
    })


def obtener_obito_paciente(request):
    idObito = request.GET.get('id')

    if not idObito:
        return JsonResponse({"error": "El parametro 'idObito' es requerido."}, status=400)

    obito = PacienteService.obtener_obito_id(idObito)

    if not obito:
        return JsonResponse({"mensaje": "no obito"}, status=200)

    # Resolver dependencia
    if obito.sala or obito.servicio_auxiliar or obito.especialidad:
        info = ServicioService.encontrar_dependencia_en_instance(obito)
        if info:
            dependencia_codigo = info["clave"]
            dependencia_label = f"{info['nombre']} ({info['tipo']})"
        else:
            dependencia_codigo = None
            dependencia_label = ""
    else:
        dependencia_codigo = None
        dependencia_label = ""

    return JsonResponse({
        "id": obito.id,
        "dependencia_codigo": dependencia_codigo,
        "dependencia_label": dependencia_label,
        "fecha_obito": obito.fecha_obito.strftime("%Y-%m-%d"),
        "reponsable_nombre": obito.responsable_nombre if obito.responsable_nombre else "",
        "reponsable_dni": obito.responsable_dni if obito.responsable_dni else "",
        "tipo_defuncion": obito.tipo_defuncion,
        "tipo_defuncion_display": obito.get_tipo_defuncion_display(),
        "registrado": obito.registrado_por.username,
        "fechaAdicion": obito.fecha_registro,
    })


def registrarEntregaCadaver(request):
    if not verificar_permisos_usuario(request.user, PACIENTE_EDITOR_ROLES, PACIENTE_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        dni = data.get('dniR')
        nombre = data.get('nombreR')
        fecha_entrega = data.get('fechaEntrega')
        id_paciente = data.get('idPaciente')
        id_defuncion = data.get('idDefuncion')

        if not dni or not nombre or not fecha_entrega:
            return JsonResponse({'error': 'Datos incompletos'}, status=400)

        try:
            datetime.strptime(fecha_entrega, "%Y-%m-%d")
        except ValueError:
            return JsonResponse({'error': 'Formato de fecha inválido'}, status=400)

        defuncion_obj = {
            "reponsable_dni": dni,
            "reponsable_nombre": nombre,
            "paciente_id": id_paciente,
            "id": id_defuncion,
            "fecha_entrega": fecha_entrega
        }

        defuncion = SimpleNamespace(**defuncion_obj)

        try:
            resultado, idDefuncion = PacienteService.procesar_entrega_cadaver(defuncion)
        except ValidationError as e:
            # errores de negocio controlados
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse(
                {'error': 'No se pudo registrar la entrega de cadáver'},
                status=500
            )

        if not resultado:
            return JsonResponse(
                {'error': 'No se encontró registro de defunción'},
                status=404
            )

        pdf_url = reverse("entrega-cadaver", kwargs={"defuncion_id": idDefuncion})

        return JsonResponse({
            'guardo': True,
            'pdf_url': pdf_url
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Error al procesar los datos JSON'}, status=400)



def verificar_defuncion(request):
    # Obtener el id del paciente del request GET
    id_paciente = request.GET.get('idP')

    if not id_paciente:
        # Retorna un error si no se pasÃ³ el idP
        return JsonResponse({'error': 'El parametro idP es requerido'}, status=400)

    # Verificar si el paciente existe
    try:
        paciente = Paciente.objects.get(id=id_paciente)
        defuncion = PacienteService.comprobar_defuncion(paciente)
        return JsonResponse({'defuncion': defuncion})
    except Paciente.DoesNotExist:
        return JsonResponse({'error': 'Paciente no encontrado'}, status=404)
    

def verificar_inactivo(request):
    # Obtener el id del paciente del request GET
    id_paciente = request.GET.get('idP')

    if not id_paciente:
        # Retorna un error si no se pasÃ³ el idP
        return JsonResponse({'error': 'El parametro idP es requerido'}, status=400)

    inactivo = PacienteService.comprobar_inactivo(id_paciente)
    return JsonResponse({'inactivo': inactivo})



@require_GET
def verificar_duplicidad(request):
    # Obtener parámetros del request GET   
    id = request.GET.get('id')
    primer_nombre = request.GET.get('primerNombre')
    primer_apellido = request.GET.get('primerApellido')
    fecha_nacimiento = request.GET.get('fechaNacimiento')
    sexo = request.GET.get('Sexo')

    # Validar campos obligatorios
    if not (primer_nombre and primer_apellido and fecha_nacimiento and sexo):
        return JsonResponse(
            {'error': 'No se consignó la información requerida para comprobar duplicidad.'},
            status=400
        )

    paciente = {
        'id': id or "",  # Puede ir vacío si es nuevo
        'primer_nombre': primer_nombre,
        'primer_apellido': primer_apellido,
        'fecha_nacimiento': fecha_nacimiento,
        'sexo': sexo
    }

    try:
        duplicados = buscar_duplicidad_paciente(paciente)
        if duplicados:
            return JsonResponse({'duplicado': True, 'pacientes': duplicados})
        else:
            return JsonResponse({'duplicado': False})
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



class HistorialPaciente(DetailView):
    model = Paciente
    template_name = 'paciente/paciente_historial.html'
    context_object_name = 'paciente'  # en el template: {{ paciente.nombre }}

    def dispatch(self, request, *args, **kwargs):
        if not verificar_permisos_usuario(request.user, PACIENTE_VISUALIZACION_ROLES, PACIENTE_VISUALIZACION_UNIDADES):
            return redirect(reverse_lazy('acceso_denegado'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        paciente = self.object

        info_paciente = {#adicional requiere formateo
            'dni': formatear_dni(paciente.dni) if paciente.dni else "--------",
            'telefono': paciente.telefono if paciente.telefono else "--------",
            'nombreCompleto': formatear_nombre_completo(paciente.primer_nombre,paciente.segundo_nombre, paciente.primer_apellido, paciente.segundo_apellido),
            'fechaNacimiento': paciente.fecha_nacimiento,
            'edad': calcular_edad_texto(str(paciente.fecha_nacimiento)),
            'sexo': paciente.get_sexo_display(),
            'domicilio': UbicacionService.obtener_cadena_ubicacion_completa(paciente)
        }
        context['info_paciente'] = info_paciente

        expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
        if expediente:
            info_expediente = {
                'numero': formatear_expediente(expediente.numero),
                'ubicacion': expediente.localizacion.descripcion_localizacion 
            }
            context['info_expediente'] = info_expediente

        def obtener_info_padre(padre_id):
            return PadreService.obtener_detalles_padre(padre_id) if padre_id else None

        context['info_madre'] = obtener_info_padre(paciente.madre_id)
        context['ultima_atencion'] = paciente.get_ultima_visita()

        #comprueba informacino si es SAI o DEFUNCION
        defuncion = PacienteService.obtener_defuncion(paciente.id)
        if defuncion:
            info_defuncion = {
                'id': defuncion.id,
                'fecha': defuncion.fecha_defuncion,
                'motivo': defuncion.motivo,
                'fecha_registro':defuncion.fecha_registro,
                'sala': defuncion.sala
            }
            context['info_defuncion'] = info_defuncion

        permisoDispensacion = verificar_permisos_dispensacion(self.request.user,PACIENTE_DISPENSACION_ROLES , PACIENTE_DISPENSACION_UNIDADES )
        context['permiso_dispensacion'] = permisoDispensacion

        tabs, activo = UsuarioService.obtener_tabs_usuario(usuario)
        if tabs and activo:
            context['tabs'] = tabs
            context['tabActiva'] = activo


        return context


def EjecutarReclasificacion(request):
    usuario = request.user
    if not verificar_permisos_usuario(usuario, ['admin'], ['Admision']):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            ejecutar = data.get('ejecutar', False)

            cantidad = PacienteService.reclasificar_rn_a_hijo(ejecutar=ejecutar)
            return JsonResponse({"success": True, "actualizacion":ejecutar, "cantidad":cantidad})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Metodo no permitido'}, status=405)


@require_GET
def dispensacion_view(request):
    id = request.GET.get('id_paciente')
    if not id:
        return JsonResponse({'error': 'El parametro id_paciente es requerido'}, status=400)

    paciente = Paciente.objects.filter(id=id).values('dni', 'expediente_numero').first()
    
    if paciente:
        try:
            resultado = obtener_dispensacion_mysql(paciente['expediente_numero'], paciente['dni'])
        except Exception as e:
            log_error(
                f"[FALLO_DISPENSACION] paciente_id={id} detalle={str(e)}",
                app=LogApp.REPLICACION
            )
            return JsonResponse({'error': 'Error obteniendo dispensaciones'}, status=500)
    else:
        return JsonResponse({'error': 'El di paciente recibido no existe'}, status=400)

    return JsonResponse({'data': resultado})


@require_GET
def obtener_obitos_paciente(request):
    id = request.GET.get('id')
    if not id:
        return JsonResponse({'error': 'El parametro id_paciente es requerido'}, status=400)

    try:
        data = PacienteService.obtener_obitos_por_paciente(id)
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({"mensaje": str(e)}, status=500)

