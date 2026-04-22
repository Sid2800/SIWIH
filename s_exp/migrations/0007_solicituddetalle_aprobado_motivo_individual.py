from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0006_prestamo_es_minutos_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudexpedientedetalle',
            name='aprobado',
            field=models.BooleanField(default=True, verbose_name='Expediente Aprobado para préstamo'),
        ),
        migrations.AddField(
            model_name='solicitudexpedientedetalle',
            name='motivo_rechazo_individual',
            field=models.TextField(blank=True, null=True, verbose_name='Motivo de rechazo del expediente'),
        ),
    ]
