"""
Datos iniciales del módulo s_exp (catálogos OBLIGATORIOS).
=============================================================================

Siembra (idempotente, get_or_create) todos los catálogos que el módulo
necesita para funcionar, de modo que un `migrate` en limpio deje la base lista
SIN scripts SQL externos:

  - Estados de solicitud / expediente físico / préstamo / devolución
  - Tipos de acción del log y tipos de objeto del log
  - Motivos de solicitud (los 16 reales del hospital)

NO siembra expediente_ubicacion (depende de las unidades de `servicio`): eso
se hace con `python manage.py poblar_ubicaciones`.
"""
from django.db import migrations


ESTADOS_SOLICITUD = [
    ('SOL_PENDIENTE',             'Pendiente',                   'Esperando aprobación del admin'),
    ('SOL_APROBADA_ORGANIZANDO',  'Buscando expedientes',        'Aprobada, admin busca expedientes en archivo'),
    ('SOL_LISTO_RECOGER',         'Listo para recoger',          'Listos, usuario debe pasar a retirar'),
    ('SOL_EN_PRESTAMO',           'En prestamo',                 'Entregada al usuario, cronómetro activo'),
    ('SOL_EN_DEVOLUCION',         'En devolucion / Por revisar', 'Usuario marcó para devolver'),
    ('SOL_INCOMPLETA',            'Devolucion incompleta',       'Devolución parcial, faltan expedientes'),
    ('SOL_FINALIZADA',            'Finalizada',                  'Devolución completa cerrada'),
    ('SOL_RECHAZADA',             'Rechazada',                   'No se aprobó la solicitud'),
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

TIPOS_OBJETO_LOG = [
    ('SolicitudPrestamo', 'SolicitudPrestamo'),
    ('Prestamo',          'Prestamo'),
    ('Devolucion',        'Devolucion'),
]

# Motivos reales del hospital (catálogo administrado por el usuario; se siembra
# el set inicial para que el módulo funcione desde el primer arranque).
MOTIVOS = [
    'ANALISIS',
    'COMISION QUIRURGICA',
    'COMPLICACIONES NEONATALES',
    'COMPLICACIONES OBSTETRICAS',
    'CONSTANCIA',
    'DEFUNCIONES',
    'FICHAS',
    'INFECCIONES',
    'INVESTIGACION',
    'MEDICION',
    'MONITORIA',
    'REPOSICION DE CONSTANCIA NACIMIENTO',
    'REVISION',
    'REVISION REFERENCIAS',
    'REVISION SAI',
    'TESIS',
]


def sembrar(apps, schema_editor):
    EstadoSolicitud = apps.get_model('s_exp', 'EstadoSolicitud')
    EstadoExpedienteFisico = apps.get_model('s_exp', 'EstadoExpedienteFisico')
    EstadoPrestamo = apps.get_model('s_exp', 'EstadoPrestamo')
    EstadoDevolucion = apps.get_model('s_exp', 'EstadoDevolucion')
    TipoAccionLog = apps.get_model('s_exp', 'TipoAccionLog')
    TipoObjetoLog = apps.get_model('s_exp', 'TipoObjetoLog')
    MotivoSolicitud = apps.get_model('s_exp', 'MotivoSolicitud')

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
    for codigo, nombre in TIPOS_OBJETO_LOG:
        TipoObjetoLog.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for nombre in MOTIVOS:
        MotivoSolicitud.objects.get_or_create(nombre=nombre, defaults={'activo': True})


def quitar(apps, schema_editor):
    """Reversa: vaciar los catálogos sembrados."""
    for modelo in ('EstadoSolicitud', 'EstadoExpedienteFisico', 'EstadoPrestamo',
                   'EstadoDevolucion', 'TipoAccionLog', 'TipoObjetoLog', 'MotivoSolicitud'):
        apps.get_model('s_exp', modelo).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('s_exp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, quitar),
    ]
