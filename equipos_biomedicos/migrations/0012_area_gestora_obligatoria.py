from django.db import migrations, models
import django.db.models.deletion


def asignar_area_gestora_indefinida(apps, schema_editor):
    AreaGestora = apps.get_model("equipos_biomedicos", "AreaGestora")
    Dispositivo = apps.get_model("equipos_biomedicos", "Dispositivo")

    area_indefinida, _ = AreaGestora.objects.get_or_create(
        nombre="INDEFINIDO",
        defaults={"descripcion": "Valor usado cuando el area gestora no aplica."},
    )
    Dispositivo.objects.filter(area_gestora__isnull=True).update(
        area_gestora=area_indefinida
    )


class Migration(migrations.Migration):

    dependencies = [
        ("equipos_biomedicos", "0011_areagestora_colordispositivo_and_more"),
    ]

    operations = [
        migrations.RunPython(
            asignar_area_gestora_indefinida,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="dispositivo",
            name="area_gestora",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dispositivos",
                to="equipos_biomedicos.areagestora",
            ),
        ),
    ]
