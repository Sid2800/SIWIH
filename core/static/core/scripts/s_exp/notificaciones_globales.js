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
            // ===== Cola SECUENCIAL: un modal global a la vez =====
            //
            // ORIGEN DEL FLUJO:
            //   /api/alertas/ devuelve SOLO las alertas del usuario actual
            //   (sus solicitudes "listas para recoger" o sus préstamos vencidos).
            //   Por eso, si el admin notifica a varias personas distintas, cada
            //   quien ve únicamente las suyas: NO se acumulan entre usuarios.
            //
            // QUÉ HACE (evita el parpadeo de modales):
            //   SweetAlert2 solo puede mostrar un modal a la vez. Antes el
            //   forEach disparaba un Swal.fire por cada alerta y cada uno
            //   reemplazaba al anterior (solo se veía el último). Ahora:
            //     1. Si YA hay un modal activo → no abrir otro (se respeta el
            //        que el usuario está leyendo).
            //     2. Si no hay ninguno → se muestra SOLO la primera alerta
            //        pendiente. Las demás NO se marcan como leídas, así que
            //        reaparecen en el siguiente ciclo (5s) en cuanto el usuario
            //        pulsa "Entendido". Resultado: se atienden una por una.
            //
            // IMPACTO EN RENDIMIENTO:
            //   Igual de ligero que antes (un solo request a /alertas/), pero
            //   sin crear/destruir modales innecesarios en el mismo ciclo.
            if (!resp.alertas || !resp.alertas.length) return;

            // Si ya hay un modal sticky abierto, esperar a que se acepte.
            if (window.__sexp_modales_activos && window.__sexp_modales_activos.size > 0) return;

            // Tomar la PRIMERA alerta sticky válida y mostrar solo esa.
            const pendiente = resp.alertas.find(function (a) {
                return a.sticky && (
                    (a.tipo_alerta === 'vencimiento' && a.prestamo_id) || a.solicitud_id
                );
            });
            if (!pendiente) return;

            if (pendiente.tipo_alerta === 'vencimiento' && pendiente.prestamo_id) {
                mostrarModalAlertaVencimiento(pendiente);
            } else if (pendiente.solicitud_id) {
                mostrarModalAlertaSticky(pendiente);
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
        title: `<span style="color:#f1f5f9;">${alerta.titulo || '¡Aviso!'}</span>`,
        html: `<div style="font-size:clamp(1.6rem, 2.4vw, 2.2rem);line-height:1.45;padding:0 0.5rem;color:#f1f5f9;">${alerta.mensaje}</div>`,
        icon: 'info',
        confirmButtonText: '<i class="bi bi-check-circle"></i> Entendido',
        allowOutsideClick: false,
        allowEscapeKey: false,
        customClass: {
            popup: 'contener-modal',
            confirmButton: 'contener-modal-boton-confirmar sexp-sticky-btn',
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
        title: `<span style="color:#f1f5f9;">${alerta.titulo || '¡ATENCIÓN!'}</span>`,
        html: `<div style="font-size:clamp(1.6rem, 2.4vw, 2.2rem);line-height:1.45;padding:0 0.5rem;color:#f1f5f9;">${alerta.mensaje}</div>`,
        icon: 'error',
        confirmButtonText: '<i class="bi bi-exclamation-triangle"></i> Entendido',
        allowOutsideClick: false,
        allowEscapeKey: false,
        customClass: {
            popup: 'contener-modal',
            confirmButton: 'contener-modal-boton-confirmar sexp-sticky-btn',
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
