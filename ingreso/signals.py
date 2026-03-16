from django.db.models.signals import post_save
from django.dispatch import receiver
from ingreso.models import Ingreso
from core.services.paciente_service import PacienteService

@receiver(post_save, sender=Ingreso)
def activar_paciente(sender, instance, created, **kwargs):
    if created and instance.paciente_id:  # asegurarnos que exista paciente
        try:
            PacienteService.paciente_a_activo(instance.paciente_id)
        except Exception as e:
            print(f"❌ Error al sincronizar paciente: {e}")