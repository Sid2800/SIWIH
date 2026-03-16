from django.db.models.signals import post_save
from django.contrib import messages
from django.dispatch import receiver
from paciente.models import Paciente, Padre
from django.forms.models import model_to_dict
from core.services.paciente_service import PacienteService
from core.services.padre_service import PadreService
from core.services.externals import sync_paciente_sqlserver, sync_paciente_mysql

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

        # Sincronizar con SQL Server
        resultado_sqlserver = sync_paciente_sqlserver(pac)
        print(f"{resultado_sqlserver}")

        # Sincronizar con MySQL (procedimiento almacenado)
        resultado_sqlserver = sync_paciente_mysql(pac)
        print(f"MySQL sync: {resultado_sqlserver}")

    except Exception as e:
        print(f"❌ Error al sincronizar paciente con SQL Server y MySQL: {e}")