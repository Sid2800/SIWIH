from django.db import migrations


def rename_aprobada_organizando(apps, schema_editor):
    EstadoSolicitud = apps.get_model('s_exp', 'EstadoSolicitud')
    try:
        e = EstadoSolicitud.objects.get(codigo='SOL_APROBADA_ORGANIZANDO')
        e.nombre = 'Buscando expedientes'
        e.descripcion = (
            'La solicitud fue aprobada y los expedientes están siendo localizados '
            'en el archivo físico. Los expedientes ya están apartados y no pueden '
            'ser solicitados por otros usuarios.'
        )
        e.save()
    except EstadoSolicitud.DoesNotExist:
        pass


def revert_aprobada_organizando(apps, schema_editor):
    EstadoSolicitud = apps.get_model('s_exp', 'EstadoSolicitud')
    try:
        e = EstadoSolicitud.objects.get(codigo='SOL_APROBADA_ORGANIZANDO')
        e.nombre = 'En proceso de organizacion'
        e.save()
    except EstadoSolicitud.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0008_solicitudprestamo_tiempo_sugerido'),
    ]

    operations = [
        migrations.RunPython(rename_aprobada_organizando, revert_aprobada_organizando),
    ]
