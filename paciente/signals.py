from django.db.models.signals import post_save
from django.contrib import messages
from django.dispatch import receiver
from paciente.models import Paciente, Padre
from django.forms.models import model_to_dict
from core.services.paciente_service import PacienteService
from core.services.padre_service import PadreService
from core.services.externals import sync_paciente_sqlserver, sync_paciente_mysql
from core.constants.domain_constants import LogApp
from core.utils.utilidades_logging import *

# Signal para sincronizar después del guardado
@receiver(post_save, sender=Paciente)
def sincronizar_paciente_sp(sender, instance, created, **kwargs):
    if created:
        # No sincronizamos al crear, solo en actualizaciones
        return

    try:
        paciente = (
            Paciente.objects
            .select_related(
                "sector__aldea__municipio__departamento",
                "ocupacion",
                "estado_civil"
            )
            .get(pk=instance.pk)
        )

        padre = PadreService.obtener_detalles_padre(paciente.padre_id) if paciente.padre else None
        madre = PadreService.obtener_detalles_padre(paciente.madre_id) if paciente.madre else None
        pac = PacienteService.crear_paciente_objeto(paciente, padre, madre)

    except Exception as e:
        log_error(
            f"[FALLO_PREPARACION] paciente_id={instance.pk} detalle={str(e)}",
            app=LogApp.REPLICACION
        )
        return

    # SQL Server
    try:
        sync_paciente_sqlserver(pac)
    except Exception as e:
        log_error(
            f"[FALLO_SQLSERVER] paciente_id={instance.pk} detalle={str(e)}",
            app=LogApp.REPLICACION
        )

    # MySQL
    try:
        sync_paciente_mysql(pac)
    except Exception as e:
        log_error(
            f"[FALLO_MYSQL] paciente_id={instance.pk} detalle={str(e)}",
            app=LogApp.REPLICACION
        )

