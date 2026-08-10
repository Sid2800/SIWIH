from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0012_viajesolicitud_creado_por"),
    ]

    operations = [
        migrations.AddField(
            model_name="viaje",
            name="centro_costo",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="tipo_viaje",
            field=models.CharField(
                blank=True,
                choices=[
                    ("REGIONAL", "Regional"),
                    ("NACIONAL", "Nacional"),
                ],
                db_index=True,
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="viatico",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]
