from django.shortcuts import render
from core.mixins import UnidadRolRequiredMixin
from core.services.comunicacion_hospitalaria.comunicacion_labor_parto_service import LaborPartoService
from django.views.generic import TemplateView
from core.constants.permisos import COMUNICACION_HOSPITALARIA_VISUALIZACION_ROLES, COMUNICACION_HOSPITALARIA_VISUALIZACION_UNIDADES, COMUNICACION_HOSPITALARIA_EDICION_ROLES, COMUNICACION_HOSPITALARIA_EDICION_UNIDADES
from core.constants.choices_constants import EstadoLaborParto
from core.constants.domain_constants import UNIDADES_ENTRADA_LABOR_PARTO, UNIDADES_SALIDA_LABOR_PARTO
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from usuario.permisos import verificar_permisos_usuario
from comunicacion_hospitalaria.validators import LaborPartoValidator
from core.utils.utilidades_request import parse_json_request
from core.validators.main_validator import validar_entero_positivo
from django.core.exceptions import ValidationError
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *
from types import SimpleNamespace

# Create your views here.
# Create your views here.
class MonitorLaborParto(UnidadRolRequiredMixin,TemplateView):
   template_name = "labor_parto.html"
   required_roles = COMUNICACION_HOSPITALARIA_VISUALIZACION_ROLES
   required_unidades = COMUNICACION_HOSPITALARIA_VISUALIZACION_UNIDADES

   def get_context_data(self, **kwargs):

      context = super().get_context_data(**kwargs)
      context["estados_labor_parto"] = (
            EstadoLaborParto.opciones()
      )
      context["unidades_entrada_labor_parto"] = (UNIDADES_ENTRADA_LABOR_PARTO)
      context["unidades_salida_labor_parto"] = (UNIDADES_SALIDA_LABOR_PARTO)

      return context


def listarEpisodiosLaborPartoAPI(request):
   pagina = int(request.GET.get("pagina", 1))
   por_pagina = int(request.GET.get("por_pagina", 10))
   busqueda = request.GET.get("busqueda", "").strip()
   orden = request.GET.get("orden", "fecha_ingreso")
   direccion = request.GET.get("direccion", "desc")
   filtros_estado = request.GET.get("filtros_estado", "")

   if filtros_estado:
      filtros_estado = [
         int(valor)
         for valor in filtros_estado.split(",")
         if valor
      ]
   else:
      filtros_estado = []


   datos = LaborPartoService.listar_episodios(
      pagina=pagina,
      por_pagina=por_pagina,
      busqueda=busqueda,
      orden=orden,
      direccion=direccion,
      filtros_estado=filtros_estado
   )

   return JsonResponse(datos)



@require_GET
def obtenerEpisodioLaborParto(request):
   id = request.GET.get('id')

   if not id:
      return JsonResponse({'error': 'El parametro id es requerido'}, status=400)
   
   detalle = LaborPartoService.obtener_episodio_laborParto_detallado(id)

   if not detalle:
      return JsonResponse(
         {"error": "No se encontró el peridodo indicado."},
         status=404
      )
   
   return JsonResponse(detalle , status=200)



@require_POST
def guardarEpisodioLaborParto(request):

   if not verificar_permisos_usuario(
      request.user,
      COMUNICACION_HOSPITALARIA_EDICION_ROLES,
      COMUNICACION_HOSPITALARIA_EDICION_UNIDADES,
   ):
      return JsonResponse(
         {"error": "No tienes permisos para realizar esta acción"},
         status=403,
      )

   try:
      data = parse_json_request(request)
   except ValueError as e:
      return JsonResponse({"error": str(e)}, status=400)

   try:
      episodio = LaborPartoValidator.validarArgumentosEpisodioLaborParto(
            data,
            request.user.id,
      )
   except ValueError as e:
      return JsonResponse(
         {"error": str(e)},
         status=400,
      )
   except ValidationError as e:
      return JsonResponse(
         {
               "error": (
                  e.message_dict
                  if hasattr(e, "message_dict")
                  else e.messages
               )
         },
         status=400,
      )

   try:
      nuevo_episodio = LaborPartoService.guardar_episodio(episodio)

      return JsonResponse(
         {"guardado": True, "episodio_id":nuevo_episodio.id},
         status=201,
      )

   except ValidationError as e:
      return JsonResponse({'error': e.messages[0]}, status=400)

   except ValueError as e:
      return JsonResponse({"error": str(e)}, status=400)

   except Exception:
      log_error(
         "Error al guardar episodio de Labor y Parto",
         LogApp.COMUNICACION,
      )
      return JsonResponse(
         {"error": "No se pudo guardar el episodio"},
         status=500,
      )



@require_POST
def procesarMovimientoLaborParto(request):

   if not verificar_permisos_usuario(
      request.user,
      COMUNICACION_HOSPITALARIA_EDICION_ROLES,
      COMUNICACION_HOSPITALARIA_EDICION_UNIDADES,
   ):
      return JsonResponse(
         {"error": "No tienes permisos para realizar esta acción"},
         status=403,
      )

   try:
      data = parse_json_request(request)
   except ValueError as e:
      return JsonResponse({"error": str(e)}, status=400)


   try:
      nuevo_movimiento = LaborPartoValidator.validarArgumentosMovimientoLaborParto(
            data,
            request.user,
      )
   except ValueError as e:
      return JsonResponse(
         {"error": str(e)},
         status=400,
      )
   except ValidationError as e:
      return JsonResponse(
         {
               "error": (
                  e.message_dict
                  if hasattr(e, "message_dict")
                  else e.messages
               )
         },
         status=400,
      )

   try:
      nuevo_movimiento = LaborPartoService.procesar_movimiento(nuevo_movimiento)

      return JsonResponse(
         {"guardado": True, "movimiento_id": nuevo_movimiento.id},
         status=201,
      )

   except ValidationError as e:
      return JsonResponse({'error': e.messages[0]}, status=400)

   except ValueError as e:
      return JsonResponse({"error": str(e)}, status=400)

   except Exception:
      log_error(
         "Error al guardar movimiento de Labor y Parto",
         LogApp.COMUNICACION,
      )
      return JsonResponse(
         {"error": "No se pudo guardar el movimiento"},
         status=500,
      )



@require_GET
def obtenerMovimientoLaborParto(request):
   id = request.GET.get('id')
   if not id:
      return JsonResponse({'error': 'El parametro id es requerido'}, status=400)

   movimiento = LaborPartoService.obtener_movimiento_laborParto_detallado(id)


   if not movimiento:
      return JsonResponse(
         {"error": "No se encontró el peridodo indicado."},
         status=404
      )
   
   return JsonResponse(movimiento, status=200)



@require_POST
def gestionarMovimientoLaborParto(request):
   """
   Permite actualizar la observación de un movimiento activo o
   desactivarlo, registrando la justificación proporcionada.
   """

   if not verificar_permisos_usuario(
      request.user,
      COMUNICACION_HOSPITALARIA_EDICION_ROLES,
      COMUNICACION_HOSPITALARIA_EDICION_UNIDADES,
   ):
      return JsonResponse(
         {"error": "No tienes permisos para realizar esta acción"},
         status=403,
      )

   try:
      data = parse_json_request(request)
      movimiento = LaborPartoValidator.validarArgumentosGestionMovimientoLaborParto( data, request.user,)
      guardo = LaborPartoService.gestionarMovimiento(movimiento)

      return JsonResponse(
         {"guardado": guardo},
         status=200,
      )

   except ValueError as e:
      return JsonResponse(
         {"error": str(e)},
         status=400,
      )

   except ValidationError as e:
      return JsonResponse(
         {
            "error": (
               e.message_dict
               if hasattr(e, "message_dict")
               else e.messages
            )
         },
         status=400,
      )

   except Exception:
      log_error(
         "Error al gestionar movimiento de Labor y Parto",
         LogApp.COMUNICACION,
      )
      return JsonResponse(
         {"error": "No se pudo gestionar el movimiento"},
         status=500,
      )


@require_POST
def registrarAltaLaborParto(request):
   """
   Registra el alta de un episodio de Labor y Parto.
   """

   if not verificar_permisos_usuario(
      request.user,
      COMUNICACION_HOSPITALARIA_EDICION_ROLES,
      COMUNICACION_HOSPITALARIA_EDICION_UNIDADES,
   ):
      return JsonResponse(
         {"error": "No tienes permisos para realizar esta acción"},
         status=403,
      )

   try:
      data = parse_json_request(request)

      alta = LaborPartoValidator.validarArgumentosAltaLaborParto(
         data,
         request.user,
      )


      guardo = LaborPartoService.registrarAlta(alta)

      return JsonResponse(
         {"guardado": guardo},
         status=200,
      )

   except ValueError as e:
      return JsonResponse(
         {"error": str(e)},
         status=400,
      )

   except ValidationError as e:
      return JsonResponse(
         {
               "error": (
                  e.message_dict
                  if hasattr(e, "message_dict")
                  else e.messages
               )
         },
         status=400,
      )

   except Exception:
      log_error(
         "Error al registrar alta de Labor y Parto",
         LogApp.COMUNICACION,
      )
      return JsonResponse(
         {"error": "No se pudo registrar el alta"},
         status=500,
      )




@require_POST
def procesarBebeLaborParto(request):
   """
   Registra o actualiza un bebé de un episodio de Labor y Parto.
   """

   if not verificar_permisos_usuario(
      request.user,
      COMUNICACION_HOSPITALARIA_EDICION_ROLES,
      COMUNICACION_HOSPITALARIA_EDICION_UNIDADES,
   ):
      return JsonResponse(
         {"error": "No tienes permisos para realizar esta acción"},
         status=403,
      )

   try:
      data = parse_json_request(request)

      print(data)

      bebe = LaborPartoValidator.validarArgumentosBebeLaborParto(
         data,
         request.user,
      )

      guardado = LaborPartoService.registrarBebe(bebe)
      

      return JsonResponse(
         {
               "guardado": True,
               "accion": guardado["accion"],
         },
         status=200,
      )

   except ValueError as e:
      return JsonResponse(
         {"error": str(e)},
         status=400,
      )

   except ValidationError as e:
      return JsonResponse(
         {
               "error": (
                  e.message_dict
                  if hasattr(e, "message_dict")
                  else e.messages
               )
         },
         status=400,
      )

   except Exception:
      log_error(
         "Error al registrar o actualizar bebé de Labor y Parto",
         LogApp.COMUNICACION,
      )
      return JsonResponse(
         {"error": "No se pudo registrar o actualizar el bebé"},
         status=500,
      )



@require_GET
def obtenerBebeLaborParto(request):
   id_bebe = request.GET.get("id")

   if not id_bebe:
      return JsonResponse(
         {"error": "El parámetro id es requerido."},
         status=400,
      )

   bebe = LaborPartoService.obtener_bebe_laborParto_detallado(
      id_bebe
   )

   if not bebe:
      return JsonResponse(
         {"error": "No se encontró el bebé indicado."},
         status=404,
      )

   return JsonResponse(bebe, status=200)

