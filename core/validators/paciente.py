from django.core.exceptions import ValidationError
from core.services.paciente_service import PacienteService
from paciente.models import Paciente
from django.utils import timezone
from datetime import datetime
from django.db.models import Q
from django.shortcuts import get_object_or_404

def validar_paciente(id_paciente):
        """
        Verifica que el paciente exista, esté activo y no fallecido.
        """
        if not id_paciente:
            raise ValidationError("Debe especificarse un paciente válido.")

        paciente = get_object_or_404(Paciente, id=id_paciente)

        if PacienteService.comprobar_inactivo(paciente.id):
            raise ValidationError("El paciente seleccionado no está activo.")

        if PacienteService.comprobar_defuncion(paciente):
            raise ValidationError("El paciente seleccionado ha fallecido.")

        return paciente


def buscar_duplicidad_paciente(paciente):
    """ hace... 
    Busca posibles pacientes duplicados según nombre, apellido, fecha de nacimiento y sexo.
    Retorna una lista con coincidencias si las hay, False si no hay, y lanza ValidationError si algo falla.
    """

    # Validaciones básicas
    id = (paciente.get('id') or "").strip()
    nombre = (paciente.get('primer_nombre') or "").strip()
    apellido = (paciente.get('primer_apellido') or "").strip()
    fecha_nacimiento = (paciente.get('fecha_nacimiento') or "").strip()
    sexo = (paciente.get('sexo') or "").strip()

    if not (nombre and apellido and fecha_nacimiento and sexo):
        raise ValidationError("Buscar duplicidad: no se recibieron todos los campos requeridos para la comprobación.")

    # Validar formato de fecha
    try:
        fecha_nacimiento = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
    except Exception:
        raise ValidationError("Buscar duplicidad: la fecha de nacimiento tiene un formato incorrecto (use YYYY-MM-DD).")

    # Prefijos para coincidencia parcial
    pref_nombre = nombre[:2]
    pref_apellido = apellido[:2]

    try:
        # Consulta filtrada: misma fecha y sexo, nombre y apellido que empiezan igual
        qs = Paciente.objects.filter(
            fecha_nacimiento=fecha_nacimiento,
            sexo=sexo
        ).filter(
            Q(primer_nombre__istartswith=pref_nombre) &
            Q(primer_apellido__istartswith=pref_apellido)
        )

        # Excluir el propio paciente si está editando
        if id:
            qs = qs.exclude(id=id)

        # Limitar resultados y seleccionar solo campos relevantes
        duplicados = list(qs.values(
            'id', 'dni', 'primer_nombre', 'segundo_nombre',
            'primer_apellido', 'segundo_apellido',
            'fecha_nacimiento', 'sexo'
        ).order_by('primer_apellido', 'primer_nombre')[:5])

        # Retorno final
        return duplicados if duplicados else False

    except Exception as e:
        raise ValidationError(f"Ocurrió un error al buscar duplicados: {e}")