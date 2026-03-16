from django.contrib import messages


def mostrar_resultado_media(request, media_result, etiqueta="imagen"):
    """
    Muestra mensajes de éxito y advertencia
    basados en el resultado del MediaService.
    """

    success_list = media_result.get("success", [])
    warning_list = media_result.get("warnings", [])

    total_exitos = len(success_list)
    total_warnings = len(warning_list)

    # Éxitos
    if total_exitos > 0:
        if total_exitos == 1:
            mensaje = f"1 {etiqueta} guardada correctamente."
        else:
            mensaje = f"{total_exitos} {etiqueta}s guardadas correctamente."

        messages.success(request, mensaje)

    # Warnings
    if total_warnings > 0:
        if total_warnings == 1:
            mensaje = f"1 {etiqueta} no pudo procesarse."
        else:
            mensaje = f"{total_warnings} {etiqueta}s no pudieron procesarse."

        messages.warning(request, mensaje)


def mostrar_resultado_media_batch(request, media_result, etiqueta="imagen"):
    """
    Muestra solo el primer mensaje disponible.
    Si hay múltiples, ignora el resto.
    """

    success_list = media_result.get("success", [])
    warning_list = media_result.get("warnings", [])

    # Mostrar primer éxito si existe
    if success_list:
        messages.success(request, success_list[0])

    # Mostrar primer warning si existe
    if warning_list:
        messages.warning(request, warning_list[0])