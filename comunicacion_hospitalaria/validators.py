from datetime import datetime
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.constants.domain_constants import UNIDADES_ENTRADA_LABOR_PARTO, UNIDADES_SALIDA_LABOR_PARTO
from core.constants.choices_constants import EstadoLaborParto, Sexo
from core.validators.main_validator import validar_entero_positivo, validar_booleano, validar_texto_opcional
from core.validators.fecha_validator import validar_fecha
from core.validators.paciente import validar_paciente
from core.utils.utilidades_fechas import parsear_fecha_iso
from comunicacion_hospitalaria.models import Episodio_labor_parto, Movimiento_labor_parto, Bebe_labor_parto


class LaborPartoValidator:

   @classmethod
   def _validarEpisodioLaborParto(cls, id_episodio):
      episodio = Episodio_labor_parto.objects.filter(id=id_episodio).first()

      if not episodio:
         raise ValidationError("El episodio de Labor y Parto no existe.")
      
      return episodio

   @classmethod
   def _validarMovimientoLaborParto(cls, id_movimiento):
      movimiento = Movimiento_labor_parto.objects.filter(
         id=id_movimiento
      ).first()

      if not movimiento:
         raise ValidationError(
               "El movimiento de Labor y Parto no existe."
         )

      return movimiento

   @classmethod
   def _validarBebeLaborParto(cls, id_bebe):
      bebe = Bebe_labor_parto.objects.filter(id=id_bebe).first()

      if not bebe:
         raise ValidationError("El bebé de Labor y Parto no existe.")

      return bebe
   

   @classmethod
   def validarArgumentosEpisodioLaborParto(cls, data, usuario):

      paciente_id = validar_entero_positivo(
         data.get("pacienteId"),
         "Paciente",
      )

      unidad_entrada_id = validar_entero_positivo(
         data.get("unidadEntradaId"),
         "Unidad de entrada",
      )

      fecha_ingreso = data.get("fechaIngreso")

      if not fecha_ingreso:
         raise ValidationError(
               "La fecha de ingreso es requerida."
         )

      try:
         fecha_ingreso = parsear_fecha_iso(fecha_ingreso)
      except (ValueError, TypeError):
         raise ValidationError(
               "El formato de la fecha de ingreso es inválido."
         )

      if not isinstance(fecha_ingreso, datetime):
         raise ValidationError(
               "La fecha de ingreso debe incluir fecha y hora."
         )

      if timezone.is_naive(fecha_ingreso):
         fecha_ingreso = timezone.make_aware(
               fecha_ingreso,
               timezone.get_current_timezone(),
         )

      if fecha_ingreso > timezone.now():
         raise ValidationError(
               "La fecha de ingreso no puede ser futura."
         )

      return SimpleNamespace(
         paciente_id=int(paciente_id),
         unidad_entrada_id=int(unidad_entrada_id),
         fecha_ingreso=fecha_ingreso,
         usuario_id=usuario,
      )

   @classmethod
   def validarReglasCriticasEpisodioLaborParto(cls, episodio):

      # reglas criticas antes de guardar 
      episodio.paciente = validar_paciente(episodio.paciente_id)

      if episodio.unidad_entrada_id not in UNIDADES_ENTRADA_LABOR_PARTO:
         raise ValidationError(
            "La unidad de entrada no es válida para Labor y Parto."
         )

      # Evitar episodios abiertos duplicados para el mismo paciente
      episodio_abierto = Episodio_labor_parto.objects.filter(
         paciente_id=episodio.paciente_id,
         alta=False,
      ).exists()

      if episodio_abierto:
         raise ValidationError(
            "El paciente ya tiene un episodio de Labor y Parto sin alta."
         )

      return episodio


   @classmethod
   def validarArgumentosMovimientoLaborParto(cls, data, usuario):

      episodio_id = validar_entero_positivo(
         data.get("episodioId"),
         "Episodio",
      )

      estado_nuevo = validar_entero_positivo(
         data.get("estadoNuevo"),
         "Estado nuevo",
      )
      observacion = data.get("observacion")
      observacion = observacion.strip() if observacion else None


      return SimpleNamespace(
         episodio_id=int(episodio_id),
         estado_nuevo=int(estado_nuevo),
         observacion=observacion,
         usuario=usuario,
      )

   @classmethod
   def validarReglasCriticasMovimientoLaborParto(cls, movimiento):

      movimiento.episodio = cls._validarEpisodioLaborParto(movimiento.episodio_id)

      if movimiento.episodio.alta:
         raise ValidationError(
            "No se puede procesar un movimiento para un episodio con alta."
         )


      if movimiento.estado_nuevo == movimiento.episodio.estado_actual:
         raise ValidationError(
            "El estado nuevo es igual al estado actual del episodio."
         )

      EstadoLaborParto.validar(movimiento.estado_nuevo)

   
   @classmethod
   def validarArgumentosGestionMovimientoLaborParto(cls, data, usuario):

      movimiento_id = validar_entero_positivo(
         data.get("movimiento_id"),
         "Movimiento",
      )

      activo = validar_booleano(
         data.get("activo"),
         "Estado",
      )


      observacion = validar_texto_opcional(
         data.get("observacion"),
         max_length=255,
         nombre_campo="Observación"
      )

      return SimpleNamespace(
         movimiento_id=int(movimiento_id),
         observacion=observacion,
         activo=activo,
         usuario=usuario,
      )



   @classmethod
   def validarReglasCriticasGestionMovimientoLaborParto(cls, movimiento):

      movimiento.registro = cls._validarMovimientoLaborParto(movimiento.movimiento_id)

      registro = movimiento.registro
      episodio = registro.episodio

      if registro.estado != 1:
         raise ValidationError(
               "No se puede gestionar un movimiento que está inactivo."
         )

      if not movimiento.activo:

         if episodio.alta:
               raise ValidationError(
                  "No se puede desactivar un movimiento de un episodio con alta."
               )

         if episodio.movimiento_actual_id != registro.id:
               raise ValidationError(
                  "Solo se puede desactivar el movimiento actual del episodio."
               )
         

      return movimiento



   @classmethod
   def validarArgumentosAltaLaborParto(cls, data, usuario):

      episodio_id = validar_entero_positivo(
         data.get("episodio_id"),
         "Episodio",
      )

      unidad_destino_id = validar_entero_positivo(
         data.get("unidad_salida"),
         "Unidad de destino",
      )

      if unidad_destino_id not in UNIDADES_SALIDA_LABOR_PARTO:
         raise ValidationError(
               "La unidad de salida seleccionada no es válida."
         )

      observacion = validar_texto_opcional(
         data.get("observacion"),
         max_length=255,
         nombre_campo="Observación"
      )

      return SimpleNamespace(
         episodio_id=int(episodio_id),
         unidad_destino_id=int(unidad_destino_id),
         observacion=observacion,
         usuario=usuario,
      )


   @classmethod
   def validarReglasCriticasAltaLaborParto(cls, alta):
      # Validar que el episodio exista
      alta.episodio = cls._validarEpisodioLaborParto(alta.episodio_id)

      # Evitar registrar el alta de un episodio que ya tiene alta
      if alta.episodio.alta:
         raise ValidationError(
               "El episodio de Labor y Parto ya tiene registrada el alta."
         )

      # Validar que la unidad de salida sea válida
      if alta.unidad_destino_id not in UNIDADES_SALIDA_LABOR_PARTO:
         raise ValidationError(
               "La unidad de salida no es válida para Labor y Parto."
         )

      return alta





   @classmethod
   def validarArgumentosBebeLaborParto(cls, data, usuario):
      episodio_id = validar_entero_positivo(
         data.get("episodioId"),
         "Episodio",
      )

      bebe_id = data.get("bebeId")

      if bebe_id is not None:
         bebe_id = validar_entero_positivo(
               bebe_id,
               "Bebé",
         )

      sexo = Sexo.validar(data.get("sexo"))

      fecha_nacimiento = data.get("fechaNacimiento")

      estado = validar_booleano(
         data.get("estado", True),
         "Estado",
      )

      observacion = validar_texto_opcional(
         data.get("observacion"),
         max_length=255,
         nombre_campo="Observación",
      )

      return SimpleNamespace(
         episodio_id=int(episodio_id),
         bebe_id=bebe_id,
         sexo=sexo,
         fecha_nacimiento=fecha_nacimiento,
         observacion=observacion,
         estado=estado,
         usuario=usuario,
      )



   @classmethod
   def validarReglasCriticasBebeLaborParto(cls, bebe):
      # Validar que el episodio exista
      bebe.episodio = cls._validarEpisodioLaborParto(
         bebe.episodio_id
      )

      # Evitar gestionar bebés de un episodio que ya tiene alta
      if bebe.episodio.alta:
         raise ValidationError(
               "No se pueden gestionar bebés de un episodio "
               "de Labor y Parto que ya tiene registrada el alta."
         )

      # Si llega un identificador, validar que el bebé exista
      if bebe.bebe_id is not None:
         bebe.bebe = cls._validarBebeLaborParto(
               bebe.bebe_id
         )

         # Verificar que el bebé pertenezca al episodio indicado
         if bebe.bebe.episodio_id != bebe.episodio_id:
               raise ValidationError(
                  "El bebé no pertenece al episodio de Labor y Parto indicado."
               )

      return bebe