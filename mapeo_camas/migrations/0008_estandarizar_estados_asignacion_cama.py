from django.db import migrations, models


def homologar_estados_asignacion(apps, schema_editor):
    AsignacionCamaPaciente = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")

    AsignacionCamaPaciente.objects.filter(estado="ACTIVA").update(estado="OCUPADA")
    AsignacionCamaPaciente.objects.filter(estado="CERRADA").update(estado="VACIA")


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0007_estandarizar_estados_historial_cama"),
    ]

    operations = [
        migrations.RunPython(homologar_estados_asignacion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="asignacioncamapaciente",
            name="estado",
            field=models.CharField(
                choices=[
                    ("VACIA", "Vacia"),
                    ("OCUPADA", "Ocupada"),
                    ("ALTA", "Alta"),
                    ("FUERA_SERVICIO", "Fuera de servicio"),
                    ("CONSULTA_EXTERNA", "Consulta externa"),
                ],
                db_index=True,
                default="VACIA",
                max_length=20,
                verbose_name="Estado",
            ),
        ),
    ]
