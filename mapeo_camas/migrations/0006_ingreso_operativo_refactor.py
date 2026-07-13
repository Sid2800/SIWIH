from django.db import migrations, models
from django.db.models import Q


def _resolver_ingreso(Ingreso, *, paciente_id, cama_id=None, fecha=None):
    if not paciente_id:
        return None

    qs = Ingreso.objects.filter(paciente_id=paciente_id)

    if fecha is not None:
        qs = qs.filter(fecha_ingreso__lte=fecha).filter(
            Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gte=fecha)
        )

    if cama_id is not None:
        ingreso_cama = qs.filter(cama_id=cama_id).order_by("-fecha_ingreso", "-id").first()
        if ingreso_cama:
            return ingreso_cama

    ingreso = qs.order_by("-fecha_ingreso", "-id").first()
    if ingreso:
        return ingreso

    return (
        Ingreso.objects.filter(paciente_id=paciente_id)
        .order_by("-fecha_ingreso", "-id")
        .first()
    )


def forwards_backfill_ingreso(apps, schema_editor):
    Asignacion = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")
    Historial = apps.get_model("mapeo_camas", "HistorialEstadoCama")
    Movimiento = apps.get_model("mapeo_camas", "MovimientoCama")
    Detalle = apps.get_model("mapeo_camas", "DetalleMapeoCama")
    Ingreso = apps.get_model("ingreso", "Ingreso")

    # [2026-05-26 AUDIT] Backfill principal por asignación actual y trazas históricas.
    for row in Asignacion.objects.exclude(paciente_id__isnull=True).iterator(chunk_size=500):
        ingreso = _resolver_ingreso(
            Ingreso,
            paciente_id=row.paciente_id,
            cama_id=row.cama_id,
            fecha=row.fecha_inicio,
        )
        if ingreso and row.ingreso_id != ingreso.id:
            row.ingreso_id = ingreso.id
            row.save(update_fields=["ingreso"])

    for row in Historial.objects.exclude(paciente_id__isnull=True).iterator(chunk_size=500):
        ingreso = _resolver_ingreso(
            Ingreso,
            paciente_id=row.paciente_id,
            cama_id=row.cama_id,
            fecha=row.fecha_hora,
        )
        if ingreso and row.ingreso_id != ingreso.id:
            row.ingreso_id = ingreso.id
            row.save(update_fields=["ingreso"])

    for row in Movimiento.objects.exclude(paciente_id__isnull=True).iterator(chunk_size=500):
        ingreso = _resolver_ingreso(
            Ingreso,
            paciente_id=row.paciente_id,
            cama_id=row.cama_destino_id,
            fecha=row.fecha_hora,
        )
        if ingreso and row.ingreso_id != ingreso.id:
            row.ingreso_id = ingreso.id
            row.save(update_fields=["ingreso"])

    for row in Detalle.objects.exclude(paciente_actual_id__isnull=True).iterator(chunk_size=500):
        ingreso = _resolver_ingreso(
            Ingreso,
            paciente_id=row.paciente_actual_id,
            cama_id=row.cama_id,
            fecha=row.fecha_hora,
        )
        if ingreso and row.ingreso_actual_id != ingreso.id:
            row.ingreso_actual_id = ingreso.id
            row.save(update_fields=["ingreso_actual"])


def backwards_clear_ingreso(apps, schema_editor):
    Asignacion = apps.get_model("mapeo_camas", "AsignacionCamaPaciente")
    Historial = apps.get_model("mapeo_camas", "HistorialEstadoCama")
    Movimiento = apps.get_model("mapeo_camas", "MovimientoCama")
    Detalle = apps.get_model("mapeo_camas", "DetalleMapeoCama")

    Asignacion.objects.update(ingreso_id=None)
    Historial.objects.update(ingreso_id=None)
    Movimiento.objects.update(ingreso_id=None)
    Detalle.objects.update(ingreso_actual_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("ingreso", "0005_ingreso_estado"),
        ("mapeo_camas", "0005_catalogo_observaciones"),
    ]

    operations = [
        migrations.AddField(
            model_name="asignacioncamapaciente",
            name="ingreso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="asignaciones_cama",
                to="ingreso.ingreso",
                verbose_name="Ingreso",
            ),
        ),
        migrations.AddField(
            model_name="detallemapeocama",
            name="ingreso_actual",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="detalles_mapeo_actual",
                to="ingreso.ingreso",
                verbose_name="Ingreso actual",
            ),
        ),
        migrations.AddField(
            model_name="historialestadocama",
            name="ingreso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="historial_camas",
                to="ingreso.ingreso",
                verbose_name="Ingreso",
            ),
        ),
        migrations.AddField(
            model_name="movimientocama",
            name="ingreso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="movimientos_cama",
                to="ingreso.ingreso",
                verbose_name="Ingreso",
            ),
        ),
        migrations.AddIndex(
            model_name="asignacioncamapaciente",
            index=models.Index(fields=["ingreso", "estado"], name="idx_asig_ingreso_estado"),
        ),
        migrations.AddIndex(
            model_name="movimientocama",
            index=models.Index(fields=["ingreso", "fecha_hora"], name="idx_mov_ingreso_fecha"),
        ),
        migrations.RunPython(forwards_backfill_ingreso, backwards_clear_ingreso),
    ]
