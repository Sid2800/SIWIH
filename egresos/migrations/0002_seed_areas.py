"""
Siembra las 14 áreas del censo de egresos (las hojas del Excel).

Se hace por migración (no por SQL manual), con get_or_create para que sea
idempotente y no duplique al re-aplicar. OA y OP son de tipo 'observación'
(formulario reducido, sin codificación CIE10); el resto es 'censo'.
"""
from django.db import migrations


# (codigo, nombre, tipo, orden)
AREAS = [
    ('710',        'Obstetricia',           'CENSO',        1),
    ('510',        'Ginecología',           'CENSO',        2),
    ('301',        'Pediatría',             'CENSO',        3),
    ('360',        'Neonatología',          'CENSO',        4),
    ('120',        'Medicina de Mujeres',   'CENSO',        5),
    ('110',        'Medicina de Hombres',   'CENSO',        6),
    ('220',        'Cirugía de Mujeres',    'CENSO',        7),
    ('210',        'Cirugía de Hombres',    'CENSO',        8),
    ('OA',         'Observación de Adultos',   'OBSERVACION', 9),
    ('OP',         'Observación de Pediatría', 'OBSERVACION', 10),
    ('DENGUE_OBS', 'Dengue Obstétrico',     'CENSO',        11),
    ('DENGUE_PED', 'Dengue Pediatría',      'CENSO',        12),
    ('DENGUE_MM',  'Dengue Medicina de Mujeres', 'CENSO',   13),
    ('DENGUE_MH',  'Dengue Medicina de Hombres', 'CENSO',   14),
]


def sembrar(apps, schema_editor):
    AreaEgreso = apps.get_model('egresos', 'AreaEgreso')
    for codigo, nombre, tipo, orden in AREAS:
        AreaEgreso.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'tipo': tipo, 'orden': orden, 'activo': True},
        )


def quitar(apps, schema_editor):
    AreaEgreso = apps.get_model('egresos', 'AreaEgreso')
    AreaEgreso.objects.filter(codigo__in=[a[0] for a in AREAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('egresos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
