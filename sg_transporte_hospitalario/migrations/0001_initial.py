from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("rrhh", "0003_remove_personalsalud_area_atencion_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoSolicitud",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=30, unique=True)),
                ("nombre", models.CharField(db_index=True, max_length=120)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "transporte_hospitalario_tipo_solicitud",
                "ordering": ["nombre"],
                "verbose_name": "Tipo solicitud",
                "verbose_name_plural": "Tipos solicitud",
            },
        ),
        migrations.CreateModel(
            name="Prioridad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=30, unique=True)),
                ("nombre", models.CharField(db_index=True, max_length=120)),
                ("nivel", models.PositiveSmallIntegerField(db_index=True)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "transporte_hospitalario_prioridad",
                "ordering": ["nivel", "nombre"],
                "verbose_name": "Prioridad",
                "verbose_name_plural": "Prioridades",
            },
        ),
        migrations.CreateModel(
            name="TipoViaje",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=30, unique=True)),
                ("nombre", models.CharField(db_index=True, max_length=120)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "transporte_hospitalario_tipo_viaje",
                "ordering": ["nombre"],
                "verbose_name": "Tipo viaje",
                "verbose_name_plural": "Tipos viaje",
            },
        ),
        migrations.CreateModel(
            name="Viatico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=30, unique=True)),
                ("nombre", models.CharField(db_index=True, max_length=120)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "transporte_hospitalario_viatico",
                "ordering": ["nombre"],
                "verbose_name": "Viatico",
                "verbose_name_plural": "Viaticos",
            },
        ),
        migrations.CreateModel(
            name="Vehiculo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=30, unique=True)),
                ("placa", models.CharField(db_index=True, max_length=20, unique=True)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "transporte_hospitalario_vehiculo",
                "ordering": ["codigo"],
                "verbose_name": "Vehiculo",
                "verbose_name_plural": "Vehiculos",
            },
        ),
        migrations.CreateModel(
            name="Motorista",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activo", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("empleado", models.OneToOneField(on_delete=models.PROTECT, related_name="motorista", to="rrhh.empleado")),
            ],
            options={
                "db_table": "transporte_hospitalario_motorista",
                "ordering": ["id"],
                "verbose_name": "Motorista",
                "verbose_name_plural": "Motoristas",
            },
        ),
    ]