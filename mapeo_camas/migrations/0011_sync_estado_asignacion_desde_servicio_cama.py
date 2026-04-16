from django.db import migrations


ESTADO_ASIGNACION_POR_ESTADO_CAMA = {
    1: "VACIA",
    2: "OCUPADA",
    3: "ALTA",
    4: "FUERA_SERVICIO",
    5: "CONSULTA_EXTERNA",
}


def sync_estado_asignacion_desde_cama(apps, schema_editor):
    Cama = apps.get_model("servicio", "Cama")
    AsignacionCamaPaciente = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")

    for cama in Cama.objects.all().iterator():
        estado_asignacion = ESTADO_ASIGNACION_POR_ESTADO_CAMA.get(cama.estado, "VACIA")

        asignacion = (
            AsignacionCamaPaciente.objects
            .filter(cama_id=cama.numero_cama)
            .order_by("-fecha_inicio", "-id")
            .first()
        )
        if not asignacion:
            continue

        asignacion.estado = estado_asignacion
        if estado_asignacion == "VACIA":
            asignacion.paciente_id = None
        asignacion.save()


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0010_normalizar_vacia_sin_paciente"),
        ("servicio", "0012_estandarizar_estados_cama"),
    ]

    operations = [
        migrations.RunPython(sync_estado_asignacion_desde_cama, migrations.RunPython.noop),
    ]
