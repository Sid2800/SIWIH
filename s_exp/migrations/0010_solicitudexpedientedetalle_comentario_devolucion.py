from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0009_rename_estado_buscando_expedientes'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudexpedientedetalle',
            name='comentario_devolucion',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Comentario de devolución del expediente'
            ),
        ),
    ]
