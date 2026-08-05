from django.apps import AppConfig


class EquiposConfig(AppConfig):
    # Django usa esta clase para registrar la app en INSTALLED_APPS.
    # verbose_name es el nombre que se muestra en el admin.
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipos'
    verbose_name = 'Equipos'

    def ready(self):
        # Registra el receptor post_migrate que asegura la unidad EQ.
        from . import signals  # noqa: F401
