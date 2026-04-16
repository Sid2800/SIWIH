from django.db import migrations, models


def homologar_estados_historial(apps, schema_editor):
    HistorialEstadoCama = apps.get_model("mapeo_camas", "HistorialEstadoCama")

    HistorialEstadoCama.objects.filter(estado_anterior="LIBRE").update(estado_anterior="VACIA")
    HistorialEstadoCama.objects.filter(estado_nuevo="LIBRE").update(estado_nuevo="VACIA")

    HistorialEstadoCama.objects.filter(estado_anterior="MANTENIMIENTO").update(estado_anterior="FUERA_SERVICIO")
    HistorialEstadoCama.objects.filter(estado_nuevo="MANTENIMIENTO").update(estado_nuevo="FUERA_SERVICIO")

    # PREALTA queda absorbido por ALTA dentro del nuevo catalogo.
    HistorialEstadoCama.objects.filter(estado_anterior="PREALTA").update(estado_anterior="ALTA")
    HistorialEstadoCama.objects.filter(estado_nuevo="PREALTA").update(estado_nuevo="ALTA")


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0006_alter_historialestadocama_fecha_hora"),
    ]

    operations = [
        migrations.RunPython(homologar_estados_historial, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="historialestadocama",
            name="estado_anterior",
            field=models.CharField(
                blank=True,
                choices=[
                    ("VACIA", "Vacia"),
                    ("OCUPADA", "Ocupada"),
                    ("ALTA", "Alta"),
                    ("FUERA_SERVICIO", "Fuera de servicio"),
                    ("CONSULTA_EXTERNA", "Consulta externa"),
                ],
                max_length=20,
                null=True,
                verbose_name="Estado anterior",
            ),
        ),
        migrations.AlterField(
            model_name="historialestadocama",
            name="estado_nuevo",
            field=models.CharField(
                choices=[
                    ("VACIA", "Vacia"),
                    ("OCUPADA", "Ocupada"),
                    ("ALTA", "Alta"),
                    ("FUERA_SERVICIO", "Fuera de servicio"),
                    ("CONSULTA_EXTERNA", "Consulta externa"),
                ],
                max_length=20,
                verbose_name="Estado nuevo",
            ),
        ),
    ]