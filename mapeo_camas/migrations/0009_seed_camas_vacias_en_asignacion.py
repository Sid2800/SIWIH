from django.conf import settings
from django.db import migrations, models


def seed_camas_vacias(apps, schema_editor):
    Cama = apps.get_model("servicio", "Cama")
    AsignacionCamaPaciente = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")

    auth_app, auth_model = settings.AUTH_USER_MODEL.split(".")
    UserModel = apps.get_model(auth_app, auth_model)

    usuario = UserModel.objects.order_by("id").first()
    if usuario is None:
        return

    cama_ids_con_asignacion = set(
        AsignacionCamaPaciente.objects.values_list("cama_id", flat=True)
    )

    camas_vacias_ids = Cama.objects.filter(estado=1).values_list("numero_cama", flat=True)

    nuevos = []
    for cama_id in camas_vacias_ids:
        if cama_id in cama_ids_con_asignacion:
            continue

        nuevos.append(
            AsignacionCamaPaciente(
                cama_id=cama_id,
                paciente_id=None,
                estado="VACIA",
                usuario_asignacion_id=usuario.id,
                usuario_cierre_id=None,
                fecha_fin=None,
            )
        )

    if nuevos:
        AsignacionCamaPaciente.objects.bulk_create(nuevos, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0008_estandarizar_estados_asignacion_cama"),
        ("servicio", "0012_estandarizar_estados_cama"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asignacioncamapaciente",
            name="paciente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="asignaciones_cama",
                to="paciente.paciente",
                verbose_name="Paciente",
            ),
        ),
        migrations.RunPython(seed_camas_vacias, migrations.RunPython.noop),
    ]
