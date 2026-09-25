"""Cierra las dos columnas nuevas que no admiten quedarse vacias.

Se agregaron aceptando NULL para poder sembrar las categorias en el paso
anterior. Un tipo sin categoria no se puede clasificar ni reportar, y una
asignacion sin ubicacion no dice donde esta el equipo, que es justamente para
lo que existe: ambas pasan a ser obligatorias en el motor y no solo en el
formulario.

Se escribe a mano porque makemigrations pregunta que hacer con las filas que
ya tuvieran NULL. Aqui no hay ninguna: la de tipos la acaba de rellenar la
migracion 0036 y las asignaciones anteriores se perdieron al cambiar de par de
columnas excluyentes a una sola.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("expediente", "0009_poblar_ubicaciones"),
        ("equipos", "0036_seed_categorias_equipo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tipodispositivo",
            name="categoria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tipos",
                to="equipos.categoriaequipo",
                verbose_name="Categoria principal",
            ),
        ),
        migrations.AlterField(
            model_name="asignaciondispositivo",
            name="ubicacion",
            field=models.ForeignKey(
                help_text=(
                    "Punto clínico o no clínico donde queda cargado el equipo."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asignaciones_dispositivos_equipos",
                to="expediente.expedienteubicacion",
                verbose_name="Unidad o área",
            ),
        ),
    ]
