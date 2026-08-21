# Mapas de presentacion compartidos por varios modulos de vistas:
# clases CSS, etiquetas e iconos. Sin logica.

from .models import (
    CriticidadDispositivo,
    EstadoDispositivo,
    EstadoGarantiaDispositivo,
)


ICONOS_TIPO_IMAGEN = {
    "GENERAL": "bi bi-camera",
    "INVENTARIO": "bi bi-upc-scan",
    "PLACA_SERIE": "bi bi-card-text",
    "ESTADO_FISICO": "bi bi-shield-check",
    "ACCESORIOS": "bi bi-plug",
    "OTRA": "bi bi-image",
}


CSS_ESTADO_DISPOSITIVO = {
    EstadoDispositivo.OPERATIVO: "equipos-estado--operativo",
    EstadoDispositivo.EN_MANTENIMIENTO: "equipos-estado--media",
    EstadoDispositivo.FUERA_DE_SERVICIO: "equipos-estado--alta",
    EstadoDispositivo.DADO_DE_BAJA: "equipos-estado--inactivo",
    EstadoDispositivo.REPUESTO_PENDIENTE: "equipos-estado--repuesto",
}


CSS_CRITICIDAD_DISPOSITIVO = {
    CriticidadDispositivo.BAJA: "equipos-estado--operativo",
    CriticidadDispositivo.MEDIA: "equipos-estado--media",
    CriticidadDispositivo.ALTA: "equipos-estado--alta",
}


ETIQUETAS_ESTADO_DISPOSITIVO = {
    EstadoDispositivo.OPERATIVO: "Oper.",
    EstadoDispositivo.EN_MANTENIMIENTO: "Mant.",
    EstadoDispositivo.FUERA_DE_SERVICIO: "F. serv.",
    EstadoDispositivo.DADO_DE_BAJA: "Baja",
    EstadoDispositivo.REPUESTO_PENDIENTE: "Rep.",
}


CSS_ESTADO_GARANTIA = {
    EstadoGarantiaDispositivo.VIGENTE: "equipos-estado--operativo",
    EstadoGarantiaDispositivo.POR_VENCER: "equipos-estado--media",
    EstadoGarantiaDispositivo.VENCIDA: "equipos-estado--alta",
    EstadoGarantiaDispositivo.PAUSADA: "equipos-estado--repuesto",
    EstadoGarantiaDispositivo.SIN_GARANTIA: "equipos-estado--inactivo",
}
