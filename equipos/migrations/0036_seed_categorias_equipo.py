"""Categorias iniciales y su asignacion a los tipos ya registrados.

Son un punto de partida administrable: el modulo permite agregar, renombrar y
desactivar categorias, asi que esta lista no es definitiva ni pretende serlo.

Los tipos que existieran antes de la categoria quedan en la primera de la
lista, porque la columna es obligatoria y no hay forma de adivinar a que
familia pertenece cada uno. Corregirlos es trabajo de la pantalla de
catalogos, no de una migracion que no puede saberlo.
"""

from django.db import migrations


CATEGORIAS = [
    ("MEDICO", "Equipo biomédico y de atención directa al paciente."),
    ("INFORMATICA", "Cómputo, redes, impresión y telefonía."),
    ("ELECTRICO", "Equipo eléctrico y electromecánico de apoyo."),
    ("MOBILIARIO CLINICO", "Camas, camillas, mesas y mobiliario asistencial."),
    ("INDUSTRIAL", "Cocina, lavandería, calderas y planta física."),
    ("INFRAESTRUCTURA", "Aire acondicionado, plantas eléctricas, agua."),
]

# Categoria de respaldo para los tipos que ya existian sin clasificar.
CATEGORIA_POR_DEFECTO = "MEDICO"


def sembrar(apps, schema_editor):
    CategoriaEquipo = apps.get_model("equipos", "CategoriaEquipo")
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")

    for nombre, descripcion in CATEGORIAS:
        CategoriaEquipo.objects.get_or_create(
            nombre=nombre,
            defaults={"descripcion": descripcion, "activo": True},
        )

    respaldo = CategoriaEquipo.objects.get(nombre=CATEGORIA_POR_DEFECTO)
    TipoDispositivo.objects.filter(categoria__isnull=True).update(
        categoria=respaldo
    )


def revertir(apps, schema_editor):
    """Solo borra las categorias que nadie haya usado todavia.

    Una categoria referida por algun tipo no se toca: al revertir esta
    migracion la columna vuelve a admitir NULL, pero borrar la fila dejaria
    al tipo apuntando a nada.
    """
    CategoriaEquipo = apps.get_model("equipos", "CategoriaEquipo")

    CategoriaEquipo.objects.filter(
        nombre__in=[nombre for nombre, _ in CATEGORIAS],
        tipos__isnull=True,
        tipos_secundarios__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0035_categorias_colores_ubicacion_garantia"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
