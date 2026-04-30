from django.db import migrations


def liberar_rechazados(apps, schema_editor):
    """
    Libera expedientes que fueron rechazados pero quedaron en EXP_APARTADO.
    Solo actualiza si no hay otra solicitud activa que mantenga ese expediente apartado/aprobado.
    """
    SolicitudExpedienteDetalle = apps.get_model('s_exp', 'SolicitudExpedienteDetalle')
    ExpedientePrestamo = apps.get_model('s_exp', 'ExpedientePrestamo')

    estados_activos = ['SOL_PENDIENTE', 'SOL_APROBADA_ORGANIZANDO', 'SOL_LISTO_RECOGER',
                       'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA']

    # Detalles rechazados que aún tienen expediente_prestamo en estado APARTADO
    rechazados = SolicitudExpedienteDetalle.objects.filter(
        aprobado=False,
        expediente_prestamo__estado_id='EXP_APARTADO',
    ).select_related('expediente_prestamo')

    for d in rechazados:
        ep = d.expediente_prestamo
        # ¿Hay otra solicitud activa aprobada que aún mantiene este expediente?
        otro_activo = SolicitudExpedienteDetalle.objects.filter(
            expediente_prestamo=ep,
            aprobado=True,
            devuelto=False,
            solicitud__estado_flujo_id__in=estados_activos,
        ).exclude(pk=d.pk).exists()
        if not otro_activo:
            ep.estado_id = 'EXP_DISPONIBLE'
            ep.save()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0010_solicitudexpedientedetalle_comentario_devolucion'),
    ]

    operations = [
        migrations.RunPython(liberar_rechazados, reverse_noop),
    ]
