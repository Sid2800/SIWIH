from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0010_seed_catalogos_solicitud"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitud",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("PROGRAMADA", "Programada"),
                    ("EN_EJECUCION", "En ejecución"),
                    ("FINALIZADA", "Finalizada"),
                    ("ANULADA", "Anulada"),
                ],
                db_index=True,
                default="PENDIENTE",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="motivo_anulacion",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="observacion_anulacion",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="anulada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="anulada_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes_anuladas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="motorista",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="viajes",
                to="sg_transporte_hospitalario.motorista",
            ),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="vehiculo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="viajes",
                to="sg_transporte_hospitalario.vehiculo",
            ),
        ),
        migrations.AlterField(
            model_name="viaje",
            name="tipo_viaje",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="viajes",
                to="sg_transporte_hospitalario.tipoviaje",
            ),
        ),
        migrations.AlterField(
            model_name="viajesolicitud",
            name="viaje",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="viaje_solicitudes",
                to="sg_transporte_hospitalario.viaje",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="viajesolicitud",
            name="uq_th_viaje_solicitud",
        ),
        migrations.AddConstraint(
            model_name="viajesolicitud",
            constraint=models.UniqueConstraint(
                fields=["solicitud"],
                name="uq_th_viaje_solicitud_solicitud",
            ),
        ),
    ]
