"""Cierra la clave ajena que la migracion anterior acaba de rellenar.

Una pausa sin garantia no pausa nada: la columna se agrego opcional para
poder repuntar las filas existentes y aqui pasa a ser obligatoria.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0041_garantias_con_historial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pausagarantia",
            name="garantia",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pausas",
                to="equipos.garantiadispositivo",
            ),
        ),
    ]
