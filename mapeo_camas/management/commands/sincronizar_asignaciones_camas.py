"""
Management command: sincronizar_asignaciones_camas
---------------------------------------------------
Recorre todos los ingresos activos (estado=1, sin fecha_egreso) que tienen
cama y paciente asignados, y verifica que exista el registro correspondiente
en AsignacionCamaPaciente con estado OCUPADA.

Si el registro falta o está cerrado lo crea / reactiva mediante
MapeoCamasService.sincronizar_cama_con_ingreso().

Uso:
    py manage.py sincronizar_asignaciones_camas
    py manage.py sincronizar_asignaciones_camas --usuario admin
    py manage.py sincronizar_asignaciones_camas --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ingreso.models import Ingreso
from mapeo_camas.models import AsignacionCamaPaciente
from core.services.mapeo_camas_service import MapeoCamasService

User = get_user_model()


class Command(BaseCommand):
    help = "Sincroniza AsignacionCamaPaciente para todos los ingresos activos con cama asignada."

    def add_arguments(self, parser):
        # Opcional: especificar qué usuario quedará registrado como responsable
        parser.add_argument(
            "--usuario",
            type=str,
            default=None,
            help="Username del usuario que se registrará como responsable de la sincronización. "
                 "Si se omite, se usa el primer superusuario disponible.",
        )
        # Modo de prueba: solo reporta, no escribe nada
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Solo muestra qué ingresos se sincronizarían sin escribir nada en la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        username = options["usuario"]

        # --- Resolver el usuario responsable ----------------------------------
        if username:
            try:
                usuario = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"No existe un usuario con username '{username}'.")
        else:
            usuario = User.objects.filter(is_superuser=True).first()
            if not usuario:
                raise CommandError(
                    "No se encontró ningún superusuario. "
                    "Usa --usuario para indicar el responsable."
                )

        self.stdout.write(f"Usuario responsable: {usuario.username}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo --dry-run: no se escribirá nada."))

        # --- Obtener ingresos activos con cama y paciente ---------------------
        # estado=1 significa activo; fecha_egreso nula confirma que sigue hospitalizado
        ingresos = (
            Ingreso.objects.filter(
                estado=1,
                fecha_egreso__isnull=True,
                cama_id__isnull=False,
                paciente_id__isnull=False,
            )
            .values("id", "cama_id", "paciente_id")
        )

        if not ingresos.exists():
            self.stdout.write(self.style.SUCCESS("No hay ingresos activos con cama asignada."))
            return

        # Obtener camas que ya tienen asignación OCUPADA (para no duplicar)
        ocupadas = set(
            AsignacionCamaPaciente.objects.filter(
                estado=AsignacionCamaPaciente.Estado.OCUPADA
            ).values_list("cama_id", flat=True)
        )

        sincronizados = 0
        omitidos = 0
        errores = 0

        for ingreso in ingresos:
            cama_id = ingreso["cama_id"]
            paciente_id = ingreso["paciente_id"]
            ingreso_id = ingreso["id"]

            # Si la cama ya tiene asignación activa, no hacer nada
            if cama_id in ocupadas:
                omitidos += 1
                self.stdout.write(
                    f"  [OMITIDO] Ingreso #{ingreso_id} — cama #{cama_id} ya está sincronizada."
                )
                continue

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRY-RUN] Ingreso #{ingreso_id} — cama #{cama_id} / paciente #{paciente_id} "
                        "necesita sincronización."
                    )
                )
                sincronizados += 1
                continue

            try:
                MapeoCamasService.sincronizar_cama_con_ingreso(
                    cama_id=cama_id,
                    paciente_id=paciente_id,
                    usuario=usuario,
                )
                # Agregar al set para no intentar sincronizar dos ingresos sobre
                # la misma cama en la misma ejecución
                ocupadas.add(cama_id)
                sincronizados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [OK] Ingreso #{ingreso_id} — cama #{cama_id} sincronizada."
                    )
                )
            except Exception as exc:
                errores += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR] Ingreso #{ingreso_id} — cama #{cama_id}: {exc}"
                    )
                )

        # --- Resumen final ----------------------------------------------------
        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Sincronizados : {sincronizados}")
        self.stdout.write(f"  Omitidos      : {omitidos}")
        self.stdout.write(f"  Errores       : {errores}")
