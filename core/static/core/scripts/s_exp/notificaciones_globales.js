/**
 * Notificaciones Globales - s_exp
 * Consulta periódicamente si hay alertas para el usuario (como expedientes listos para recoger).
 *
 * - Polling cada 30 segundos
 * - Modales sticky (no se cierran al hacer click fuera ni con Escape)
 * - Se evita duplicar el mismo modal mediante registro en window.__sexp_modales_activos
 */
(function () {
    const INTERVALO_POLLING_MS = 30 * 1000; // 30 segundos
    let pollingTimer = null;

    // Registro de modales activos para evitar duplicados al hacer polling
    if (!window.__sexp_modales_activos) {
        window.__sexp_modales_activos = new Set();
    }

    $(document).ready(function () {
        // Consulta inicial al cargar la página
        verificarAlertasGlobales();

        // Polling periódico cada 30 segundos
        pollingTimer = setInterval(verificarAlertasGlobales, INTERVALO_POLLING_MS);
    });

    // Limpiar el polling si la página se cierra/navega
    $(window).on('beforeunload', function () {
        if (pollingTimer) clearInterval(pollingTimer);
    });
})();

function verificarAlertasGlobales() {
    if (!window.urls || !window.urls.s_exp_alertas_api) return;

    $.ajax({
        url: window.urls.s_exp_alertas_api,
        method: 'GET',
        success: function (resp) {
            if (resp.alertas && resp.alertas.length > 0) {
                resp.alertas.forEach(function (alerta) {
                    // Solo procesar alertas persistentes (sticky)
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
 * Anti-duplicado via window.__sexp_modales_activos.
 */
function mostrarModalAlertaSticky(alerta) {
    const clave = 'solicitud-' + alerta.solicitud_id;

    // Si ya hay un modal activo para esta solicitud, no abrir otro
    if (window.__sexp_modales_activos && window.__sexp_modales_activos.has(clave)) return;

    if (window.__sexp_modales_activos) {
        window.__sexp_modales_activos.add(clave);
    }

    Swal.fire({
        title: alerta.titulo || '¡Aviso!',
        text: alerta.mensaje,
        icon: 'info',
        confirmButtonText: '<i class="bi bi-check-circle"></i> Entendido, pasaré por ellos',
        allowOutsideClick: false,
        allowEscapeKey: false,
        customClass: {
            popup: 'contener-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
        },
    }).then((result) => {
        if (window.__sexp_modales_activos) {
            window.__sexp_modales_activos.delete(clave);
        }
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
    const clave = 'vencimiento-' + alerta.prestamo_id;

    if (window.__sexp_modales_activos && window.__sexp_modales_activos.has(clave)) return;

    if (window.__sexp_modales_activos) {
        window.__sexp_modales_activos.add(clave);
    }

    Swal.fire({
        title: alerta.titulo || '¡ATENCIÓN!',
        text: alerta.mensaje,
        icon: 'error',
        confirmButtonText: '<i class="bi bi-exclamation-triangle"></i> Entendido, devolveré los expedientes',
        allowOutsideClick: false,
        allowEscapeKey: false,
        customClass: {
            popup: 'contener-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
        },
    }).then((result) => {
        if (window.__sexp_modales_activos) {
            window.__sexp_modales_activos.delete(clave);
        }
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
