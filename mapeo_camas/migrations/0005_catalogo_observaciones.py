from django.db import migrations, models
import django.db.models.deletion


OBSERVACION_DEFAULT = "Sin observaciones"


def forwards(apps, schema_editor):
    EstadoMapeo = apps.get_model("mapeo_camas", "EstadoMapeo")
    DetalleMapeoCama = apps.get_model("mapeo_camas", "DetalleMapeoCama")
    HistorialEstadoCama = apps.get_model("mapeo_camas", "HistorialEstadoCama")
    MovimientoCama = apps.get_model("mapeo_camas", "MovimientoCama")

    def get_observacion(codigo):
        codigo_normalizado = (codigo or "").strip() or OBSERVACION_DEFAULT
        observacion, _ = EstadoMapeo.objects.get_or_create(
            codigo=codigo_normalizado,
            categoria="OBSERVACION",
            defaults={"activo": True},
        )
        return observacion

    for model, field_name in (
        (DetalleMapeoCama, "observacion_catalogo"),
        (HistorialEstadoCama, "observacion_catalogo"),
        (MovimientoCama, "observacion_catalogo"),
    ):
        for row in model.objects.all().only("id", "observacion"):
            codigo = getattr(row, "observacion", "") or ""
            setattr(row, field_name, get_observacion(codigo))
            row.save(update_fields=[field_name])


def backwards(apps, schema_editor):
    # La migracion no es reversible de forma segura porque las columnas de texto
    # originales se eliminan al consolidar la FK catalogada.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0004_mapeosesionservicio"),
    ]

    operations = [
        migrations.AlterField(
            model_name="estadomapeo",
            name="codigo",
            field=models.CharField(db_index=True, max_length=255, unique=True, verbose_name="Código"),
        ),
        migrations.AddField(
            model_name="detallemapeocama",
            name="observacion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="detalles_mapeo_como_observacion",
                to="mapeo_camas.estadomapeo",
                verbose_name="Observacion",
                limit_choices_to={"categoria": "OBSERVACION"},
            ),
        ),
        migrations.AddField(
            model_name="historialestadocama",
            name="observacion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="historiales_como_observacion",
                to="mapeo_camas.estadomapeo",
                verbose_name="Observacion",
                limit_choices_to={"categoria": "OBSERVACION"},
            ),
        ),
        migrations.AddField(
            model_name="movimientocama",
            name="observacion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="movimientos_como_observacion",
                to="mapeo_camas.estadomapeo",
                verbose_name="Observacion",
                limit_choices_to={"categoria": "OBSERVACION"},
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="detallemapeocama",
            name="observacion",
        ),
        migrations.RemoveField(
            model_name="historialestadocama",
            name="observacion",
        ),
        migrations.RemoveField(
            model_name="movimientocama",
            name="observacion",
        ),
        migrations.RenameField(
            model_name="detallemapeocama",
            old_name="observacion_catalogo",
            new_name="observacion",
        ),
        migrations.RenameField(
            model_name="historialestadocama",
            old_name="observacion_catalogo",
            new_name="observacion",
        ),
        migrations.RenameField(
            model_name="movimientocama",
            old_name="observacion_catalogo",
            new_name="observacion",
        ),
    ]
