def validar_texto_obligatorio(valor, campo):
    """Valida un texto requerido para futuros formularios del modulo."""
    if valor is None:
        raise ValueError(f"El campo '{campo}' es requerido.")

    if isinstance(valor, str) and not valor.strip():
        raise ValueError(f"El campo '{campo}' no puede estar vacio.")

    return valor.strip() if isinstance(valor, str) else valor