from django.db import migrations


def normalizar_vacia_sin_paciente(apps, schema_editor):
    AsignacionCamaPaciente = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")
    AsignacionCamaPaciente.objects.filter(estado="VACIA").update(paciente_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0009_seed_camas_vacias_en_asignacion"),
    ]

    operations = [
        migrations.RunPython(normalizar_vacia_sin_paciente, migrations.RunPython.noop),
    ]
