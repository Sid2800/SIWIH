from django.db import migrations


AREAS_GESTORAS_INICIALES = [
    "BIOMEDICA",
    "INFORMATICA",
    "REDES",
    "ANALOGICA",
]


def seed_areas_gestoras_reales(apps, schema_editor):
    AreaGestora = apps.get_model("equipos_biomedicos", "AreaGestora")

    for nombre in AREAS_GESTORAS_INICIALES:
        AreaGestora.objects.update_or_create(
            nombre=nombre,
            defaults={"activo": True},
        )

    AreaGestora.objects.filter(nombre="INDEFINIDO").update(activo=False)


class Migration(migrations.Migration):

    dependencies = [
        ("equipos_biomedicos", "0012_area_gestora_obligatoria"),
    ]

    operations = [
        migrations.RunPython(
            seed_areas_gestoras_reales,
            migrations.RunPython.noop,
        ),
    ]
