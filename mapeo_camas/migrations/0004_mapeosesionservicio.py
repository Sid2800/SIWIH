from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0003_remove_asignacioncamapaciente_fecha_fin_usuario_cierre"),
        ("servicio", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MapeoSesionServicio",
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
                (
                    "servicio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sesiones_mapeo_incluidas",
                        to="servicio.servicio",
                        verbose_name="Servicio",
                    ),
                ),
                (
                    "sesion_mapeo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="servicios_incluidos",
                        to="mapeo_camas.mapeosesioncama",
                        verbose_name="Sesion de mapeo",
                    ),
                ),
            ],
            options={
                "verbose_name": "Servicio incluido en sesion de mapeo",
                "verbose_name_plural": "Servicios incluidos en sesiones de mapeo",
                "db_table": "mapeo_camas_sesion_servicio",
                "ordering": ["sesion_mapeo_id", "servicio_id"],
                "unique_together": {("sesion_mapeo", "servicio")},
            },
        ),
    ]
