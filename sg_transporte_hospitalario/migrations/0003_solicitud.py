from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0002_punto_solicitud"),
        ("rrhh", "0003_remove_personalsalud_area_atencion_and_more"),
        ("servicio", "0018_alter_cama_estado_alter_unidad_tipo"),
    ]

    operations = [
        migrations.CreateModel(
            name="Solicitud",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_solicitud", models.CharField(db_index=True, max_length=30, unique=True)),
                ("fecha_solicitud", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("motivo", models.TextField()),
                ("observaciones", models.TextField(blank=True, null=True)),
                ("estado", models.CharField(db_index=True, max_length=30)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("prioridad", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes", to="sg_transporte_hospitalario.prioridad")),
                ("punto_solicitud", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes", to="sg_transporte_hospitalario.puntosolicitud")),
                ("solicitante_empleado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_emitidas", to="rrhh.empleado")),
                ("tipo_solicitud", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes", to="sg_transporte_hospitalario.tiposolicitud")),
                ("lugar_destino", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_destino", to="servicio.institucion_salud")),
                ("lugar_salida", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_salida", to="servicio.institucion_salud")),
            ],
            options={
                "db_table": "transporte_hospitalario_solicitud",
                "ordering": ["-fecha_solicitud", "numero_solicitud"],
                "verbose_name": "Solicitud",
                "verbose_name_plural": "Solicitudes",
            },
        ),
    ]