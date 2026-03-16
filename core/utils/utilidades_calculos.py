

def calcular_porcentaje(valor, total, decimales=2, mostrar_simbolo=True):
    """
    Calcula un porcentaje seguro. 
    - Devuelve el porcentaje con 'decimales' decimales.
    - Maneja división entre cero, None y tipos inválidos.
    - Si 'mostrar_simbolo' es False, devuelve solo el número.
    """
    if total in (0, None):
        return f"0{' %' if mostrar_simbolo else ''}"

    try:
        porcentaje = (float(valor) / float(total)) * 100
        resultado = f"{porcentaje:.{decimales}f}"
        return f"{resultado} %" if mostrar_simbolo else resultado
    except (TypeError, ValueError, ZeroDivisionError):
        return f"0{' %' if mostrar_simbolo else ''}"