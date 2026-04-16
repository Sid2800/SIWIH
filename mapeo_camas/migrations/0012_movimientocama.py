from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mapeo_camas", "0011_sync_estado_asignacion_desde_servicio_cama"),
        ("paciente", "0018_defuncion_especialidad_defuncion_servicio_auxiliar_and_more"),
        ("servicio", "0012_estandarizar_estados_cama"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MovimientoCama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_movimiento", models.CharField(db_index=True, default="TRASLADO", max_length=50, verbose_name="Tipo de movimiento")),
                ("fecha_hora", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha y hora")),
                ("observacion", models.CharField(blank=True, default="", max_length=255, verbose_name="Observacion")),
                ("cama_destino", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_como_destino", to="servicio.cama", verbose_name="Cama destino")),
                ("cama_origen", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_como_origen", to="servicio.cama", verbose_name="Cama origen")),
                ("paciente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_cama", to="paciente.paciente", verbose_name="Paciente")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_cama_usuario", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Movimiento de cama",
                "verbose_name_plural": "Movimientos de cama",
                "db_table": "mapeo_camas_MovimientoCama",
                "ordering": ["-fecha_hora"],
                "indexes": [
                    models.Index(fields=["fecha_hora"], name="idx_mov_cama_fecha"),
                    models.Index(fields=["cama_origen", "cama_destino"], name="idx_mov_origen_destino"),
                    models.Index(fields=["paciente", "fecha_hora"], name="idx_mov_paciente_fecha"),
                ],
            },
        ),
    ]
