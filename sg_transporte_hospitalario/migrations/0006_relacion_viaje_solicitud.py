from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0005_viaje"),
    ]

    operations = [
        migrations.CreateModel(
            name="ViajeSolicitud",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_asignacion", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("solicitud", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viaje_solicitudes", to="sg_transporte_hospitalario.solicitud")),
                ("viaje", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viaje_solicitudes", to="sg_transporte_hospitalario.viaje")),
            ],
            options={
                "db_table": "transporte_hospitalario_viaje_solicitud",
                "ordering": ["-fecha_asignacion", "id"],
                "verbose_name": "Viaje solicitud",
                "verbose_name_plural": "Viajes solicitud",
            },
        ),
        migrations.AddConstraint(
            model_name="viajesolicitud",
            constraint=models.UniqueConstraint(fields=["viaje", "solicitud"], name="uq_th_viaje_solicitud"),
        ),
    ]