from django.shortcuts import render
import json
from datetime import datetime
from types import SimpleNamespace

from core.utils.utilidades_textos import formatear_nombre_completo
from core.utils.utilidades_fechas import formatear_fecha_dd_mm_yyyy_hh_mm, formatear_fecha_dd_mm_yyyy
from usuario.permisos import verificar_permisos_usuario


from core.services.atencion_service import AtencionService
from core.services.paciente_service import PacienteService
from core.services.recepcion_atenciones_service import RecepcionAtencionService
from core.mixins import UnidadRolRequiredMixin
from core.constants import permisos
from django.http.response import JsonResponse
from datetime import datetime, timedelta, time
from django.db.models import  F, Value, CharField,Case, When

from paciente.models import Paciente
from atencion.models import Atencion
from django.db.models.functions import Concat
from django.views import View
from django.views.generic import TemplateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import  redirect
from django.utils.timezone import now 
from django.utils import timezone
from django.contrib import messages
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *


# Create your views here.

def guardarAtencion(request):
   if not verificar_permisos_usuario(request.user, permisos.ATENCION_EDITOR_ROLES, permisos.ATENCION_EDITOR_UNIDADES):
      return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)


   if request.method == 'POST':
      try:
         data = json.loads(request.body)

         #validaciones      

         #validacion de la fecha 
         fecha_str = data.get('fecha')
         try:
               fecha_sola = datetime.strptime(fecha_str, '%Y-%m-%d').date()

               # Combinar con hora al mediodía
               fecha_naive = datetime.combine(fecha_sola, time(12, 0))

               # Convertir a fecha con zona horaria
               fecha_aware = timezone.make_aware(fecha_naive, timezone.get_current_timezone())

               if fecha_aware.date() > timezone.now().date():
                  return JsonResponse({'error': 'La fecha no puede ser futura'}, status=400)
         except ValueError:
               return JsonResponse({'error': 'Formato de fecha inválido. Se espera YYYY-MM-DD'}, status=400)
         
         #validacion del paciente 
         pacienteId = data.get('idPaciente')
         try:
            paciente = Paciente.objects.get(id=pacienteId)

            # Verificar si está fallecido
            if PacienteService.comprobar_defuncion(paciente):
               return JsonResponse({'error': 'No puedes registrar una atencion para un paciente fallecido.'}, status=400)    

            # Verificar si está inactivo
            if PacienteService.comprobar_inactivo(paciente.id):
               return JsonResponse({'error': 'No puedes registrar una atencion para un paciente inactivo.'}, status=400)    




         except Paciente.DoesNotExist:
            return JsonResponse({'error': 'Paciente no registrado en la base de datos'}, status=400)


         atencion_obj = {
               "fecha": fecha_aware,
               "especialidad_id": data.get('especialidad'),
               "observaciones": data.get('observaciones'),
               "paciente_id": pacienteId,
               "id": data.get('idAtencion'),
               "usuario_id": request.user.id
         }



         atencion = SimpleNamespace(**atencion_obj)
         resultado = AtencionService.procesar_atencion(atencion)

         return JsonResponse({'guardo': resultado}, status=200)

      except json.JSONDecodeError:
         return JsonResponse({'error': 'Error al procesar los datos JSON'}, status=400)

   return JsonResponse({'error': 'Método no permitido'}, status=405)

#verifica si un apciente tiene una atencion muy reciente
def verificar_atencion_h(request):
   try:
      # Obtener el id del paciente del request GET
      id_paciente = request.GET.get('idP')
      if not id_paciente:
            return JsonResponse({'error': 'El parámetro idP es requerido'}, status=400)

      # Consultar la última atención reciente
      reciente = AtencionService.verificar_atencion_hora(id_paciente)

      if reciente:
            nombre_completo = formatear_nombre_completo(
               reciente['paciente__primer_nombre'],
               reciente.get('paciente__segundo_nombre'),
               reciente['paciente__primer_apellido'],
               reciente.get('paciente__segundo_apellido')
            )

            return JsonResponse({
               'reciente': True,
               'id': reciente['id'],
               'nombre': nombre_completo,
               'especialidad': reciente.get('especialidad__nombre_especialidad'),
               'sala': reciente.get('sala__sala_nombre'),
               'fecha_creado': formatear_fecha_dd_mm_yyyy_hh_mm(reciente.get('fecha_creado'))
            })

      # Si no hay atención reciente
      return JsonResponse({'reciente': False})

   except Exception as e:
      # Captura cualquier error inesperado
      return JsonResponse({'error': f'Ocurrió un error: {str(e)}'}, status=500)


#vista que lista los pcientes
class listarAtenciones(UnidadRolRequiredMixin,TemplateView):
   template_name = "atencion/atencion_list.html"
   required_roles = permisos.ATENCION_VISUALIZACION_ROLES
   required_unidades = permisos.ATENCION_VISUALIZACION_UNIDADES

#sirve ak datatables que lista las atenciones
def listarAtencionesAPI(request):
   draw = int(request.GET.get('draw', 0))
   start = int(request.GET.get('start', 0))
   length = int(request.GET.get('length', 10))
   search_value = request.GET.get('search_value', '').strip()
   order_column = int(request.GET.get('order[0][column]', 0))
   order_direction = request.GET.get('order[0][dir]', 'desc')
   search_column = request.GET.get('search_column')
   fechaIni = request.GET.get('fecha_inicio')
   fechaFin = request.GET.get('fecha_fin')

   # Validar fechas con zona horaria
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

   # Consulta base
   atenciones_qs = Atencion.objects.filter(
      fecha_atencion__gte=fechaIni,
      fecha_atencion__lte=fechaFin
   )

   # Búsqueda por nombre completo (solo si aplica)
   if search_column == '3' and search_value:
      atenciones_qs = atenciones_qs.annotate(
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

   elif search_column and search_value:
      if search_column == '0':
         try:
               numero = int(search_value.lstrip("0"))
               atenciones_qs = atenciones_qs.filter(id=numero)
         except ValueError:
               atenciones_qs = atenciones_qs.none()
      elif search_column == '1':
         try:
               numero = int(search_value.lstrip("0"))
               atenciones_qs = atenciones_qs.filter(paciente__expediente_numero=numero)
         except ValueError:
               atenciones_qs = atenciones_qs.none()
      elif search_column == '2':
         dni_limpio = search_value.replace("-", "").strip()
         atenciones_qs = atenciones_qs.filter(paciente__dni__iexact=dni_limpio)

   # Columnas del DataTable
   columns = [
      "id",                                # 0
      "fecha_atencion",                    # 1
      "fecha_recepcion",                   # 2
      "especialidad__nombre_especialidad", # 3
      "paciente__expediente_numero",       # 4
      "paciente__dni",                     # 5
      "paciente__primer_nombre",           # 6
   ]

   if order_column < len(columns):
      order_column_name = columns[order_column]
      if order_direction == 'asc':
         atenciones_qs = atenciones_qs.order_by(order_column_name)
      else:
         atenciones_qs = atenciones_qs.order_by('-' + order_column_name)

   # Conteo
   total_records = Atencion.objects.count()
   filtered_records = atenciones_qs.count()

   # Paginación + valores
   atenciones = list(atenciones_qs[start:start + length].values(
      "id",
      "fecha_atencion",
      "fecha_recepcion",
      "especialidad__nombre_especialidad",
      "especialidad__servicio__nombre_corto",
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
      "data": atenciones
   })


def obtener_atencion(request):
   id = request.GET.get('id')
   usuario = request.user

   if not id:  
      return JsonResponse({"error": "El parámetro 'id' es requerido."}, status=400)

   atencion = AtencionService.obtener_atencion(id)
   recepcion = atencion.recepcion_detalles_atencion.select_related('recepcion__recibido_por').first()

   if not atencion:
      return JsonResponse({"mensaje": "No hay atención"}, status=200)

   # editable: True si el usuario tiene permisos, False si solo lectura
   editable = verificar_permisos_usuario(usuario, permisos.ATENCION_EDITOR_ROLES, permisos.ATENCION_EDITOR_UNIDADES)


   # Construir la respuesta con los datos del paciente
   return JsonResponse({
      "id": atencion.id,
      "idEspecialidad": atencion.especialidad.id,
      "especialidadNombre": atencion.especialidad.nombre_especialidad,
      "pacienteNombre1": atencion.paciente.primer_nombre,
      "pacienteNombre2": atencion.paciente.segundo_nombre,
      "pacienteApellido1": atencion.paciente.primer_apellido,
      "pacienteApellido2": atencion.paciente.segundo_apellido,
      "pacienteId": atencion.paciente.id,
      "idServicio": atencion.especialidad.servicio.id,
      "fecha": atencion.fecha_atencion,
      "observaciones": atencion.observaciones,
      "fechaRecepcion": atencion.fecha_recepcion,
      "recibidoPor":recepcion.recepcion.recibido_por.username if recepcion else None,
      "creado_por": atencion.creado_por.username, 
      "modificado_por": atencion.modificado_por.username, 
      "fecha_creado": atencion.fecha_creado, 
      "fecha_modificado": atencion.fecha_modificado,
      "editable": editable  # True/False
   })


class RecepcionAtenciones(View):
    def dispatch(self, request, *args, **kwargs):
      usuario = request.user
      if not verificar_permisos_usuario(usuario, permisos.ATENCION_EDITOR_ROLES, permisos.ATENCION_EDITOR_UNIDADES):
         return redirect(reverse_lazy('acceso_denegado'))
      
      return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
      try:
         serviciosAtenciones = AtencionService.obtener_servicio_atenciones_activas()
         atencionesActivas = AtencionService.obtener_atenciones_activas()
         atenciones = list(atencionesActivas)

         for atencion in atenciones:
               if atencion['fecha_atencion']:
                  atencion['fecha_atencion'] = formatear_fecha_dd_mm_yyyy(atencion['fecha_atencion'])
               



         context = {
               'responsable': f"{request.user.username} | {request.user.first_name} {request.user.last_name}",
               'fecha_actual': now(),
               'servicios': serviciosAtenciones,
               'atenciones': json.dumps(atenciones),
         }


         return render(request, 'atencion/recepcion_atenciones.html', context)
      
      except Exception as e:
         # Aquí podrías registrar el error si usas logging
         messages.warning(request, "Ha ocurrido un error al cargar la información.")


def registrarRecepcionAtencion(request):
   usuario = request.user
   if not verificar_permisos_usuario(usuario, permisos.ATENCION_EDITOR_ROLES, permisos.ATENCION_EDITOR_UNIDADES):
      return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)

   if request.method == "POST":
      try:
         data = json.loads(request.body)
         observacion = data.get('observaciones')
         atenciones = data.get('atenciones', [])

         if not atenciones:
               return JsonResponse({'error': 'No se proporcionaron ingresos'}, status=400)

         # Validación básica de estructura de cada ingreso
         for atencion in atenciones:
               if not atencion.get('id') or not atencion.get('idServicio') or not atencion.get('idPaciente'):
                  return JsonResponse({'error': 'Datos incompletos en una de las atenciones'}, status=400)

         # Llamar al servicio
         resultado = RecepcionAtencionService.procesar_recepcion_atencion(observacion, atenciones, usuario)

         #mostrar el comporbante que todo salio bien 
         pdf_url = reverse("reporte_detalle_recepcion_atenciones", kwargs={"recepcion_id":resultado['idRecepcion'] })
         return JsonResponse({"success": True, 'message': resultado['mensaje'],"pdf_url": pdf_url, "redirect_url": reverse_lazy('listar_atenciones') })


      except Exception as e:
         log_error(
            f"[FALLO_RECEPCION_ATENCION] usuario={usuario.id} detalle={str(e)}",
            app=LogApp.ATENCION
         )

         return JsonResponse(
            {'error': 'Ocurrió un error al procesar la recepción de atenciones'},
            status=500
         )

   return JsonResponse({'error': 'Método no permitido'}, status=405)


def listarAtencionPacienteAPI(request):
   id_paciente = request.GET.get('id_paciente')
   if not id_paciente:
      return JsonResponse({"error": "Parámetro 'id_paciente' es requerido."}, status=400)

   atenciones = AtencionService.listar_atenciones_por_paciente(id_paciente)
   return JsonResponse({"data": atenciones})


