"""La tecnologia del tipo pasa de ser un par fijo a ser un catalogo.

Estaba escrita en el codigo como dos opciones -electronico y no electronico-
asi que no habia donde agregar una tercera sin una migracion. En equipo
hospitalario aparecen tambien electromecanicos, neumaticos e hidraulicos, y
anadirlos deberia ser trabajo de quien lleva el catalogo, no del programador.

Las dos opciones existentes se siembran como filas y cada tipo queda apuntando
a la que tenia, asi que no cambia nada de lo ya registrado.
"""

import django.db.models.deletion
from django.db import migrations, models


# Los valores que tenia el campo entero.
ELECTRONICO = 1
NO_ELECTRONICO = 2

NOMBRES = {
    ELECTRONICO: "ELECTRONICO",
    NO_ELECTRONICO: "NO ELECTRONICO",
}

DESCRIPCIONES = {
    "ELECTRONICO": "Lleva electrónica: placas, sensores o programación.",
    "NO ELECTRONICO": "Mecánico o manual, sin componentes electrónicos.",
}


def sembrar_y_convertir(apps, schema_editor):
    TecnologiaEquipo = apps.get_model("equipos", "TecnologiaEquipo")
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")

    tecnologias = {}

    for valor, nombre in NOMBRES.items():
        tecnologia, _ = TecnologiaEquipo.objects.get_or_create(
            nombre=nombre,
            defaults={
                "descripcion": DESCRIPCIONES[nombre],
                "activo": True,
            },
        )
        tecnologias[valor] = tecnologia

    for valor, tecnologia in tecnologias.items():
        TipoDispositivo.objects.filter(tipo_tecnologia=valor).update(
            tecnologia=tecnologia
        )

    # Un tipo sin valor reconocible se deja en electronico, que es el caso
    # mayoritario y el que tenia por defecto la columna vieja.
    TipoDispositivo.objects.filter(tecnologia__isnull=True).update(
        tecnologia=tecnologias[ELECTRONICO]
    )


def devolver_al_entero(apps, schema_editor):
    TecnologiaEquipo = apps.get_model("equipos", "TecnologiaEquipo")
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")

    for valor, nombre in NOMBRES.items():
        tecnologia = TecnologiaEquipo.objects.filter(nombre=nombre).first()

        if tecnologia is not None:
            TipoDispositivo.objects.filter(tecnologia=tecnologia).update(
                tipo_tecnologia=valor
            )


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0042_pausa_garantia_obligatoria"),
    ]

    operations = [
        migrations.CreateModel(
            name="TecnologiaEquipo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, unique=True)),
                ("descripcion", models.CharField(blank=True, max_length=250)),
                ("activo", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Tecnologia de equipo",
                "verbose_name_plural": "Tecnologias de equipo",
                "db_table": "equipo_tecnologia",
                "ordering": ["nombre"],
            },
        ),
        # Se agrega opcional para poder convertir las filas existentes.
        migrations.AddField(
            model_name="tipodispositivo",
            name="tecnologia",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tipos",
                to="equipos.tecnologiaequipo",
                verbose_name="Tecnología",
            ),
        ),
        migrations.RunPython(sembrar_y_convertir, devolver_al_entero),
        # Y ahora si: obligatoria, y la columna vieja fuera.
        migrations.AlterField(
            model_name="tipodispositivo",
            name="tecnologia",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tipos",
                to="equipos.tecnologiaequipo",
                verbose_name="Tecnología",
            ),
        ),
        migrations.RemoveField(
            model_name="tipodispositivo",
            name="tipo_tecnologia",
        ),
    ]
