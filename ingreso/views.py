from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import TemplateView
from django.contrib import messages
from .forms import IngresoCreateForm, IngresoEditForm
from django.urls import reverse_lazy, reverse
from .models import Ingreso
from paciente.models import Paciente
from django.utils import timezone
from django import forms
from django.db import transaction
from django.utils.timezone import now 
from django.http.response import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from core.utils.utilidades_fechas import  formatear_fecha_simple,calcular_edad_texto, formatear_fecha2, formatear_fecha_dd_mm_yyyy,formatear_fecha_dd_mm_yyyy_hh_mm
from core.utils.utilidades_textos import formatear_nombre_completo, formatear_ubicacion_completo

from core.services.expediente_service import ExpedienteService
from core.services.ingreso.ingreso_service import IngresoService
from core.services.mapeo_camas_service import MapeoCamasService
from core.constants.permisos import (
    INGRESO_EDITOR_ROLES,
    INGRESO_EDITOR_UNIDADES,
    INGRESO_VISUALIZACION_ROLES,
    INGRESO_VISUALIZACION_UNIDADES,
)
from usuario.templatetags.permisos_unidad import tiene_rol
from core.services.recepcion_ingresos_service import RecepcionIngresoServiceSala, RecepcionIngresoServiceSDGI
from core.services.paciente_service import PacienteService
from usuario.permisos import verificar_permisos_usuario
import json
from django.views import View
from django.db.models import Q, F, Value, OuterRef, Subquery, CharField,Case, When
from django.db.models.functions import Coalesce, Concat
from datetime import datetime, timedelta

# Create your views here.
class IngresoAddView(UnidadRolRequiredMixin, CreateView):
    model = Ingreso 
    required_roles = INGRESO_EDITOR_ROLES
    required_unidades = INGRESO_EDITOR_UNIDADES
    form_class = IngresoCreateForm
    success_url = reverse_lazy('listar_ingresos') 

    def get_initial(self):
        initial = super().get_initial()
        zona_codigo_sesion = self.request.session.get('zona_codigo')
        if zona_codigo_sesion:
            initial['zona'] = zona_codigo_sesion
        return initial

    def form_valid(self, form):
        usuario_id = self.request.user.id
        zona = form.cleaned_data.get("zona", None)
        #paceinte validaddo en form clean 
        pacienteId = form.cleaned_data.get('idPaciente') or self.request.POST.get('idPaciente')


        if pacienteId or zona:
            # Buscar el tipo del paciente (por eficiencia: values_list y first)
            paciente_tipo = Paciente.objects.filter(id=pacienteId).values_list('tipo_id', flat=True).first()

            if paciente_tipo == 3:
                # Si es RN, la zona debe ser 3 sin importar lo demás
                form.instance.zona_id = 3
            elif zona.codigo == 3 and paciente_tipo != 3:
                # Si no es RN pero viene de Labor y Parto (zona 3), corregimos a zona 2
                form.instance.zona_id = 4

        if usuario_id:
            form.instance.creado_por_id = usuario_id
            form.instance.modificado_por_id = usuario_id
        
        


        if pacienteId:
            form.instance.paciente_id = pacienteId


        datos_acompaniante = self.extraer_datos_acompaniante()

        try:
            with transaction.atomic():
                acompaniante = IngresoService.procesar_acompaniante(**datos_acompaniante)
                if acompaniante:
                    form.instance.acompaniante = acompaniante
                #Cmabiar el eastdo de expediente
                if pacienteId:

                    cambio = ExpedienteService.cambiar_ubicacion(pacienteId, 2, usuario_id)
                    if not cambio:
                        raise Exception("No se logro cambiar la ubicacion del expediente")

                response = super().form_valid(form) # gurada l ingreo

                # Si el ingreso se guarda con cama y paciente, sincroniza la tabla
                # de asignacion para reutilizar o activar el registro de esa cama.
                if self.object.cama_id and self.object.paciente_id:
                    MapeoCamasService.sincronizar_cama_con_ingreso(
                        cama_id=self.object.cama_id,
                        paciente_id=self.object.paciente_id,
                        usuario=self.request.user,
                    )

                # Mensaje de éxito
                # URL del PDF
                pdf_url = reverse("reporte_hospitalizacion_26", kwargs={"ingreso_id": self.object.id})
                messages.success(self.request, "Ingreso registrado correctamente")

                return JsonResponse({"success": True, "pdf_url": pdf_url, "redirect_url": reverse_lazy('listar_ingresos') })

        except Exception as e:
            # Si ocurre cualquier error, se revertirá la transacción automáticamente
            transaction.rollback()  # Aunque esto es opcional, porque `atomic()` lo maneja
            messages.error(self.request, f"Hubo un error al registrar el ingreso: {str(e)}")
            return JsonResponse({"success": False, "error": f"Hubo un error al registrar el ingreso: {str(e)}"})
        return response

    def dispatch(self, request, *args, **kwargs):
        pkPaciente = self.kwargs.get('pk')  
        if pkPaciente == 0:
            return super().dispatch(request, *args, **kwargs)

        paciente = get_object_or_404(Paciente, id=pkPaciente)

        if not self.validar_puede_ingresar(paciente):
            return redirect(reverse_lazy('listar_pacientes'))

        return super().dispatch(request, *args, **kwargs)



    def validar_puede_ingresar(self, paciente):
        if IngresoService.tiene_ingreso_activo(paciente.id):
            messages.warning(self.request, "Este paciente ya tiene un ingreso activo.")
            return False

        if PacienteService.comprobar_defuncion(paciente):
            messages.warning(self.request, "El paciente ha fallecido.")
            return False

        if PacienteService.comprobar_inactivo(paciente.id):
            messages.warning(self.request, "El paciente está inactivo.")
            return False
        
        return True

    def extraer_datos_acompaniante(self):
        """Extrae datos del formulario según el tipo (madre/padre)."""
        return {
            
            "id": self.request.POST.get("acompanianteId", ""),
            "dni": self.request.POST.get("acompanianteDni", "").replace("-", "").upper(),
            "nombre1": self.request.POST.get("acompanianteNombre1", "").strip().upper(),
            "nombre2": self.request.POST.get("acompanianteNombre2", "").strip().upper(),
            "apellido1": self.request.POST.get("acompanianteApellido1", "").strip().upper(),
            "apellido2": self.request.POST.get("acompanianteApellido2", "").strip().upper(),
            "sector": self.request.POST.get("sector", "").strip().upper(),
            "telefono": self.request.POST.get("telefono", "").strip(),
                    
        }

    def form_invalid(self, form):
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] 
        
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)
    
    def get_form(self, form_class = None):
        form = super().get_form(form_class)

        paciente_id = self.kwargs.get("pk")
        asignar_propiedades_campos_paciente(form)  

        #campos que pertencen a ingreso
        form.fields['observaciones'].widget.attrs.update({
            'class': 'formularioCampo-select','placeholder':'Observaciones'
            })
        
        form.fields['idPaciente'] = forms.CharField(
            widget=forms.HiddenInput(attrs={'required': 'required'}),
            initial=None,  
            required=True  
            )
            

        if paciente_id and paciente_id != 0:
            paciente = get_object_or_404(
                Paciente.objects.select_related(
                    'sector__aldea__municipio__departamento'
                ), pk=paciente_id
            )
            numero_expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id)

            if numero_expediente and not paciente.estado == "I":
                llenar_datos_campos_paciente(form, paciente, numero_expediente)

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
        context['titulo'] = 'Agregar Ingreso'
        context['subtitulo'] = 'Agregando'
        context['MD'] = 1
        context['fecha_hoy'] = formatear_fecha2(now(), '%A %d de %B del %Y, %H:%M:%S')

        return context

class IngresoEditView(UnidadRolRequiredMixin, UpdateView):
    model = Ingreso
    required_roles = INGRESO_VISUALIZACION_ROLES
    required_unidades = INGRESO_VISUALIZACION_UNIDADES
    form_class = IngresoEditForm
    success_url = reverse_lazy('listar_ingresos') 
    
    #no requiere validacion para servri mas que los permisos para ver
    
    def form_valid(self, form):
        usuario = self.request.user
        zona = form.cleaned_data.get("zona", None)
        paciente = form.cleaned_data.get("paciente", None)
        #paceinte validaddo en form clean 

        if not verificar_permisos_usuario(
            usuario,
            INGRESO_EDITOR_ROLES,
            INGRESO_EDITOR_UNIDADES):
            return JsonResponse({"success": False, "error": f"No tiene permiso para editar el ingreso"})
        

        if usuario.id:
            form.instance.modificado_por_id = usuario.id

        # Se toma una foto del ingreso antes de guardar para saber cual era la
        # cama anterior y poder cerrar esa asignacion correctamente.
        ingreso_anterior = Ingreso.objects.filter(pk=self.object.pk).values(
            "cama_id",
            "paciente_id",
        ).first()
        cama_anterior_id = ingreso_anterior.get("cama_id") if ingreso_anterior else None
        paciente_anterior_id = ingreso_anterior.get("paciente_id") if ingreso_anterior else None

        datos_acompaniante = self.extraer_datos_acompaniante()

        
        if paciente.tipo_id and zona:
            # Buscar el tipo del paciente (por eficiencia: values_list y first)
            if paciente.tipo_id == 3:
                # Si es RN, la zona debe ser 3 sin importar lo demás
                form.instance.zona_id = 3
            elif zona.codigo == 3 and paciente.tipo_id != 3:
                # Si no es RN pero viene de Labor y Parto (zona 3), corregimos a zona 4
                form.instance.zona_id = 4


        try:
            with transaction.atomic():
                acompaniante = IngresoService.procesar_acompaniante(**datos_acompaniante)
                if acompaniante:
                    form.instance.acompaniante = acompaniante
                #Cmabiar el eastdo de expediente

                response = super().form_valid(form) # gurada l ingreo

                # Solo sincronizamos camas si el paciente sigue siendo el mismo.
                # En ese caso la cama anterior se cierra y la cama nueva se activa.
                if paciente_anterior_id == self.object.paciente_id and self.object.paciente_id:
                    MapeoCamasService.sincronizar_cambio_cama_en_ingreso(
                        cama_anterior_id=cama_anterior_id,
                        cama_nueva_id=self.object.cama_id,
                        paciente_id=self.object.paciente_id,
                        usuario=usuario,
                    )

                return JsonResponse({"success": True,"redirect_url": reverse_lazy('listar_ingresos') })

        except Exception as e:
            # Si ocurre cualquier error, se revertirá la transacción automáticamente
            transaction.rollback()  # Aunque esto es opcional, porque `atomic()` lo maneja
            messages.error(self.request, f"Se presento un error al registrar el ingreso: {str(e)}")
            return JsonResponse({"success": False, "error": f"Hubo un error al registrar el ingreso: {str(e)}"})
        return response
    

    def form_invalid(self, form):
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = error_list[0] 
        
        return JsonResponse({
            'success': False,
            'errors': errors
        }, status=400)

    #preparar como se comportara el form.
    def get_form(self, form_class = None):
        form = super().get_form(form_class)
        #servir desde backen todo lo referente al ingreo y sus relaciones

        ingreso = self.object
        paciente = ingreso.paciente
        numero_expediente = ExpedienteService.obtener_expediente_activo_paciente(paciente.id) 
        #campos del ingreso como tal 

        
        form.fields['observaciones'].widget.attrs.update({
            'class': 'formularioCampo-select','placeholder':'Observaciones'
            })
            #fecha de ingreso envia por contexto
        
        #campos paciente
        form.fields['idPaciente'] = forms.CharField(
        widget=forms.HiddenInput(attrs={'required': 'required'}),
        initial=paciente.id,
        required=True  
        )

        asignar_propiedades_campos_paciente(form)
        llenar_datos_campos_paciente(form, paciente, numero_expediente)

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ingreso = self.object 
        context['titulo'] = 'Editar ingreso'
        context['subtitulo'] = 'Editando'
        context['MD'] = 2

        # Fechas
        fIngreso = formatear_fecha_dd_mm_yyyy_hh_mm(ingreso.fecha_ingreso)
        fEgreso = formatear_fecha_dd_mm_yyyy_hh_mm(ingreso.fecha_egreso) if ingreso.fecha_egreso else "Pendiente"
        fSDGI = formatear_fecha_dd_mm_yyyy_hh_mm(ingreso.fecha_recepcion_sdgi) if ingreso.fecha_recepcion_sdgi else "Pendiente"
        context['fechas_egreso_sdgi'] = f"{fIngreso}  | {fEgreso}  | {fSDGI}"

        # Acompañante
        if ingreso.acompaniante:
            sector = ingreso.acompaniante.sector
            aldea = sector.aldea if sector else None
            municipio = aldea.municipio if aldea else None
            departamento = municipio.departamento if municipio else None

            acompaniante = {
                "id": ingreso.acompaniante.id or "",
                "dni": ingreso.acompaniante.dni or "",
                "primer_nombre": ingreso.acompaniante.primer_nombre or "",
                "segundo_nombre": ingreso.acompaniante.segundo_nombre or "",
                "primer_apellido": ingreso.acompaniante.primer_apellido or "",
                "segundo_apellido": ingreso.acompaniante.segundo_apellido or "",
                "telefono": ingreso.acompaniante.telefono or "",
                "sector_id": sector.id if sector else "",
                "sector_nombre": sector.nombre_sector if sector else "",
                "departamento_id": departamento.id if departamento else "",
                "departamento_nombre": departamento.nombre_departamento if departamento else "",
                "municipio_id": municipio.id if municipio else "",
                "municipio_nombre": municipio.nombre_municipio if municipio else "",
            }

            context['acompaniante'] = json.dumps(acompaniante)

        #paciente ver si requiere mascara o no
        extranjero = ingreso.paciente.get_extranjeroPasaporte()
        context['extranjero'] = extranjero

        #modo solo lectura 
        context['solo_lectura'] = (
            (ingreso.fecha_recepcion_sdgi is not None) or 
            (tiene_rol(self.request.user, "auditor:DIRECTIVOS,visitante:Admision") and not self.request.user.is_superuser)
        )

        return context



    def extraer_datos_acompaniante(self):
        """Extrae datos del formulario según el tipo (madre/padre)."""
        return {
            
            "id": self.request.POST.get("acompanianteId", None),
            "dni": self.request.POST.get("acompanianteDni", "").replace("-", "").upper(),
            "nombre1": self.request.POST.get("acompanianteNombre1", "").strip().upper(),
            "nombre2": self.request.POST.get("acompanianteNombre2", "").strip().upper(),
            "apellido1": self.request.POST.get("acompanianteApellido1", "").strip().upper(),
            "apellido2": self.request.POST.get("acompanianteApellido2", "").strip().upper(),
            "sector": self.request.POST.get("sector", "").strip().upper(),
            "telefono": self.request.POST.get("telefono", "").strip(),
                    
        }

#METODO PARA LOS GET FOM DE AMBAS VISTAS BASADAS EN CLASES 
def asignar_propiedades_campos_paciente(form):
    campos = [
        'dniPaciente',
        'numeroExpediente',
        'nombreCompletoPaciente',
        'fechaNacimientoPaciente',
        'edadPaciente',
        'sexoPaciente',
        'telefonoPaciente',
        'direccionPaciente'
    ]

    for campo in campos:
        if campo in form.fields:
            form.fields[campo].widget.attrs.update({
                'class': 'formularioCampo-select',
                'placeholder': campo.replace("Paciente", "").replace("_", " ").capitalize(),
                'disabled': True
            })

def llenar_datos_campos_paciente(form, paciente, numero_expediente=None):
    form.fields['dniPaciente'].initial = paciente.dni
    form.fields['numeroExpediente'].initial = str(numero_expediente).zfill(7) if numero_expediente else None
    form.fields['nombreCompletoPaciente'].initial = formatear_nombre_completo(
        paciente.primer_nombre, paciente.segundo_nombre,
        paciente.primer_apellido, paciente.segundo_apellido
    )
    form.fields['fechaNacimientoPaciente'].initial = formatear_fecha_simple(paciente.fecha_nacimiento)
    form.fields['edadPaciente'].initial = calcular_edad_texto(str(paciente.fecha_nacimiento))
    form.fields['sexoPaciente'].initial = paciente.get_sexo_display()
    form.fields['telefonoPaciente'].initial = paciente.telefono
    form.fields['direccionPaciente'].initial = formatear_ubicacion_completo(
        paciente.sector.aldea.municipio.departamento.nombre_departamento,
        paciente.sector.aldea.municipio.nombre_municipio,
        paciente.sector.nombre_sector
    )

def obtener_acompaniante(request):
    dni = request.GET.get('DNI')

    if not dni:  # Verifica si el parámetro no está presente o está vacío
        return JsonResponse({"error": "El parámetro 'dni' es requerido."}, status=400)

    acompaniante = IngresoService.obtener_acompaniante(dni)
  
    
    if not acompaniante:
        return JsonResponse({"mensaje": "No se encontró un acompaniante con ese número de dni."}, status=200)

    # Construir la respuesta con los datos del paciente
    return JsonResponse(acompaniante)

def validar_ingreso_activo(request):
    # Obtener el id del paciente del request GET
    id_paciente = request.GET.get('idP')

    if not id_paciente:
        # Retorna un error si no se pasó el idP
        return JsonResponse({'error': 'El parámetro idP es requerido'}, status=400)

    # Verificar si el paciente tiene un ingreso activo
    ingreso_activo = IngresoService.tiene_ingreso_activo(id_paciente)
    # Retornar la respuesta con el estado del ingreso
    return JsonResponse({'ingresoActivo': ingreso_activo})

class RecepcionIngresosSala(View):
    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario, INGRESO_EDITOR_ROLES, INGRESO_EDITOR_UNIDADES):
            return redirect(reverse_lazy('acceso_denegado'))
        
        return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        try:
            salasConIngresos = IngresoService.obtener_salas_con_ingresos_activos()
            ingresosActivos = IngresoService.obtener_ingresos_activos()
            ingresos = list(ingresosActivos)

            for ingreso in ingresos:
                if ingreso['fecha_ingreso']:
                    ingreso['fecha_ingreso'] = formatear_fecha_dd_mm_yyyy(ingreso['fecha_ingreso'])
                

            context = {
                'responsable': f"{request.user.username} | {request.user.first_name} {request.user.last_name}",
                'fecha_actual': now(),
                'salas': salasConIngresos,
                'ingresos': json.dumps(ingresos),
            }

            return render(request, 'ingreso/recepcion_ingresos_sala.html', context)
        
        except Exception as e:
            # Aquí podrías registrar el error si usas logging
            messages.warning(request, "Ha ocurrido un error al cargar la información.")
            return redirect(reverse_lazy('home'))


def registrarRecepcionIngresosSala(request):
    usuario = request.user
    if not verificar_permisos_usuario(usuario,  INGRESO_EDITOR_ROLES, INGRESO_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            observacion = data.get('observaciones')
            ingresos = data.get('ingresos', [])

            if not ingresos:
                return JsonResponse({'error': 'No se proporcionaron ingresos'}, status=400)

            # Validación básica de estructura de cada ingreso
            for ingreso in ingresos:
                if not ingreso.get('id') or not ingreso.get('idSala') or not ingreso.get('idPaciente'):
                    return JsonResponse({'error': 'Datos incompletos en uno de los ingresos'}, status=400)

            # Llamar al servicio
            resultado = RecepcionIngresoServiceSala.procesar_recepcion_ingreso_sala (observacion, ingresos, usuario)

            #mostrar el comporbante que todo salio bien 
            pdf_url = reverse("reporte_detalle_recepcion_ingresos_sala", kwargs={"recepcion_id":resultado['idRecepcion'] })
            return JsonResponse({"success": True, 'message': resultado['mensaje'],"pdf_url": pdf_url, "redirect_url": reverse_lazy('listar_ingresos') })


        except Exception as e:
            return JsonResponse(
                {'error': 'Error interno al procesar la recepción de ingresos'},
                status=500
            )

    return JsonResponse({'error': 'Metodo no permitido'}, status=405)



class RecepcionIngresosSDGI(View):
    def dispatch(self, request, *args, **kwargs):
        usuario = request.user
        if not verificar_permisos_usuario(usuario,  INGRESO_EDITOR_ROLES, INGRESO_EDITOR_UNIDADES):
            return redirect(reverse_lazy('acceso_denegado'))
        
        return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        try:

            ingresosSDGI = IngresoService.obtener_ingresos_SDGI()
            ingresosSDGI = list(ingresosSDGI)

            for ingreso in ingresosSDGI:
                if ingreso['fecha_ingreso']:
                    ingreso['fecha_ingreso'] = formatear_fecha_dd_mm_yyyy(ingreso['fecha_ingreso'])
                
                if ingreso['fecha_egreso']:
                    ingreso['fecha_egreso'] = formatear_fecha_dd_mm_yyyy(ingreso['fecha_egreso'])

            context = {
                'responsable': f"{request.user.username} | {request.user.first_name} {request.user.last_name}",
                'fecha_actual': now(),
                'ingresos': json.dumps(ingresosSDGI),
            }


            return render(request, 'ingreso/recepcion_ingresos_sdgi.html', context)
        
        except Exception as e:
            # Aquí podrías registrar el error si usas logging
            messages.warning(request, f"Ha ocurrido un error al cargar la información.{e}")
            return redirect(reverse_lazy('home'))



def registrarRecepcionIngresosSDGI(request):
    usuario = request.user
    if not verificar_permisos_usuario(usuario, INGRESO_EDITOR_ROLES, INGRESO_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            observacion = data.get('observaciones')
            ingresos = data.get('ingresos', [])

            if not ingresos:
                return JsonResponse({'error': 'No se proporcionaron ingresos'}, status=400)

            # Validación básica de estructura de cada ingreso

            for ingreso in ingresos:
                #print(ingreso)
                if not ingreso.get('id') or not ingreso.get('idPaciente'):
                    return JsonResponse({'error': 'Datos incompletos en uno de los ingresos'}, status=400)

            # Llamar al servicio
            resultado = RecepcionIngresoServiceSDGI.procesar_recepcion_ingreso_sdgi (observacion, ingresos, usuario)

 
            #mostrar el comporbante que todo salio bien 
            pdf_url = reverse("reporte_detalle_recepcion_ingresos_sdgi", kwargs={"recepcion_id":resultado['idRecepcion'] })
            return JsonResponse({"success": True, 'message': resultado['mensaje'],"pdf_url": pdf_url, "redirect_url": reverse_lazy('listar_ingresos') })

        except Exception as e:
            return JsonResponse(
                {'error': 'Error interno al procesar la recepción de ingresos SDGI'},
                status=500
            )

    return JsonResponse({'error': 'Método no permitido'}, status=405)

#vista que lista los pcientes
class listarIngresos(UnidadRolRequiredMixin,TemplateView):
    template_name = 'ingreso/ingreso_list.html'
    required_roles = INGRESO_VISUALIZACION_ROLES
    required_unidades = INGRESO_VISUALIZACION_UNIDADES

#retorna el Json que alimento el Datatables Ingresos

def listarIngresosAPI(request):
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search_value', '').strip()
    order_column = int(request.GET.get('order[0][column]', 0))
    order_direction = request.GET.get('order[0][dir]', 'desc')
    search_column = request.GET.get('search_column')
    fechaIni = request.GET.get('fecha_inicio')
    fechaFin = request.GET.get('fecha_fin')

    # Validar fechas
    tz = timezone.get_current_timezone()

    try:
        if fechaFin:
            # Fin del día: 2025-06-26 23:59:59.999999
            fechaFin = timezone.make_aware(datetime.strptime(fechaFin, '%Y-%m-%d'), timezone=tz)
            fechaFin = fechaFin.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            fechaFin = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=999999)

        if fechaIni:
            # Inicio del día: 2025-06-01 00:00:00
            fechaIni = timezone.make_aware(datetime.strptime(fechaIni, '%Y-%m-%d'), timezone=tz)
            fechaIni = fechaIni.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            fechaIni = fechaFin - timedelta(days=30)
            fechaIni = fechaIni.replace(hour=0, minute=0, second=0, microsecond=0)

    except ValueError:
        fechaFin = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=999999)
        fechaIni = fechaFin - timedelta(days=30)
        fechaIni = fechaIni.replace(hour=0, minute=0, second=0, microsecond=0)

    # Query base
    ingresos_qs = Ingreso.objects.filter(
        fecha_ingreso__gte=fechaIni,
        fecha_ingreso__lte=fechaFin,
        estado=1 #solo lo activos 
    )

    # Si se requiere búsqueda por nombre completo
    if search_column == '3' and search_value:
        ingresos_qs = ingresos_qs.annotate(
            nombre_completo=Concat(
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
            )
        ).filter(nombre_completo__icontains=search_value)

    # Filtro por columnas específicas
    elif search_column and search_value:
        if search_column == '0':
            try:
                numero = int(search_value.lstrip("0"))
                ingresos_qs = ingresos_qs.filter(id=numero)
            except ValueError:
                ingresos_qs = ingresos_qs.none()
        elif search_column == '1':
            try:
                numero = int(search_value.lstrip("0"))
                ingresos_qs = ingresos_qs.filter(paciente__expediente_numero=numero)
            except ValueError:
                ingresos_qs = ingresos_qs.none()
        elif search_column == '2':
            dni_limpio = search_value.replace("-", "").strip()
            ingresos_qs = ingresos_qs.filter(paciente__dni__iexact=dni_limpio)

    # Columnas para ordenamiento (deben coincidir con las columnas del DataTable)
    columns = [
        "id",                            # 0
        "fecha_ingreso",                # 1
        "fecha_egreso",                 # 2
        "fecha_recepcion_sdgi",        # 3
        "sala__nombre_sala",           # 4
        "paciente__expediente_numero", # 5
        "paciente__dni",               # 6
        "paciente__primer_nombre",     # 7
    ]

    if order_column < len(columns):
        order_column_name = columns[order_column]
        if order_direction == 'asc':
            ingresos_qs = ingresos_qs.order_by(order_column_name)
        else:
            ingresos_qs = ingresos_qs.order_by('-' + order_column_name)

    # Conteo
    total_records = Ingreso.objects.count()
    filtered_records = ingresos_qs.count()

    # Paginación + datos
    ingresos = list(ingresos_qs[start:start + length].values(
        "id",
        "fecha_ingreso",
        "fecha_egreso",
        "fecha_recepcion_sdgi",
        "sala__nombre_sala",
        "sala__servicio__nombre_corto",
        "paciente__expediente_numero",
        "paciente__dni",
        "paciente__primer_nombre",
        "paciente__segundo_nombre",
        "paciente__primer_apellido",
        "paciente__segundo_apellido",
        "modificado_por__username",
        "fecha_modificado"
    ))

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": ingresos
    })


def listarIngresosPacienteAPI(request):
    id_paciente = request.GET.get('id_paciente')
    if not id_paciente:
        return JsonResponse({"error": "Parámetro 'id_paciente' es requerido."}, status=400)

    ingresos = IngresoService.listar_ingresos_por_paciente(id_paciente)
    return JsonResponse({"data": ingresos})


def inactivarIngreso(request):
    if not verificar_permisos_usuario(request.user, INGRESO_EDITOR_ROLES, INGRESO_EDITOR_UNIDADES):
        return JsonResponse({'error': 'No tienes permisos para realizar esta accion'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            idIngreso = data.get('id')
            if idIngreso:
                if Ingreso.objects.filter(id=idIngreso).exists():
                    # La inactivacion delega el cierre de cama al servicio para que
                    # el ingreso y la asignacion queden consistentes en una sola operacion.
                    resultado = IngresoService.inactivar_ingreso(idIngreso, request.user)
                    if resultado:
                        return JsonResponse({"success": resultado })
                    else:
                        return JsonResponse({"success": resultado,"error": "NO es posible inactivar este ingreso" })
                else:
                    return JsonResponse({"success": False, "error": "El id proporcionado no petenece a ningun ingreso existente"}, status=400)
            else:
                return JsonResponse({"success": False, "error": "El parametro id es obligatorio"}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Error al procesar los datos JSON"}, status=400)
    
    return JsonResponse({"success": False, "error": "Metodo no permitido"}, status=405)
