from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0007_solicituddetalle_aprobado_motivo_individual'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudprestamo',
            name='tiempo_sugerido_horas',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text='Sugerencia opcional del usuario al crear la solicitud. Mismo día: máx hasta 4:00 PM. Días posteriores: máx 72 horas.',
                verbose_name='Tiempo sugerido por el solicitante (horas)'
            ),
        ),
    ]
