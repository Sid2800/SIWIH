"""Cada modelo pasa a pertenecer a una marca.

TRATAMIENTO DE LOS DATOS EXISTENTES
-----------------------------------
Antes, marca y modelo eran catalogos independientes y un mismo modelo podia
aparecer con marcas distintas segun el equipo. Al colgar el modelo de una
marca hay que resolver esas combinaciones sin perder ningun registro. Se
aplican cuatro reglas, en este orden:

1. Modelo llamado "INDEFINIDO"
   Deja de existir como fila de catalogo. Los equipos que lo usaban quedan con
   modelo NULL, que es como se representa ahora "no se conoce el modelo". La
   interfaz sigue mostrando la palabra INDEFINIDO.

2. Modelo usado con una sola marca
   Se le asigna esa marca. Es un dato observado, no una suposicion.

3. Modelo usado con varias marcas
   No se elige una ni se descarta el resto: se divide en un modelo por cada
   combinacion realmente existente y cada equipo se repunta al suyo. Esto es
   posible porque el mismo nombre puede repetirse entre marcas distintas. Se
   conserva el 100% de los equipos y no se reasigna nada en silencio.
   Algunas de estas combinaciones son errores de captura (por ejemplo un
   switch de red registrado bajo una marca de monitores). Se preservan tal
   cual para que alguien las revise desde la vista de catalogo.

4. Modelo que ningun equipo usa
   No hay dato del que deducir su marca y el catalogo se cargo fuera de
   migraciones, asi que no existe fuente autoritativa. Inventar la relacion
   seria adivinar. Se agrupan bajo la marca "SIN CLASIFICAR" y se desactivan:
   siguen existiendo, no aparecen en el alta de equipos y quedan listados como
   pendientes de clasificar en la vista de catalogo.

La marca "SIN CLASIFICAR" nace inactiva para no ensuciar el selector de marcas
del formulario de equipos.
"""
from collections import defaultdict

import django.db.models.deletion
from django.db import migrations, models


MARCA_PENDIENTE = "SIN CLASIFICAR"
NOMBRE_INDEFINIDO = "INDEFINIDO"


def asignar_marcas_a_modelos(apps, schema_editor):
    Marca = apps.get_model("equipos", "MarcaDispositivo")
    Modelo = apps.get_model("equipos", "ModeloDispositivo")
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    db = schema_editor.connection.alias

    # --- Regla 1: el modelo INDEFINIDO se convierte en ausencia de modelo ---
    indefinidos = list(
        Modelo.objects.using(db)
        .filter(nombre=NOMBRE_INDEFINIDO)
        .values_list("pk", flat=True)
    )
    if indefinidos:
        Dispositivo.objects.using(db).filter(
            modelo_id__in=indefinidos
        ).update(modelo=None)
        Modelo.objects.using(db).filter(pk__in=indefinidos).delete()

    # --- Combinaciones (modelo -> marcas) observadas en equipos reales ---
    combinaciones = defaultdict(set)
    for fila in (
        Dispositivo.objects.using(db)
        .filter(modelo__isnull=False)
        .values("marca_id", "modelo_id")
    ):
        if fila["marca_id"] is not None:
            combinaciones[fila["modelo_id"]].add(fila["marca_id"])

    marca_pendiente = None

    for modelo in Modelo.objects.using(db).all():
        marcas = sorted(combinaciones.get(modelo.pk, set()))

        # --- Regla 4: nunca usado, no hay de donde deducir la marca ---
        if not marcas:
            if marca_pendiente is None:
                marca_pendiente, _ = Marca.objects.using(db).get_or_create(
                    nombre=MARCA_PENDIENTE,
                    defaults={
                        "descripcion": (
                            "Modelos heredados sin marca conocida. "
                            "Reasignelos desde el catalogo de marcas."
                        ),
                        "activo": False,
                    },
                )
            Modelo.objects.using(db).filter(pk=modelo.pk).update(
                marca_id=marca_pendiente.pk,
                activo=False,
            )
            continue

        # --- Regla 2: una sola marca, asignacion directa ---
        Modelo.objects.using(db).filter(pk=modelo.pk).update(marca_id=marcas[0])

        # --- Regla 3: el resto de marcas recibe su propia copia del modelo ---
        for marca_id in marcas[1:]:
            copia = Modelo.objects.using(db).create(
                marca_id=marca_id,
                nombre=modelo.nombre,
                descripcion=modelo.descripcion,
                activo=modelo.activo,
            )
            Dispositivo.objects.using(db).filter(
                modelo_id=modelo.pk,
                marca_id=marca_id,
            ).update(modelo_id=copia.pk)


def revertir(apps, schema_editor):
    """Los modelos divididos no se pueden volver a unir sin perder el vinculo
    de cada equipo, asi que la vuelta atras solo deshace el esquema."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0020_ordentrabajobajadispositivo"),
    ]

    operations = [
        # El nombre deja de ser unico a nivel global antes de dividir modelos,
        # porque la division crea nombres repetidos entre marcas distintas.
        migrations.AlterField(
            model_name="modelodispositivo",
            name="nombre",
            field=models.CharField(max_length=100),
        ),
        # Se agrega nullable para que las filas existentes sobrevivan hasta que
        # el paso de datos les asigne su marca.
        migrations.AddField(
            model_name="modelodispositivo",
            name="marca",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="modelos",
                to="equipos.marcadispositivo",
                verbose_name="Marca",
            ),
        ),
        migrations.RunPython(asignar_marcas_a_modelos, revertir),
        migrations.AlterField(
            model_name="modelodispositivo",
            name="marca",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="modelos",
                to="equipos.marcadispositivo",
                verbose_name="Marca",
            ),
        ),
        migrations.AlterModelOptions(
            name="modelodispositivo",
            options={
                "ordering": ["marca__nombre", "nombre"],
                "verbose_name": "Modelo de equipo",
                "verbose_name_plural": "Modelos de equipo",
            },
        ),
        migrations.AddConstraint(
            model_name="modelodispositivo",
            constraint=models.UniqueConstraint(
                fields=("marca", "nombre"),
                name="equipo_modelo_unico_por_marca",
            ),
        ),
    ]
