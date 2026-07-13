/**
 * Realtime — Sistema global de polling inteligente para s_exp.
 *
 * Características:
 *  - Polling configurable por pantalla
 *  - Header X-Polling-Request:true para NO renovar sesión del usuario
 *  - Pausa automática cuando la pestaña no está visible (Page Visibility API)
 *  - Reanudación instantánea al volver a la pestaña
 *  - Cancela request previo si todavía está en curso
 *  - Backoff exponencial si hay errores de red
 *  - Indicador visual "Live" opcional por pantalla
 *
 * Uso típico:
 *   RealtimeSExp.registrar('miPantalla', () => table.ajax.reload(null, false), 5);
 *   RealtimeSExp.mostrarIndicador('miPantalla', '#mi-contenedor');
 *
 *   // Al salir de la pantalla:
 *   RealtimeSExp.desregistrar('miPantalla');
 */
(function (global) {
    'use strict';

    // jQuery global: inyectar el header X-Polling-Request en cualquier petición
    // marcada como tal. Para que no afecte a otras peticiones, NO lo hacemos por
    // ajaxSetup global, sino que cada llamada de polling lo pone manualmente.
    // Aquí dejamos un helper para hacerlo fácil:
    function pollingAjax(opts) {
        // Seguridad: si ya detectamos sesión expirada, no enviar más requests
        if (sesionExpirada) {
            return $.Deferred().reject({ status: 401 }).promise();
        }
        const userError = opts.error;
        const merged = Object.assign({}, opts, {
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-Polling-Request', 'true');
                if (opts.beforeSend) opts.beforeSend.call(this, xhr);
            },
            error: function (xhr, status, err) {
                // Si la sesión expiró (401/403 o redirect a login), detener TODO el polling
                if (xhr && (xhr.status === 401 || xhr.status === 403)) {
                    sesionExpirada = true;
                    RealtimeSExp.pausar();
                    pantallas.clear();
                }
                if (userError) userError.call(this, xhr, status, err);
            },
        });
        return $.ajax(merged);
    }

    // Estado interno
    const pantallas = new Map();         // nombre → { timer, fn, intervalMs, ultimoOk, fallosConsecutivos }
    let pausado = false;                  // pausa global por visibilidad
    let sesionExpirada = false;           // si se pierde la sesión, deja de hacer requests

    // -----------------------------------------------------------------
    // Banner flotante "Hay N novedades — Actualizar"
    // -----------------------------------------------------------------
    function _asegurarContenedorBanner() {
        let cont = document.getElementById('realtime-banners');
        if (!cont) {
            cont = document.createElement('div');
            cont.id = 'realtime-banners';
            cont.style.cssText =
                'position:fixed;right:1.5rem;bottom:1.5rem;z-index:9000;' +
                'display:flex;flex-direction:column;gap:0.5rem;pointer-events:none;';
            document.body.appendChild(cont);

            // Estilos para el banner (una sola vez)
            if (!document.getElementById('realtime-banner-styles')) {
                const st = document.createElement('style');
                st.id = 'realtime-banner-styles';
                st.textContent = `
                    .rt-banner {
                        background: var(--colorFondoModal, #1f2937);
                        color: var(--colorTextoModal, #fff);
                        border: 1px solid rgba(255,255,255,0.1);
                        border-radius: 12px;
                        padding: 0.8rem 1.1rem;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
                        display: flex;
                        align-items: center;
                        gap: 0.9rem;
                        font-size: 1.3rem;
                        animation: rt-banner-in 0.25s ease-out;
                        pointer-events: auto;
                        max-width: 420px;
                    }
                    @keyframes rt-banner-in {
                        from { transform: translateY(20px); opacity: 0; }
                        to { transform: translateY(0); opacity: 1; }
                    }
                    .rt-banner__dot {
                        width: 0.7rem; height: 0.7rem;
                        background: #22c55e; border-radius: 50%;
                        flex-shrink: 0;
                        animation: rt-pulse 1.4s ease-in-out infinite;
                    }
                    @keyframes rt-pulse {
                        0%, 100% { opacity: 1; transform: scale(1); }
                        50% { opacity: 0.55; transform: scale(0.85); }
                    }
                    .rt-banner__text { flex: 1; line-height: 1.3; }
                    .rt-banner__btn {
                        background: var(--colorBoton, #3b82f6);
                        color: var(--colorTextoBoton, #fff);
                        border: none;
                        border-radius: 8px;
                        padding: 0.45rem 0.9rem;
                        font-size: 1.2rem;
                        font-weight: 600;
                        cursor: pointer;
                        display: inline-flex;
                        align-items: center;
                        gap: 0.4rem;
                    }
                    .rt-banner__btn:hover { filter: brightness(1.1); }
                    .rt-banner__close {
                        background: transparent;
                        color: inherit;
                        border: none;
                        cursor: pointer;
                        opacity: 0.6;
                        font-size: 1.5rem;
                        line-height: 1;
                        padding: 0 0.25rem;
                    }
                    .rt-banner__close:hover { opacity: 1; }
                    @media (max-width: 600px) {
                        #realtime-banners {
                            left: 1rem; right: 1rem; bottom: 1rem;
                        }
                        .rt-banner { max-width: none; font-size: 1.4rem; }
                    }
                `;
                document.head.appendChild(st);
            }
        }
        return cont;
    }

    function _mostrarBannerActualizacion(nombre, cantidad, etiqueta, onActualizar) {
        const cont = _asegurarContenedorBanner();
        const bannerId = 'rt-banner-' + nombre;
        let banner = document.getElementById(bannerId);

        const palabra = cantidad === 1 ? etiqueta.replace(/s$/, '') : etiqueta;
        const textoHtml = `<strong>${cantidad}</strong> ${cantidad === 1 ? 'novedad' : 'novedades'}` +
                          (etiqueta && etiqueta !== 'novedades' ? ` en ${etiqueta}` : '');

        if (banner) {
            // Actualizar contador (no recrear el banner)
            const txt = banner.querySelector('.rt-banner__text');
            if (txt) txt.innerHTML = textoHtml;
            return;
        }

        banner = document.createElement('div');
        banner.id = bannerId;
        banner.className = 'rt-banner';
        banner.innerHTML = `
            <span class="rt-banner__dot"></span>
            <span class="rt-banner__text">${textoHtml}</span>
            <button type="button" class="rt-banner__btn"><i class="bi bi-arrow-clockwise"></i> Actualizar</button>
            <button type="button" class="rt-banner__close" title="Descartar">&times;</button>
        `;

        const btnRefresh = banner.querySelector('.rt-banner__btn');
        const btnClose = banner.querySelector('.rt-banner__close');

        btnRefresh.addEventListener('click', function () {
            try { onActualizar(); } catch (e) { console.error(e); }
            banner.remove();
        });
        btnClose.addEventListener('click', function () { banner.remove(); });

        cont.appendChild(banner);
    }

    function _ejecutar(nombre) {
        const p = pantallas.get(nombre);
        if (!p) return;

        try {
            // Llamar la función de refresh provista por la pantalla.
            // Se le pasa pollingAjax para que pueda usarlo si quiere.
            const resultado = p.fn(pollingAjax);

            // Si la función retorna una promesa, manejarla
            if (resultado && typeof resultado.then === 'function') {
                resultado
                    .then(() => {
                        p.fallosConsecutivos = 0;
                    })
                    .catch(() => {
                        p.fallosConsecutivos++;
                    });
            }
        } catch (e) {
            console.error(`[Realtime] Error en pantalla "${nombre}":`, e);
            p.fallosConsecutivos++;
        }

        // Programar el siguiente tick (backoff exponencial si hay fallos)
        if (!pausado && pantallas.has(nombre)) {
            const factor = Math.min(8, Math.pow(2, p.fallosConsecutivos));
            const delay = p.intervalMs * factor;
            p.timer = setTimeout(() => _ejecutar(nombre), delay);
        }
    }

    const RealtimeSExp = {
        /**
         * Registra una pantalla para auto-refresh.
         *
         * @param {string} nombre - Identificador único de la pantalla
         * @param {function} funcionRecarga - Función que ejecuta el refresh (recibe pollingAjax como argumento opcional)
         * @param {number} intervalSegundos - Intervalo en segundos (default 5)
         */
        registrar(nombre, funcionRecarga, intervalSegundos = 5) {
            // Si ya estaba registrada, limpiar primero
            this.desregistrar(nombre);

            const intervalMs = Math.max(1000, intervalSegundos * 1000);

            pantallas.set(nombre, {
                fn: funcionRecarga,
                intervalMs: intervalMs,
                timer: null,
                fallosConsecutivos: 0,
            });

            // Primera ejecución después del intervalo (no inmediata, ya hay carga inicial)
            const p = pantallas.get(nombre);
            p.timer = setTimeout(() => _ejecutar(nombre), intervalMs);
        },

        /**
         * Registra una pantalla con AUTO-RELOAD cuando hay cambios.
         *
         * A diferencia de registrarConTrigger (que muestra banner), esta versión
         * recarga directamente la UI cuando el backend reporta cambios. Útil para
         * vistas de usuario donde no hay interacción crítica en curso (ej: Mis Solicitudes).
         *
         * @param {string} nombre - Identificador único
         * @param {string} seccion - 'solicitudes' | 'prestamos' | 'devoluciones' | 'global'
         * @param {function} funcionRecarga - Función que aplica el refresh
         * @param {number} intervalSegundos - Default 5
         */
        registrarConAutoReload(nombre, seccion, funcionRecarga, intervalSegundos = 5) {
            let ultimoTs = null;
            let primeraEjecucion = true;

            const wrapper = function () {
                if (!window.urls || !window.urls.s_exp_changes_check_api) {
                    return funcionRecarga();
                }

                return new Promise(function (resolve) {
                    pollingAjax({
                        url: window.urls.s_exp_changes_check_api,
                        method: 'GET',
                        timeout: 10000,
                    }).then(function (resp) {
                        const tsActual = (resp && resp[seccion]) || '';

                        if (primeraEjecucion) {
                            ultimoTs = tsActual;
                            primeraEjecucion = false;
                            resolve();
                            return;
                        }

                        if (tsActual && tsActual !== ultimoTs) {
                            ultimoTs = tsActual;
                            try { funcionRecarga(); }
                            catch (e) { console.error(`[Realtime auto] Error "${nombre}":`, e); }
                        }
                        resolve();
                    }).fail(function () {
                        resolve();
                    });
                });
            };

            this.registrar(nombre, wrapper, intervalSegundos);
        },

        /**
         * Registra una pantalla con TRIGGER inteligente.
         *
         * En lugar de recargar siempre, consulta un endpoint ULTRA LIGERO que
         * devuelve timestamps por sección. Si hubo cambios, NO recarga
         * automáticamente: muestra un BANNER flotante con un botón "Actualizar".
         *
         * El usuario decide cuándo aplicar el refresh, sin interrumpir su trabajo
         * actual (revisar/aprobar/expandir tarjetas).
         *
         * @param {string} nombre - Identificador único de la pantalla
         * @param {string} seccion - 'solicitudes' | 'prestamos' | 'devoluciones' | 'global'
         * @param {function} funcionRecarga - Función que ejecuta el refresh REAL
         * @param {number} intervalSegundos - Intervalo en segundos (default 5)
         * @param {object} opts - Opcional: { etiqueta: 'novedades' | 'solicitudes' | ... }
         */
        registrarConTrigger(nombre, seccion, funcionRecarga, intervalSegundos = 5, opts) {
            opts = opts || {};
            let ultimoTs = null;
            let primeraEjecucion = true;
            let cambiosPendientes = 0;

            const wrapper = function () {
                if (!window.urls || !window.urls.s_exp_changes_check_api) {
                    return funcionRecarga();
                }

                return new Promise(function (resolve) {
                    pollingAjax({
                        url: window.urls.s_exp_changes_check_api,
                        method: 'GET',
                        timeout: 10000,
                    }).then(function (resp) {
                        const tsActual = (resp && resp[seccion]) || '';

                        if (primeraEjecucion) {
                            ultimoTs = tsActual;
                            primeraEjecucion = false;
                            resolve();
                            return;
                        }

                        if (tsActual && tsActual !== ultimoTs) {
                            // Hay cambios — incrementar contador y mostrar banner
                            ultimoTs = tsActual;
                            cambiosPendientes++;
                            _mostrarBannerActualizacion(nombre, cambiosPendientes,
                                opts.etiqueta || 'novedades',
                                function () {
                                    // Al hacer clic en "Actualizar":
                                    try {
                                        funcionRecarga();
                                    } catch (e) {
                                        console.error(`[Realtime] Error en recarga "${nombre}":`, e);
                                    }
                                    cambiosPendientes = 0;
                                }
                            );
                        }
                        resolve();
                    }).fail(function () {
                        resolve();
                    });
                });
            };

            this.registrar(nombre, wrapper, intervalSegundos);
        },

        /**
         * Desregistra una pantalla y detiene su polling.
         */
        desregistrar(nombre) {
            const p = pantallas.get(nombre);
            if (p && p.timer) clearTimeout(p.timer);
            pantallas.delete(nombre);
        },

        /**
         * Pausa todo el polling (útil para cuando la pestaña pierde foco)
         */
        pausar() {
            pausado = true;
            pantallas.forEach((p) => {
                if (p.timer) clearTimeout(p.timer);
                p.timer = null;
            });
        },

        /**
         * Reanuda todo el polling
         */
        reanudar() {
            pausado = false;
            pantallas.forEach((p, nombre) => {
                if (!p.timer) {
                    // Ejecutar inmediatamente al volver
                    _ejecutar(nombre);
                }
            });
        },

        /**
         * Helper para hacer peticiones AJAX marcadas como polling
         * (no renuevan la sesión del usuario)
         */
        ajax: pollingAjax,

        /**
         * Inserta un indicador "Live" sutil dentro del selector indicado
         */
        mostrarIndicador(nombre, selectorContenedor) {
            const $cont = $(selectorContenedor);
            if (!$cont.length) return;

            const indicadorId = `realtime-indicator-${nombre}`;
            if (document.getElementById(indicadorId)) return;

            const html = `
                <span id="${indicadorId}" class="realtime-indicator" title="Actualizándose automáticamente"
                      style="display:inline-flex;align-items:center;gap:0.4rem;padding:0.2rem 0.6rem;
                             background:rgba(34,197,94,0.15);color:var(--negro);
                             border-radius:12px;font-size:1.1rem;font-weight:600;
                             margin-left:0.5rem;">
                    <span style="width:0.7rem;height:0.7rem;background:#22c55e;border-radius:50%;
                                 display:inline-block;animation:realtime-pulse 1.5s ease-in-out infinite;"></span>
                    Live
                </span>
                <style>
                    @keyframes realtime-pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.4; }
                    }
                </style>
            `;
            $cont.append(html);
        },

        /**
         * Devuelve el listado de pantallas activas (para debug)
         */
        debug() {
            return Array.from(pantallas.entries()).map(([k, v]) => ({
                pantalla: k,
                intervaloMs: v.intervalMs,
                fallosConsecutivos: v.fallosConsecutivos,
                activa: !!v.timer,
                pausado: pausado,
            }));
        }
    };

    // Auto-pausa cuando la pestaña no está visible (ahorra recursos y queries)
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            RealtimeSExp.pausar();
        } else {
            RealtimeSExp.reanudar();
        }
    });

    // Limpieza al salir de la página
    window.addEventListener('beforeunload', function () {
        pantallas.forEach((p) => {
            if (p.timer) clearTimeout(p.timer);
        });
        pantallas.clear();
    });

    // Exportar al global
    global.RealtimeSExp = RealtimeSExp;
})(window);
