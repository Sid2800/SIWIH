"""La garantia deja de ser tres columnas del equipo y pasa a ser una tabla.

Antes cabia una sola garantia por equipo, asi que cambiarla borraba la
anterior. En la practica un equipo pasa por varias: se renueva al vencer, se
termina a mano cuando el proveedor incumple o cuando el aparato se sustituye,
y a veces se contrata una extension aparte. Guardarlas como filas permite
responder "que cobertura tenia este equipo en marzo del ano pasado", que es
justo lo que se pregunta cuando aparece un reclamo tardio.

Las pausas por reparacion pasan a colgar de la garantia y no del equipo: lo
que se detiene es esa cobertura concreta, y con varias por equipo hace falta
saber a cual se le sumaron los dias.

El orden de las operaciones importa: las garantias se crean a partir de las
columnas del equipo ANTES de borrarlas, y las pausas se repuntan antes de
soltar su FK al equipo. Django las habia generado al reves, que habria
perdido lo ya registrado.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def trasladar_garantias(apps, schema_editor):
    """Crea una garantia por equipo que tuviera fechas, y repunta sus pausas.

    El usuario que queda como registrador es el que creo el equipo: es lo mas
    cercano a la verdad que hay en la base, porque la garantia se capturaba en
    el mismo formulario del alta.
    """
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    GarantiaDispositivo = apps.get_model("equipos", "GarantiaDispositivo")
    PausaGarantia = apps.get_model("equipos", "PausaGarantia")

    creadas = 0

    for equipo in Dispositivo.objects.exclude(fecha_fin_garantia__isnull=True):
        # Sin inicio registrado se toma el propio vencimiento: es lo unico que
        # consta, y dejarlo vacio romperia la columna obligatoria.
        inicio = equipo.fecha_inicio_garantia or equipo.fecha_fin_garantia

        garantia = GarantiaDispositivo.objects.create(
            dispositivo=equipo,
            fecha_inicio=inicio,
            meses=equipo.garantia_meses,
            fecha_fin=equipo.fecha_fin_garantia,
            registrado_por_id=equipo.creado_por_id,
            # Es la que estaba en curso: nace vigente.
            fecha_cierre=None,
            equipo_con_garantia_vigente=equipo.pk,
        )
        creadas += 1

        # Las pausas de ese equipo pertenecen a esta garantia: era la unica
        # que tenia.
        PausaGarantia.objects.filter(dispositivo_id=equipo.pk).update(
            garantia=garantia
        )

    # Una pausa sin garantia no se puede conservar: la columna pasa a ser
    # obligatoria en la migracion siguiente. Solo puede ocurrir si el equipo
    # tenia pausas sin ninguna fecha de garantia, que es un dato incoherente
    # de todos modos.
    huerfanas = PausaGarantia.objects.filter(garantia__isnull=True)
    cantidad = huerfanas.count()

    if cantidad:
        huerfanas.delete()
        print(
            f"\n  {cantidad} pausa(s) de equipos sin garantia registrada se "
            f"descartaron: no habia cobertura que pausar."
        )

    if creadas:
        print(f"\n  {creadas} garantia(s) trasladadas a la tabla nueva.")


def devolver_garantias(apps, schema_editor):
    """Devuelve la garantia vigente a las columnas del equipo.

    El historial no se puede recuperar: en el modelo viejo solo cabia una.
    """
    Dispositivo = apps.get_model("equipos", "Dispositivo")
    GarantiaDispositivo = apps.get_model("equipos", "GarantiaDispositivo")

    for garantia in GarantiaDispositivo.objects.filter(fecha_cierre__isnull=True):
        Dispositivo.objects.filter(pk=garantia.dispositivo_id).update(
            fecha_inicio_garantia=garantia.fecha_inicio,
            garantia_meses=garantia.meses,
            fecha_fin_garantia=garantia.fecha_fin,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0040_modelo_tipo_obligatorio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. La tabla nueva, con sus dos claves ajenas.
        migrations.CreateModel(
            name='GarantiaDispositivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_inicio', models.DateField(help_text='Día en que empezó a correr esta garantía.', verbose_name='Inicio de la cobertura')),
                ('meses', models.PositiveSmallIntegerField(blank=True, help_text='Vacío si el contrato solo da la fecha de vencimiento.', null=True, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Duración pactada (meses)')),
                ('fecha_fin', models.DateField(help_text='Fecha en que vence según el contrato.', verbose_name='Vence el')),
                ('referencia', models.CharField(blank=True, max_length=100, verbose_name='Contrato o factura')),
                ('observaciones', models.TextField(blank=True)),
                ('fecha_cierre', models.DateField(blank=True, null=True, verbose_name='Cerrada el')),
                ('motivo_cierre', models.CharField(blank=True, choices=[('renovacion', 'Renovada por otra'), ('incumplimiento', 'Incumplimiento del proveedor'), ('sustitucion', 'Equipo sustituido'), ('error', 'Corrección de un dato mal registrado'), ('otro', 'Otro motivo')], max_length=20, verbose_name='Motivo del cierre')),
                ('detalle_cierre', models.TextField(blank=True, verbose_name='Detalle del cierre')),
                ('fecha_creado', models.DateTimeField(auto_now_add=True)),
                ('equipo_con_garantia_vigente', models.BigIntegerField(blank=True, editable=False, null=True, unique=True)),
            ],
            options={
                'verbose_name': 'Garantía de equipo',
                'verbose_name_plural': 'Garantías de equipos',
                'db_table': 'equipo_garantia',
                'ordering': ['fecha_cierre', '-fecha_inicio', '-pk'],
            },
        ),
        migrations.AddField(
            model_name='garantiadispositivo',
            name='dispositivo',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='garantias', to='equipos.dispositivo'),
        ),
        migrations.AddField(
            model_name='garantiadispositivo',
            name='registrado_por',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='garantias_equipos_registradas', to=settings.AUTH_USER_MODEL),
        ),

        # 2. La pausa gana su FK a la garantia, todavia opcional.
        migrations.AddField(
            model_name='pausagarantia',
            name='garantia',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='pausas', to='equipos.garantiadispositivo'),
        ),

        # 3. Se traslada lo registrado, con las columnas viejas todavia en pie.
        migrations.RunPython(trasladar_garantias, devolver_garantias),

        # 4. Y ahora si se sueltan las columnas viejas.
        migrations.RemoveConstraint(
            model_name='dispositivo',
            name='equipo_disp_garantia_meses_positiva',
        ),
        migrations.RemoveConstraint(
            model_name='dispositivo',
            name='equipo_disp_garantia_fechas_coherentes',
        ),
        migrations.RemoveIndex(
            model_name='pausagarantia',
            name='equipo_pausa_disp_retorno_idx',
        ),
        migrations.RenameField(
            model_name='pausagarantia',
            old_name='equipo_con_pausa_abierta',
            new_name='garantia_con_pausa_abierta',
        ),
        migrations.RemoveField(
            model_name='dispositivo',
            name='fecha_fin_garantia',
        ),
        migrations.RemoveField(
            model_name='dispositivo',
            name='fecha_inicio_garantia',
        ),
        migrations.RemoveField(
            model_name='dispositivo',
            name='garantia_meses',
        ),
        migrations.RemoveField(
            model_name='pausagarantia',
            name='dispositivo',
        ),

        # 5. Indices y restricciones de la tabla nueva.
        migrations.AddIndex(
            model_name='pausagarantia',
            index=models.Index(fields=['garantia', 'fecha_retorno'], name='equipo_pausa_gar_retorno_idx'),
        ),
        migrations.AddIndex(
            model_name='garantiadispositivo',
            index=models.Index(fields=['dispositivo', 'fecha_cierre'], name='equipo_gar_disp_cierre_idx'),
        ),
        migrations.AddIndex(
            model_name='garantiadispositivo',
            index=models.Index(fields=['fecha_fin'], name='equipo_gar_fin_idx'),
        ),
        migrations.AddConstraint(
            model_name='garantiadispositivo',
            constraint=models.CheckConstraint(condition=models.Q(('meses__isnull', True), ('meses__gt', 0), _connector='OR'), name='equipo_gar_meses_positiva'),
        ),
        migrations.AddConstraint(
            model_name='garantiadispositivo',
            constraint=models.CheckConstraint(condition=models.Q(('fecha_fin__gte', models.F('fecha_inicio'))), name='equipo_gar_fin_no_anterior_al_inicio'),
        ),
        migrations.AddConstraint(
            model_name='garantiadispositivo',
            constraint=models.CheckConstraint(condition=models.Q(('fecha_cierre__isnull', True), models.Q(('motivo_cierre', ''), _negated=True), _connector='OR'), name='equipo_gar_cierre_con_motivo'),
        ),
    ]
