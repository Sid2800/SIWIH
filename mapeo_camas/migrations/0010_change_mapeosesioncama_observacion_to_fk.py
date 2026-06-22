from django.db import migrations, models
import django.db.models.deletion


OBSERVACION_DEFAULT = "Sin observaciones"


def forwards(apps, schema_editor):
    EstadoMapeo = apps.get_model("mapeo_camas", "EstadoMapeo")
    MapeoSesionCama = apps.get_model("mapeo_camas", "MapeoSesionCama")

    for sesion in MapeoSesionCama.objects.all().only("id", "observacion"):
        codigo = (getattr(sesion, "observacion", "") or "").strip() or OBSERVACION_DEFAULT
        observacion = (
            EstadoMapeo.objects.filter(categoria="OBSERVACION", codigo__iexact=codigo).first()
        )
        if observacion is None:
            observacion = EstadoMapeo.objects.create(
                codigo=codigo,
                categoria="OBSERVACION",
                activo=True,
            )
        sesion.observacion_catalogo_id = observacion.id
        sesion.save(update_fields=["observacion_catalogo"])


def backwards(apps, schema_editor):
    # [2026-05-26 AUDIT] No se revierte a texto para no perder catalogación estructurada.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0009_seed_asignaciones_vacias_iniciales"),
    ]

    operations = [
        migrations.AddField(
            model_name="mapeosesioncama",
            name="observacion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sesiones_mapeo_como_observacion",
                to="mapeo_camas.estadomapeo",
                verbose_name="Observacion",
                limit_choices_to={"categoria": "OBSERVACION"},
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="mapeosesioncama",
            name="observacion",
        ),
        migrations.RenameField(
            model_name="mapeosesioncama",
            old_name="observacion_catalogo",
            new_name="observacion",
        ),
    ]
