from django.db.models.signals import post_save
from django.dispatch import receiver
from atencion.models import Atencion
from core.services.paciente_service import PacienteService
from datetime import date

@receiver(post_save, sender=Atencion)
def activar_paciente(sender, instance, created, **kwargs):
    """
    Activa el paciente si tiene una atención con fecha reciente,
    sin importar si la atención fue creada o actualizada.
    """
    try:
        if not instance.paciente_id:
            return  # seguridad extra

        fecha = getattr(instance, "fecha_atencion", None)
        if not fecha:
            return

        # Convertir a date si es datetime
        if hasattr(fecha, "date"):
            fecha = fecha.date()

        hoy = date.today()
        inicio_anio = date(hoy.year, 1, 1)

        if fecha >= inicio_anio:
            PacienteService.paciente_a_activo(instance.paciente_id)
            print(f"Paciente {instance.paciente_id} activado por atención ({fecha})")
        else:
            print(f"Paciente {instance.paciente_id} no activado: atención antigua ({fecha})")

    except Exception as e:
        print(f" (atencion) Error al sincronizar paciente: {e}")
