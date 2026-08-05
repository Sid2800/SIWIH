"""
Backfill de fecha_entrega / fecha_devolucion en los detalles históricos.

Origen del problema: la migración 0006 agregó estas fechas POR EXPEDIENTE, pero
los préstamos que ya existían quedaron con ambas en NULL. Sin este backfill, un
expediente entregado y devuelto hace meses se mostraría como "Sin entregar" /
"Sin devolver" en el historial, que es un dato incorrecto (no solo estético).

Fuente de los datos históricos (lo más preciso disponible por registro):
  - fecha_entrega    <- Prestamo.fecha_entrega (la entrega era de toda la
                        solicitud a la vez, así que aplica a todos sus detalles).
  - fecha_devolucion <- Prestamo.fecha_devolucion_real si el préstamo ya cerró;
                        si no, la fecha de la última Devolucion registrada.
                        Si no hay ninguna, se deja NULL (no se inventa un dato).

Solo se tocan filas con la fecha en NULL, por lo que es idempotente y no pisa
valores nuevos. Se usa bulk_update para no hacer un UPDATE por fila.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Detalle = apps.get_model('s_exp', 'SolicitudExpedienteDetalle')

    # --- 1) Hora de entrega: de Prestamo.fecha_entrega ---
    # El préstamo cuelga de la solicitud (OneToOne), de ahí sale la fecha.
    a_actualizar = []
    qs = Detalle.objects.filter(
        aprobado=True,
        fecha_entrega__isnull=True,
        solicitud__prestamo__fecha_entrega__isnull=False,
    ).select_related('solicitud__prestamo')
    for d in qs:
        d.fecha_entrega = d.solicitud.prestamo.fecha_entrega
        a_actualizar.append(d)
    if a_actualizar:
        Detalle.objects.bulk_update(a_actualizar, ['fecha_entrega'], batch_size=500)

    # --- 2) Hora de devolución: solo para los ya marcados como devueltos ---
    a_actualizar = []
    qs = Detalle.objects.filter(
        devuelto=True,
        fecha_devolucion__isnull=True,
    ).select_related('solicitud__prestamo')
    for d in qs:
        prestamo = getattr(d.solicitud, 'prestamo', None)
        if prestamo is None:
            continue
        fecha = prestamo.fecha_devolucion_real
        if fecha is None:
            # El préstamo no cerró (p. ej. devolución parcial antigua):
            # se usa la última auditoría de devolución registrada.
            ultima = prestamo.devoluciones.order_by('-fecha_devolucion').first()
            fecha = ultima.fecha_devolucion if ultima else None
        if fecha is not None:
            d.fecha_devolucion = fecha
            a_actualizar.append(d)
    if a_actualizar:
        Detalle.objects.bulk_update(a_actualizar, ['fecha_devolucion'], batch_size=500)


def revertir(apps, schema_editor):
    # No se revierte: volver a NULL perdería datos si ya se registraron entregas
    # o devoluciones reales después de aplicar esta migración.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0006_solicitudexpedientedetalle_fecha_devolucion_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill, revertir),
    ]
