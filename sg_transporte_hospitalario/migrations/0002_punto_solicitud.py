from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0001_initial"),
        ("servicio", "0018_alter_cama_estado_alter_unidad_tipo"),
    ]

    operations = [
        migrations.CreateModel(
            name="PuntoSolicitud",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("unidad_clinica", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="puntos_solicitud_clinica", to="servicio.unidad_clinica")),
                ("unidad", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="puntos_solicitud_unidad", to="servicio.unidad")),
            ],
            options={
                "db_table": "transporte_hospitalario_punto_solicitud",
                "ordering": ["id"],
                "verbose_name": "Punto solicitud",
                "verbose_name_plural": "Puntos solicitud",
            },
        ),
        migrations.AddConstraint(
            model_name="puntosolicitud",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(unidad_clinica__isnull=False, unidad__isnull=True)
                    | models.Q(unidad_clinica__isnull=True, unidad__isnull=False)
                ),
                name="ck_th_punto_solicitud_xor",
            ),
        ),
    ]