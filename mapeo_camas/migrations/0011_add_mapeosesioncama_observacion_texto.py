from django.db import migrations, models
import django.db.models.deletion


OBSERVACION_DEFAULT = "Sin observaciones"


def forwards(apps, schema_editor):
    EstadoMapeo = apps.get_model("mapeo_camas", "EstadoMapeo")
    MapeoSesionCama = apps.get_model("mapeo_camas", "MapeoSesionCama")

    default_obs = (
        EstadoMapeo.objects.filter(categoria="OBSERVACION", codigo__iexact=OBSERVACION_DEFAULT).first()
    )
    if default_obs is None:
        default_obs = EstadoMapeo.objects.create(
            codigo=OBSERVACION_DEFAULT,
            categoria="OBSERVACION",
            activo=True,
        )

    sesiones = MapeoSesionCama.objects.select_related("observacion")
    for sesion in sesiones.iterator():
        codigo_observacion = getattr(getattr(sesion, "observacion", None), "codigo", "") or ""
        codigo_normalizado = codigo_observacion.strip()
        if codigo_normalizado and codigo_normalizado.lower() != OBSERVACION_DEFAULT.lower():
            sesion.observacion_texto = codigo_normalizado
            sesion.observacion = default_obs
        elif not codigo_normalizado:
            sesion.observacion = default_obs
            sesion.observacion_texto = ""
        else:
            sesion.observacion = default_obs
            sesion.observacion_texto = ""
        sesion.save(update_fields=["observacion", "observacion_texto"])


def backwards(apps, schema_editor):
    # [2026-05-26 AUDIT] No se revierte para no volver a mezclar texto libre con el catálogo.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0010_change_mapeosesioncama_observacion_to_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="mapeosesioncama",
            name="observacion_texto",
            field=models.CharField(blank=True, default="", max_length=500, verbose_name="Observacion libre"),
        ),
        migrations.RunPython(forwards, backwards),
    ]
