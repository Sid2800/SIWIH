/**
 * Recuperación de Expedientes de URGENCIA — s_exp (solo Admisión).
 *
 * Origen del flujo:
 *   Admisión necesita un expediente que YA está prestado por una emergencia.
 *   Aquí se listan todos los expedientes de solicitudes ACTIVAS, se filtran y se
 *   pasan a la lista de la derecha los que se van a exigir. Al confirmar, el
 *   backend los devuelve de inmediato al archivo (saltándose el flujo normal) y
 *   notifica al usuario que los tenía.
 *
 * Estructura: doble lista igual a la Recepción de egresos SDGI, reusando sus
 * clases (listbox, contendorLista, listasRecepcion...) para no duplicar estilos.
 *
 * Estado en memoria:
 *   _todos      -> catálogo completo devuelto por la API (fuente de verdad)
 *   _idsDerecha -> Set con los detalle_id que están "Por Recuperar"
 *   La selección se conserva aunque el usuario filtre, porque el filtro solo
 *   decide qué se PINTA, no qué está seleccionado.
 */

let _todos = [];
const _idsDerecha = new Set();
// detalle_id marcados (resaltados) en cada lista, para los botones de mover.
const _selIzq = new Set();
const _selDer = new Set();

$(document).ready(function () {
    // Fecha/hora local del navegador, solo informativa (el backend sella la suya).
    const ahora = new Date();
    $('#recup-fecha').val(ahora.toLocaleString('es-HN', { hour12: false }));

    cargarRecuperables();

    $('#recup-buscar-izq').on('input', () => pintarIzquierda());
    $('#recup-buscar-der').on('input', () => pintarDerecha());

    $('#recup-mover-der').on('click', () => { _selIzq.forEach(id => _idsDerecha.add(id)); _selIzq.clear(); repintar(); });
    $('#recup-mover-izq').on('click', () => { _selDer.forEach(id => _idsDerecha.delete(id)); _selDer.clear(); repintar(); });
    // "Todos" respeta el filtro visible: mueve solo lo que se está viendo.
    $('#recup-mover-todo-der').on('click', () => { visibles(_todos, '#recup-buscar-izq').filter(e => !_idsDerecha.has(e.detalle_id)).forEach(e => _idsDerecha.add(e.detalle_id)); _selIzq.clear(); repintar(); });
    $('#recup-mover-todo-izq').on('click', () => { visibles(seleccionados(), '#recup-buscar-der').forEach(e => _idsDerecha.delete(e.detalle_id)); _selDer.clear(); repintar(); });

    $('#recup-confirmar').on('click', confirmarRecuperacion);
});

/** Carga el catálogo de expedientes que se pueden exigir. */
function cargarRecuperables() {
    $.ajax({
        url: window.urls.s_exp_expedientes_recuperables_api,
        method: 'GET',
        cache: false,
        success: function (resp) {
            _todos = resp.data || [];
            // Texto de búsqueda precalculado: identidad, expediente y nombre.
            _todos.forEach(e => {
                e._buscar = `${e.paciente_identidad || ''} ${e.numero || ''} ${e.paciente_nombre || ''}`.toLowerCase();
            });
            repintar();
        },
        error: function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los expedientes';
            toastr.error(err);
        }
    });
}

/** Los que NO están en la derecha (siguen disponibles para elegir). */
function disponibles() { return _todos.filter(e => !_idsDerecha.has(e.detalle_id)); }
/** Los elegidos para recuperar. */
function seleccionados() { return _todos.filter(e => _idsDerecha.has(e.detalle_id)); }

/** Aplica el texto del buscador indicado sobre una lista. */
function visibles(lista, selectorInput) {
    const q = ($(selectorInput).val() || '').trim().toLowerCase();
    if (!q) return lista;
    return lista.filter(e => e._buscar.indexOf(q) >= 0);
}

/** Recorta la fecha "dd/mm/aaaa hh:mm" a "dd/mm hh:mm" para que la fila quepa. */
function _fechaCorta(f) {
    if (!f) return '—';
    return f.replace(/^(\d{2}\/\d{2})\/\d{4}\s/, '$1 ');
}

/**
 * Cabecera de columnas. Va DENTRO del <ul> (sticky) para que se desplace en
 * horizontal junto con las filas y quede siempre alineada con ellas.
 */
function cabeceraHtml() {
    return `
        <li class="sexp-recup-item sexp-recup-head">
            <span class="sexp-recup-c sexp-recup-c--exp">Exp.</span>
            <span class="sexp-recup-c sexp-recup-c--id">Identidad</span>
            <span class="sexp-recup-c sexp-recup-c--nom">Nombre</span>
            <span class="sexp-recup-c sexp-recup-c--sol">Sol.</span>
            <span class="sexp-recup-c sexp-recup-c--fec">Solicitado</span>
            <span class="sexp-recup-c sexp-recup-c--fec">Entregado</span>
            <span class="sexp-recup-c sexp-recup-c--per">Prestado a</span>
            <span class="sexp-recup-c sexp-recup-c--area">Área</span>
        </li>`;
}

/**
 * HTML de un ítem: UNA sola fila por expediente.
 *
 * Se muestran los 8 datos en línea (como la Recepción SDGI) en vez de un
 * bloque por expediente: con varios registros un bloque de dos líneas se
 * acumula y hace la lista inmanejable. La fila no se parte (nowrap) y, si no
 * cabe, el listado desplaza en horizontal; el title trae el detalle completo.
 */
function itemHtml(e, marcado) {
    const sanitize = (t) => (t || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    const entrega = e.fecha_entrega || 'Sin entregar';
    const tip = `Solicitud #${e.solicitud_id} — Exp #${e.numero} — ${sanitize(e.paciente_nombre)}\n`
              + `Solicitado: ${e.fecha_solicitud || '—'} | Entregado: ${entrega}\n`
              + `Prestado a: ${sanitize(e.prestado_a)} — ${sanitize(e.area)}`;
    return `
        <li class="sexp-recup-item${marcado ? ' sexp-recup-item--sel' : ''}" data-id="${e.detalle_id}"
            title="${tip}">
            <span class="sexp-recup-c sexp-recup-c--exp">#${e.numero}</span>
            <span class="sexp-recup-c sexp-recup-c--id">${sanitize(e.paciente_identidad) || 'S/ID'}</span>
            <span class="sexp-recup-c sexp-recup-c--nom">${sanitize(e.paciente_nombre) || 'N/A'}</span>
            <span class="sexp-recup-c sexp-recup-c--sol">Sol.${e.solicitud_id}</span>
            <span class="sexp-recup-c sexp-recup-c--fec">${_fechaCorta(e.fecha_solicitud)}</span>
            <span class="sexp-recup-c sexp-recup-c--fec">${e.fecha_entrega ? _fechaCorta(e.fecha_entrega) : 'Sin entregar'}</span>
            <span class="sexp-recup-c sexp-recup-c--per">${sanitize(e.prestado_a) || '—'}</span>
            <span class="sexp-recup-c sexp-recup-c--area">${sanitize(e.area) || '—'}</span>
        </li>`;
}

function pintarIzquierda() {
    const lista = visibles(disponibles(), '#recup-buscar-izq');
    const filas = lista.map(e => itemHtml(e, _selIzq.has(e.detalle_id))).join('');
    $('#recup-lista-izq').html(filas
        ? cabeceraHtml() + filas
        : '<li class="sexp-recup-vacio">Sin expedientes</li>');
    $('#recup-total-izq').text(disponibles().length);
    $('#recup-sub-izq').text(lista.length);
}

function pintarDerecha() {
    const lista = visibles(seleccionados(), '#recup-buscar-der');
    const filas = lista.map(e => itemHtml(e, _selDer.has(e.detalle_id))).join('');
    $('#recup-lista-der').html(filas
        ? cabeceraHtml() + filas
        : '<li class="sexp-recup-vacio">Seleccione los expedientes requeridos</li>');
    $('#recup-total-der').text(seleccionados().length);
    $('#recup-sub-der').text(lista.length);
}

function repintar() { pintarIzquierda(); pintarDerecha(); }

// Marcar/desmarcar un ítem (click) y mover con doble click, como en SDGI.
$(document).on('click', '#recup-lista-izq .sexp-recup-item:not(.sexp-recup-head)', function () {
    const id = parseInt(this.dataset.id, 10);
    _selIzq.has(id) ? _selIzq.delete(id) : _selIzq.add(id);
    pintarIzquierda();
});
$(document).on('click', '#recup-lista-der .sexp-recup-item:not(.sexp-recup-head)', function () {
    const id = parseInt(this.dataset.id, 10);
    _selDer.has(id) ? _selDer.delete(id) : _selDer.add(id);
    pintarDerecha();
});
$(document).on('dblclick', '#recup-lista-izq .sexp-recup-item:not(.sexp-recup-head)', function () {
    _idsDerecha.add(parseInt(this.dataset.id, 10)); _selIzq.clear(); repintar();
});
$(document).on('dblclick', '#recup-lista-der .sexp-recup-item:not(.sexp-recup-head)', function () {
    _idsDerecha.delete(parseInt(this.dataset.id, 10)); _selDer.clear(); repintar();
});

/** Confirma la recuperación: pide motivo y avisa del alcance antes de ejecutar. */
function confirmarRecuperacion() {
    const elegidos = seleccionados();
    if (!elegidos.length) {
        toastr.warning('Seleccione al menos un expediente para recuperar.');
        return;
    }
    const motivo = ($('#recup-observaciones').val() || '').trim();
    if (!motivo) {
        toastr.warning('Indique el motivo de la urgencia.');
        $('#recup-observaciones').focus();
        return;
    }

    // Resumen por persona: deja claro a quién se le va a quitar el expediente.
    const porPersona = {};
    elegidos.forEach(e => {
        const k = `${e.prestado_a || '—'} — ${e.area || '—'}`;
        (porPersona[k] = porPersona[k] || []).push('#' + e.numero);
    });
    const detalle = Object.entries(porPersona).map(([k, v]) =>
        `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">${k}</span>
            <span class="sexp-exp-info-valor">${v.join(', ')}</span>
         </div>`).join('');

    Swal.fire({
        title: '¿Recuperar expedientes?',
        width: '52rem',
        html: `
            <div class="sexp-revision-modal">
                <p class="sexp-auditoria-help">
                    <i class="bi bi-exclamation-triangle"></i>
                    <span>Se recuperarán <strong>${elegidos.length}</strong> expediente(s).
                    Volverán <strong>de inmediato a Admisión</strong> y se notificará a quien los tiene.
                    Esta acción <strong>no se puede deshacer</strong>.</span>
                </p>
                <div class="sexp-exp-info-popup">${detalle}</div>
            </div>`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, recuperar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contenedor-modal sexp-modal-grande',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const a = document.querySelector('.swal2-actions');
            if (a) a.classList.add('contener-modal-contenedor-botones');
        }
    }).then(function (result) {
        if (!result.isConfirmed) return;
        $.ajax({
            url: window.urls.s_exp_recuperar_expedientes_api,
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            contentType: 'application/json',
            data: JSON.stringify({
                detalle_ids: elegidos.map(e => e.detalle_id),
                observaciones: motivo,
            }),
            success: function (resp) {
                if (!resp.success) return;
                const fin = (resp.solicitudes_finalizadas || []).length;
                toastr.success(
                    `${resp.recuperados} expediente(s) recuperado(s) y devuelto(s) a Admisión.` +
                    (fin ? ` ${fin} solicitud(es) finalizada(s).` : '')
                );
                // Limpiar y recargar: los recuperados ya no son recuperables.
                _idsDerecha.clear(); _selIzq.clear(); _selDer.clear();
                $('#recup-observaciones').val('');
                cargarRecuperables();
            },
            error: function (xhr) {
                const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                toastr.error(err);
            }
        });
    });
}
