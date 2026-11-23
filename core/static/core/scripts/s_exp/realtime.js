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
    // Recarga automatica sin pisar lo que el usuario tiene abierto
    //
    // Antes, las pantallas de administracion mostraban un banner "hay
    // novedades" y esperaban un clic, para no borrar lo que el admin estaba
    // marcando. Ahora recargan solas, pero solo cuando no hay nada a medias:
    // si hay un modal abierto (SweetAlert) o una fila expandida, la recarga
    // espera a que se cierre. Asi la pantalla se mueve sola, como un chat,
    // sin que se pierda una auditoria a medio llenar.
    // -----------------------------------------------------------------
    const ESPERA_AGRUPAR_MS = 300;   // varios avisos seguidos -> una recarga
    const REVISAR_LIBRE_MS = 1000;   // comprobacion local, sin red

    const recargasPendientes = new Map();  // nombre -> { fn, timer }

    function ocupado() {
        if (global.Swal && typeof global.Swal.isVisible === 'function' && global.Swal.isVisible()) {
            return true;
        }
        // Fila de DataTables con su detalle desplegado.
        return !!document.querySelector('tr.shown');
    }

    // Las tarjetas plegables (.sexp-card-collapsible) se pintan plegadas al
    // recargar. Se recuerda cuales estaban abiertas por su titulo y se
    // vuelven a abrir, junto con la posicion de scroll.
    function _capturarEstadoVista() {
        const abiertas = new Set();
        document.querySelectorAll('.sexp-card-collapsible:not(.sexp-collapsed)').forEach(function (card) {
            const t = card.querySelector('h3, h4');
            if (t) abiertas.add(t.textContent.trim());
        });
        return { abiertas: abiertas, scrollY: global.scrollY };
    }

    function _restaurarEstadoVista(estado) {
        if (estado.abiertas.size) {
            document.querySelectorAll('.sexp-card-collapsible.sexp-collapsed').forEach(function (card) {
                const t = card.querySelector('h3, h4');
                if (t && estado.abiertas.has(t.textContent.trim())) {
                    card.classList.remove('sexp-collapsed');
                }
            });
        }
        global.scrollTo(0, estado.scrollY);
    }

    function _ejecutarRecarga(nombre, fn) {
        const estado = _capturarEstadoVista();
        let restaurado = false;
        const restaurar = function () {
            if (restaurado) return;
            restaurado = true;
            _restaurarEstadoVista(estado);
        };

        try { fn(); }
        catch (e) { console.error('[Realtime] Error en recarga "' + nombre + '":', e); }

        // Las recargas son AJAX: se restaura cuando terminan todas.
        if (global.jQuery && global.jQuery.active > 0) {
            global.jQuery(document).one('ajaxStop', restaurar);
            setTimeout(restaurar, 5000);
        } else {
            restaurar();
        }
    }

    function _recargarCuandoLibre(nombre, fn) {
        const previa = recargasPendientes.get(nombre);
        if (previa) clearTimeout(previa.timer);

        const intentar = function () {
            if (ocupado()) {
                recargasPendientes.set(nombre, { fn: fn, timer: setTimeout(intentar, REVISAR_LIBRE_MS) });
                return;
            }
            recargasPendientes.delete(nombre);
            _ejecutarRecarga(nombre, fn);
        };

        recargasPendientes.set(nombre, { fn: fn, timer: setTimeout(intentar, ESPERA_AGRUPAR_MS) });
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

        // Programar el siguiente tick (backoff exponencial si hay fallos).
        // Con el socket conectado no se programa nada: el servidor avisa, y
        // preguntar ademas seria hacer el trabajo dos veces.
        if (!pausado && !socketConectado && pantallas.has(nombre)) {
            const factor = Math.min(8, Math.pow(2, p.fallosConsecutivos));
            const delay = p.intervalMs * factor;
            p.timer = setTimeout(() => _ejecutar(nombre), delay);
        }
    }


    // =====================================================================
    // WebSocket: el servidor avisa en lugar de que el navegador pregunte
    //
    // Mientras el socket este vivo, los temporizadores no se programan. Si
    // se cae -se reinicia el servidor, se va la red, un proxy corta la
    // conexion- vuelve el polling automaticamente, porque una pantalla que
    // deja de enterarse en silencio es peor que una que gasta de mas.
    // =====================================================================

    // Pantalla -> { seccion, alCambiar }. Lo llenan registrarConTrigger y
    // registrarConAutoReload; lo lee el socket para saber a quien avisar.
    const manejadores = new Map();

    // Quien quiera ver cada mensaje del socket tal cual (los avisos en
    // pantalla lo usan para saber que accion ocurrio).
    const suscriptores = [];

    let socket = null;
    let socketConectado = false;
    let reintentos = 0;
    let socketTimer = null;

    // Espera antes de reintentar, creciendo con cada fallo hasta medio
    // minuto. Reintentar cada segundo contra un servidor caido es la forma
    // de que, cuando vuelva, se lo encuentre con todos los navegadores del
    // hospital llamando a la vez.
    function _esperaReintento() {
        return Math.min(30000, 1000 * Math.pow(2, Math.min(reintentos, 5)));
    }

    function _urlSocket() {
        const esquema = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${esquema}//${window.location.host}/ws/s_exp/cambios/`;
    }

    function _despacharCambio(seccion) {
        manejadores.forEach(function (m) {
            if (m.seccion === seccion || m.seccion === 'global') {
                try { m.alCambiar(); }
                catch (e) { console.error('[Realtime] Error atendiendo cambio:', e); }
            }
        });
    }

    function _detenerTemporizadores() {
        pantallas.forEach(function (p) {
            if (p.timer) {
                clearTimeout(p.timer);
                p.timer = null;
            }
        });
    }

    function _arrancarTemporizadores() {
        if (pausado) return;

        pantallas.forEach(function (p, nombre) {
            if (!p.timer) {
                p.timer = setTimeout(() => _ejecutar(nombre), p.intervalMs);
            }
        });
    }

    function conectarSocket() {
        if (sesionExpirada) return;
        if (socket && (socket.readyState === 0 || socket.readyState === 1)) return;

        try {
            socket = new WebSocket(_urlSocket());
        } catch (e) {
            // Navegador sin WebSocket o URL invalida: el polling se queda.
            return;
        }

        socket.onopen = function () {
            socketConectado = true;
            reintentos = 0;
            // Ya no hace falta preguntar.
            _detenerTemporizadores();
        };

        socket.onmessage = function (evento) {
            let datos;

            try { datos = JSON.parse(evento.data); }
            catch (e) { return; }

            if (datos && datos.tipo === 'cambio' && datos.seccion) {
                _despacharCambio(datos.seccion);
                suscriptores.forEach(function (fn) {
                    try { fn(datos); }
                    catch (e) { console.error('[Realtime] Error en suscriptor:', e); }
                });
            }
        };

        socket.onclose = function (evento) {
            socketConectado = false;

            // 4401 es el cierre que manda el servidor cuando no hay sesion.
            // Reintentar con la sesion caducada solo produce un bucle de
            // conexiones rechazadas.
            if (evento && evento.code === 4401) {
                sesionExpirada = true;
                return;
            }

            // Mientras no haya socket, se vuelve a preguntar.
            _arrancarTemporizadores();

            reintentos++;
            clearTimeout(socketTimer);
            socketTimer = setTimeout(conectarSocket, _esperaReintento());
        };

        socket.onerror = function () {
            // onclose viene detras y se encarga del respaldo; aqui no hay
            // nada que hacer salvo no dejar el error sin manejar.
        };
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
         * Recarga la UI cuando el backend reporta cambios, esperando a que no
         * haya un modal abierto ni una fila expandida.
         *
         * @param {string} nombre - Identificador único
         * @param {string} seccion - 'solicitudes' | 'prestamos' | 'devoluciones' | 'global'
         * @param {function} funcionRecarga - Función que aplica el refresh
         * @param {number} intervalSegundos - Default 5
         */
        registrarConAutoReload(nombre, seccion, funcionRecarga, intervalSegundos = 5) {
            let ultimoTs = null;
            let primeraEjecucion = true;

            // Lo que hay que hacer cuando esta seccion cambia, venga el aviso
            // por socket o por polling. Guardarlo aqui es lo que permite que
            // el socket dispare exactamente el mismo comportamiento sin
            // duplicar la logica de cada pantalla.
            manejadores.set(nombre, {
                seccion: seccion,
                alCambiar: function () {
                    _recargarCuandoLibre(nombre, funcionRecarga);
                },
            });

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
                            _recargarCuandoLibre(nombre, funcionRecarga);
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
         * Se entera de los cambios por el socket (o, sin socket, por el
         * endpoint ligero de timestamps) y recarga sola en cuanto no hay nada
         * a medias. Conserva la firma de antes para no tocar las pantallas;
         * 'opts.etiqueta' ya no se usa (era el texto del banner).
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

            // Ya no hay banner: la pantalla se actualiza sola en cuanto no
            // hay nada a medias (ver _recargarCuandoLibre).
            manejadores.set(nombre, {
                seccion: seccion,
                alCambiar: function () {
                    _recargarCuandoLibre(nombre, funcionRecarga);
                },
            });

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
                            _recargarCuandoLibre(nombre, funcionRecarga);
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
            const r = recargasPendientes.get(nombre);
            if (r) clearTimeout(r.timer);
            recargasPendientes.delete(nombre);
            pantallas.delete(nombre);
            manejadores.delete(nombre);
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

            if (socketConectado) {
                // El socket se mantiene al cambiar de pestaña, asi que al
                // volver no hay nada que reanudar ni nada que recuperar.
                return;
            }

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

        /** Si hay algo a medias (modal abierto, fila expandida). */
        ocupado: ocupado,

        /** Suscribirse a cada mensaje 'cambio' que llega por el socket. */
        onMensaje(fn) {
            if (typeof fn === 'function') suscriptores.push(fn);
        },

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

    // Cerrar el socket al salir, para que el servidor libere el grupo en el
    // acto en lugar de esperar a que la conexion caduque sola.
    window.addEventListener('beforeunload', function () {
        clearTimeout(socketTimer);
        if (socket) {
            try { socket.close(); } catch (e) { /* la pagina ya se va */ }
        }
    });

    // Estado del socket, para diagnosticar desde la consola.
    RealtimeSExp.socket = function () {
        return {
            conectado: socketConectado,
            reintentos: reintentos,
            secciones: Array.from(manejadores.entries()).map(([k, v]) => ({
                pantalla: k, seccion: v.seccion,
            })),
        };
    };

    // Exportar al global
    global.RealtimeSExp = RealtimeSExp;

    // Se conecta en cuanto carga el modulo. Hasta que el socket abra, las
    // pantallas que se registren usan sus temporizadores; al abrir, se
    // apagan solos.
    conectarSocket();
})(window);
