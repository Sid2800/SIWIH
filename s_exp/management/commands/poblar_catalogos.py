"""
Comando: poblar_catalogos
=============================================================================

ORIGEN DEL FLUJO
----------------
    python manage.py poblar_catalogos

QUÉ HACE
--------
Crea (idempotente, get_or_create) los registros de los catálogos de estados y
tipos de acción del módulo s_exp. Útil para:
  - Repoblar tras limpiar la base.
  - Asegurar que un entorno nuevo tenga los códigos esperados.

NO toca MotivoSolicitud (los motivos los administra el usuario desde el admin).

Tras poblar, invalida la caché codigo→id de los modelos para que id_de()/
codigo_de() reflejen los ids recién creados sin reiniciar el proceso.

RENDIMIENTO
-----------
Operación puntual y barata (pocas filas por catálogo).
"""
from django.core.management.base import BaseCommand

from s_exp.models import (
    EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo,
    EstadoDevolucion, TipoAccionLog,
)

# (codigo, nombre[, descripcion])
ESTADOS_SOLICITUD = [
    ('SOL_PENDIENTE',            'Pendiente',                   'Esperando aprobación del admin'),
    ('SOL_APROBADA_ORGANIZANDO', 'Buscando expedientes',        'Aprobada, admin busca expedientes en archivo'),
    ('SOL_LISTO_RECOGER',        'Listo para recoger',          'Listos, usuario debe pasar a retirar'),
    ('SOL_EN_PRESTAMO',          'En prestamo',                 'Entregada al usuario, cronómetro activo'),
    ('SOL_EN_DEVOLUCION',        'En devolucion / Por revisar', 'Usuario marcó para devolver'),
    ('SOL_INCOMPLETA',           'Devolucion incompleta',       'Devolución parcial, faltan expedientes'),
    ('SOL_FINALIZADA',           'Finalizada',                  'Devolución completa cerrada'),
    ('SOL_RECHAZADA',            'Rechazada',                   'No se aprobó la solicitud'),
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


class Command(BaseCommand):
    help = "Crea (idempotente) los catálogos de estados y tipos de acción del módulo s_exp."

    def handle(self, *args, **options):
        creados = 0

        for codigo, nombre, desc in ESTADOS_SOLICITUD:
            _, c = EstadoSolicitud.objects.get_or_create(
                codigo=codigo, defaults={'nombre': nombre, 'descripcion': desc})
            creados += int(c)
        for codigo, nombre in ESTADOS_EXP_FISICO:
            _, c = EstadoExpedienteFisico.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
            creados += int(c)
        for codigo, nombre in ESTADOS_PRESTAMO:
            _, c = EstadoPrestamo.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
            creados += int(c)
        for codigo, nombre in ESTADOS_DEVOLUCION:
            _, c = EstadoDevolucion.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
            creados += int(c)
        for codigo, nombre in TIPOS_ACCION_LOG:
            _, c = TipoAccionLog.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
            creados += int(c)

        # Invalidar caches codigo<->id por si cambiaron los ids.
        for M in (EstadoSolicitud, EstadoExpedienteFisico, EstadoPrestamo,
                  EstadoDevolucion, TipoAccionLog):
            M.limpiar_cache()

        self.stdout.write(self.style.SUCCESS(
            f"Catálogos poblados. Nuevos registros creados: {creados} "
            f"(los ya existentes se conservaron)."))
