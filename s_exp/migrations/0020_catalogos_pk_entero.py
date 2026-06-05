"""
Migración: catálogos de estados/acciones con PK ENTERA (id) en vez de texto.
=============================================================================

PROBLEMA QUE RESUELVE
---------------------
EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo, EstadoDevolucion y
TipoAccionLog usaban el 'codigo' (texto) como PRIMARY KEY. Eso obligaba a las
FK de las tablas transaccionales a guardar el texto repetido (mayor tamaño y
diseño menos normalizado). Ahora la PK es un 'id' entero autoincremental
(igual que s_exp_motivosolicitud) y 'codigo' pasa a ser una columna ÚNICA.

ESTRATEGIA (segura y agnóstica de BD)
-------------------------------------
Como las tablas TRANSACCIONALES están vacías (datos de prueba ya limpiados) y
los catálogos son repoblables, hacemos el cambio en pasos limpios:

  1. Vaciar los 5 catálogos (RunPython).  -> tablas de catálogo vacías
  2. QUITAR las 7 FK que apuntan a los catálogos (RemoveField). Esto elimina
     las restricciones FK y desbloquea el cambio de PRIMARY KEY.
  3. Cambiar la PK de cada catálogo: AddField id (BigAutoField, PK) + dejar
     'codigo' como CharField unique.
  4. RECREAR las 7 FK (AddField), que ahora guardan el id entero.
  5. Repoblar los 5 catálogos (RunPython).

No hay pérdida de datos de negocio (transaccional estaba vacío) y los
catálogos quedan repoblados con los mismos códigos de siempre.

IMPACTO EN RENDIMIENTO
----------------------
Operación de migración puntual. En adelante las FK ocupan un entero (no texto),
reduciendo el tamaño de la BD y acelerando joins/índices.
"""
import django.db.models.deletion
from django.db import migrations, models


# ---------------------------------------------------------------------------
# Datos canónicos de los catálogos (codigo, nombre[, descripcion])
# ---------------------------------------------------------------------------
ESTADOS_SOLICITUD = [
    ('SOL_PENDIENTE',             'Pendiente',                    'Esperando aprobación del admin'),
    ('SOL_APROBADA_ORGANIZANDO',  'Buscando expedientes',         'Aprobada, admin busca expedientes en archivo'),
    ('SOL_LISTO_RECOGER',         'Listo para recoger',           'Listos, usuario debe pasar a retirar'),
    ('SOL_EN_PRESTAMO',           'En prestamo',                  'Entregada al usuario, cronómetro activo'),
    ('SOL_EN_DEVOLUCION',         'En devolucion / Por revisar',  'Usuario marcó para devolver'),
    ('SOL_INCOMPLETA',            'Devolucion incompleta',        'Devolución parcial, faltan expedientes'),
    ('SOL_FINALIZADA',            'Finalizada',                   'Devolución completa cerrada'),
    ('SOL_RECHAZADA',             'Rechazada',                    'No se aprobó la solicitud'),
]

ESTADOS_EXP_FISICO = [
    ('EXP_DISPONIBLE', 'Disponible'),
    ('EXP_APARTADO',   'Apartado en solicitud'),
    ('EXP_PRESTADO',   'En prestamo'),
    ('EXP_PERDIDO',    'Perdido'),
    ('EXP_BAJA',       'Retirado / Dado de baja'),
]

ESTADOS_PRESTAMO = [
    ('Activo',            'Activo (aprobado, sin entregar)'),
    ('Entregado',         'Entregado'),
    ('Vencido',           'Vencido'),
    ('DevolucionParcial', 'Devolución Parcial'),
    ('Cerrado',           'Cerrado'),
    ('DevueltoVencido',   'Devuelto fuera de tiempo'),
]

ESTADOS_DEVOLUCION = [
    ('Completa',   'Completa'),
    ('Incompleta', 'Incompleta'),
    ('Parcial',    'Parcial'),
]

TIPOS_ACCION_LOG = [
    ('SOLICITUD_CREADA',              'Solicitud creada'),
    ('SOLICITUD_APROBADA',            'Solicitud aprobada'),
    ('SOLICITUD_RECHAZADA',           'Solicitud rechazada'),
    ('SOLICITUD_LISTA',               'Solicitud lista para recoger'),
    ('SOLICITUD_DEVOLUCION_INICIADA', 'Devolución iniciada por el usuario'),
    ('PRESTAMO_ENTREGADO',            'Préstamo entregado'),
    ('REVISION_ENTREGA',              'Revisión de entrega'),
    ('DEVOLUCION_PROCESADA',          'Devolución procesada (auditoría)'),
]


def _vaciar_catalogos(apps, schema_editor):
    """Paso 1: vaciar los catálogos antes del cambio de PK (transaccional vacío)."""
    for modelo in ('EstadoSolicitud', 'EstadoExpedienteFisico', 'EstadoPrestamo',
                   'EstadoDevolucion', 'TipoAccionLog'):
        apps.get_model('s_exp', modelo).objects.all().delete()


def _poblar_catalogos(apps, schema_editor):
    """Paso 5: repoblar los catálogos con los códigos/nombres de siempre.
    Idempotente (get_or_create)."""
    EstadoSolicitud = apps.get_model('s_exp', 'EstadoSolicitud')
    EstadoExpedienteFisico = apps.get_model('s_exp', 'EstadoExpedienteFisico')
    EstadoPrestamo = apps.get_model('s_exp', 'EstadoPrestamo')
    EstadoDevolucion = apps.get_model('s_exp', 'EstadoDevolucion')
    TipoAccionLog = apps.get_model('s_exp', 'TipoAccionLog')

    for codigo, nombre, desc in ESTADOS_SOLICITUD:
        EstadoSolicitud.objects.get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'descripcion': desc})
    for codigo, nombre in ESTADOS_EXP_FISICO:
        EstadoExpedienteFisico.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in ESTADOS_PRESTAMO:
        EstadoPrestamo.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in ESTADOS_DEVOLUCION:
        EstadoDevolucion.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in TIPOS_ACCION_LOG:
        TipoAccionLog.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})


def _noop(apps, schema_editor):
    pass


def _swap_pk(tabla):
    """
    Operación SeparateDatabaseAndState para cambiar la PK de un catálogo de
    'codigo' (texto) a 'id' (entero), manteniendo 'codigo' como UNIQUE.

    - state_operations: lo que Django registra en su estado (AddField id +
      AlterField codigo unique).
    - database_operations: el SQL real en MySQL. Hay que hacerlo en UN solo
      ALTER porque una columna AUTO_INCREMENT debe ser clave en todo momento:
      no se puede quedar la tabla sin PK entre instrucciones.

    Se ejecuta DESPUÉS de quitar las 7 FK (sus constraints referenciaban a
    'codigo' y bloquearían el DROP PRIMARY KEY) y con las tablas vacías.
    """
    model = tabla[len('s_exp_'):]  # 's_exp_estadosolicitud' -> 'estadosolicitud'
    sql = (
        f"ALTER TABLE `{tabla}` "
        f"DROP PRIMARY KEY, "
        f"MODIFY COLUMN `codigo` varchar(50) NOT NULL, "
        f"ADD COLUMN `id` bigint NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST, "
        f"ADD UNIQUE (`codigo`);"
    )
    reverse_sql = (
        f"ALTER TABLE `{tabla}` "
        f"DROP PRIMARY KEY, DROP INDEX `codigo`, DROP COLUMN `id`, "
        f"ADD PRIMARY KEY (`codigo`);"
    )
    return migrations.SeparateDatabaseAndState(
        state_operations=[
            migrations.AddField(
                model_name=model, name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True,
                                          serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name=model, name='codigo',
                field=models.CharField(max_length=50, unique=True),
            ),
        ],
        database_operations=[
            migrations.RunSQL(sql=sql, reverse_sql=reverse_sql),
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0019_convertir_estados_a_fk'),
    ]

    operations = [
        # ---- 1) Vaciar catálogos (transaccional ya está vacío) ----
        migrations.RunPython(_vaciar_catalogos, _noop),

        # ---- 2) Quitar las 7 FK que apuntan a los catálogos ----
        migrations.RemoveField(model_name='prestamo', name='estado'),
        migrations.RemoveField(model_name='devolucion', name='estado'),
        migrations.RemoveField(model_name='expedienteprestamo', name='estado'),
        migrations.RemoveField(model_name='solicitudprestamo', name='estado_flujo'),
        migrations.RemoveField(model_name='expedienteestadolog', name='estado_anterior'),
        migrations.RemoveField(model_name='expedienteestadolog', name='estado_nuevo'),
        migrations.RemoveField(model_name='loghistorico', name='accion'),

        # ---- 3) Cambiar PK de cada catálogo: codigo(texto) -> id(entero) ----
        _swap_pk('s_exp_estadosolicitud'),
        _swap_pk('s_exp_estadoexpedientefisico'),
        _swap_pk('s_exp_estadoprestamo'),
        _swap_pk('s_exp_estadodevolucion'),
        _swap_pk('s_exp_tipoaccionlog'),

        # ---- 4) Recrear las 7 FK (ahora guardan el id entero) ----
        migrations.AddField(
            model_name='prestamo', name='estado',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='prestamos', to='s_exp.estadoprestamo',
                                    verbose_name='Estado del Préstamo'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='devolucion', name='estado',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='devoluciones', to='s_exp.estadodevolucion',
                                    verbose_name='Estado de Devolución'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='expedienteprestamo', name='estado',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='expedientes', to='s_exp.estadoexpedientefisico',
                                    verbose_name='Estado Físico Actual'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='solicitudprestamo', name='estado_flujo',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='solicitudes', to='s_exp.estadosolicitud',
                                    verbose_name='Estado de la Solicitud'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='expedienteestadolog', name='estado_anterior',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='logs_como_anterior', to='s_exp.estadoexpedientefisico',
                                    verbose_name='Estado Anterior'),
        ),
        migrations.AddField(
            model_name='expedienteestadolog', name='estado_nuevo',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='logs_como_nuevo', to='s_exp.estadoexpedientefisico',
                                    verbose_name='Estado Nuevo'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='loghistorico', name='accion',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='logs', to='s_exp.tipoaccionlog',
                                    verbose_name='Acción'),
            preserve_default=False,
        ),

        # ---- 5) Repoblar catálogos ----
        migrations.RunPython(_poblar_catalogos, _noop),
    ]
