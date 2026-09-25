"""Los colores pasan a ser una lista ordenada, no un conjunto.

El orden es informacion: el primero es el color con el que se reconoce el
aparato y los demas lo acompanan. Una relacion simple devuelve las filas en el
orden que quiera el motor, asi que hace falta una tabla propia con su columna.

La relacion anterior usaba el mismo nombre de tabla, y una tabla no se puede
crear dos veces: se retira primero. No hay datos que rescatar porque el
inventario todavia no tiene equipos registrados.
"""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0037_categoria_y_ubicacion_obligatorias'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dispositivo',
            name='colores',
        ),
        migrations.CreateModel(
            name='DispositivoColor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('color', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='dispositivos_asignados', to='equipos.colordispositivo')),
                ('dispositivo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='colores_asignados', to='equipos.dispositivo')),
            ],
            options={
                'verbose_name': 'Color del equipo',
                'verbose_name_plural': 'Colores del equipo',
                'db_table': 'equipo_dispositivo_color',
                'ordering': ['orden'],
            },
        ),
        migrations.AddField(
            model_name='dispositivo',
            name='colores',
            field=models.ManyToManyField(blank=True, related_name='dispositivos', through='equipos.DispositivoColor', to='equipos.colordispositivo', verbose_name='Colores'),
        ),
        migrations.AddConstraint(
            model_name='dispositivocolor',
            constraint=models.UniqueConstraint(fields=('dispositivo', 'color'), name='equipo_disp_color_sin_repetir'),
        ),
        migrations.AddConstraint(
            model_name='dispositivocolor',
            constraint=models.UniqueConstraint(fields=('dispositivo', 'orden'), name='equipo_disp_color_orden_unico'),
        ),
        migrations.AddConstraint(
            model_name='dispositivocolor',
            constraint=models.CheckConstraint(condition=models.Q(('orden__gt', 0)), name='equipo_disp_color_orden_positivo'),
        ),
    ]
