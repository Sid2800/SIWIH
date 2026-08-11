import django.db.models.deletion
from django.db import migrations, models


def validar_tabla_dispositivos_vacia(apps, schema_editor):
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    alias = schema_editor.connection.alias

    if Dispositivo.objects.using(alias).exists():
        raise RuntimeError(
            "No se puede agregar la procedencia obligatoria porque "
            "equipo_dispositivo contiene registros. Limpie la tabla o defina "
            "una estrategia de migracion antes de continuar."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0030_pausas_garantia_textos_obligatorios"),
    ]

    operations = [
        migrations.RunPython(
            validar_tabla_dispositivos_vacia,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="Procedencia",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=150, unique=True)),
                (
                    "tipo",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "Empresa"), (2, "Persona")],
                    ),
                ),
                (
                    "rtn",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        unique=True,
                    ),
                ),
                ("telefono", models.CharField(blank=True, max_length=30)),
                ("contacto", models.CharField(blank=True, max_length=150)),
                ("correo", models.EmailField(blank=True, max_length=254)),
                ("activo", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Procedencia de equipo",
                "verbose_name_plural": "Procedencias de equipos",
                "db_table": "equipo_procedencia",
                "ordering": ["nombre"],
            },
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="modalidad_procedencia",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "Compra"), (2, "Donación")],
            ),
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="numero_referencia",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="procedencia",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dispositivos",
                to="equipos.procedencia",
            ),
        ),
    ]
