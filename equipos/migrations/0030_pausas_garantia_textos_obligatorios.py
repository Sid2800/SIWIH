from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0029_pausagarantia_observaciones_retorno"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pausagarantia",
            name="motivo",
            field=models.TextField(
                help_text=(
                    "A dónde fue y por qué. Número de orden del proveedor si lo hay."
                ),
                verbose_name="Motivo",
            ),
        ),
        migrations.AddConstraint(
            model_name="pausagarantia",
            constraint=models.CheckConstraint(
                condition=~models.Q(motivo=""),
                name="equipo_pausa_motivo_no_vacio",
            ),
        ),
        migrations.AddConstraint(
            model_name="pausagarantia",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(fecha_retorno__isnull=True)
                    | ~models.Q(observaciones_retorno="")
                ),
                name="equipo_pausa_retorno_con_observacion",
            ),
        ),
    ]
