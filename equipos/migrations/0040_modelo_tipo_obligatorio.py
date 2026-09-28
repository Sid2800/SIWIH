"""Cierra la columna que la migracion anterior acaba de rellenar.

Un modelo sin tipo no se puede ofrecer en ninguna cascada: no se sabe bajo que
equipo mostrarlo. Se separa en su propia migracion porque la columna se
agrego admitiendo NULL para poder clasificar las filas existentes primero.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0039_modelo_por_tipo_y_tecnologia_del_tipo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modelodispositivo",
            name="tipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="modelos",
                to="equipos.tipodispositivo",
                verbose_name="Tipo de equipo",
            ),
        ),
    ]
