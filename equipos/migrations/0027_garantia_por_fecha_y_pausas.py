"""La garantia deja de ser una duracion y pasa a ser la fecha del contrato.

Antes solo podia decirse "1 año" o "2 años". Las garantias reales no vienen en
esos tamanios: vienen como "hasta el 15 de marzo de 2027". Guardar la fecha que
firmo el proveedor permite ademas que las pausas la ajusten sin tocar el dato
original, porque el vencimiento efectivo se calcula.

Esto no contradice a la 0025, que retiro una fecha *calculada*: aquella se
quedaba obsoleta sola, esta es un hecho que alguien transcribe del papel.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Valores del antiguo DuracionGarantiaDispositivo, ya retirado del codigo.
SIN_GARANTIA = 0


def duracion_a_fecha(apps, schema_editor):
    """Convierte los anios de garantia en la fecha de vencimiento.

    El punto de partida es cuando se registro la ficha, que es como venia
    funcionando: la garantia empezaba a correr desde ahi.
    """
    Dispositivo = apps.get_model("equipos", "Dispositivo")

    for dispositivo in Dispositivo.objects.exclude(
        garantia_anios=SIN_GARANTIA
    ).iterator():
        registro = dispositivo.fecha_creado
        if registro is None:
            continue

        inicio = registro.date()
        anios = dispositivo.garantia_anios

        try:
            fin = inicio.replace(year=inicio.year + anios)
        except ValueError:
            # 29 de febrero hacia un anio no bisiesto: se corre al 28.
            fin = inicio.replace(year=inicio.year + anios, day=28)

        dispositivo.fecha_fin_garantia = fin
        dispositivo.save(update_fields=["fecha_fin_garantia"])


def fecha_a_duracion(apps, schema_editor):
    """Marcha atras aproximada: una fecha no siempre cabe en anios enteros.

    Una garantia de 18 meses no existe en el modelo antiguo. Se redondea al
    anio mas cercano dentro de lo que admitia aquel campo (0, 1 o 2). Si se
    vuelve atras, conviene revisar a mano los equipos afectados.
    """
    Dispositivo = apps.get_model("equipos", "Dispositivo")

    for dispositivo in Dispositivo.objects.exclude(
        fecha_fin_garantia=None
    ).iterator():
        registro = dispositivo.fecha_creado
        if registro is None:
            continue

        dias = (dispositivo.fecha_fin_garantia - registro.date()).days
        anios = max(0, min(2, round(dias / 365)))
        dispositivo.garantia_anios = anios
        dispositivo.save(update_fields=["garantia_anios"])


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0026_unidad_equipos'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PausaGarantia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_salida', models.DateField(help_text='Día en que el equipo salió del hospital.', verbose_name='Fecha de salida')),
                ('fecha_retorno', models.DateField(blank=True, help_text='Día en que el equipo volvió. Vacío si sigue fuera.', null=True, verbose_name='Fecha de retorno')),
                ('motivo', models.TextField(blank=True, help_text='A dónde fue y por qué. Número de orden del proveedor si lo hay.', verbose_name='Motivo')),
                ('fecha_creado', models.DateTimeField(auto_now_add=True)),
                ('fecha_modificado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Pausa de garantía',
                'verbose_name_plural': 'Pausas de garantía',
                'db_table': 'equipo_pausa_garantia',
                'ordering': ['-fecha_salida'],
            },
        ),
        # El orden importa: primero se crea el campo nuevo, despues se
        # traspasan los datos y solo entonces se retira el viejo. Al reves se
        # perderia la garantia de los equipos ya registrados.
        migrations.AddField(
            model_name='dispositivo',
            name='fecha_fin_garantia',
            field=models.DateField(blank=True, help_text='Fecha en que vence la garantía según el contrato. Dejar vacío si el equipo no tiene garantía.', null=True, verbose_name='Fin de garantía'),
        ),
        migrations.RunPython(duracion_a_fecha, fecha_a_duracion),
        migrations.RemoveConstraint(
            model_name='dispositivo',
            name='equipo_garantia_anios_valida',
        ),
        migrations.RemoveField(
            model_name='dispositivo',
            name='garantia_anios',
        ),
        migrations.AddField(
            model_name='pausagarantia',
            name='dispositivo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pausas_garantia', to='equipos.dispositivo'),
        ),
        migrations.AddField(
            model_name='pausagarantia',
            name='registrado_por',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pausas_garantia_registradas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name='pausagarantia',
            index=models.Index(fields=['dispositivo', 'fecha_retorno'], name='equipo_pausa_disp_retorno_idx'),
        ),
        migrations.AddConstraint(
            model_name='pausagarantia',
            constraint=models.CheckConstraint(condition=models.Q(('fecha_retorno__isnull', True), ('fecha_retorno__gte', models.F('fecha_salida')), _connector='OR'), name='equipo_pausa_retorno_no_anterior'),
        ),
        migrations.AddConstraint(
            model_name='pausagarantia',
            constraint=models.UniqueConstraint(condition=models.Q(('fecha_retorno__isnull', True)), fields=('dispositivo',), name='equipo_una_pausa_abierta_por_equipo'),
        ),
    ]
