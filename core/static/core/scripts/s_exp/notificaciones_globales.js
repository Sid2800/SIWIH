/**
 * Notificaciones Globales - s_exp
 * Consulta periódicamente si hay alertas para el usuario (como expedientes listos).
 */
$(document).ready(function () {
    // Primera consulta al cargar
    verificarAlertasGlobales();

    // Consultar cada 60 segundos
    setInterval(verificarAlertasGlobales, 60000);
});

function verificarAlertasGlobales() {
    if (!window.urls.s_exp_alertas_api) return;

    $.ajax({
        url: window.urls.s_exp_alertas_api,
        method: 'GET',
        success: function (resp) {
            if (resp.alertas && resp.alertas.length > 0) {
                resp.alertas.forEach(function (alerta) {
                    // Si es una alerta persistente e informativa de "Listo para recoger"
                    if (alerta.sticky) {
                        if (alerta.tipo_alerta === 'vencimiento' && alerta.prestamo_id) {
                            mostrarModalAlertaVencimiento(alerta);
                        } else if (alerta.solicitud_id) {
                            mostrarModalAlertaSticky(alerta);
                        }
                    }
                });
            }
        }
    });
}

/**
 * Muestra un modal de SweetAlert2 que persiste hasta ser aceptado.
 */
function mostrarModalAlertaSticky(alerta) {
    // Usar una marca temporal en el DOM para evitar duplicar el mismo modal si ya está abierto
    const modalId = 'modal-alerta-solicitud-' + alerta.solicitud_id;
    if ($('#' + modalId).length) return;

    Swal.fire({
        id: modalId,
        title: alerta.titulo || '¡Aviso!',
        text: alerta.mensaje,
        icon: 'info',
        confirmButtonText: '<i class="bi bi-check-circle"></i> Entendido, pasaré por ellos',
        confirmButtonColor: '#22c55e',
        allowOutsideClick: false,
        allowEscapeKey: false,
    }).then((result) => {
        if (result.isConfirmed) {
            marcarAlertaLeida(alerta.solicitud_id);
        }
    });
}

function marcarAlertaLeida(solicitudId) {
    $.ajax({
        url: window.urls.s_exp_notificado_listo_api,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ solicitud_id: solicitudId }),
        success: function (resp) {
            // No hacemos nada, la alerta ya no vendrá en la siguiente consulta
        },
        error: function () {
            console.error("Error al marcar alerta como leída");
        }
    });
}

/**
 * Muestra el modal de alerta de vencimiento (Nagging cada 5 min).
 */
function mostrarModalAlertaVencimiento(alerta) {
    const modalId = 'modal-alerta-vencimiento-' + alerta.prestamo_id;
    if ($('#' + modalId).length) return;

    Swal.fire({
        id: modalId,
        title: alerta.titulo || '¡ATENCIÓN!',
        text: alerta.mensaje,
        icon: 'error',
        confirmButtonText: '<i class="bi bi-exclamation-triangle"></i> Entendido, devolveré los expedientes',
        confirmButtonColor: '#ef4444',
        allowOutsideClick: false,
        allowEscapeKey: false,
    }).then((result) => {
        if (result.isConfirmed) {
            marcarVencimientoLeido(alerta.prestamo_id);
        }
    });
}

function marcarVencimientoLeido(prestamoId) {
    $.ajax({
        url: window.urls.s_exp_vencimiento_leido_api,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ prestamo_id: prestamoId }),
        success: function (resp) {
            // Aceptado temporalmente por 5 minutos
        },
        error: function () {
            console.error("Error al marcar alerta de vencimiento como leída");
        }
    });
}
