"""
Comando: limpiar_transaccional
=============================================================================

ORIGEN DEL FLUJO
----------------
Se invoca manualmente desde la terminal:

    python manage.py limpiar_transaccional --dry-run   # solo muestra qué borraría
    python manage.py limpiar_transaccional             # pide confirmación y borra
    python manage.py limpiar_transaccional --noinput   # borra sin preguntar

QUÉ HACE
--------
Borra los datos TRANSACCIONALES (de prueba/operación) del módulo s_exp para
dejar la base limpia tras los cambios de esquema, CONSERVANDO los catálogos:

  SE CONSERVAN (catálogos / configuración):
    - MotivoSolicitud            (motivos)
    - EstadoSolicitud            (estados de solicitud)
    - EstadoExpedienteFisico     (estados físicos del expediente)
    - EstadoPrestamo             (estados de préstamo)
    - EstadoDevolucion           (estados de devolución)
    - TipoAccionLog              (tipos de acción del log)
    - expediente.ExpedienteUbicacion (catálogo de ubicaciones, otra app)

  SE BORRAN (transaccionales):
    - Devolucion
    - ExpedienteEstadoLog
    - SolicitudExpedienteDetalle
    - Prestamo
    - SolicitudPrestamo
    - ExpedientePrestamo   (se regenera con get_or_create al crear solicitudes)
    - LogHistorico

ORDEN DE BORRADO (importante)
-----------------------------
Varias FK usan on_delete=PROTECT, por lo que NO se puede borrar una fila
referenciada antes que sus referencias. El orden de abajo respeta esa cadena:
los "hijos" se borran antes que los "padres".

IMPACTO EN RENDIMIENTO
----------------------
Operación puntual (no en caliente). Se ejecuta dentro de una transacción
atómica: si algo falla, se revierte todo (no deja la BD a medias). Los
conteos se calculan una sola vez para evitar consultas repetidas.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from s_exp.models import (
    Devolucion,
    ExpedienteEstadoLog,
    SolicitudExpedienteDetalle,
    Prestamo,
    SolicitudPrestamo,
    ExpedientePrestamo,
    LogHistorico,
)

# Orden de borrado respetando las FK PROTECT (hijos -> padres).
MODELOS_A_BORRAR = [
    Devolucion,                  # -> Prestamo (PROTECT)
    ExpedienteEstadoLog,         # -> Solicitud (SET_NULL), estados (PROTECT, se conservan)
    SolicitudExpedienteDetalle,  # -> Solicitud (CASCADE), ExpedientePrestamo (PROTECT)
    Prestamo,                    # -> Solicitud (PROTECT)
    SolicitudPrestamo,           # referenciada por los anteriores (ya borrados)
    ExpedientePrestamo,          # referenciada por Detalle (ya borrado)
    LogHistorico,                # -> TipoAccionLog/User (PROTECT, se conservan)
]


class Command(BaseCommand):
    help = ("Borra los datos transaccionales del módulo s_exp conservando los "
            "catálogos (estados, motivos, ubicaciones).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra cuántos registros se borrarían, sin borrar nada.'
        )
        parser.add_argument(
            '--noinput', action='store_true',
            help='No pedir confirmación interactiva (para scripts).'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        noinput = options['noinput']

        # 1) Conteo previo (una sola consulta por modelo).
        conteos = {M.__name__: M.objects.count() for M in MODELOS_A_BORRAR}
        total = sum(conteos.values())

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nRegistros transaccionales detectados:'))
        for nombre, n in conteos.items():
            self.stdout.write(f'  - {nombre:30} {n}')
        self.stdout.write(f'  {"TOTAL":30} {total}\n')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay datos transaccionales que borrar.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '[DRY-RUN] No se borró nada. Quita --dry-run para ejecutar.'))
            return

        # 2) Confirmación interactiva (salvo --noinput).
        if not noinput:
            resp = input(
                f'\n¿Borrar {total} registros transaccionales? '
                f'(se conservan estados, motivos y ubicaciones) [escribe "SI"]: '
            )
            if resp.strip().upper() != 'SI':
                self.stdout.write(self.style.ERROR('Cancelado. No se borró nada.'))
                return

        # 3) Borrado atómico en el orden seguro.
        with transaction.atomic():
            for M in MODELOS_A_BORRAR:
                borrados, _ = M.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(
                    f'  Borrado {M.__name__}: {borrados} fila(s) afectada(s).'))

        self.stdout.write(self.style.SUCCESS(
            '\nLimpieza completada. Catálogos (estados/motivos/ubicaciones) intactos.'))
