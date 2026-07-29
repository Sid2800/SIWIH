from django.db import migrations


COLORES_INICIALES = [
    "BLANCO",
    "NEGRO",
    "GRIS",
    "PLATEADO",
    "AZUL",
    "CELESTE",
    "VERDE",
    "ROJO",
    "AMARILLO",
    "NARANJA",
    "MORADO",
    "MARRON",
    "BEIGE",
    "DORADO",
    "TRANSPARENTE",
]


def seed_colores_dispositivo(apps, schema_editor):
    ColorDispositivo = apps.get_model("equipos", "ColorDispositivo")

    ColorDispositivo.objects.update_or_create(
        nombre="INDEFINIDO",
        defaults={
            "descripcion": "Valor usado cuando el color no aplica.",
            "activo": True,
        },
    )

    for nombre in COLORES_INICIALES:
        ColorDispositivo.objects.update_or_create(
            nombre=nombre,
            defaults={"activo": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0013_seed_areas_gestoras_reales"),
    ]

    operations = [
        migrations.RunPython(
            seed_colores_dispositivo,
            migrations.RunPython.noop,
        ),
    ]
