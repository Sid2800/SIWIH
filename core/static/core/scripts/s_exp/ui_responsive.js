/**
 * ui_responsive.js — Ajustes de interacción responsive del módulo s_exp.
 *
 * Se carga globalmente (base.html) porque los avisos que maneja nacen dentro de
 * modales creados al vuelo (SweetAlert), que no existen al cargar la página.
 * Por eso el listener va DELEGADO en document en vez de atarse a cada elemento.
 *
 * Solo actúa sobre clases sexp-* (avisos del módulo), no toca el resto del
 * sistema.
 *
 * Qué resuelve:
 *   En teléfono, el texto de ayuda de los modales ocupa media pantalla antes de
 *   llegar a lo importante (la lista o los botones). El CSS lo recorta a 2
 *   líneas; aquí se le da la interacción de tocar para ampliar/contraer.
 *   En PC no aplica: el aviso se lee completo y el clic no hace nada.
 */
(function () {
    'use strict';

    // Debe coincidir con el breakpoint del CSS (max-width: 768px).
    const MAX_MOVIL = 768;
    const SELECTOR = '.sexp-auditoria-help, .sexp-revision-help';

    function esMovil() {
        return window.matchMedia(`(max-width: ${MAX_MOVIL}px)`).matches;
    }

    document.addEventListener('click', function (ev) {
        if (!esMovil()) return;
        const aviso = ev.target.closest(SELECTOR);
        if (!aviso) return;
        aviso.classList.toggle('sexp-help--abierto');
    });

    // Al pasar de móvil a PC, quitar el estado "abierto": en PC el aviso se ve
    // completo y esa clase dejaría un remanente sin sentido.
    window.addEventListener('resize', function () {
        if (esMovil()) return;
        document.querySelectorAll('.sexp-help--abierto').forEach(function (el) {
            el.classList.remove('sexp-help--abierto');
        });
    });
})();
