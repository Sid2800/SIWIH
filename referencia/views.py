
from core.mixins import UnidadRolRequiredMixin
from datetime import datetime, timedelta, time
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import View, TemplateView
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Value, CharField, F, Q, Count, Case, When, Exists, OuterRef,  IntegerField, Subquery
from django.db.models.functions import Concat, Coalesce
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from referencia.models import Referencia, Respuesta, SeguimientoTic, Referencia_diagnostico
from paciente.models import Paciente
from referencia.validators import validar_respuesta_vs_referencia, validar_referencia_para_respuesta
from referencia.forms import ReferenciaCreateForm, ReferenciaEditForm, RespuestaCreateForm, RespuestaEditForm
from types import SimpleNamespace
import json
from django.core.serializers.json import DjangoJSONEncoder
from core.constants import permisos
from core.utils.utilidades_textos import generar_slug
from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy_hh_mm
from usuario.permisos import verificar_permisos_usuario
from core.services.expediente_service import ExpedienteService
from core.services.paciente_service import PacienteService
from core.services.referencia.referencia_diagnostico_service import RefDiagnosticoService
from core.services.referencia.referencia_service import ReferenciaService
from core.utils.utilidades_request import cargar_json
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


# Create your views here.
class ReferenciaAddView(UnidadRolRequiredMixin, CreateView):
    model = Referencia
    required_roles = permisos.REFERENCIA_EDITOR_ROLES
    required_unidades = permisos.REFERENCIA_EDITOR_UNIDADES
    form_class = ReferenciaCreateForm
    success_url = reverse_lazy('listar_pacientes') 

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

        # modo de uso del formulario
        context['MD'] = 1 # modo de uso del formulario, 1 = crear, 2 = editar
        context['titulo'] = 'Agregar'
        context['subtitulo'] = 'Agregando'


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
        diagnosticos = form.diagnosticos_validados
        paciente = form.cleaned_data.get('paciente')
        motivo_no_atencion = form.cleaned_data.get('motivo_no_atencion')
        
        if usuario:
            form.instance.creado_por = usuario
            form.instance.modificado_por = usuario

        if not verificar_permisos_usuario(
            usuario,
            permisos.REFERENCIA_EDITOR_ROLES,
            permisos.REFERENCIA_EDITOR_UNIDADES):
            return JsonResponse({"success": False, "error": f"No tiene permiso para registrar una referencia"})

        if paciente:
            form.instance.paciente = paciente

        form.instance.motivo_no_atencion = motivo_no_atencion

        for campo in ["area_refiere_sala", "area_refiere_especialidad", "area_refiere_servicio_auxiliar"]:
            valor = form.cleaned_data.get(campo)
            if valor:
                setattr(form.instance, campo, valor)
                break 
            
        try:
            with transaction.atomic():
                response = super().form_valid(form) 

                for diag in diagnosticos:
                    RefDiagnosticoService.crear_referencia_diagnostico(
                        id_referencia=self.object.id,
                        id_diagnostico=diag['id'],
                        detalle=diag['detalle'],
                        confirmado=diag.get('confirmado', False)
                    )

                # Generar slug a partir de nombre y primer apellido
                editar_url = reverse_lazy(
                    'referencia_editar',
                    kwargs={
                        'pk': self.object.pk,
                        'slug': generar_slug(f"{paciente.primer_nombre} {paciente.primer_apellido}")
                    }
                )

                #messages.success(self.request, "Referencia registrada correctamente")
                return JsonResponse({"success": True, "redirect_url": editar_url})

        except ValidationError as ve:
            # Error esperado por validaciones, mostrar mensaje amigable
            return JsonResponse({"success": False, "error": ve.message})
        
        except Exception as e:
            # logger.error(f"Error al registrar evaluación: {e}")
            return JsonResponse({"success": False, "error": "Hubo un error al registrar la referencia, inténtelo nuevamente."})


class ReferenciaEditView(UnidadRolRequiredMixin, UpdateView):
    model=Referencia
    required_roles = permisos.REFERENCIA_VISUALIZACION_ROLES
    required_unidades = permisos.REFERENCIA_VISUALIZACION_UNIDADES
    form_class = ReferenciaEditForm
    success_url = reverse_lazy('listar_pacientes') 

    def get_form(self, form_class = None):
        form = super().get_form(form_class)
        referencia = self.get_object()
        paciente = referencia.paciente

        if paciente:
            numero_expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)
            if numero_expediente and not paciente.estado == "I":
                PacienteService.llenarDatosCamposPaciente(form, paciente, numero_expediente)
                form.fields['idPaciente'].initial = paciente.id
            else:
                messages.error(self.request, "El paciente no tiene un expediente activo.")
                return self.form_invalid(form)
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        referencia = self.object

        # modo de uso del formulario
        context['MD'] = 2 # modo de uso del formulario, 1 = crear, 2 = editar
        context['titulo'] = 'Editar'
        context['subtitulo'] = 'Editando'

        #diagnosticos ligados a la refreicna
        diagnosticos_referencia = RefDiagnosticoService.obtener_diagnosticos_referencia(referencia.id)
        context['diagnosticos_referencia_actuales'] = json.dumps(diagnosticos_referencia, cls=DjangoJSONEncoder)

        
        respuesta = getattr(referencia, 'respuesta', None)

        if not respuesta:
            # No hay respuesta: creamos nueva
            form_respuesta = RespuestaCreateForm(principal_instance=referencia)
            context['seguimiento'] = 1  # por defecto seguimiento interno

        else:
            # Edición de respuesta existente
            form_respuesta = RespuestaEditForm(instance=respuesta, principal_instance=referencia)

            context['idReferenciaEnviadaRespuesta'] = 0 
            # Determinar tipo de seguimiento
            if respuesta.seguimiento_referencia:
                seguimiento = 2  # seguimiento por referencia enviada
                context['referencia_enviada_seguimiento_url'] = reverse_lazy(
                    'referencia_editar',
                    kwargs={'pk': respuesta.seguimiento_referencia.id, 'slug': "slug-por-defecto"}
                )

            elif respuesta.institucion_destino:
                seguimiento = 0  # seguimiento fuera de la institución
            else:
                seguimiento = 1  # seguimiento interno

            context['seguimiento'] = seguimiento
            

            # Diagnósticos actuales de la respuesta
            diagnosticos_respuesta = RefDiagnosticoService.obtener_diagnosticos_respuesta(respuesta.id)
            context['diagnosticos_respuesta_actuales'] = json.dumps(
                diagnosticos_respuesta, cls=DjangoJSONEncoder
            )
        


        context['form_respuesta'] = form_respuesta
        context['respuesta_id'] = respuesta.id if respuesta else 0

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
        diagnosticos = form.diagnosticos_validados
        motivo_no_atencion = form.cleaned_data.get('motivo_no_atencion')
        
        if usuario:
            form.instance.modificado_por = usuario

        if not verificar_permisos_usuario(
            usuario,
            permisos.REFERENCIA_EDITOR_ROLES,
            permisos.REFERENCIA_EDITOR_UNIDADES):
            return JsonResponse({"success": False, "error": f"No tiene permiso para actualizar una referencia"})

        for campo in ["area_refiere_sala", "area_refiere_especialidad", "area_refiere_servicio_auxiliar"]:
            valor = form.cleaned_data.get(campo)
            setattr(form.instance, campo, valor if valor else None)

        form.instance.motivo_no_atencion = motivo_no_atencion

        try:
            with transaction.atomic():
                response = super().form_valid(form)

                #procesar diagnosticos 
                RefDiagnosticoService.procesar_diagnosticos_referencia(
                    referencia_id=self.object.id,
                    diagnosticos=diagnosticos
                )

                #messages.success(self.request, "Referencia actualizada correctamente")
                return JsonResponse({"success": True, "redirect_url": reverse_lazy('listar_evalucionesrx')})
        except ValidationError as ve:
            # Error esperado por validaciones, mostrar mensaje amigable
            return JsonResponse({"success": False, "error": ve.message})       
        except Exception as e:
            # logger.error(f"Error al registrar evaluación: {e}")
            return JsonResponse({"success": False, "error": f"Hubo un error {e} al registrar la referencia, inténtelo nuevamente."})


class RespuestaCreateUpdateView(View):
    """
    Vista que procesa agregar o actualizar una respuesta
    usando la misma vista. Devuelve JSON, no renderiza template.
    """
    def get_form(self, form_class=None, data=None, instance=None, principal_instance=None):
        form_class = form_class or RespuestaCreateForm
        return form_class(data=data, instance=instance, principal_instance=principal_instance)

    def form_valid(self, form):
        usuario = self.request.user
        diagnosticos = form.diagnosticos_validados
        referencia = form.referencia
        seguimiento = form.cleaned_data.get("seguimiento")


        if usuario:
            form.instance.creado_por = usuario
            form.instance.modificado_por = usuario


        if referencia:
            form.instance.referencia = referencia


        for campo in ["area_reponde_sala", "area_reponde_especialidad", "area_reponde_servicio_auxiliar"]:
            valor = form.cleaned_data.get(campo)
            setattr(form.instance, campo, valor if valor else None)


        try:
            with transaction.atomic():

                if referencia.motivo_no_atencion is not None:
                    referencia.motivo_no_atencion = None
                    referencia.save(update_fields=["motivo_no_atencion"])

                instance = form.save(commit=False)
                
                if seguimiento == 2:  # tipo 3 / seguimiento con referencia enviada
                    # SOLO crear referencia si no existe previamente
                    if not instance.seguimiento_referencia:
                        # crear la nueva referencia
                        nueva_ref = ReferenciaService.crear_referencia_enviada_segun_repuesta({
                        "fecha_elaboracion": instance.fecha_elaboracion,
                        "tipo": 1, # enviada
                        "paciente": instance.referencia.paciente,
                        # inst origen de obetiene del object (HEAC)
                        "institucion_destino": form.cleaned_data.get('seguimiento_referencia_institucion_destino'),
                        "motivo": instance.motivo,
                        "motivo_detalle": instance.motivo_detalle,
                        "atencion_requerida": instance.atencion_requerida,
                        "elaborada_por": instance.elaborada_por,
                        #area que refiere paso el campo como tal para podemos mapear
                        "area_refiere_sala": instance.area_reponde_sala,
                        "area_refiere_especialidad": instance.area_reponde_especialidad,
                        "area_refiere_servicio_auxiliar": instance.area_reponde_servicio_auxiliar,
                        "especialidad_destino": form.cleaned_data.get('seguimiento_referencia_especialidad_destino'),
                        "observaciones": instance.observaciones                    
                        },diagnosticos, usuario)
                        instance.seguimiento_referencia = nueva_ref
                instance.save()

                #procesar diagnosticos 
                RefDiagnosticoService.procesar_diagnosticos_respuesta(
                    respuesta_id=instance.id,
                    diagnosticos=diagnosticos
                )

                return JsonResponse({"success": True, "redirect_url": reverse_lazy('home')})
            
                

        except ValidationError as ve:
            # Error esperado por validaciones, mostrar mensaje amigable
            return JsonResponse({"success": False, "error": ve.message})

        except Exception as e:
            # logger.error(f"Error al registrar evaluación: {e}")
            return JsonResponse({"success": False, "error": f"Hubo un error al registrar la repuesta, inténtelo nuevamente. {e}"})
        

    def form_invalid(self, form):
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] 
        
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)


    def dispatch(self, request, *args, **kwargs):
        if not verificar_permisos_usuario(request.user, permisos.REFERENCIA_EDITOR_ROLES, permisos.REFERENCIA_EDITOR_UNIDADES):
            return JsonResponse({"success": False, "error": "No tiene permisos para registrar/actualizar este registro"})
        return super().dispatch(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):
        id_respuesta =  int(request.POST.get('idRespuesta')) if request.POST.get('idRespuesta') else None
        id_referencia =  int(request.POST.get('idReferencia')) if request.POST.get('idReferencia') else None
        id_paciente =  int(request.POST.get('idPaciente')) if request.POST.get('idPaciente') else None
        tipo_referencia = int(request.POST.get("tipo")) if request.POST.get("tipo") is not None else None

        data = request.POST.copy()


        # VALIDAR CAMPOS CLAVE
        if not (id_paciente and id_referencia and tipo_referencia is not None):
            return JsonResponse({
                'error': True,
                'errors': {'__all__': "Faltan campos importantes a consignar."}
            }, status=400)


        # VALIDAR REFERENCIA
        try:
            if id_respuesta == 0:  # CREACIÓN
                # Solo aquí validamos que la referencia exista y no tenga respuesta
                try:
                    referencia = validar_referencia_para_respuesta(id_referencia, id_paciente, tipo_referencia)
                except ValidationError as e:
                    return JsonResponse({
                        'error': True,
                        'errors': {'Referencia': str(e)}
                    }, status=400)

                self.referencia = referencia
                form = self.get_form(form_class=RespuestaCreateForm, data=data, principal_instance=referencia)

            else:  # EDICIÓN
                # Solo validamos que la respuesta exista y pertenezca a la referencia
                try:
                    respuesta = validar_respuesta_vs_referencia(id_respuesta, id_referencia)
                except ValidationError as e:
                    return JsonResponse({
                        'error': True,
                        'errors': {'Respuesta': str(e)}
                    }, status=400)

                form = self.get_form(form_class=RespuestaEditForm, data=data, instance=respuesta, principal_instance=respuesta.referencia)

        except ValidationError as e:
            return JsonResponse({
                'error': True,
                'errors': {'__all__': str(e)}
            }, status=400)  
    
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
        

class SeguimientoCreateUpdateView(View):
    
    def dispatch(self, request, *args, **kwargs):
        if not verificar_permisos_usuario(request.user, permisos.REFERENCIA_EDITOR_ROLES, permisos.REFERENCIA_EDITOR_UNIDADES):
            return JsonResponse({"guardo": False, "mensaje": "No tiene permisos para registrar/actualizar este registro"})
        return super().dispatch(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):

        usuario = request.user
        data = cargar_json(request.body)

        try:
            seguimiento_obj = {
                    "idSeguimiento": data.get("idSeguimiento"),
                    "idReferencia": data.get("idReferencia"),
                    "metodo": data.get("metodo"),
                    "establece_comunicacion": data.get("estableceComunicacion"),
                    "asistio_referencia": data.get("asistioReferencia"),
                    "fuente_info": data.get("fuenteInfo"),
                    "condicion_paciente": data.get("condicionPaciente"),
                    "observaciones": data.get("observaciones"),
                }

            seguimiento = SimpleNamespace(**seguimiento_obj)
            idSeguimiento = ReferenciaService.crear_actualizar_seguimiento(seguimiento, usuario)


            return JsonResponse({"guardo": True, "idSeguimiento":idSeguimiento, "mensaje": "Seguimiento guardado correctamente"})
        except ValueError as e:
            return JsonResponse({"guardo": False, "idSeguimiento": None, "mensaje": str(e) })
        except Exception:
            log_error(
                f"Error en vista seguimiento referencia {data.get('idReferencia')}",
                app=LogApp.REFERENCIAS
            )
            return JsonResponse({"guardo": False, "idSeguimiento": None, "mensaje": "Error interno, contacte al administrador"
    })

    

def obtener_seguimiento_tic(request):
    idSeguimiento = request.GET.get('id')

    # Validar parámetro requerido
    if not idSeguimiento:
        return JsonResponse({"error": "El parámetro 'id' es requerido."}, status=400)

    seguimiento = ReferenciaService.obtener_seguimiento_id(idSeguimiento)

    if not seguimiento:
        return JsonResponse({"error": "no_seguimiento"}, status=200)

    # Respuesta lista para el frontend
    return JsonResponse({
        "idSeguimiento": seguimiento.id,
        "idReferencia": seguimiento.referencia_id,
        "metodo": seguimiento.metodo_comunicacion,
        "establece_comunicacion": seguimiento.establece_comunicacion,
        "asistio_referencia": seguimiento.asistio_referencia,
        "fuente_info": seguimiento.fuente_info,
        "condicion_paciente": seguimiento.condicion_paciente.id if seguimiento.condicion_paciente else None,
        "observacion": seguimiento.observaciones,
        "fechaCreado": formatear_fecha_dd_mm_yyyy_hh_mm(seguimiento.fecha_registro),
        "creado_por": seguimiento.creado_por.username if hasattr(seguimiento, 'creado_por') and seguimiento.creado_por else None
    })

#vista que lista los pcientes # disponibles a todos lo suaurios y unidades
class listarReferencias(UnidadRolRequiredMixin,TemplateView):
    template_name = 'referencia/referencia_list.html'
    required_roles = permisos.REFERENCIA_VISUALIZACION_ROLES
    required_unidades = permisos.REFERENCIA_VISUALIZACION_UNIDADES


def listarEvaluacionrxAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', 1))
    order_direction = request.GET.get('order[0][dir]', 'desc')
    search_column = request.GET.get('search_column')
    fechaIni = request.GET.get('fecha_inicio')
    fechaFin = request.GET.get('fecha_fin')

    tz = timezone.get_current_timezone()

    try:
        # ========== FECHA FIN ==========
        if fechaFin:
            f_fin = datetime.strptime(fechaFin, '%Y-%m-%d').date()
        else:
            f_fin = timezone.localdate()  # solo fecha

        # Final del día: 23:59:59.999999, always aware
        fechaFin = timezone.make_aware(datetime.combine(f_fin, time.max), tz)

        # ========== FECHA INICIO ==========
        if fechaIni:
            f_ini = datetime.strptime(fechaIni, '%Y-%m-%d').date()
        else:
            f_ini = f_fin - timedelta(days=30)

        # Inicio del día: 00:00:00
        fechaIni = timezone.make_aware(datetime.combine(f_ini, time.min), tz)

    except ValueError:
        f_fin = timezone.localdate()
        fechaFin = timezone.make_aware(datetime.combine(f_fin, time.max), tz)

        f_ini = f_fin - timedelta(days=30)
        fechaIni = timezone.make_aware(datetime.combine(f_ini, time.min), tz)

    respuesta_subquery = Respuesta.objects.filter(referencia_id=OuterRef('id'))
    seguimiento_subquery = SeguimientoTic.objects.filter(referencia_id=OuterRef('id'))
    primer_diagnostico_subquery = (
        Referencia_diagnostico.objects
        .filter(referencia_id=OuterRef('id'))
        .order_by('id')
        .values('diagnostico__nombre_diagnostico')[:1]
    )

    referencia_qs = (
        Referencia.objects
        .annotate(
            fecha_filtro = Coalesce('fecha_recepcion', 'fecha_elaboracion'),

            institucion = Case(
                When(
                    tipo=0,
                    then=Concat(
                        F('institucion_origen__nivel_complejidad_institucional__siglas'),
                        Value('-'),
                        F('institucion_origen__nombre_institucion_salud')
                    )
                ),
                When(
                    tipo=1,
                    then=Concat(
                        F('institucion_destino__nivel_complejidad_institucional__siglas'),
                        Value('-'),
                        F('institucion_destino__nombre_institucion_salud')
                    )
                ),
                default=Value('Sin Institucion'),
                output_field=CharField()
            ),

            # Indicadores booleanos para la tabla
            tiene_respuesta = Exists(respuesta_subquery),
            tiene_seguimiento = Exists(seguimiento_subquery),
            tiene_no_atencion = Case(
                When(motivo_no_atencion__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            primer_diagnostico = Subquery(primer_diagnostico_subquery)
        )
        .filter(
            fecha_filtro__gte=fechaIni,
            fecha_filtro__lte=fechaFin,
            estado=1
        )
    )
    
    # Si se requiere búsqueda por nombre completo
    if search_column == '3' and search_value:
        referencia_qs = referencia_qs.annotate(
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
            
        ).filter(
            Q(nombre_completo_interno__icontains=search_value)
        )

    # Filtro por columnas específicas
    elif search_column and search_value:
        if search_column == '0':
            try:
                numero = int(search_value.lstrip("0"))
                referencia_qs = referencia_qs.filter(id=numero)
            except ValueError:
                referencia_qs = referencia_qs.none()
        elif search_column == '1':
            try:
                numero = int(search_value.lstrip("0"))
                referencia_qs = referencia_qs.filter(paciente__expediente_numero=numero)
            except ValueError:
                referencia_qs = referencia_qs.none()
        elif search_column == '2':
            dni_limpio = search_value.replace("-", "").strip()
            referencia_qs = referencia_qs.filter(
                Q(paciente__dni__icontains=dni_limpio)
            )
        elif search_column == '4':
            referencia_qs = referencia_qs.filter(
                Q(primer_diagnostico__icontains=search_value)
            )
        elif search_column == '5':
            referencia_qs = referencia_qs.filter(
                Q(institucion__icontains=search_value)
            )



    
    # Columnas para ordenamiento (deben coincidir con las columnas del DataTable)
    columns = [
        "id",                               # 0
        "tipo",                             # 1
        "fecha_filtro",                     # 2
        "institucion",                      # 3 
        "primer_diagnostico",               # 4
        "paciente__expediente_numero",      # 5
        "paciente__dni",                    # 6
        "paciente__primer_nombre",          # 7     
    ]

    # Mapea columnas que necesitan coalesce para evitar null en orden
    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            referencia_qs = referencia_qs.order_by(order_column_name)
        else:
            referencia_qs = referencia_qs.order_by('-' + order_column_name)


    # Conteo
    total_records = Referencia.objects.count()
    filtered_records = referencia_qs.count()
    
    refrencias = list(referencia_qs[start:start + length].values(
        "id",
        "tipo",
        "fecha_filtro",
        "institucion",
        "motivo__nombre_motivo_envio",
        "primer_diagnostico",
        "paciente__dni",
        "paciente__expediente_numero",
        "paciente__primer_nombre",
        "paciente__segundo_nombre",
        "paciente__primer_apellido",
        "paciente__segundo_apellido",
        "tiene_respuesta",
        "tiene_seguimiento",
        "tiene_no_atencion"
    ))
    
    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": refrencias #evaluaciones
    })
    