from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0008_ejecucion_viaje"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitud",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("EN_PROCESO", "En proceso"),
                    ("FINALIZADA", "Finalizada"),
                    ("CANCELADA", "Cancelada"),
                ],
                db_index=True,
                default="PENDIENTE",
                max_length=30,
            ),
        ),
    ]
