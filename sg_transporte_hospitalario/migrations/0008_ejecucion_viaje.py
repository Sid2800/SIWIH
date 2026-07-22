from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sg_transporte_hospitalario", "0007_personal_viaje"),
    ]

    operations = [
        migrations.CreateModel(
            name="EjecucionViaje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_salida", models.DateTimeField(db_index=True)),
                ("fecha_retorno", models.DateTimeField(db_index=True)),
                ("kilometraje_salida", models.DecimalField(decimal_places=2, max_digits=10)),
                ("kilometraje_retorno", models.DecimalField(decimal_places=2, max_digits=10)),
                ("combustible_salida", models.DecimalField(decimal_places=2, max_digits=10)),
                ("combustible_retorno", models.DecimalField(decimal_places=2, max_digits=10)),
                ("observaciones", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("viaje", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="ejecucion_viaje", to="sg_transporte_hospitalario.viaje")),
            ],
            options={
                "db_table": "transporte_hospitalario_ejecucion_viaje",
                "ordering": ["-fecha_salida", "id"],
                "verbose_name": "Ejecucion viaje",
                "verbose_name_plural": "Ejecuciones viaje",
            },
        ),
    ]