"""
Migración:
  1. Crea el catálogo TipoObjetoLog (id entero PK + codigo único).
  2. Elimina ExpedientePrestamo.ubicacion_fisica (texto deprecado; la
     ubicación ahora es la FK 'ubicacion' al catálogo expediente_ubicacion).
  3. Convierte LogHistorico.objeto_tipo de TEXTO a FK (TipoObjetoLog),
     preservando los datos existentes mediante backfill.

El backfill se hace en pasos seguros:
  - Se renombra la columna texto a 'objeto_tipo_txt'.
  - Se agrega la nueva FK 'objeto_tipo' (nullable).
  - Se crean filas de TipoObjetoLog para cada valor distinto y se enlaza.
  - Se elimina la columna texto temporal.
"""
import django.db.models.deletion
from django.db import migrations, models


# Tipos de objeto conocidos (nombre del modelo referenciado en los logs).
TIPOS_OBJETO_CONOCIDOS = ['SolicitudPrestamo', 'Prestamo', 'Devolucion']


def _backfill_objeto_tipo(apps, schema_editor):
    LogHistorico = apps.get_model('s_exp', 'LogHistorico')
    TipoObjetoLog = apps.get_model('s_exp', 'TipoObjetoLog')

    # 1) Sembrar los tipos conocidos.
    for codigo in TIPOS_OBJETO_CONOCIDOS:
        TipoObjetoLog.objects.get_or_create(codigo=codigo, defaults={'nombre': codigo})

    # 2) Crear cualquier tipo distinto presente en los datos + enlazar cada log.
    valores = (LogHistorico.objects
               .exclude(objeto_tipo_txt__isnull=True)
               .exclude(objeto_tipo_txt='')
               .values_list('objeto_tipo_txt', flat=True)
               .distinct())
    mapa = {}
    for val in valores:
        tipo, _ = TipoObjetoLog.objects.get_or_create(codigo=val, defaults={'nombre': val})
        mapa[val] = tipo.id

    for log in LogHistorico.objects.exclude(objeto_tipo_txt__isnull=True).exclude(objeto_tipo_txt=''):
        log.objeto_tipo_id = mapa.get(log.objeto_tipo_txt)
        log.save(update_fields=['objeto_tipo'])


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0020_catalogos_pk_entero'),
    ]

    operations = [
        # 1) Catálogo nuevo
        migrations.CreateModel(
            name='TipoObjetoLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=50, unique=True)),
                ('nombre', models.CharField(max_length=100, verbose_name='Nombre legible del Tipo de Objeto')),
            ],
            options={
                'verbose_name': 'Tipo de Objeto (Log)',
                'verbose_name_plural': 'Tipos de Objeto (Log)',
                'db_table': 's_exp_tipoobjetolog',
            },
        ),
        # 2) Quitar el texto deprecado
        migrations.RemoveField(
            model_name='expedienteprestamo',
            name='ubicacion_fisica',
        ),
        # 3) objeto_tipo: texto -> FK con backfill
        migrations.RenameField(
            model_name='loghistorico',
            old_name='objeto_tipo',
            new_name='objeto_tipo_txt',
        ),
        migrations.AddField(
            model_name='loghistorico',
            name='objeto_tipo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='logs', to='s_exp.tipoobjetolog',
                                    verbose_name='Tipo de Objeto'),
        ),
        migrations.RunPython(_backfill_objeto_tipo, _noop),
        migrations.RemoveField(
            model_name='loghistorico',
            name='objeto_tipo_txt',
        ),
    ]
