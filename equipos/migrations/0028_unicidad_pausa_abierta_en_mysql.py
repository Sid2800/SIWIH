"""Hace cumplir de verdad "una sola pausa abierta por equipo" en MySQL.

La 0027 lo declaraba con un UniqueConstraint condicional, pero MySQL no los
soporta: Django avisa con W036 y la restriccion no llega a crearse. La regla
quedaba solo en Python, donde un doble clic o una peticion repetida podrian
esquivarla y dejar dos pausas abiertas del mismo equipo.

Se sustituye por una columna que vale el id del equipo mientras la pausa esta
abierta y NULL cuando se cierra. MySQL admite varios NULL en un indice unico,
de modo que un indice unico corriente sobre esa columna consigue el efecto
buscado y funciona igual en el resto de motores.
"""

from django.db import migrations, models


def rellenar_columna(apps, schema_editor):
    """Marca las pausas ya abiertas. En la practica todavia no hay ninguna."""
    PausaGarantia = apps.get_model("equipos", "PausaGarantia")

    for pausa in PausaGarantia.objects.filter(fecha_retorno__isnull=True).iterator():
        pausa.equipo_con_pausa_abierta = pausa.dispositivo_id
        pausa.save(update_fields=["equipo_con_pausa_abierta"])


def vaciar_columna(apps, schema_editor):
    """La marcha atras no necesita hacer nada: la columna se elimina."""


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0027_garantia_por_fecha_y_pausas'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='pausagarantia',
            name='equipo_una_pausa_abierta_por_equipo',
        ),
        migrations.AddField(
            model_name='pausagarantia',
            name='equipo_con_pausa_abierta',
            field=models.BigIntegerField(blank=True, editable=False, null=True, unique=True),
        ),
        migrations.RunPython(rellenar_columna, vaciar_columna),
    ]
