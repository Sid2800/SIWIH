
from django.core.exceptions import ValidationError



def validar_entero_positivo(valor, nombre_campo="campo"):
    """
    Validador genérico para asegurar que un valor sea un entero >= 1.
    Convierte automáticamente desde string si viene de request.GET.
    """

    # 1. Validar que no sea None
    if valor is None:
        raise ValidationError(f"{nombre_campo}: Este campo no puede ser nulo.")

    # 2. Convertir a entero
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{nombre_campo}: Debe ser un número entero válido.")

    # 3. Validar rango (>= 1)
    if valor < 1:
        raise ValidationError(f"{nombre_campo}: El valor debe ser mayor o igual a 1.")

    return valor



def validar_booleano(valor, nombre_campo="campo"):
    """
    Valida que el valor represente un booleano válido.

    Acepta:
    - True / False
    - 1 / 0
    - "1" / "0"

    Retorna:
        bool
    """

    # 1. Validar que no sea nulo
    if valor is None:
        raise ValidationError(
            f"{nombre_campo}: Este campo no puede ser nulo."
        )

    # 2. Si ya es booleano
    if isinstance(valor, bool):
        return valor

    # 3. Convertir desde entero/string
    if str(valor) == "1":
        return True

    if str(valor) == "0":
        return False

    raise ValidationError(
        f"{nombre_campo}: Debe ser un valor booleano válido."
    )


def validar_texto_opcional(valor, nombre_campo="campo", max_length=255):

    if valor is None:
        return None

    if not isinstance(valor, str):
        raise ValidationError(
            f"El campo {nombre_campo} debe ser texto válido."
        )

    valor = valor.strip()

    if not valor:
        return None

    if len(valor) > max_length:
        raise ValidationError(
            f"El campo {nombre_campo} no puede superar "
            f"los {max_length} caracteres."
        )

    return valor