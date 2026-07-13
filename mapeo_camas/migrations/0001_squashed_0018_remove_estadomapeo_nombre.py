from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_estados_mapeo(apps, schema_editor):
    EstadoMapeo = apps.get_model("mapeo_camas", "EstadoMapeo")

    catalogo = [
        ("VACIA", "ESTADO_CAMA"),
        ("OCUPADA", "ESTADO_CAMA"),
        ("PRE_ALTA", "ESTADO_CAMA"),
        ("FUERA_SERVICIO", "ESTADO_CAMA"),
        ("CONSULTA_EXTERNA", "ESTADO_CAMA"),
        ("ALTA", "ESTADO_CAMA"),
        ("EN_PROGRESO", "ESTADO_SESION"),
        ("FINALIZADO", "ESTADO_SESION"),
        ("CANCELADO", "ESTADO_SESION"),
        ("CONFIRMACION", "TIPO_ACCION"),
        ("CAMBIO", "TIPO_ACCION"),
        ("TRASLADO", "TIPO_ACCION"),
        ("CORRECCION", "TIPO_ACCION"),
    ]

    for codigo, categoria in catalogo:
        EstadoMapeo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "categoria": categoria,
                "activo": True,
            },
        )


class Migration(migrations.Migration):
    replaces = [
        ("mapeo_camas", "0001_initial"),
        ("mapeo_camas", "0002_alter_asignacioncamapaciente_table"),
        ("mapeo_camas", "0003_asignacioncamapaciente_uq_asig_cama_activa_and_more"),
        ("mapeo_camas", "0004_remove_asignacioncamapaciente_uq_asig_cama_activa_and_more"),
        ("mapeo_camas", "0005_historialestadocama"),
        ("mapeo_camas", "0006_alter_historialestadocama_fecha_hora"),
        ("mapeo_camas", "0007_estandarizar_estados_historial_cama"),
        ("mapeo_camas", "0008_estandarizar_estados_asignacion_cama"),
        ("mapeo_camas", "0009_seed_camas_vacias_en_asignacion"),
        ("mapeo_camas", "0010_normalizar_vacia_sin_paciente"),
        ("mapeo_camas", "0011_sync_estado_asignacion_desde_servicio_cama"),
        ("mapeo_camas", "0012_movimientocama"),
        ("mapeo_camas", "0013_mapeosesioncama_detallemapeocama"),
        ("mapeo_camas", "0014_detallemapeocama_estado_actual_and_more"),
        ("mapeo_camas", "0015_add_observacion_to_mapeosesioncama"),
        ("mapeo_camas", "0016_prealta_estado_operativo"),
        ("mapeo_camas", "0017_normalizar_estados_a_catalogo"),
        ("mapeo_camas", "0018_remove_estadomapeo_nombre"),
    ]

    initial = True

    dependencies = [
        ("paciente", "0018_defuncion_especialidad_defuncion_servicio_auxiliar_and_more"),
        ("servicio", "0015_merge_20260422_1515"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EstadoMapeo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=40, unique=True, verbose_name="Codigo")),
                (
                    "categoria",
                    models.CharField(
                        choices=[
                            ("ESTADO_CAMA", "Estado de cama"),
                            ("ESTADO_SESION", "Estado de sesion"),
                            ("TIPO_ACCION", "Tipo de accion"),
                        ],
                        max_length=20,
                        verbose_name="Categoria",
                    ),
                ),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
            ],
            options={
                "verbose_name": "Estado de mapeo",
                "verbose_name_plural": "Estados de mapeo",
                "db_table": "mapeo_camas_estado_mapeo",
                "ordering": ["categoria", "codigo"],
            },
        ),
        migrations.CreateModel(
            name="AsignacionCamaPaciente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_inicio", models.DateTimeField(auto_now_add=True, verbose_name="Fecha de inicio")),
                ("fecha_fin", models.DateTimeField(blank=True, null=True, verbose_name="Fecha de fin")),
                ("cama", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_cama", to="servicio.cama", verbose_name="Cama")),
                ("paciente", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_cama", to="paciente.paciente", verbose_name="Paciente")),
                ("estado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_cama", to="mapeo_camas.estadomapeo", verbose_name="Estado")),
                ("usuario_asignacion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_cama_creadas", to=settings.AUTH_USER_MODEL, verbose_name="Usuario de asignacion")),
                ("usuario_cierre", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_cama_cerradas", to=settings.AUTH_USER_MODEL, verbose_name="Usuario de cierre")),
            ],
            options={
                "verbose_name": "Asignacion de cama por paciente",
                "verbose_name_plural": "Asignaciones de cama por paciente",
                "db_table": "mapeo_camas_asignacion_cama_paciente",
                "ordering": ["-fecha_inicio"],
                "indexes": [
                    models.Index(fields=["cama", "estado"], name="idx_asig_cama_estado"),
                    models.Index(fields=["paciente", "estado"], name="idx_asig_paciente_estado"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        check=models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=models.F("fecha_inicio")),
                        name="chk_asig_fechas_validas",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="HistorialEstadoCama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_hora", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha y hora")),
                ("observacion", models.CharField(blank=True, default="Ingreso (sync)", max_length=255, verbose_name="Observacion")),
                ("cama", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historial_estado", to="servicio.cama", verbose_name="Cama")),
                ("estado_anterior", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="historiales_como_anterior", to="mapeo_camas.estadomapeo", verbose_name="Estado anterior")),
                ("estado_nuevo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historiales_como_nuevo", to="mapeo_camas.estadomapeo", verbose_name="Estado nuevo")),
                ("paciente", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="historial_camas", to="paciente.paciente", verbose_name="Paciente")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="historial_camas_usuario", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Historial de estado de cama",
                "verbose_name_plural": "Historial de estados de camas",
                "db_table": "mapeo_camas_historial_estado_cama",
                "ordering": ["-fecha_hora"],
                "indexes": [models.Index(fields=["cama", "fecha_hora"], name="idx_hist_cama_fecha")],
            },
        ),
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
        migrations.CreateModel(
            name="MapeoSesionCama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_inicio", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha de inicio")),
                ("fecha_fin", models.DateTimeField(blank=True, null=True, verbose_name="Fecha de fin")),
                ("observacion", models.CharField(blank=True, default="Sin Observaciones", max_length=500, verbose_name="Observacion")),
                ("estado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sesiones_mapeo", to="mapeo_camas.estadomapeo", verbose_name="Estado")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sesiones_mapeo_cama", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Sesion de mapeo de cama",
                "verbose_name_plural": "Sesiones de mapeo de cama",
                "db_table": "mapeo_camas_sesion_cama",
                "ordering": ["-fecha_inicio"],
            },
        ),
        migrations.CreateModel(
            name="DetalleMapeoCama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fue_validada", models.BooleanField(default=False, verbose_name="Fue validada")),
                ("hubo_cambio", models.BooleanField(default=False, verbose_name="Hubo cambio")),
                ("ubicacion", models.CharField(blank=True, default="", max_length=255, verbose_name="Ubicacion")),
                ("fecha_hora", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha y hora")),
                ("observacion", models.CharField(blank=True, default="", max_length=255, verbose_name="Observacion")),
                ("cama", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles_mapeo", to="servicio.cama", verbose_name="Cama")),
                ("estado_actual", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="detalles_mapeo_como_estado", to="mapeo_camas.estadomapeo", verbose_name="Estado actual")),
                ("paciente_actual", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="detalles_mapeo_actual", to="paciente.paciente", verbose_name="Paciente actual")),
                ("sesion_mapeo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles", to="mapeo_camas.mapeosesioncama", verbose_name="Sesion de mapeo")),
                ("tipo_accion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles_mapeo_como_accion", to="mapeo_camas.estadomapeo", verbose_name="Tipo de accion")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="detalles_mapeo_cama", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Detalle de mapeo de cama",
                "verbose_name_plural": "Detalles de mapeo de cama",
                "db_table": "mapeo_camas_detalle_mapeo_cama",
                "ordering": ["-fecha_hora"],
                "indexes": [
                    models.Index(fields=["sesion_mapeo", "fecha_hora"], name="idx_det_mapeo_sesion_fecha"),
                    models.Index(fields=["cama", "fecha_hora"], name="idx_det_mapeo_cama_fecha"),
                    models.Index(fields=["sesion_mapeo", "cama"], name="idx_det_mapeo_sesion_cama"),
                ],
            },
        ),
        migrations.RunPython(seed_estados_mapeo, migrations.RunPython.noop),
    ]
