from django.apps import AppConfig


class ServicioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'servicio'

    def ready(self):
        import servicio.signals  # noqa: F401
