from django.conf import settings
from django.db import migrations


def seed_asignaciones_vacias_iniciales(apps, schema_editor):
    EstadoMapeo = apps.get_model("mapeo_camas", "EstadoMapeo")
    AsignacionCamaPaciente = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")
    Cama = apps.get_model("servicio", "Cama")

    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    Usuario = apps.get_model(app_label, model_name)

    # [2026-05-26 FEATURE] Semilla inicial para asegurar estado VACIA por cama.
    estado_vacia = EstadoMapeo.objects.filter(
        codigo="VACIA",
        categoria="ESTADO_CAMA",
    ).first()
    if not estado_vacia:
        return

    usuario = Usuario.objects.order_by("id").first()
    if usuario is None:
        username_field = getattr(Usuario, "USERNAME_FIELD", "username")
        usuario = Usuario.objects.create(**{username_field: "sistema_mapeo_seed"})
        if hasattr(usuario, "set_unusable_password"):
            usuario.set_unusable_password()
            usuario.save(update_fields=["password"])

    camas_con_asignacion = set(
        AsignacionCamaPaciente.objects.values_list("cama_id", flat=True)
    )
    camas_sin_asignacion = Cama.objects.exclude(pk__in=camas_con_asignacion)

    nuevas_asignaciones = [
        AsignacionCamaPaciente(
            cama_id=cama.pk,
            estado_id=estado_vacia.pk,
            ingreso_id=None,
            usuario_asignacion_id=usuario.pk,
        )
        for cama in camas_sin_asignacion.iterator()
    ]

    if nuevas_asignaciones:
        AsignacionCamaPaciente.objects.bulk_create(nuevas_asignaciones, batch_size=500)


def noop_reverse(apps, schema_editor):
    # [2026-05-26 AUDIT] Reversa no destructiva para no borrar historial operativo.
    return


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mapeo_camas", "0008_drop_paciente_columns_use_ingreso_only"),
    ]

    operations = [
        migrations.RunPython(seed_asignaciones_vacias_iniciales, noop_reverse),
    ]
