from django.apps import AppConfig


class IngresoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingreso'

    def ready(self):
        import ingreso.signals
