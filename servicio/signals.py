from django.db.models.signals import post_save
from django.dispatch import receiver

from mapeo_camas.models import AsignacionCamaPaciente
from servicio.models import Cama


ESTADO_ASIGNACION_POR_ESTADO_CAMA = {
    1: AsignacionCamaPaciente.Estado.VACIA,
    2: AsignacionCamaPaciente.Estado.OCUPADA,
    3: AsignacionCamaPaciente.Estado.PRE_ALTA,
    4: AsignacionCamaPaciente.Estado.FUERA_SERVICIO,
    5: AsignacionCamaPaciente.Estado.CONSULTA_EXTERNA,
}


@receiver(post_save, sender=Cama)
def sincronizar_estado_cama_en_asignacion(sender, instance, created, **kwargs):
    """Replica estado inicial solo cuando se crea una cama nueva."""
    if not created:
        return

    estado_asignacion = ESTADO_ASIGNACION_POR_ESTADO_CAMA.get(
        instance.estado,
        AsignacionCamaPaciente.Estado.VACIA,
    )

    AsignacionCamaPaciente.objects.get_or_create(
        cama_id=instance.numero_cama,
        defaults={
            "estado": estado_asignacion,
            "paciente": None,
            "usuario_asignacion": instance.creado_por,
            "fecha_fin": None,
            "usuario_cierre": None,
        },
    )
