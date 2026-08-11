from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0016_viatico_historial_viaje_viatico"),
    ]

    operations = [
        migrations.AlterField(
            model_name="viaje",
            name="tipo_viaje",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Regional"),
                    (2, "Nacional"),
                ],
                db_index=True,
            ),
        ),
    ]