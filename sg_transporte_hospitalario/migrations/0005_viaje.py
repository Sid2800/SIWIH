from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0004_detalles_solicitud"),
    ]

    operations = [
        migrations.CreateModel(
            name="Viaje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero_viaje", models.CharField(db_index=True, max_length=30, unique=True)),
                ("fecha_programacion", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("estado", models.CharField(db_index=True, max_length=30)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("motorista", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viajes", to="sg_transporte_hospitalario.motorista")),
                ("vehiculo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viajes", to="sg_transporte_hospitalario.vehiculo")),
                ("tipo_viaje", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viajes", to="sg_transporte_hospitalario.tipoviaje")),
                ("viatico", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="viajes", to="sg_transporte_hospitalario.viatico")),
            ],
            options={
                "db_table": "transporte_hospitalario_viaje",
                "ordering": ["-fecha_programacion", "numero_viaje"],
                "verbose_name": "Viaje",
                "verbose_name_plural": "Viajes",
            },
        ),
    ]