from django.apps import AppConfig


class PacienteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paciente'

    def ready(self):
        import paciente.signals 