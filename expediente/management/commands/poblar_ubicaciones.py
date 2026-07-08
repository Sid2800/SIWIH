"""
Comando manual para poblar el catálogo expediente_ubicacion.

Recorre las unidades CLÍNICAS (servicio.Unidad_clinica) y NO CLÍNICAS
(servicio.Unidad) activas, y crea una fila en ExpedienteUbicacion por cada
una que aún no esté registrada.

NO se ejecuta automáticamente — el operador lo corre cuando lo necesita:

    python manage.py poblar_ubicaciones                # ambas (clínicas + no clínicas)
    python manage.py poblar_ubicaciones --solo-clinicas
    python manage.py poblar_ubicaciones --solo-noclinicas
    python manage.py poblar_ubicaciones --dry-run       # simula sin guardar

Es idempotente: si una unidad ya tiene su fila, la salta (no duplica).
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Pobla expediente_ubicacion desde Unidad_clinica y Unidad (servicio).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-clinicas', action='store_true',
            help='Solo procesa unidades clínicas (servicio_unidad_clinica).'
        )
        parser.add_argument(
            '--solo-noclinicas', action='store_true',
            help='Solo procesa unidades no clínicas (servicio_unidad).'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula la operación sin guardar nada en la BD.'
        )

    def handle(self, *args, **options):
        from expediente.models import ExpedienteUbicacion
        from servicio.models import Unidad_clinica, Unidad

        solo_clinicas = options['solo_clinicas']
        solo_noclinicas = options['solo_noclinicas']
        dry_run = options['dry_run']

        # Si no se especifica filtro, procesar ambas
        hacer_clinicas = solo_clinicas or not solo_noclinicas
        hacer_noclinicas = solo_noclinicas or not solo_clinicas

        creadas_clinicas = 0
        creadas_noclinicas = 0
        saltadas = 0

        with transaction.atomic():
            # ---------------- Unidades CLÍNICAS ----------------
            if hacer_clinicas:
                # IDs ya registrados para no duplicar
                ya_registradas = set(
                    ExpedienteUbicacion.objects
                    .filter(unidad_clinica__isnull=False)
                    .values_list('unidad_clinica_id', flat=True)
                )
                clinicas = Unidad_clinica.objects.filter(estado=1)
                for uc in clinicas:
                    if uc.id in ya_registradas:
                        saltadas += 1
                        continue
                    if dry_run:
                        self.stdout.write(f"  [DRY] CLINICA -> {uc}")
                    else:
                        ExpedienteUbicacion.objects.create(
                            unidad_clinica=uc,
                            tipo=ExpedienteUbicacion.TIPO_CLINICA,
                        )
                    creadas_clinicas += 1

            # ---------------- Unidades NO CLÍNICAS ----------------
            if hacer_noclinicas:
                ya_registradas = set(
                    ExpedienteUbicacion.objects
                    .filter(unidad_no_clinica__isnull=False)
                    .values_list('unidad_no_clinica_id', flat=True)
                )
                # Unidad usa SmallIntegerField estado con EstadoRegistro.ACTIVO (=1)
                no_clinicas = Unidad.objects.filter(estado=1)
                for u in no_clinicas:
                    if u.id in ya_registradas:
                        saltadas += 1
                        continue
                    if dry_run:
                        self.stdout.write(f"  [DRY] NO CLINICA -> {u.nombre_unidad}")
                    else:
                        ExpedienteUbicacion.objects.create(
                            unidad_no_clinica=u,
                            tipo=ExpedienteUbicacion.TIPO_NO_CLINICA,
                        )
                    creadas_noclinicas += 1

            if dry_run:
                # No persistir nada
                transaction.set_rollback(True)

        # Resumen
        self.stdout.write(self.style.SUCCESS(
            f"\n{'[DRY-RUN] ' if dry_run else ''}Resumen:"
        ))
        self.stdout.write(f"  Clínicas creadas:    {creadas_clinicas}")
        self.stdout.write(f"  No clínicas creadas: {creadas_noclinicas}")
        self.stdout.write(f"  Saltadas (ya existían): {saltadas}")
