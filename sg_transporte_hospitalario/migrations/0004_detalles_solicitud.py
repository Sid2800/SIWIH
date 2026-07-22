from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0003_solicitud"),
        ("paciente", "0021_alter_defuncion_options_and_more"),
        ("ingreso", "0005_ingreso_estado"),
        ("rrhh", "0003_remove_personalsalud_area_atencion_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolicitudPaciente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("ingreso", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_transporte", to="ingreso.ingreso")),
                ("paciente", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_transporte", to="paciente.paciente")),
                ("solicitud", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitud_pacientes", to="sg_transporte_hospitalario.solicitud")),
            ],
            options={
                "db_table": "transporte_hospitalario_solicitud_paciente",
                "ordering": ["-created_at", "id"],
                "verbose_name": "Solicitud paciente",
                "verbose_name_plural": "Solicitudes paciente",
            },
        ),
        migrations.AddConstraint(
            model_name="solicitudpaciente",
            constraint=models.CheckConstraint(
                check=(models.Q(paciente__isnull=False) | models.Q(ingreso__isnull=False)),
                name="ck_th_solicitud_paciente_ref",
            ),
        ),
        migrations.CreateModel(
            name="SolicitudPersonal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("observacion", models.TextField(blank=True, null=True)),
                ("empleado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitudes_personal_transporte", to="rrhh.empleado")),
                ("solicitud", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="solicitud_personal", to="sg_transporte_hospitalario.solicitud")),
            ],
            options={
                "db_table": "transporte_hospitalario_solicitud_personal",
                "ordering": ["id"],
                "verbose_name": "Solicitud personal",
                "verbose_name_plural": "Solicitudes personal",
            },
        ),
    ]