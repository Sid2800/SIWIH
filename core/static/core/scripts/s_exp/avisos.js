/**
 * Avisos de s_exp: que cada quien se entere cuando le toca actuar.
 *
 *   - Admin: llega una solicitud nueva, o un usuario inicia una devolución.
 *   - Personal: sus expedientes están listos, le rechazaron una solicitud,
 *     Admisión recuperó uno de sus expedientes, o un préstamo está por vencer.
 *
 * Cómo se muestran:
 *   - Pestaña a la vista: aviso en pantalla (toastr).
 *   - Pestaña oculta, en https/localhost y con permiso: notificación del
 *     sistema (Windows, macOS, Linux). Al tocarla, vuelve a la pestaña y
 *     abre la pantalla correspondiente.
 *   - Pestaña oculta sin eso (hoy SIWIH va por http): el aviso en pantalla
 *     se queda fijo hasta que lo cierren, y el título de la pestaña muestra
 *     cuántos hay pendientes, para que se vea desde la barra de pestañas.
 *
 * Los textos son genéricos a propósito: una notificación del sistema se ve
 * en la pantalla de bloqueo y en el centro de notificaciones, así que nunca
 * lleva nombres de pacientes ni números de expediente.
 *
 * Por el socket solo llega la acción y la sección. Este módulo no pide datos.
 */
(function (global) {
    'use strict';

    // seccion: de dónde tiene que venir el mensaje para que el aviso aplique.
    // EXPEDIENTES_RECUPERADOS también llega a los admins como 'global', y a
    // ellos no hay que decirles "su expediente fue recuperado".
    // enPantalla: false cuando ya hay un modal fijo que lo dice (listo para
    // recoger, recuperación): ahí solo se usa la notificación del sistema.
    const AVISOS = {
        SOLICITUD_CREADA: {
            seccion: 'solicitudes', enPantalla: true, url: 's_exp_solicitudes',
            titulo: 'Nueva solicitud', mensaje: 'Llegó una nueva solicitud de expedientes.',
        },
        SOLICITUD_DEVOLUCION_INICIADA: {
            seccion: 'devoluciones', enPantalla: true, url: 's_exp_devoluciones',
            titulo: 'Devolución iniciada', mensaje: 'Un usuario inició la devolución de expedientes.',
        },
        SOLICITUD_LISTA: {
            seccion: 'mis_solicitudes', enPantalla: false, url: 's_exp_seguimiento',
            titulo: 'Expedientes listos', mensaje: 'Sus expedientes están listos para recoger.',
        },
        SOLICITUD_RECHAZADA: {
            seccion: 'mis_solicitudes', enPantalla: true, url: 's_exp_seguimiento',
            titulo: 'Solicitud rechazada', mensaje: 'Una de sus solicitudes fue rechazada.',
        },
        EXPEDIENTES_RECUPERADOS: {
            seccion: 'mis_solicitudes', enPantalla: false, url: 's_exp_seguimiento',
            titulo: 'Expediente requerido por Admisión', mensaje: 'Admisión recuperó un expediente que tenía prestado.',
        },
    };

    let pendientesOcultos = 0;
    const tituloOriginal = document.title;

    function _url(nombre) {
        return (global.urls && global.urls[nombre]) || null;
    }

    function puedeNotificarSistema() {
        return global.isSecureContext && 'Notification' in global && Notification.permission === 'granted';
    }

    function _marcarTitulo() {
        pendientesOcultos++;
        document.title = '(' + pendientesOcultos + ') ' + tituloOriginal;
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden && pendientesOcultos) {
            pendientesOcultos = 0;
            document.title = tituloOriginal;
        }
    });

    function _irA(url) {
        try { global.focus(); } catch (e) { /* sin foco no pasa nada */ }
        if (url && global.location.pathname !== url) global.location.href = url;
    }

    function _notificacionSistema(titulo, mensaje, url) {
        const opciones = { body: mensaje, tag: 'sexp-' + titulo, renotify: true };

        // Android solo deja mostrarlas desde un service worker. Si la página
        // tiene uno, se usa; si no, en escritorio basta el constructor.
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            navigator.serviceWorker.ready
                .then(function (reg) { return reg.showNotification(titulo, opciones); })
                .catch(function () { /* sin aviso del sistema queda el de pantalla */ });
            return;
        }
        try {
            const n = new Notification(titulo, opciones);
            n.onclick = function () { n.close(); _irA(url); };
        } catch (e) {
            // Navegadores móviles sin service worker lanzan aquí.
        }
    }

    function _toast(titulo, mensaje, url, fijo) {
        if (!global.toastr) return;
        global.toastr.info(mensaje, titulo, {
            closeButton: true,
            timeOut: fijo ? 0 : 8000,
            extendedTimeOut: fijo ? 0 : 2000,
            onclick: function () { _irA(url); },
        });
    }

    /**
     * Muestra un aviso por el mejor canal disponible.
     * @param {{titulo:string, mensaje:string, url?:string, enPantalla?:boolean}} aviso
     */
    function mostrar(aviso) {
        const url = aviso.url || null;
        const enPantalla = aviso.enPantalla !== false;

        if (!document.hidden) {
            if (enPantalla) _toast(aviso.titulo, aviso.mensaje, url, false);
            return;
        }

        _marcarTitulo();
        if (puedeNotificarSistema()) {
            _notificacionSistema(aviso.titulo, aviso.mensaje, url);
        } else if (enPantalla) {
            // Sin notificación del sistema (http): fijo, para que lo vea al volver.
            _toast(aviso.titulo, aviso.mensaje, url, true);
        }
    }

    // ----- Botón para pedir permiso (solo donde se puede) ----------------
    //
    // El navegador solo deja pedir permiso tras un clic, y solo en https o
    // localhost. Con http no se muestra nada: no hay nada que activar.
    const CLAVE_DESCARTADO = 'sexp-avisos-descartado';

    function _ofrecerActivar() {
        if (!global.isSecureContext || !('Notification' in global)) return;
        if (Notification.permission !== 'default') return;
        try { if (global.localStorage.getItem(CLAVE_DESCARTADO)) return; } catch (e) { /* sin storage */ }

        const caja = document.createElement('div');
        caja.className = 'sexp-activar-avisos';
        caja.style.cssText =
            'position:fixed;left:1rem;bottom:1rem;z-index:9000;display:flex;gap:0.6rem;align-items:center;' +
            'background:var(--colorFondoModal,#1f2937);color:var(--colorTextoModal,#fff);' +
            'padding:0.7rem 1rem;border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,0.25);font-size:1.25rem;' +
            'max-width:calc(100vw - 2rem);';
        caja.innerHTML =
            '<i class="bi bi-bell"></i><span>Recibir avisos aunque la pestaña no esté abierta</span>' +
            '<button type="button" data-a="si" style="border:none;border-radius:6px;padding:0.35rem 0.8rem;cursor:pointer;' +
            'background:var(--colorBoton,#3b82f6);color:var(--colorTextoBoton,#fff);font-weight:600;">Activar</button>' +
            '<button type="button" data-a="no" title="Ahora no" style="border:none;background:transparent;color:inherit;' +
            'opacity:0.6;cursor:pointer;font-size:1.5rem;line-height:1;">&times;</button>';

        caja.addEventListener('click', function (e) {
            const accion = e.target && e.target.getAttribute('data-a');
            if (accion === 'si') {
                Notification.requestPermission().finally(function () { caja.remove(); });
            } else if (accion === 'no') {
                try { global.localStorage.setItem(CLAVE_DESCARTADO, '1'); } catch (err) { /* sin storage */ }
                caja.remove();
            }
        });
        document.body.appendChild(caja);
    }

    function _alMensaje(datos) {
        const aviso = AVISOS[datos.accion];
        if (!aviso || aviso.seccion !== datos.seccion) return;
        mostrar({
            titulo: aviso.titulo,
            mensaje: aviso.mensaje,
            url: _url(aviso.url),
            enPantalla: aviso.enPantalla,
        });
    }

    global.AvisosSExp = { mostrar: mostrar, puedeNotificarSistema: puedeNotificarSistema };

    if (global.RealtimeSExp && global.RealtimeSExp.onMensaje) {
        global.RealtimeSExp.onMensaje(_alMensaje);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _ofrecerActivar);
    } else {
        _ofrecerActivar();
    }
})(window);
