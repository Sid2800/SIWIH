from comunicacion_hospitalaria.models import Episodio_labor_parto, Bebe_labor_parto, Movimiento_labor_parto
from comunicacion_hospitalaria.validators import LaborPartoValidator
from django.core.paginator import Paginator
from math import ceil
from django.db.models import (
   F, Q,
   Value,
   CharField,
   Case,
   When,
   Prefetch
   )
from django.db.models.functions import Concat
from django.db.models import Max
from django.utils import timezone
from django.db import transaction
from core.constants.choices_constants import EstadoLaborParto, EstadoRegistro, TipoMovimientoLaborParto
from core.constants.domain_constants import UNIDAD_SALIDA_OBSTETRICIA, UNIDAD_SALIDA_QUIROFANO, UNIDAD_SALIDA_EXTERNO,UNIDADES_ENTRADA_LABOR_PARTO, UNIDADES_SALIDA_LABOR_PARTO
from core.utils.utilidades_fechas import hora_local_iso, calcular_edad_texto
from core.utils.utilidades_textos import formatear_dni, formatear_expediente



class LaborPartoService:
   
   @classmethod
   def _obtener_indicador_episodio(cls, episodio):

      # Mostrar el indicador de salida si el movimiento actual es una salida
      movimiento = episodio.movimiento_actual

      if (
         movimiento
         and movimiento.tipo == TipoMovimientoLaborParto.SALIDA
      ):
         indicador = cls.obtener_indicador_salida(
               movimiento.unidad_destino_id
         )

         if indicador:
               return indicador

      # Mostrar el estado interno del episodio
      if episodio.estado_actual is not None:

         return {
               "texto": EstadoLaborParto.obtener_texto(
                  episodio.estado_actual
               ),
               **EstadoLaborParto.obtener_color(
                  episodio.estado_actual
               ),
         }

      return None



   @classmethod
   def _calcular_tiempo_labor_parto(cls, episodio):
      ahora = timezone.now()

      fin = (
         episodio.fecha_alta
         if episodio.alta and episodio.fecha_alta
         else ahora
      )

      duracion = fin - episodio.fecha_ingreso

      if duracion.total_seconds() < 0:
         return "0 horas"

      dias = duracion.days
      horas = duracion.seconds // 3600

      partes = []

      if dias:
         partes.append(f"{dias} día{'s' if dias != 1 else ''}")

      if horas:
         partes.append(f"{horas} hora{'s' if horas != 1 else ''}")

      return " ".join(partes) if partes else "0 horas"



   @classmethod
   def _desactivar_movimiento(cls, movimiento):

      episodio = movimiento.episodio

      movimiento.estado = 2
      movimiento.save(update_fields=["estado"])

      # Si no queda ningún movimiento vigente, recuperar
      # el estado del último movimiento activo restante.
      movimiento_anterior = (
         Movimiento_labor_parto.objects
         .filter(
               episodio=episodio,
               estado=1,
         )
         .exclude(id=movimiento.id)
         .order_by("-fecha_movimiento", "-id")
         .first()
      )

      episodio.movimiento_actual = movimiento_anterior

      if movimiento_anterior:
         episodio.estado_actual = movimiento_anterior.estado_nuevo
      else:
         episodio.estado_actual = EstadoLaborParto.LABOR

      episodio.save(
         update_fields=["movimiento_actual", "estado_actual"]
      )

      return movimiento



   @classmethod
   def calcular_duracion_estado(cls, episodio):

      movimientos = list(episodio.movimientos.all())
      ahora = timezone.now()

      # Sin movimientos:
      # el episodio acaba de ingresar a Labor y Parto.
      if not movimientos:
         inicio = episodio.fecha_ingreso
         fin = (
            episodio.fecha_alta
            if episodio.alta and episodio.fecha_alta
            else ahora
         )

      else:

         ultimo_movimiento = movimientos[0]

         # Episodio dado de alta.
         # La última acción será una SALIDA.
         if episodio.alta and episodio.fecha_alta:

            ultimo_cambio_estado = next(
               (
                  movimiento
                  for movimiento in movimientos
                  if movimiento.tipo == TipoMovimientoLaborParto.CAMBIO_ESTADO
               ),
               None
            )

            # Si nunca hubo cambio de estado,
            # contamos desde el ingreso.
            inicio = (
               ultimo_cambio_estado.fecha_movimiento
               if ultimo_cambio_estado
               else episodio.fecha_ingreso
            )

            fin = episodio.fecha_alta

         # Episodio activo.
         else:

            # Salió temporalmente de Labor y Parto.
            if ultimo_movimiento.tipo == TipoMovimientoLaborParto.SALIDA:
               ultimo_cambio_estado = next(
                  (
                     movimiento
                     for movimiento in movimientos
                     if movimiento.tipo == TipoMovimientoLaborParto.CAMBIO_ESTADO
                  ),
                  None
               )

               inicio = (
                  ultimo_cambio_estado.fecha_movimiento
                  if ultimo_cambio_estado
                  else episodio.fecha_ingreso
               )

               fin = ahora

            # Retorno.
            elif ultimo_movimiento.tipo == TipoMovimientoLaborParto.RETORNO:
               ultima_salida = next(
                  (
                     movimiento
                     for movimiento in movimientos
                     if movimiento.tipo == TipoMovimientoLaborParto.SALIDA
                  ),
                  None
               )

               if not ultima_salida:
                  return None

                  inicio = ultimo_movimiento.fecha_movimiento
                  fin = ahora

            # Cambio de estado normal.
            elif ultimo_movimiento.tipo == TipoMovimientoLaborParto.CAMBIO_ESTADO:
               inicio = ultimo_movimiento.fecha_movimiento
               fin = ahora

            else:
               return None

      duracion = fin - inicio
      horas = int(duracion.total_seconds() // 3600)

      return f"{horas} hora{'s' if horas != 1 else ''}"



   @classmethod
   def obtener_indicador_salida(cls, unidad_id):

      indicadores = {

         UNIDAD_SALIDA_OBSTETRICIA: {
            "texto": UNIDADES_SALIDA_LABOR_PARTO.get(UNIDAD_SALIDA_OBSTETRICIA),
            "color": "rgb(190, 95, 64)",
            "fondo": "rgba(190, 95, 64, 0.07)",
            "borderColor": "rgba(190, 95, 64, 0.50)",
            "icono": "obstetricia",
            },

         UNIDAD_SALIDA_QUIROFANO: {
            "texto": UNIDADES_SALIDA_LABOR_PARTO.get(UNIDAD_SALIDA_QUIROFANO),
            "color": "rgb(91, 91, 98)",
            "fondo": "rgba(91, 91, 98, 0.07)",
            "borderColor": "rgba(91, 91, 98, 0.50)",
            "icono": "quirofano",
         },

         UNIDAD_SALIDA_EXTERNO: {
            "texto": UNIDADES_SALIDA_LABOR_PARTO.get(UNIDAD_SALIDA_EXTERNO),
            "color": "rgb(116, 117, 47)",
            "fondo": "rgba(116, 117, 47, 0.07)",
            "borderColor": "rgba(116, 117, 47, 0.50)",
            "icono": "referencia",
         }

      }

      return indicadores.get(unidad_id)



   @classmethod
   def obtener_episodios_labor_parto(cls, pagina=1, por_pagina=10):
      queryset = (
         Episodio_labor_parto.objects
         .filter(
               estado=EstadoRegistro.ACTIVO,
               alta=False,
         )
         .select_related("paciente")
         .order_by("-fecha_ingreso")
      )

      paginator = Paginator(queryset, por_pagina)
      pagina_obj = paginator.get_page(pagina)

      return {
         "total": paginator.count,
         "episodios": pagina_obj,
         "pagina_actual": pagina_obj.number,
         "total_paginas": paginator.num_pages,
      }



   @classmethod
   def listar_episodios(
         cls,
         pagina=1,
         por_pagina=10,
         busqueda=None,
         orden="fecha_ingreso",
         direccion="desc",
         filtros_estado=None,
      ):

      if not filtros_estado:
         return {
            "total": 0,
            "total_filtrado": 0,
            "pagina": 1,
            "por_pagina": por_pagina,
            "total_paginas": 0,
            "episodios": [],
         }


      episodios_qs = (
            Episodio_labor_parto.objects
            .filter(
                  estado=EstadoRegistro.ACTIVO,
            )
            .select_related(
               "paciente",
               "movimiento_actual",
               "movimiento_actual__unidad_destino",
            ) 
         )

      total = episodios_qs.count()


      if len(filtros_estado) < 5:

         filtros = Q()

         estados = [1, 2, 3, 4]

         estados_seleccionados = [
            estado
            for estado in filtros_estado
            if estado in estados
         ]

         if estados_seleccionados:
            filtros |= Q(
                  estado_actual__in=estados_seleccionados,
                  alta=False
            )

         if 5 in filtros_estado:
            filtros |= Q(alta=True)

         episodios_qs = episodios_qs.filter(filtros)


      # Busqueda por nombre completo 
      if busqueda:
         busqueda = busqueda.strip()

         if busqueda:
            busqueda_limpia = (
                  busqueda
                  .replace("-", "")
                  .replace(" ", "")
            )

            if busqueda_limpia.isdigit():
                  episodios_qs = episodios_qs.filter(
                     Q(
                        paciente__dni__icontains=busqueda_limpia
                     )
                     |
                     Q(
                        paciente__expediente_numero__icontains=busqueda_limpia
                     )
                  )
            else:
                  episodios_qs = episodios_qs.annotate(
                     nombre_completo_interno=Concat(
                        F("paciente__primer_nombre"),
                        Case(
                              When(
                                 paciente__segundo_nombre__isnull=False,
                                 paciente__segundo_nombre__exact="",
                                 then=Value(""),
                              ),
                              When(
                                 paciente__segundo_nombre__isnull=False,
                                 then=Concat(
                                    Value(" "),
                                    F("paciente__segundo_nombre"),
                                 ),
                              ),
                              default=Value(""),
                              output_field=CharField(),
                        ),
                        Value(" "),
                        F("paciente__primer_apellido"),
                        Case(
                              When(
                                 paciente__segundo_apellido__isnull=False,
                                 paciente__segundo_apellido__exact="",
                                 then=Value(""),
                              ),
                              When(
                                 paciente__segundo_apellido__isnull=False,
                                 then=Concat(
                                    Value(" "),
                                    F("paciente__segundo_apellido"),
                                 ),
                              ),
                              default=Value(""),
                              output_field=CharField(),
                        ),
                        output_field=CharField(),
                     )
                  ).filter(
                     nombre_completo_interno__icontains=busqueda
                  )
         
      # Total después de filtros
      total_filtrado = episodios_qs.count()

      # paginación
      paginator = Paginator(episodios_qs, por_pagina)
      pagina_obj = paginator.get_page(pagina)


      # Orden y resultados
      episodios = list(
         pagina_obj.object_list.values(
            "id",
            "paciente__primer_nombre",
            "paciente__segundo_nombre",
            "paciente__primer_apellido",
            "paciente__segundo_apellido",
            "paciente__dni",
            "paciente__expediente_numero",
            "estado_actual",
            "alta",
            "movimiento_actual__tipo",
            "movimiento_actual__unidad_destino",
            "fecha_ingreso",
         )
      )

      for episodio in episodios:

         movimiento_tipo = episodio["movimiento_actual__tipo"]
         unidad_destino_id = episodio["movimiento_actual__unidad_destino"]

         # Mostrar el indicador de salida
         if movimiento_tipo == TipoMovimientoLaborParto.SALIDA:

            indicador = cls.obtener_indicador_salida(
                  unidad_destino_id
            )

            if indicador:
                  episodio["estado_actual_texto"] = indicador["texto"]
                  episodio["estado_actual_color"] = {
                     clave: valor
                     for clave, valor in indicador.items()
                     if clave != "texto"
                  }
            else:
                  episodio["estado_actual_texto"] = None
                  episodio["estado_actual_color"] = None

         # Mostrar el estado interno del episodio
         elif episodio["estado_actual"] is not None:

            episodio["estado_actual_texto"] = (
                  EstadoLaborParto.obtener_texto(
                     episodio["estado_actual"]
                  )
            )

            episodio["estado_actual_color"] = (
                  EstadoLaborParto.obtener_color(
                     episodio["estado_actual"]
                  )
            )

         else:
            episodio["estado_actual_texto"] = None
            episodio["estado_actual_color"] = None

         # Formatear fecha de ingreso
         episodio["fecha_ingreso"] = hora_local_iso(
            episodio["fecha_ingreso"]
         )


      return {
         "total": total,
         "total_filtrado": total_filtrado,
         "pagina": pagina_obj.number,
         "por_pagina": por_pagina,
         "total_paginas": paginator.num_pages,
         "episodios": episodios,
      }


   @classmethod
   def guardar_episodio(cls, episodio):
      LaborPartoValidator.validarReglasCriticasEpisodioLaborParto(episodio)
      nuevo_episodio = Episodio_labor_parto.objects.create(
         paciente=episodio.paciente,
         estado_actual=EstadoLaborParto.LABOR,
         unidad_entrada_id=episodio.unidad_entrada_id,
         fecha_ingreso=episodio.fecha_ingreso,
         creado_por_id=episodio.usuario_id,
         modificado_por_id=episodio.usuario_id,
      )

      return nuevo_episodio


   @classmethod
   def procesar_movimiento(cls, movimiento):
      with transaction.atomic():
         LaborPartoValidator.validarReglasCriticasMovimientoLaborParto(
            movimiento
         )

         episodio = movimiento.episodio
         movimiento_actual = episodio.movimiento_actual

         # Determinar el estado anterior.
         if movimiento_actual:
            estado_anterior = movimiento_actual.estado_nuevo
         else:
            estado_anterior = EstadoLaborParto.LABOR

         # Crear el nuevo movimiento sin modificar el historial anterior.
         nuevo_movimiento = Movimiento_labor_parto.objects.create(
            episodio=episodio,
            tipo=TipoMovimientoLaborParto.CAMBIO_ESTADO,
            estado_anterior=estado_anterior,
            estado_nuevo=movimiento.estado_nuevo,
            unidad_destino=None,
            fecha_movimiento=timezone.now(),
            usuario=movimiento.usuario,
            observacion=movimiento.observacion,
         )

         # Actualizar el episodio y su referencia al nuevo movimiento.
         episodio.estado_actual = movimiento.estado_nuevo
         episodio.movimiento_actual = nuevo_movimiento
         episodio.save(
            update_fields=[
                  "estado_actual",
                  "movimiento_actual",
            ]
         )

         return nuevo_movimiento


   @classmethod
   def obtener_episodio_laborParto_detallado(cls, episodio_id):

   
      episodio = (
         Episodio_labor_parto.objects
         .select_related(
            "paciente",
            "movimiento_actual__unidad_destino",
            "creado_por",
            "modificado_por",
         )
         .prefetch_related(
               Prefetch(
                  "bebes",
                  queryset=Bebe_labor_parto.objects
                  .filter(estado=EstadoRegistro.ACTIVO)
                  .order_by("orden")
               ),
               Prefetch(
                  "movimientos",
                  queryset=Movimiento_labor_parto.objects
                  .select_related(
                     "unidad_destino__sala",
                     "unidad_destino__servicio_aux",
                     "usuario",
                  )
                  .filter(
                     estado=EstadoRegistro.ACTIVO
                  )
                  .order_by("-fecha_movimiento")
               ),
         )
         .filter(
               id=episodio_id,
               estado=EstadoRegistro.ACTIVO,
         )
         .first()
      )

      if not episodio:
         return None

      #bebes 
      bebes = []

      for bebe in episodio.bebes.all():

         bebes.append({
               "id": bebe.id,
               "sexo": bebe.sexo,
               "sexo_texto": bebe.get_sexo_display(),
               "orden": bebe.orden,
               "fecha_nacimiento": (
                  hora_local_iso(bebe.fecha_nacimiento)
                  if bebe.fecha_nacimiento
                  else None
               ),
         })

      movimientos = []

      for movimiento in episodio.movimientos.all():

         movimientos.append({
               "id": movimiento.id,
               "tipo": movimiento.tipo,
               "tipo_texto": movimiento.get_tipo_display(),
               "estado_anterior": movimiento.estado_anterior, 
               "estado_anterior_texto": (
                  EstadoLaborParto.obtener_texto(
                     movimiento.estado_anterior
                  )
                  if movimiento.estado_anterior is not None
                  else None
               ),
               "estado_nuevo": movimiento.estado_nuevo,
               "estado_nuevo_texto": (
                  EstadoLaborParto.obtener_texto(
                     movimiento.estado_nuevo
                  )
                  if movimiento.estado_nuevo is not None
                  else None
               ),
               "unidad_destino": (
                  {
                     "id": movimiento.unidad_destino.id,

                     "nombre": (
                           UNIDADES_SALIDA_LABOR_PARTO.get(
                              movimiento.unidad_destino_id
                           )
                           if movimiento.tipo == TipoMovimientoLaborParto.SALIDA
                           else None
                     ),
                  }
                  if movimiento.unidad_destino
                  else None
               ),
               "fecha_movimiento": hora_local_iso(
                  movimiento.fecha_movimiento
               ),
               "usuario": movimiento.usuario.get_full_name(),
               "observacion": movimiento.observacion,
         })

      return {
         "id": episodio.id,

         "paciente": {
               "id": episodio.paciente.id,
               "primer_nombre": episodio.paciente.primer_nombre,
               "segundo_nombre": episodio.paciente.segundo_nombre,
               "primer_apellido": episodio.paciente.primer_apellido,
               "segundo_apellido": episodio.paciente.segundo_apellido,
               "dni": formatear_dni(str(episodio.paciente.dni)),
               "expediente_numero": formatear_expediente(episodio.paciente.expediente_numero),
               "edad":calcular_edad_texto(str(episodio.paciente.fecha_nacimiento),True),
         },

         "estado_actual": episodio.estado_actual,

         "estado_actual_info": cls._obtener_indicador_episodio(episodio),


         "alta": episodio.alta,

         "fecha_ingreso": hora_local_iso(
               episodio.fecha_ingreso
         ),

         "fecha_alta": (
               hora_local_iso(episodio.fecha_alta)
               if episodio.fecha_alta
               else None
         ),

         "tiempo_labor_parto": cls._calcular_tiempo_labor_parto(episodio),

         "duracion_estado": cls.calcular_duracion_estado(
            episodio
         ),


         "unidad_entrada": (
            UNIDADES_ENTRADA_LABOR_PARTO.get(episodio.unidad_entrada_id)
            if episodio.unidad_entrada_id
            else None
         ),

         "unidad_salida": (
            UNIDADES_SALIDA_LABOR_PARTO.get(
               episodio.movimiento_actual.unidad_destino_id
            )
            if (
               episodio.movimiento_actual
               and episodio.movimiento_actual.tipo
               == TipoMovimientoLaborParto.SALIDA
               and episodio.movimiento_actual.unidad_destino_id
            )
            else None
         ),

         "bebes": bebes,

         "movimientos": movimientos,
      }



   @classmethod
   def obtener_movimiento_laborParto_detallado(cls, movimiento_id):


      movimiento = (
         Movimiento_labor_parto.objects
         .select_related(
               "usuario",
         )
         .filter(
               id=movimiento_id,
               estado=EstadoRegistro.ACTIVO,
         )
         .first()
      )

      if not movimiento:
         return None

      # Obtener el indicador de salida cuando corresponda
      estado_alta_info = None

      if (
         movimiento.tipo == TipoMovimientoLaborParto.SALIDA
         and movimiento.unidad_destino_id
      ):
         estado_alta_info = cls.obtener_indicador_salida(
               movimiento.unidad_destino_id
         )


      return {
            "movimiento": {
               "id": movimiento.id,
               "tipo": movimiento.tipo,
               "estado_alta_info": estado_alta_info,
               "tipo_display": movimiento.get_tipo_display(),
               "estado_anterior": movimiento.estado_anterior,
               "estado_anterior_display": movimiento.get_estado_anterior_display(),
               "estado_nuevo": movimiento.estado_nuevo,
               "estado_nuevo_display": movimiento.get_estado_nuevo_display(),
               "fecha_movimiento": movimiento.fecha_movimiento,
               "observacion": movimiento.observacion,
               "estado": movimiento.estado,
               "usuario": {
                     "id": movimiento.usuario_id,
                     "nombre": movimiento.usuario.username,
               },
            },

         }


   @classmethod
   def gestionarMovimiento(cls, movimiento):

      with transaction.atomic():

         LaborPartoValidator.validarReglasCriticasGestionMovimientoLaborParto(movimiento)

         registro = movimiento.registro

         observacion_actual = registro.observacion or ""
         observacion_nueva = movimiento.observacion or ""

         observacion_modificada = (
               observacion_actual != observacion_nueva
         )

         if movimiento.activo and not observacion_modificada:
               return False

         if observacion_modificada:
               registro.observacion = movimiento.observacion
               registro.save(update_fields=["observacion"])

         if movimiento.activo:
               return True

         cls._desactivar_movimiento(registro)

         return True


   @classmethod
   def registrarAlta(cls, alta):

      with transaction.atomic():

         LaborPartoValidator.validarReglasCriticasAltaLaborParto(alta)

         episodio = alta.episodio

         # Registrar el movimiento de salida
         movimiento = Movimiento_labor_parto.objects.create(
               episodio=episodio,
               tipo=TipoMovimientoLaborParto.SALIDA,
               estado_anterior=episodio.estado_actual,
               estado_nuevo=None,
               unidad_destino_id=alta.unidad_destino_id,
               fecha_movimiento=timezone.now(),
               usuario=alta.usuario,
               observacion=alta.observacion,
         )

         # Registrar el alta del episodio
         episodio.alta = True
         episodio.fecha_alta = movimiento.fecha_movimiento
         episodio.movimiento_actual = movimiento

         episodio.save(update_fields=[
               "alta",
               "fecha_alta",
               "movimiento_actual",
         ])

         return True



   @classmethod
   def registrarBebe(cls, bebe):
      with transaction.atomic():

         LaborPartoValidator.validarReglasCriticasBebeLaborParto(
               bebe
         )

         episodio = bebe.episodio

         # Editar o desactivar un bebé existente
         if bebe.bebe_id is not None:
               bebe_existente = bebe.bebe

               # Desactivar bebé: guardar únicamente estado y observaciones
               if bebe.estado is False:
                  bebe_existente.estado = False
                  bebe_existente.observacion = bebe.observacion

                  bebe_existente.save(
                     update_fields=["estado", "observacion"]
                  )

                  return {
                     "accion": "desactivado",
                     "bebe": bebe_existente,
                  }

               # Editar bebé: guardar únicamente los campos modificados
               update_fields = []

               if bebe_existente.sexo != bebe.sexo:
                  bebe_existente.sexo = bebe.sexo
                  update_fields.append("sexo")

               if bebe_existente.fecha_nacimiento != bebe.fecha_nacimiento:
                  bebe_existente.fecha_nacimiento = bebe.fecha_nacimiento
                  update_fields.append("fecha_nacimiento")

               if bebe_existente.observacion != bebe.observacion:
                  bebe_existente.observacion = bebe.observacion
                  update_fields.append("observacion")

               if update_fields:
                  bebe_existente.save(update_fields=update_fields)
                  accion = "actualizado"
               else:
                  accion = "sin_cambios"

               return {
                  "accion": accion,
                  "bebe": bebe_existente,
               }

         # Registrar un bebé nuevo como activo
         ultimo_orden = (
               Bebe_labor_parto.objects
               .filter(episodio=episodio, estado=EstadoRegistro.ACTIVO)
               .aggregate(orden_maximo=Max("orden"))["orden_maximo"]
               or 0
         )

         nuevo_bebe = Bebe_labor_parto.objects.create(
               episodio=episodio,
               sexo=bebe.sexo,
               fecha_nacimiento=bebe.fecha_nacimiento,
               observacion=bebe.observacion,
               estado=True,
               orden=ultimo_orden + 1,
         )

         return {
               "accion": "creado",
               "bebe": nuevo_bebe,
         }




   @classmethod
   def obtener_bebe_laborParto_detallado(cls, bebe_id):

      bebe = (
         Bebe_labor_parto.objects
         .filter(
               id=bebe_id,
               estado=EstadoRegistro.ACTIVO,
         )
         .first()
      )

      if not bebe:
         return None



      return {
         "bebe": {
            "id": bebe.id,
            "episodio_id": bebe.episodio_id,
            "sexo": bebe.sexo,
            "sexo_display": bebe.get_sexo_display(),
            "orden": bebe.orden,
            "fecha_nacimiento": bebe.fecha_nacimiento,
            "observacion": bebe.observacion,
         },
      }

