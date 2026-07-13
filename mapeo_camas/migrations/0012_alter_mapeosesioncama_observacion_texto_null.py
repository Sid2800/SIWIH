from django.db import migrations, models



def forwards(apps, schema_editor):
    MapeoSesionCama = apps.get_model("mapeo_camas", "MapeoSesionCama")
    MapeoSesionCama.objects.filter(observacion_texto="").update(observacion_texto=None)



def backwards(apps, schema_editor):
    MapeoSesionCama = apps.get_model("mapeo_camas", "MapeoSesionCama")
    MapeoSesionCama.objects.filter(observacion_texto__isnull=True).update(observacion_texto="")


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0011_add_mapeosesioncama_observacion_texto"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mapeosesioncama",
            name="observacion_texto",
            field=models.CharField(blank=True, default=None, max_length=500, null=True, verbose_name="Observacion libre"),
        ),
        migrations.RunPython(forwards, backwards),
    ]
