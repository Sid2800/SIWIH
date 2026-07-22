from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0006_relacion_viaje_solicitud"),
        ("rrhh", "0003_remove_personalsalud_area_atencion_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ViajePersonal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_participacion", models.CharField(max_length=30)),
                ("empleado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viajes_personal_transporte", to="rrhh.empleado")),
                ("viaje", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viaje_personal", to="sg_transporte_hospitalario.viaje")),
            ],
            options={
                "db_table": "transporte_hospitalario_viaje_personal",
                "ordering": ["viaje_id", "id"],
                "verbose_name": "Viaje personal",
                "verbose_name_plural": "Viajes personal",
            },
        ),
    ]