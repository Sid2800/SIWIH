from django.db import migrations, models


def migrar_estados_cama(apps, schema_editor):
    Cama = apps.get_model("servicio", "Cama")

    # Homologacion legado: "En Mantenimiento" (3) pasa a "Fuera de servicio" (4).
    Cama.objects.filter(estado=3).update(estado=4)


class Migration(migrations.Migration):

    dependencies = [
        ("servicio", "0011_cubiculo_cama_cubiculo"),
    ]

    operations = [
        migrations.RunPython(migrar_estados_cama, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cama",
            name="estado",
            field=models.IntegerField(
                choices=[
                    (1, "Vacia"),
                    (2, "Ocupada"),
                    (3, "Alta"),
                    (4, "Fuera de servicio"),
                    (5, "Consulta externa"),
                ],
                default=1,
                verbose_name="Estado de la Cama",
            ),
        ),
    ]