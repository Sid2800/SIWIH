from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
from servicio.models import Sala, Especialidad, ServiciosAux
from django.db.models.functions import Concat, Coalesce
from core.mixins import UnidadRolRequiredMixin
from core.services.expediente_service import ExpedienteService
from core.services.imagenologia_service import EvaluacionService
from core.services.paciente_service import PacienteService
from core.services.server_image.media_service import MediaService
from core.services.server_image.request_service import RequestService
from core.constants import permisos
from core.constants.domain_constants import AccionEstudio
from core.constants.media_constants import TipoPaciente
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import EvaluacionRx
from django.db.models import Value, CharField, F, Count
from imagenologia.forms import EvaluacionRXCreateForm, EvaluacionRXEditForm
from paciente.models import Paciente
from core.utils.utilidades_fechas import formatear_fecha_simple
from core.utils.utilidades_mensajes import mostrar_resultado_media, mostrar_resultado_media_batch
from core.validators.main_validator import validar_entero_positivo
from core.exceptions import EvaluacionDominioError
from usuario.permisos import verificar_permisos_usuario
import json
from collections import defaultdict

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, F, Value, OuterRef, Subquery, CharField,Case, When
from django.views.decorators.http import require_GET
from django.core.exceptions import ValidationError




class EvaluacionRxAddView(UnidadRolRequiredMixin, CreateView):
    model = EvaluacionRx 
    required_roles = permisos.IMAGENOLOGIA_VISUALIZACION_ROLES
    required_unidades = permisos.IMAGENOLOGIA_EDITOR_UNIDADES
    form_class = EvaluacionRXCreateForm
    success_url = reverse_lazy('listar_evalucionesrx') 

    def get_form(self, form_class = None):
        form = super().get_form(form_class)
        paciente_id = self.kwargs.get("pk")

        if paciente_id and paciente_id != 0:
            paciente = get_object_or_404(
                Paciente.objects.select_related(
                    'sector__aldea__municipio__departamento'
                ), pk=paciente_id
            )
            numero_expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)

            if numero_expediente and not paciente.estado == "I":
                PacienteService.llenarDatosCamposPaciente(form, paciente, numero_expediente)

                form.fields['idPaciente'].initial = paciente.id
                
            else:
                messages.error(self.request, "El paciente no tiene un expediente activo.")
                return self.form_invalid(form)
        else: #el id es 0
            #desbloquear los campos de paciente con el que usurio debe interactuar en este flujo
            form.fields['dniPaciente'].widget.attrs.update({
            'disabled': False,
            })
            form.fields['numeroExpediente'].widget.attrs.update({
            'disabled': False,
            })

        return form


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paciente_id = self.kwargs.get("pk")
        # modo de uso del formulario
        context['MD'] = 1 # modo de uso del formulario, 1 = crear, 2 = editar
        context['titulo'] = 'Agregar'

        estudios = EvaluacionService.obtener_estudios()
        context['estudios'] = json.dumps(estudios, cls=DjangoJSONEncoder)

        context['Pexterno'] = 1 if paciente_id == 0 else 0
        

        return context
    
    def form_valid(self, form):
        usuario = self.request.user
        estudios = form.estudios_validados
        externo = getattr(form, "externo", None)
        paciente = form.cleaned_data.get('paciente') or self.request.POST.get('paciente')
        archivos = self.request.FILES

        try:
            with transaction.atomic():
                
                # ---------- Usuario ----------
                if usuario:
                    form.instance.creado_por = usuario
                    form.instance.modificado_por = usuario

                # ---------- Paciente ----------
                form.instance.paciente = paciente if paciente else None
                form.instance.paciente_externo = None
                    
                if not paciente and externo:
                    paciente_externo_obj = EvaluacionService.procesar_paciente_externo(
                        externo,
                        usuario
                    )
                    if paciente_externo_obj:
                        form.instance.paciente_externo = paciente_externo_obj

                # ---------- Dependencia ----------
                for campo in ["sala", "especialidad", "servicio_auxiliar"]:
                    valor = form.cleaned_data.get(campo)
                    if valor:
                        setattr(form.instance, campo, valor)
                        break

                # ---------- Guardar evaluación ----------
                super().form_valid(form)


                # ---------- Crear estudios ----------
                for est in estudios:
                    
                    accion_raw = est.get('accionEstudio')

                    try:
                        accion = AccionEstudio(accion_raw)
                    except ValueError:
                        raise EvaluacionDominioError("Acción de estudio inválida")

                    if accion == AccionEstudio.DELETE:
                        continue

                    estudio_id = est.get('id')
                    if not estudio_id:
                        raise EvaluacionDominioError("ID de estudio inválido")

                    nuevo_id = EvaluacionService.crear_evaluacionrx_estudio_detalle(
                        id_evaluacionrx=self.object.id,
                        id_estudio=estudio_id,
                        impreso=est.get('impreso', False)
                    )

                    est['idDetalle'] = nuevo_id

            # ---------- FUERA DEL ATOMIC ----------

            evaluacion = self.object

            paciente_tipo, paciente_id = evaluacion.obtener_tipo_y_paciente_id()

            media_result = MediaService.agregar_imagenes_evaluacion(
                estudios=estudios,
                archivos=archivos,
                paciente_tipo=paciente_tipo,
                paciente_id=paciente_id,
                usuario=usuario,
            )

            mostrar_resultado_media(self.request, media_result)

            messages.success(
                self.request,
                "Evaluación imagenológica registrada correctamente"
            )

            return JsonResponse({
                "success": True,
                "redirect_url": reverse_lazy('listar_evalucionesrx')
            })
            

        except EvaluacionDominioError as e:
            return JsonResponse({
                "success": False,
                "error": str(e)
            })

        except ValidationError as ve:
            return JsonResponse({
                "success": False,
                "error": ve.message
            })

        except Exception:
            return JsonResponse({
                "success": False,
                "error": "Hubo un error interno al registrar la evaluación."
            })


    def form_invalid(self, form):
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] 
        
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)

class EvaluacionRxEditView(UnidadRolRequiredMixin, UpdateView):
    model = EvaluacionRx 
    required_roles = permisos.IMAGENOLOGIA_VISUALIZACION_ROLES
    required_unidades = permisos.IMAGENOLOGIA_VISUALIZACION_UNIDADES
    form_class = EvaluacionRXEditForm
    success_url = reverse_lazy('listar_evalucionesrx') 

    def get_form(self, form_class = None):
        form = super().get_form(form_class)
        evaluacion = self.get_object()
        paciente = evaluacion.paciente

        if paciente:
            numero_expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
            if numero_expediente and not paciente.estado == "I":
                PacienteService.llenarDatosCamposPaciente(form, paciente, numero_expediente)
                form.fields['idPaciente'].initial = paciente.id
                fecha_nacimiento_formateada = formatear_fecha_simple(paciente.fecha_nacimiento)
                form.fields['fechaNacimientoPaciente'].initial = fecha_nacimiento_formateada

            else:
                messages.error(self.request, "El paciente no tiene un expediente activo.")
                return self.form_invalid(form)
        return form


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # modo de uso del formulario
        context['MD'] = 2 # modo de uso del formulario, 1 = crear, 2 = editar
        context['titulo'] = 'Editar'
        # valor inicial de dependencia 
        evaluacion = self.get_object()

        # estudios ligados a la evalucion   
        estudios = EvaluacionService.obtener_estudios_evaluacion(
            evaluacion.id,
            evaluacion.paciente_id
        )

        paciente_tipo, paciente_id = evaluacion.obtener_tipo_y_paciente_id()
        #agregar la imagenes

        estudios, media_server_offline = MediaService.obtener_imagenes_estudios(
            estudios,
            paciente_tipo,
            paciente_id
        )

        
        context["media_server_offline"] = media_server_offline


        context['estudios_actuales'] = json.dumps(estudios, cls=DjangoJSONEncoder)
        # Ahora puedes unir las tres listas
        estudios = EvaluacionService.obtener_estudios()
        context['estudios'] = json.dumps(estudios, cls=DjangoJSONEncoder)
        

        #el paceinte no es intercambiable entre evaluciones solo lo enviamos para consulta
        if not evaluacion.paciente and evaluacion.paciente_externo:
            context['Pexterno'] = 1 
            externo = evaluacion.paciente_externo
            fecha_nacimiento_local = externo.fecha_nacimiento
            info_externo = {
                'id': externo.id,
                'dni': externo.dni if externo.dni else None,  
                'primer_nombre': externo.primer_nombre,
                'segundo_nombre': externo.segundo_nombre,
                'primer_apellido': externo.primer_apellido if externo.primer_apellido else None,
                'segundo_apellido': externo.segundo_apellido,
                'fecha_nacimiento': fecha_nacimiento_local.strftime('%Y-%m-%d') if fecha_nacimiento_local else None,
                'sexo': externo.sexo
            }
            context['info_externo'] = json.dumps(info_externo)
        else:
            context['Pexterno'] = 0

        

        return context
    


    def form_invalid(self, form):
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] 
        
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)

    def form_valid(self, form):

        usuario = self.request.user
        estudios = form.estudios_validados
        externo = getattr(form, "externo", None)
        paciente = form.cleaned_data.get('paciente')
        archivos = self.request.FILES

        # Permisos primero 
        if not verificar_permisos_usuario(
            usuario,
            permisos.IMAGENOLOGIA_EDITOR_ROLES,
            permisos.IMAGENOLOGIA_EDITOR_UNIDADES
        ):
            return JsonResponse({
                "success": False,
                "error": "No tiene permiso para editar la evaluación"
            })

        try:

            with transaction.atomic():

                # ---------- Asignaciones básicas ----------
                form.instance.paciente = paciente if paciente else None
                form.instance.paciente_externo = None

                if usuario:
                    form.instance.modificado_por = usuario

                # Limpiar dependencias
                for campo in ["sala", "especialidad", "servicio_auxiliar"]:
                    setattr(form.instance, campo, None)

                # Asignar primera dependencia válida
                for campo in ["sala", "especialidad", "servicio_auxiliar"]:
                    valor = form.cleaned_data.get(campo)
                    if valor:
                        setattr(form.instance, campo, valor)
                        break

                # Guardar evaluación principal
                super().form_valid(form)

                # Procesar estudios
                id_map = EvaluacionService.procesar_estudios_evaluacion(
                    evaluacion_id=self.object.id,
                    estudios=estudios
                )

                # Paciente externo
                if externo and externo.get('id') and not form.instance.paciente:
                    paciente_externo_obj = EvaluacionService.procesar_paciente_externo(
                        externo,
                        usuario
                    )
                    if paciente_externo_obj:
                        form.instance.paciente_externo = paciente_externo_obj
                        form.instance.save(update_fields=['paciente_externo'])

            # Mapear nuevos IDs para procesar bien las imagenes
            for est in estudios:
                frontend_id = est.get('frontendId')
                if frontend_id in id_map:
                    est['idDetalle'] = id_map[frontend_id]

            # Determinar paciente_id seguro
            evaluacion = self.object
            paciente_tipo, paciente_id = evaluacion.obtener_tipo_y_paciente_id()

            media_result = MediaService.procesar_imagenes_evaluacion(
                estudios=estudios,
                archivos=archivos,
                paciente_tipo=paciente_tipo,
                paciente_id=paciente_id,
                usuario=usuario
            )

            mostrar_resultado_media(self.request, media_result)

            messages.success(
                self.request,
                "Evaluación imagenológica actualizada correctamente"
            )

            return JsonResponse({
                "success": True,
                "redirect_url": reverse_lazy('listar_evalucionesrx')
            })

        except EvaluacionDominioError as e:
            # Error de negocio controlado
            return JsonResponse({
                "success": False,
                "error": str(e)
            })

        except Exception as r:
            print(r)
            # Error inesperado (DB, código, etc.)
            return JsonResponse({
                "success": False,
                "error": "Ocurrió un error interno al actualizar la evaluación."
            })
        



class listarEvaluacionrx(UnidadRolRequiredMixin,TemplateView):
    template_name = 'imagenologia/evaluacionrx_list.html'
    required_roles = permisos.IMAGENOLOGIA_VISUALIZACION_ROLES
    required_unidades = permisos.IMAGENOLOGIA_VISUALIZACION_UNIDADES

def listarEvaluacionrxAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', 8))
    order_direction = request.GET.get('order[0][dir]', 'desc')
    search_column = request.GET.get('search_column')
    fechaIni = request.GET.get('fecha_inicio')
    fechaFin = request.GET.get('fecha_fin')


    # Validar fechas
    tz = timezone.get_current_timezone()
    hoy = timezone.localdate()

    try:
        if fechaFin:
            fechaFin = datetime.strptime(fechaFin, '%Y-%m-%d').date()
        else:
            fechaFin = hoy

        if fechaIni:
            fechaIni = datetime.strptime(fechaIni, '%Y-%m-%d').date()
        else:
            fechaIni = fechaFin - timedelta(days=30)

    except ValueError:
        fechaFin = hoy
        fechaIni = fechaFin - timedelta(days=30)

    # Query base
    evaluacion_qs = EvaluacionRx.objects.filter(
        fecha__gte=fechaIni,
        fecha__lte=fechaFin,
        estado=1
    ).annotate(
        total_estudios=Count('detalles', filter=Q(detalles__activo=True)),
        nombre_dependencia=Case(
            When(sala__isnull=False, then=F('sala__nombre_sala')),
            When(especialidad__isnull=False, then=F('especialidad__nombre_especialidad')),
            When(servicio_auxiliar__isnull=False, then=F('servicio_auxiliar__nombre_servicio_a')),
            default=Value('Desconocido'),
            output_field=CharField()
        ),
        tipo_dependencia=Case(
            When(sala__isnull=False, then=Value('HOSP')),
            When(especialidad__isnull=False, then=Value('CEXT')),
            When(servicio_auxiliar__isnull=False, then=Value('SVAUX')),
            default=Value('DESC'),
            output_field=CharField()
        )
    )
    # Si se requiere búsqueda por nombre completo
    if search_column == '3' and search_value:
        evaluacion_qs = evaluacion_qs.annotate(
            nombre_completo_interno=Concat(
                F("paciente__primer_nombre"),
                Case(
                    When(paciente__segundo_nombre__isnull=False, paciente__segundo_nombre__exact="", then=Value("")),
                    When(paciente__segundo_nombre__isnull=False, then=Concat(Value(" "), F("paciente__segundo_nombre"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                Value(" "),
                F("paciente__primer_apellido"),
                Case(
                    When(paciente__segundo_apellido__isnull=False, paciente__segundo_apellido__exact="", then=Value("")),
                    When(paciente__segundo_apellido__isnull=False, then=Concat(Value(" "), F("paciente__segundo_apellido"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                output_field=CharField()
            ),
            nombre_completo_externo=Concat(
                F("paciente_externo__primer_nombre"),
                Case(
                    When(paciente_externo__segundo_nombre__isnull=False, paciente_externo__segundo_nombre__exact="", then=Value("")),
                    When(paciente_externo__segundo_nombre__isnull=False, then=Concat(Value(" "), F("paciente_externo__segundo_nombre"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                Value(" "),
                F("paciente_externo__primer_apellido"),
                Case(
                    When(paciente_externo__segundo_apellido__isnull=False, paciente_externo__segundo_apellido__exact="", then=Value("")),
                    When(paciente_externo__segundo_apellido__isnull=False, then=Concat(Value(" "), F("paciente_externo__segundo_apellido"))),
                    default=Value(""),
                    output_field=CharField(),
                ),
                output_field=CharField()
            )
        ).filter(
            Q(nombre_completo_interno__icontains=search_value) | 
            Q(nombre_completo_externo__icontains=search_value)
        )

    # Filtro por columnas específicas
    elif search_column and search_value:
        if search_column == '0':
            try:
                numero = int(search_value.lstrip("0"))
                evaluacion_qs = evaluacion_qs.filter(id=numero)
            except ValueError:
                evaluacion_qs = evaluacion_qs.none()
        elif search_column == '1':
            try:
                numero = int(search_value.lstrip("0"))
                evaluacion_qs = evaluacion_qs.filter(paciente__expediente_numero=numero)
            except ValueError:
                evaluacion_qs = evaluacion_qs.none()
        elif search_column == '2':
            dni_limpio = search_value.replace("-", "").strip()
            evaluacion_qs = evaluacion_qs.filter(
                Q(paciente__dni__iexact=dni_limpio) | 
                Q(paciente_externo__dni__iexact=dni_limpio)
            )


    # Columnas para ordenamiento (deben coincidir con las columnas del DataTable)
    columns = [
        "id",                               # 0
        "fecha",                            # 1
        "nombre_dependencia",               # 2 depencia no se pondre fecha por poner algo
        "maquinarx__descripcion_maquina",   # 3
        "total_estudios",                   # 4
        "paciente__expediente_numero",      # 5
        "paciente__dni",                    # 6
        "paciente__primer_nombre",          # 7
        "fecha_modificado"                  # 8         
    ]

    # Mapea columnas que necesitan coalesce para evitar null en orden
    campos_coalesce = {
        'paciente__dni': Coalesce('paciente__dni', 'paciente_externo__dni', output_field=CharField()),
        'paciente__primer_nombre': Coalesce('paciente__primer_nombre', 'paciente_externo__primer_nombre', output_field=CharField()),
    }


    if order_column < len(columns):
        order_column_name = columns[order_column]

        if order_column_name in campos_coalesce:
            campo_orden = campos_coalesce[order_column_name]
            if order_direction == 'asc':
                evaluacion_qs = evaluacion_qs.order_by(campo_orden)
            else:
                evaluacion_qs = evaluacion_qs.order_by(campo_orden.desc())
        else:
            if order_direction == 'asc':
                evaluacion_qs = evaluacion_qs.order_by(order_column_name)
            else:
                evaluacion_qs = evaluacion_qs.order_by('-' + order_column_name)

    # Conteo
    total_records = EvaluacionRx.objects.count()
    filtered_records = evaluacion_qs.count()

    # Paginación + datos
    evaluaciones = list(evaluacion_qs[start:start + length].values(
        "id",
        "fecha",
        "nombre_dependencia",
        "tipo_dependencia",
        "maquinarx__descripcion_maquina",
        "total_estudios",
        "paciente__dni",
        "paciente__expediente_numero",
        "paciente__primer_nombre",
        "paciente__segundo_nombre",
        "paciente__primer_apellido",
        "paciente__segundo_apellido",
        "paciente_externo__dni",
        "paciente_externo__primer_nombre",
        "paciente_externo__segundo_nombre",
        "paciente_externo__primer_apellido",
        "paciente_externo__segundo_apellido",
        "modificado_por__username",
        "fecha_modificado"
    ))

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": evaluaciones
    })

@require_GET
def obtenerPacienteExterno(request):
    dni = request.GET.get('dni_externo')
    if not dni:
        return JsonResponse({'error': 'El parametro dni_externo es requerido'}, status=400)
    
    dni_e = dni.replace('-', '').strip()

    
    paciente_externo = EvaluacionService.obtener_paciente_externo_DNI(dni_e)


    if not paciente_externo:
        return JsonResponse({"mensaje": "No se encontro un paciente externo habilitado con este numero."}, status=200)

    fecha_nac = getattr(paciente_externo, 'fecha_nacimiento', None)
    fecha_nac_str = fecha_nac.strftime('%Y-%m-%d') if fecha_nac else None

    return JsonResponse({
        "id": getattr(paciente_externo, 'id', None),
        "dni": getattr(paciente_externo, 'dni', None),
        "primer_nombre": getattr(paciente_externo, 'primer_nombre', None),
        "segundo_nombre": getattr(paciente_externo, 'segundo_nombre', None),
        "primer_apellido": getattr(paciente_externo, 'primer_apellido', None),
        "segundo_apellido": getattr(paciente_externo, 'segundo_apellido', None),
        "fecha_nacimiento": fecha_nac_str,
        "sexo": getattr(paciente_externo, 'sexo', None),
    })


def inactivarEvalucionRX(request):
    if not verificar_permisos_usuario(request.user, permisos.IMAGENOLOGIA_EDITOR_ROLES, permisos.IMAGENOLOGIA_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    try:
        data = json.loads(request.body)
        idEvaluacion = data.get('id')
        if not idEvaluacion:
            return JsonResponse({"success": False, "error": "El parámetro id es obligatorio"}, status=400)

        resultado, media_resultado = EvaluacionService.inactivar_evaluacion_rx(idEvaluacion, request.user)

        mostrar_resultado_media_batch(request,media_resultado)

        if resultado:
            messages.success(request, "Evaluacion imagenologica inactivada correctamente")
            return JsonResponse({"success": True})
        
        else:
            return JsonResponse({"success": False, "error": "No es posible inactivar esta evaluación imagenológica"})
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Error al procesar los datos JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error inesperado: {str(e)}"}, status=500)




def obtenerImagenesEvaluacion(request):
    if not verificar_permisos_usuario(
        request.user,
        permisos.IMAGENOLOGIA_VISUALIZACION_ROLES,
        permisos.IMAGENOLOGIA_VISUALIZACION_UNIDADES
    ):
        return JsonResponse({'error': 'No tienes permisos para consultar la galeria'}, status=403)

    if request.method != "GET":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)
    try:

        idEvaluacion = validar_entero_positivo(request.GET.get("id"))
        idPaciente = validar_entero_positivo(request.GET.get("id_paciente"))


        if not EvaluacionService.validar_evaluacion_paciente(idEvaluacion, idPaciente):
            raise ValidationError("La evaluación no pertenece al paciente")
        
        estudios = EvaluacionService.obtener_estudios_evaluacion(
            idEvaluacion,
            idPaciente
        )

        

        estudios, media_server_offline = MediaService.obtener_imagenes_estudios(
            estudios,
            TipoPaciente.INTERNO,
            idPaciente
        )

        return JsonResponse({
            "success": True,
            "media_server_offline": media_server_offline,
            "data": estudios
        })
    
    except (ValidationError) as e:
        return JsonResponse(
            {"success": False, "error": f"Los parámetros {e}"},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"Error inesperado: {str(e)}"},
            status=500
        )



def listarEvaluacionRxPacienteAPI(request):
    id_paciente = request.GET.get('id_paciente')
    if not id_paciente:
        return JsonResponse({"error": "Parámetro 'id_paciente' es requerido."}, status=400)

    evaluaciones = EvaluacionService.listar_evaluaciones_por_paciente(id_paciente)
    return JsonResponse({"data": evaluaciones})



class DemoView(UnidadRolRequiredMixin,TemplateView):
    template_name = 'imagenologia/demo.html'
    required_roles = permisos.IMAGENOLOGIA_VISUALIZACION_ROLES
    required_unidades = permisos.IMAGENOLOGIA_VISUALIZACION_UNIDADES

