from django.apps import AppConfig


class EquiposBiomedicosConfig(AppConfig):
    # Django usa esta clase para registrar la app en INSTALLED_APPS.
    # verbose_name es el nombre que se muestra en el admin.
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipos_biomedicos'
    verbose_name = 'Equipos'
