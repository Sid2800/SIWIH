from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder


APP_LABEL_ANTERIOR = "equipos_biomedicos"
APP_LABEL_NUEVO = "equipos"


class Command(BaseCommand):
    help = (
        "Traslada el historial de migraciones y los ContentType de "
        "equipos_biomedicos a equipos sin modificar las tablas del modulo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los cambios necesarios sin escribir en la base.",
        )

    def handle(self, *args, **options):
        alias = connection.alias
        migraciones = MigrationRecorder(connection).Migration.objects.using(alias)
        content_types = ContentType.objects.using(alias)

        migraciones_anteriores = list(
            migraciones.filter(app=APP_LABEL_ANTERIOR)
            .order_by("name")
            .values_list("name", flat=True)
        )
        migraciones_nuevas = set(
            migraciones.filter(app=APP_LABEL_NUEVO)
            .values_list("name", flat=True)
        )
        conflictos_migraciones = sorted(
            set(migraciones_anteriores) & migraciones_nuevas
        )

        modelos_anteriores = list(
            content_types.filter(app_label=APP_LABEL_ANTERIOR)
            .order_by("model")
            .values_list("model", flat=True)
        )
        modelos_nuevos = set(
            content_types.filter(app_label=APP_LABEL_NUEVO)
            .values_list("model", flat=True)
        )
        conflictos_content_types = sorted(
            set(modelos_anteriores) & modelos_nuevos
        )
        modelos_vigentes = {
            modelo._meta.model_name
            for modelo in apps.get_app_config(APP_LABEL_NUEVO).get_models()
        }
        modelos_obsoletos = sorted(
            set(
                content_types.filter(
                    app_label__in=[APP_LABEL_ANTERIOR, APP_LABEL_NUEVO]
                )
                .exclude(model__in=modelos_vigentes)
                .values_list("model", flat=True)
            )
        )

        if conflictos_migraciones or conflictos_content_types:
            detalles = []
            if conflictos_migraciones:
                detalles.append(
                    "migraciones: " + ", ".join(conflictos_migraciones)
                )
            if conflictos_content_types:
                detalles.append(
                    "content types: " + ", ".join(conflictos_content_types)
                )
            raise CommandError(
                "La transicion esta parcialmente aplicada y requiere revision ("
                + "; ".join(detalles)
                + ")."
            )

        self.stdout.write(
            f"Migraciones por trasladar: {len(migraciones_anteriores)}"
        )
        self.stdout.write(
            f"ContentType por trasladar: {len(modelos_anteriores)}"
        )
        self.stdout.write(
            "ContentType obsoletos por retirar: "
            + (
                ", ".join(modelos_obsoletos)
                if modelos_obsoletos
                else "ninguno"
            )
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("[DRY-RUN] No se modifico la base de datos.")
            )
            return

        if (
            not migraciones_anteriores
            and not modelos_anteriores
            and not modelos_obsoletos
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    "La app ya esta registrada como equipos; no hubo cambios."
                )
            )
            return

        with transaction.atomic(using=alias):
            migraciones_actualizadas = migraciones.filter(
                app=APP_LABEL_ANTERIOR
            ).update(app=APP_LABEL_NUEVO)
            content_types_actualizados = content_types.filter(
                app_label=APP_LABEL_ANTERIOR
            ).update(app_label=APP_LABEL_NUEVO)
            content_types_obsoletos = content_types.filter(
                app_label=APP_LABEL_NUEVO,
                model__in=modelos_obsoletos,
            )
            obsoletos_eliminados = content_types_obsoletos.count()
            content_types_obsoletos.delete()

        ContentType.objects.clear_cache()
        self.stdout.write(
            self.style.SUCCESS(
                "Transicion completada: "
                f"{migraciones_actualizadas} migraciones y "
                f"{content_types_actualizados} ContentType actualizados; "
                f"{obsoletos_eliminados} ContentType obsoletos retirados."
            )
        )
