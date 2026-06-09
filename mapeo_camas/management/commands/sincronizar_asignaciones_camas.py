"""
Management command: sincronizar_asignaciones_camas
---------------------------------------------------
Recorre todos los ingresos activos (estado=1, sin fecha_egreso) que tienen
cama asignada, y verifica que exista el registro correspondiente
en AsignacionCamaPaciente con estado OCUPADA.

Si el registro falta o está cerrado lo crea / reactiva directamente usando
ingreso_id como pivote operativo.

Uso:
    py manage.py sincronizar_asignaciones_camas
    py manage.py sincronizar_asignaciones_camas --usuario admin
    py manage.py sincronizar_asignaciones_camas --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, Max, OuterRef, Q

from core.services.mapeo_camas_service import MapeoCamasService
from ingreso.models import Ingreso
from mapeo_camas.models import AsignacionCamaPaciente, EstadoMapeo, HistorialEstadoCama, get_observacion_mapeo
from servicio.models import Cama

User = get_user_model()

def get_estado_mapeo(codigo, categoria="ESTADO_CAMA"):
    # 2026-06-01: reutiliza helper central de core/services/mapeo_camas_service.py.
    return MapeoCamasService.get_estado_mapeo(codigo, categoria)

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

        # [2026-05-25] Saneamiento previo: normalizar asignaciones con estado nulo/invalido.
        # Esto evita que el flujo de ingreso falle por estados huérfanos en la tabla operativa.
        estado_vacia = get_estado_mapeo("VACIA")
        estado_valido_subquery = EstadoMapeo.objects.filter(
            pk=OuterRef("estado_id"),
            categoria="ESTADO_CAMA",
        )
        asignaciones_invalidas_qs = (
            AsignacionCamaPaciente.objects
            .annotate(estado_valido=Exists(estado_valido_subquery))
            .filter(Q(estado_id__isnull=True) | Q(estado_valido=False))
        )
        asignaciones_candidatas_reparacion = asignaciones_invalidas_qs.count()
        asignaciones_reparadas = 0
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "[DRY-RUN] Asignaciones con estado nulo/invalido detectadas: "
                    f"{asignaciones_candidatas_reparacion}."
                )
            )
        elif asignaciones_candidatas_reparacion:
            # 2026-06-01: asegura atomic en saneamiento masivo de asignaciones inválidas.
            with transaction.atomic():
                asignaciones_reparadas = asignaciones_invalidas_qs.update(
                    estado_id=estado_vacia.pk,
                    ingreso_id=None,
                )
            self.stdout.write(
                self.style.SUCCESS(
                    "[OK] Asignaciones reparadas a VACIA: "
                    f"{asignaciones_reparadas}."
                )
            )

        # --- Obtener el último ingreso activo por cama ---------------------
        # [2026-05-26 AUDIT] Evita pisar una cama con ingresos activos históricos de la misma cama.
        camas_ultimos_ingresos = (
            Ingreso.objects.filter(
                estado=1,
                fecha_egreso__isnull=True,
                cama_id__isnull=False,
            )
            .values("cama_id")
            .annotate(ingreso_id=Max("id"))
            .values_list("ingreso_id", flat=True)
        )
        ingresos = (
            Ingreso.objects.filter(pk__in=camas_ultimos_ingresos)
            .values("id", "cama_id")
        )

        # [2026-05-25] Camas con ingreso activo para diferenciar ocupadas reales.
        camas_con_ingreso_activo = set(ingresos.values_list("cama_id", flat=True))

        estado_ocupada = get_estado_mapeo("OCUPADA")
        # 2026-06-04: optimiza lectura masiva con values() para evitar instanciar modelos completos.
        asignaciones_actuales_qs = (
            AsignacionCamaPaciente.objects
            .order_by("cama_id", "-fecha_inicio", "-id")
            .values("cama_id", "estado__codigo", "ingreso_id")
        )
        ultima_asignacion_por_cama = {}
        for asig in asignaciones_actuales_qs:
            if asig["cama_id"] not in ultima_asignacion_por_cama:
                ultima_asignacion_por_cama[asig["cama_id"]] = asig

        sincronizados = 0
        omitidos = 0
        errores = 0

        for ingreso in ingresos:
            cama_id = ingreso["cama_id"]
            ingreso_id = ingreso["id"]
            asig_actual = ultima_asignacion_por_cama.get(cama_id)

            # Si la última asignación ya está OCUPADA para el mismo ingreso, no hacer nada.
            if (
                asig_actual
                and asig_actual.get("estado__codigo") == "OCUPADA"
                and asig_actual.get("ingreso_id") == ingreso_id
            ):
                omitidos += 1
                self.stdout.write(
                    f"  [OMITIDO] Ingreso #{ingreso_id} — cama #{cama_id} ya está sincronizada."
                )
                continue

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRY-RUN] Ingreso #{ingreso_id} — cama #{cama_id} "
                        "necesita sincronización."
                    )
                )
                sincronizados += 1
                continue

            try:
                # [2026-05-26 AUDIT] Sincronización ingreso-only para evitar dependencia del flujo legacy por paciente_id.
                with transaction.atomic():
                    asig_bloqueada = (
                        AsignacionCamaPaciente.objects
                        .select_for_update()
                        .filter(cama_id=cama_id)
                        .order_by("-fecha_inicio", "-id")
                        .first()
                    )
                    if (
                        asig_bloqueada
                        and asig_bloqueada.estado
                        and asig_bloqueada.estado.codigo == "OCUPADA"
                        and asig_bloqueada.ingreso_id == ingreso_id
                    ):
                        omitidos += 1
                        self.stdout.write(
                            f"  [OMITIDO] Ingreso #{ingreso_id} — cama #{cama_id} ya quedó sincronizada."
                        )
                        ultima_asignacion_por_cama[cama_id] = {
                            "cama_id": cama_id,
                            "estado__codigo": asig_bloqueada.estado.codigo,
                            "ingreso_id": asig_bloqueada.ingreso_id,
                        }
                        continue

                    estado_anterior = asig_bloqueada.estado if asig_bloqueada else estado_vacia

                    if asig_bloqueada:
                        asig_bloqueada.estado = estado_ocupada
                        asig_bloqueada.ingreso_id = ingreso_id
                        asig_bloqueada.usuario_asignacion = usuario
                        asig_bloqueada.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
                        asig_sync = asig_bloqueada
                    else:
                        asig_sync = AsignacionCamaPaciente.objects.create(
                            cama_id=cama_id,
                            estado=estado_ocupada,
                            ingreso_id=ingreso_id,
                            usuario_asignacion=usuario,
                        )

                    HistorialEstadoCama.objects.create(
                        cama_id=cama_id,
                        estado_anterior=estado_anterior,
                        estado_nuevo=estado_ocupada,
                        ingreso_id=ingreso_id,
                        usuario=usuario,
                        observacion=get_observacion_mapeo("Ingreso (sync masivo)"),
                    )

                    ultima_asignacion_por_cama[cama_id] = {
                        "cama_id": cama_id,
                        "estado__codigo": "OCUPADA",
                        "ingreso_id": ingreso_id,
                    }

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

        # [2026-05-25] Registrar también camas desocupadas en VACIA.
        camas_activas_ids = set(Cama.objects.filter(estado=1).values_list("pk", flat=True))
        camas_desocupadas_ids = camas_activas_ids - camas_con_ingreso_activo
        vacias_creadas = 0
        vacias_actualizadas = 0
        if camas_desocupadas_ids:
            asignaciones_desocupadas = (
                AsignacionCamaPaciente.objects
                .select_related("estado")
                .filter(cama_id__in=camas_desocupadas_ids)
                .order_by("cama_id", "-fecha_inicio", "-id")
            )
            ultima_asignacion_por_cama = {}
            for asig in asignaciones_desocupadas:
                if asig.cama_id not in ultima_asignacion_por_cama:
                    ultima_asignacion_por_cama[asig.cama_id] = asig

            camas_para_crear = []
            asignaciones_para_actualizar = []
            for cama_id in camas_desocupadas_ids:
                asig = ultima_asignacion_por_cama.get(cama_id)
                if not asig:
                    camas_para_crear.append(cama_id)
                    continue

                estado_codigo = getattr(asig.estado, "codigo", None)
                if estado_codigo == "VACIA" and asig.ingreso_id is None:
                    continue

                if estado_codigo == "OCUPADA" or asig.ingreso_id is not None or estado_codigo is None:
                    asignaciones_para_actualizar.append(asig)

            if dry_run:
                vacias_creadas = len(camas_para_crear)
                vacias_actualizadas = len(asignaciones_para_actualizar)
                self.stdout.write(
                    self.style.WARNING(
                        "[DRY-RUN] Camas desocupadas a registrar en VACIA: "
                        f"crear={vacias_creadas}, actualizar={vacias_actualizadas}."
                    )
                )
            else:
                # 2026-06-01: asegura atomic en creación/actualización de camas VACIA.
                with transaction.atomic():
                    if camas_para_crear:
                        AsignacionCamaPaciente.objects.bulk_create([
                            AsignacionCamaPaciente(
                                cama_id=cama_id,
                                estado=estado_vacia,
                                ingreso=None,
                                usuario_asignacion=usuario,
                            )
                            for cama_id in camas_para_crear
                        ])
                        vacias_creadas = len(camas_para_crear)

                    for asig in asignaciones_para_actualizar:
                        asig.estado = estado_vacia
                        asig.ingreso = None
                        asig.usuario_asignacion = usuario
                        asig.save(update_fields=["estado", "ingreso", "usuario_asignacion"])
                    vacias_actualizadas = len(asignaciones_para_actualizar)

                if vacias_creadas or vacias_actualizadas:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "[OK] Camas desocupadas registradas en VACIA: "
                            f"creadas={vacias_creadas}, actualizadas={vacias_actualizadas}."
                        )
                    )

        # --- Resumen final ----------------------------------------------------
        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Candidatas reparacion estado : {asignaciones_candidatas_reparacion}")
        self.stdout.write(f"  Reparadas a VACIA            : {asignaciones_reparadas}")
        self.stdout.write(f"  Vacias creadas               : {vacias_creadas}")
        self.stdout.write(f"  Vacias actualizadas          : {vacias_actualizadas}")
        self.stdout.write(f"  Sincronizados : {sincronizados}")
        self.stdout.write(f"  Omitidos      : {omitidos}")
        self.stdout.write(f"  Errores       : {errores}")
