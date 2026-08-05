"""Red de seguridad para la unidad EQ.

La migracion 0026 crea la unidad que autoriza el modulo, pero no puede
hacerlo si la base todavia no tiene usuarios: Unidad.creado_por es
obligatorio. En una instalacion limpia el orden es migrate y despues
createsuperuser, asi que la migracion se marca aplicada sin crear nada y no
vuelve a ejecutarse jamas.

Este receptor lo reintenta despues de cada migrate. En cuanto exista un
usuario, el siguiente migrate deja la unidad en su sitio.
"""

from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import post_migrate
from django.dispatch import receiver

CODIGO_UNIDAD = "EQ"
NOMBRE_UNIDAD = "EQUIPOS"


@receiver(post_migrate)
def asegurar_unidad_equipos(sender, app_config=None, using=DEFAULT_DB_ALIAS, **kwargs):
    # post_migrate se emite una vez por aplicacion; sin este filtro el trabajo
    # se repetiria una vez por cada app instalada.
    if app_config is None or app_config.label != "equipos":
        return

    from django.contrib.auth import get_user_model

    from core.constants.choices_constants import EstadoRegistro, TipoUnidad
    from servicio.models import Unidad

    gestor = Unidad.objects.using(using)

    if gestor.filter(nombre_corto_unidad=CODIGO_UNIDAD).exists():
        return

    responsable = get_user_model()._default_manager.using(using).order_by("pk").first()

    if responsable is None:
        # Sigue sin haber a quien atribuir la unidad. Se reintenta en el
        # proximo migrate; hasta entonces el modulo queda cerrado.
        return

    gestor.get_or_create(
        nombre_corto_unidad=CODIGO_UNIDAD,
        defaults={
            "nombre_unidad": NOMBRE_UNIDAD,
            "tipo": TipoUnidad.APOYO,
            "estado": EstadoRegistro.ACTIVO,
            "creado_por": responsable,
            "modificado_por": responsable,
        },
    )
