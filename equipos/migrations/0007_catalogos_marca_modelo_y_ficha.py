# Generated manually on 2026-06-22

import django.db.models.deletion
from django.db import migrations, models


INDEFINIDO = "INDEFINIDO"


def normalizar_nombre(valor):
    return (valor or "").strip().upper() or INDEFINIDO


def migrar_catalogos_marca_modelo(apps, schema_editor):
    TipoDispositivo = apps.get_model("equipos", "TipoDispositivo")
    MarcaDispositivo = apps.get_model("equipos", "MarcaDispositivo")
    ModeloDispositivo = apps.get_model("equipos", "ModeloDispositivo")
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    db_alias = schema_editor.connection.alias

    for tipo in TipoDispositivo.objects.using(db_alias).all():
        TipoDispositivo.objects.using(db_alias).filter(pk=tipo.pk).update(
            nombre=normalizar_nombre(tipo.nombre)
        )

    marca_indefinida, _ = MarcaDispositivo.objects.using(db_alias).get_or_create(
        nombre=INDEFINIDO,
        defaults={"descripcion": "Valor usado cuando el dato no aplica."},
    )
    modelo_indefinido, _ = ModeloDispositivo.objects.using(db_alias).get_or_create(
        nombre=INDEFINIDO,
        defaults={"descripcion": "Valor usado cuando el dato no aplica."},
    )

    for dispositivo in Dispositivo.objects.using(db_alias).all():
        nombre_marca = normalizar_nombre(getattr(dispositivo, "marca", ""))
        nombre_modelo = normalizar_nombre(getattr(dispositivo, "modelo", ""))

        if nombre_marca == INDEFINIDO:
            marca = marca_indefinida
        else:
            marca, _ = MarcaDispositivo.objects.using(db_alias).get_or_create(
                nombre=nombre_marca
            )

        if nombre_modelo == INDEFINIDO:
            modelo = modelo_indefinido
        else:
            modelo, _ = ModeloDispositivo.objects.using(db_alias).get_or_create(
                nombre=nombre_modelo
            )

        Dispositivo.objects.using(db_alias).filter(pk=dispositivo.pk).update(
            marca_catalogo_id=marca.pk,
            modelo_catalogo_id=modelo.pk,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("equipos", "0006_alter_asignaciondispositivo_table_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarcaDispositivo",
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
                ("nombre", models.CharField(max_length=100, unique=True)),
                ("descripcion", models.CharField(blank=True, max_length=250)),
                ("activo", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Marca de equipo",
                "verbose_name_plural": "Marcas de equipo",
                "ordering": ["nombre"],
                "db_table": "equipo_marca_dispositivo",
            },
        ),
        migrations.CreateModel(
            name="ModeloDispositivo",
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
                ("nombre", models.CharField(max_length=100, unique=True)),
                ("descripcion", models.CharField(blank=True, max_length=250)),
                ("activo", models.BooleanField(db_index=True, default=True)),
            ],
            options={
                "verbose_name": "Modelo de equipo",
                "verbose_name_plural": "Modelos de equipo",
                "ordering": ["nombre"],
                "db_table": "equipo_modelo_dispositivo",
            },
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="inventario_numero_ficha",
            field=models.CharField(blank=True, max_length=30, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="marca_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dispositivos",
                to="equipos.marcadispositivo",
            ),
        ),
        migrations.AddField(
            model_name="dispositivo",
            name="modelo_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dispositivos",
                to="equipos.modelodispositivo",
            ),
        ),
        migrations.RunPython(
            migrar_catalogos_marca_modelo,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="dispositivo",
            name="nombre",
        ),
        migrations.RemoveField(
            model_name="dispositivo",
            name="marca",
        ),
        migrations.RemoveField(
            model_name="dispositivo",
            name="modelo",
        ),
        migrations.RenameField(
            model_name="dispositivo",
            old_name="marca_catalogo",
            new_name="marca",
        ),
        migrations.RenameField(
            model_name="dispositivo",
            old_name="modelo_catalogo",
            new_name="modelo",
        ),
        migrations.AlterModelOptions(
            name="dispositivo",
            options={
                "ordering": ["tipo_id", "marca_id", "modelo_id", "numero_serie"],
                "verbose_name": "Equipo",
                "verbose_name_plural": "Equipos",
            },
        ),
    ]
