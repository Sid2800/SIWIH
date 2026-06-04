"""
Migración de datos: poblar los catálogos de estados.

Inserta los códigos/nombres de:
  - EstadoPrestamo
  - EstadoDevolucion
  - TipoAccionLog

Los códigos coinciden EXACTAMENTE con los valores de texto que ya tienen
las tablas Prestamo.estado, Devolucion.estado y LogHistorico.accion. Así,
cuando esos campos se conviertan a FK (migración 0019), los valores
existentes apuntarán a un registro válido del catálogo (PK = código).

Es idempotente (get_or_create), así que correrla varias veces no duplica.
"""
from django.db import migrations


# Datos de cada catálogo: (codigo, nombre_legible)
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


def poblar(apps, schema_editor):
    EstadoPrestamo = apps.get_model('s_exp', 'EstadoPrestamo')
    EstadoDevolucion = apps.get_model('s_exp', 'EstadoDevolucion')
    TipoAccionLog = apps.get_model('s_exp', 'TipoAccionLog')
    Prestamo = apps.get_model('s_exp', 'Prestamo')
    Devolucion = apps.get_model('s_exp', 'Devolucion')
    LogHistorico = apps.get_model('s_exp', 'LogHistorico')

    # 1) Poblar los códigos conocidos
    for codigo, nombre in ESTADOS_PRESTAMO:
        EstadoPrestamo.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})

    for codigo, nombre in ESTADOS_DEVOLUCION:
        EstadoDevolucion.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})

    for codigo, nombre in TIPOS_ACCION_LOG:
        TipoAccionLog.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})

    # 2) RED DE SEGURIDAD: si en los datos existentes hay valores que no están
    #    en las listas de arriba, también se crean. Así, al convertir los
    #    campos a FK (migración 0019), ningún registro queda con un valor
    #    huérfano que viole la integridad referencial.
    for valor in Prestamo.objects.values_list('estado', flat=True).distinct():
        if valor:
            EstadoPrestamo.objects.get_or_create(codigo=valor, defaults={'nombre': valor})

    for valor in Devolucion.objects.values_list('estado', flat=True).distinct():
        if valor:
            EstadoDevolucion.objects.get_or_create(codigo=valor, defaults={'nombre': valor})

    for valor in LogHistorico.objects.values_list('accion', flat=True).distinct():
        if valor:
            TipoAccionLog.objects.get_or_create(codigo=valor, defaults={'nombre': valor})


def despoblar(apps, schema_editor):
    """Reversa: vacía los catálogos."""
    apps.get_model('s_exp', 'EstadoPrestamo').objects.all().delete()
    apps.get_model('s_exp', 'EstadoDevolucion').objects.all().delete()
    apps.get_model('s_exp', 'TipoAccionLog').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0017_crear_catalogos_estado'),
    ]

    operations = [
        migrations.RunPython(poblar, despoblar),
    ]
