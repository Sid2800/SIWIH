"""Cierre de la fase de ingreso de equipos.

Tres correcciones antes de empezar con los mantenimientos:

1. "Una sola asignacion abierta por equipo" pasa a imponerla el motor. La
   regla ya estaba en clean(), pero preguntar y despues insertar deja una
   rendija: dos ediciones del mismo equipo a la vez pasan las dos la
   comprobacion y el equipo acaba con dos responsables abiertos.

2. La frecuencia del preventivo pasa a declararse en el tipo. El criterio es
   del tipo y no del aparato -todos los autoclaves se revisan igual- y en el
   equipo queda solo como excepcion.

3. (En el modelo) las ordenes de baja toman su prefijo propio, OTB, para no
   chocar con las de mantenimiento que vienen en la fase siguiente.
"""

import django.core.validators
from django.db import migrations, models


def llenar_candado(apps, schema_editor):
    """Pone el id del equipo en las asignaciones que ya estaban abiertas.

    Sin esto el candado solo valdria para las que se guarden de aqui en
    adelante: las filas viejas se quedarian en NULL, que el indice unico deja
    repetir, y el equipo que ya tiene una asignacion abierta admitiria otra.
    """
    AsignacionDispositivo = apps.get_model("equipos", "AsignacionDispositivo")

    for asignacion in AsignacionDispositivo.objects.filter(
        fecha_fin__isnull=True
    ).iterator():
        AsignacionDispositivo.objects.filter(pk=asignacion.pk).update(
            equipo_con_asignacion_abierta=asignacion.dispositivo_id
        )


def vaciar_candado(apps, schema_editor):
    AsignacionDispositivo = apps.get_model("equipos", "AsignacionDispositivo")
    AsignacionDispositivo.objects.update(equipo_con_asignacion_abierta=None)


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0043_tecnologia_como_catalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='asignaciondispositivo',
            name='equipo_con_asignacion_abierta',
            field=models.BigIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(llenar_candado, vaciar_candado),
        migrations.AlterField(
            model_name='asignaciondispositivo',
            name='equipo_con_asignacion_abierta',
            field=models.BigIntegerField(blank=True, editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='tipodispositivo',
            name='frecuencia_mantenimiento_meses',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Meses entre mantenimientos preventivos de este tipo. Cada equipo puede cambiarla si es una excepción.', null=True, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Frecuencia de mantenimiento (meses)'),
        ),
        migrations.AlterField(
            model_name='dispositivo',
            name='frecuencia_mantenimiento_meses',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Solo si este equipo es una excepción. En blanco se usa la frecuencia de su tipo.', null=True, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Frecuencia propia (meses)'),
        ),
        migrations.AddConstraint(
            model_name='tipodispositivo',
            constraint=models.CheckConstraint(condition=models.Q(('frecuencia_mantenimiento_meses__isnull', True), ('frecuencia_mantenimiento_meses__gt', 0), _connector='OR'), name='equipo_tipo_frecuencia_positiva'),
        ),
    ]
