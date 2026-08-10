from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0028_unicidad_pausa_abierta_en_mysql"),
    ]

    operations = [
        migrations.AddField(
            model_name="pausagarantia",
            name="observaciones_retorno",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Trabajo realizado o novedades informadas al devolver el equipo."
                ),
                verbose_name="Observaciones del retorno",
            ),
        ),
    ]
