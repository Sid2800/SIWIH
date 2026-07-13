"""
Management command para poblar las unidades iniciales del hospital.

Uso:
    py manage.py crear_unidades_iniciales
    py manage.py crear_unidades_iniciales --forzar   (actualiza los existentes)
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.constants.choices_constants import TipoUnidad
from servicio.models import Unidad

User = get_user_model()

UNIDADES_INICIALES = [
    {
        "nombre_unidad": "Admisión",
        "nombre_corto_unidad": "ADMI",
        "tipo": TipoUnidad.ADMINISTRATIVA,
    },
    {
        "nombre_unidad": "Radiología",
        "nombre_corto_unidad": "RX",
        "tipo": TipoUnidad.APOYO,
    },
    {
        "nombre_unidad": "Unidad de Atención al Usuario",
        "nombre_corto_unidad": "UAU",
        "tipo": TipoUnidad.ADMINISTRATIVA,
    },
    {
        "nombre_unidad": "Sala Clínica",
        "nombre_corto_unidad": "SALA",
        "tipo": TipoUnidad.CLINICA,
    },
]


class Command(BaseCommand):
    help = "Crea las unidades iniciales requeridas por el sistema de permisos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Actualiza el nombre y tipo si la unidad ya existe.",
        )

    def handle(self, *args, **options):
        # Obtener el primer superusuario disponible para asignar como creador
        superusuario = User.objects.filter(is_superuser=True).first()
        if not superusuario:
            raise CommandError(
                "No existe ningún superusuario. Crea uno primero con "
                "'py manage.py createsuperuser'."
            )

        self.stdout.write(f"Usando superusuario: {superusuario.username}")

        creadas = 0
        actualizadas = 0
        omitidas = 0

        for datos in UNIDADES_INICIALES:
            corto = datos["nombre_corto_unidad"]
            unidad = Unidad.objects.filter(nombre_corto_unidad=corto).first()

            if unidad:
                if options["forzar"]:
                    unidad.nombre_unidad = datos["nombre_unidad"]
                    unidad.tipo = datos["tipo"]
                    unidad.modificado_por = superusuario
                    unidad.save(update_fields=["nombre_unidad", "tipo", "modificado_por", "fecha_modificado"])
                    self.stdout.write(self.style.WARNING(f"  Actualizada: {corto} — {datos['nombre_unidad']}"))
                    actualizadas += 1
                else:
                    self.stdout.write(f"  Omitida (ya existe): {corto} — {unidad.nombre_unidad}")
                    omitidas += 1
            else:
                Unidad.objects.create(
                    nombre_unidad=datos["nombre_unidad"],
                    nombre_corto_unidad=corto,
                    tipo=datos["tipo"],
                    creado_por=superusuario,
                    modificado_por=superusuario,
                )
                self.stdout.write(self.style.SUCCESS(f"  Creada: {corto} — {datos['nombre_unidad']}"))
                creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nListo. Creadas: {creadas} | Actualizadas: {actualizadas} | Omitidas: {omitidas}"
            )
        )
