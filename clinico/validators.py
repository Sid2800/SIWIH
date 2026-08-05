
from django.core.exceptions import ValidationError
from core.constants.choices_constants import EstadoRegistro
from clinico.models import Tipo_atencion


def validar_tipo_atencion_activo(id_tipo):

    tipo = Tipo_atencion.objects.filter(
        id=id_tipo,
        estado=EstadoRegistro.ACTIVO
    ).first()

    if not tipo:
        raise ValidationError(
            "El tipo de atención indicado no existe."
        )

    return tipo