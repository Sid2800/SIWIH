from django.apps import AppConfig


class SExpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 's_exp'
    verbose_name = 'Sistema de Expedientes - Préstamos'

    def ready(self):
        # Conecta la señal que convierte cada apunte de la bitacora en un
        # aviso por WebSocket. Va aqui y no a nivel de modulo porque ready()
        # es el unico punto en que Django garantiza que los modelos ya estan
        # cargados; importarlo antes falla con AppRegistryNotReady.
        from . import signals  # noqa: F401
