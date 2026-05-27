/**
 * Notificaciones Globales - s_exp
 *
 * Sistema event-driven en lugar de polling ciego:
 *   1. Al cargar la página → consulta inicial /api/alertas/
 *   2. Después → usa RealtimeSExp con trigger (changes-check) para detectar
 *      cuando hay cambios reales en backend. Solo entonces consulta /api/alertas/.
 *
 * Beneficio: si NO hay cambios en backend, NO se hacen requests a /api/alertas/.
 * Cuando alguien notifica una solicitud → el timestamp 'global' cambia → trigger
 * dispara verificarAlertasGlobales() casi instantáneamente.
 *
 * - Modales sticky (no se cierran al hacer click fuera ni con Escape)
 * - Header X-Polling-Request:true → no renueva el timer de sesión
 * - Anti-duplicado por solicitud_id / prestamo_id
 */
(function () {
    let pollingFallback = null;

    // Registro de modales activos para evitar duplicados al hacer polling
    if (!window.__sexp_modales_activos) {
        window.__sexp_modales_activos = new Set();
    }

    $(document).ready(function () {
        // Consulta inicial al cargar la página (por si hay alertas pendientes al abrir)
        verificarAlertasGlobales();

        // Sistema event-driven con changes-check (PREFERIDO)
        // Solo dispara verificarAlertasGlobales cuando 'global' cambia en backend
        if (window.RealtimeSExp && window.RealtimeSExp.registrarConAutoReload) {
            window.RealtimeSExp.registrarConAutoReload(
                'notificaciones-globales',
                'global',
                verificarAlertasGlobales,
                5  // cada 5s consulta changes-check (ligero), pero solo llama a /alertas/ si hay cambios
            );
        } else {
            // Fallback: si realtime.js no está cargado, polling tradicional cada 30s
            pollingFallback = setInterval(verificarAlertasGlobales, 30 * 1000);
        }
    });

    // Limpiar el polling fallback si la página se cierra/navega
    $(window).on('beforeunload', function () {
        if (pollingFallback) clearInterval(pollingFallback);
    });
})();

function verificarAlertasGlobales() {
    if (!window.urls || !window.urls.s_exp_alertas_api) return;

    $.ajax({
        url: window.urls.s_exp_alertas_api,
        method: 'GET',
        // Header para que este polling NO renueve la sesión del usuario
        headers: { 'X-Polling-Request': 'true' },
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
        },
        error: function (xhr) {
            // Si la sesión expiró (401/403) o backend redirige a login,
            // detener el polling para no hacer requests innecesarios
            if (xhr.status === 401 || xhr.status === 403 || xhr.status === 0) {
                if (typeof pollingTimer !== 'undefined' && pollingTimer) {
                    clearInterval(pollingTimer);
                }
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
        html: `<div style="font-size:clamp(1.6rem, 2.4vw, 2.2rem);line-height:1.45;padding:0 0.5rem;">${alerta.mensaje}</div>`,
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
        html: `<div style="font-size:clamp(1.6rem, 2.4vw, 2.2rem);line-height:1.45;padding:0 0.5rem;">${alerta.mensaje}</div>`,
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
