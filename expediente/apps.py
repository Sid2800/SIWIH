from django.apps import AppConfig


class ExpedienteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'expediente'

    def ready(self):
        # Importar signals para que se registren al iniciar la app.
        # Mantienen expediente_ubicacion sincronizado con las unidades
        # de servicio (clínicas y no clínicas) cuando se crean nuevas.
        import expediente.signals  # noqa: F401
