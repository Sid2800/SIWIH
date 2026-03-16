
from django.core.exceptions import ValidationError

def validar_entero_positivo(valor, nombre_campo="campo"):
    """
    Validador genérico para asegurar que un valor sea un entero >= 1.
    Convierte automáticamente desde string si viene de request.GET.
    """

    # 1. Validar que no sea None
    if valor is None:
        raise ValidationError({nombre_campo: "Este campo no puede ser nulo."})

    # 2. Convertir a entero
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        raise ValidationError({nombre_campo: "Debe ser un número entero válido."})

    # 3. Validar rango (>= 1)
    if valor < 1:
        raise ValidationError({nombre_campo: "El valor debe ser mayor o igual a 1."})

    return valor