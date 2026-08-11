from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0015_ref_021_ejecucion_viaje"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="viatico",
            name="monto_vigente",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.CreateModel(
            name="ViaticoHistorial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monto_anterior", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("monto_nuevo", models.DecimalField(decimal_places=2, max_digits=12)),
                ("motivo", models.TextField()),
                ("fecha_cambio", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("cambiado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="viaticos_historial_cambios", to=settings.AUTH_USER_MODEL)),
                ("viatico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historial_cambios", to="sg_transporte_hospitalario.viatico")),
            ],
            options={
                "db_table": "transporte_hospitalario_viatico_historial",
                "ordering": ["-fecha_cambio", "-id"],
                "verbose_name": "Viatico historial",
                "verbose_name_plural": "Viaticos historial",
            },
        ),
        migrations.CreateModel(
            name="ViajeViatico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monto_aplicado", models.DecimalField(decimal_places=2, max_digits=12)),
                ("fecha_asignacion", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("observacion", models.TextField(blank=True, null=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="viajes_viaticos_creados", to=settings.AUTH_USER_MODEL)),
                ("viaje", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viaje_viaticos", to="sg_transporte_hospitalario.viaje")),
                ("viatico", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viaje_viaticos", to="sg_transporte_hospitalario.viatico")),
            ],
            options={
                "db_table": "transporte_hospitalario_viaje_viatico",
                "ordering": ["-fecha_asignacion", "-id"],
                "verbose_name": "Viaje viatico",
                "verbose_name_plural": "Viajes viatico",
            },
        ),
    ]
