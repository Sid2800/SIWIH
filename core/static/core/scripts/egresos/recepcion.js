/**
 * Recepción de Egresos (Admisión).
 *
 * Admisión ve los lotes enviados: cuál lote, quién lo pidió y qué expedientes
 * regresaron. Puede recibir VARIOS a la vez: selecciona los que trajo y pulsa
 * "Marcar seleccionados como devueltos". Los que se quedan más tiempo no se
 * seleccionan. El lote se cierra solo cuando regresan TODOS.
 */
let _lotes = [];

$(document).ready(function () {
    cargarLotes();
    $('#rec-buscar').on('input', pintar);
    $('#rec-solo-pendientes').on('change', pintar);
});

function cargarLotes() {
    $.ajax({
        url: window.urls.egresos_lotes_para_recepcion_api,
        method: 'GET',
        cache: false,
        success: function (resp) {
            _lotes = resp.data || [];
            _lotes.forEach(l => l.detalles.forEach(d => {
                d._buscar = `${d.identidad || ''} ${d.numero_expediente || ''} ${d.nombre || ''}`.toLowerCase();
            }));
            pintar();
        },
        error: function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los lotes';
            toastr.error(err);
        }
    });
}

function esc(t) {
    return (t || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function urlConId(molde, id) { return molde.replace(/\/0\/$/, '/' + id + '/'); }

function filtrarDetalles(detalles) {
    const q = ($('#rec-buscar').val() || '').trim().toLowerCase();
    const soloPend = $('#rec-solo-pendientes').is(':checked');
    return detalles.filter(d => {
        if (soloPend && d.devuelto) return false;
        if (q && d._buscar.indexOf(q) < 0) return false;
        return true;
    });
}

function filaHtml(d) {
    const badgeEgreso = d.con_egreso
        ? '<span class="egresos-badge egresos-badge--ok"><i class="bi bi-check-circle-fill"></i> Con egreso</span>'
        : '<span class="egresos-badge egresos-badge--pend"><i class="bi bi-exclamation-circle"></i> Sin egreso</span>';
    // Devuelto -> etiqueta + deshacer; pendiente -> checkbox de selección.
    const accion = d.devuelto
        ? `<span class="egresos-badge egresos-badge--ok"><i class="bi bi-check-circle-fill"></i> Devuelto</span>
           <button type="button" class="egresos-link-deshacer rec-deshacer" data-detalle="${d.detalle_id}">deshacer</button>`
        : `<label class="egresos-check-inline egresos-rec-check">
               <input type="checkbox" class="rec-sel" data-detalle="${d.detalle_id}"> Regresó
           </label>`;
    return `
        <li class="egresos-item egresos-recepcion-item${d.devuelto ? ' egresos-item--ok' : ''}">
            <span class="egresos-c egresos-c--exp">#${d.numero_expediente || '—'}</span>
            <span class="egresos-c egresos-c--id">${esc(d.identidad) || 'S/ID'}</span>
            <span class="egresos-c egresos-c--nom">${esc(d.nombre) || 'N/A'}</span>
            <span class="egresos-c egresos-c--estado">${badgeEgreso}</span>
            <span class="egresos-rec-accion">${accion}</span>
        </li>`;
}

function loteHtml(lote, detallesVisibles) {
    const filas = detallesVisibles.map(filaHtml).join('');
    const pct = lote.total ? Math.round(lote.devueltos / lote.total * 100) : 0;
    return `
        <section class="egresos-lote" data-lote="${lote.lote_id}">
            <header class="egresos-lote__cab">
                <div>
                    <strong>Lote #${lote.lote_id}</strong>
                    <span class="egresos-lote__meta">Solicitó: ${esc(lote.responsable)} ·
                        enviado ${lote.fecha_envio || lote.fecha_captura}</span>
                </div>
                <div class="egresos-lote__prog">
                    <span>${lote.devueltos}/${lote.total} devueltos</span>
                    <div class="egresos-prog"><div class="egresos-prog__barra"
                         style="width:${pct}%"></div></div>
                </div>
            </header>
            <ul class="listbox sin-margen">${filas}</ul>
            <footer class="egresos-lote__pie">
                <button type="button" class="formularioBotones-boton egresos-btn-secundario egresos-btn-selall"
                        data-lote="${lote.lote_id}">
                    <i class="bi bi-check2-square"></i> Seleccionar todos
                </button>
                <button type="button" class="formularioBotones-boton egresos-btn-marcar"
                        data-lote="${lote.lote_id}">
                    <i class="bi bi-box-arrow-in-left"></i> Marcar seleccionados como devueltos
                </button>
                <button type="button" class="formularioBotones-boton egresos-btn-cerrar"
                        data-lote="${lote.lote_id}" ${lote.todos_devueltos ? '' : 'disabled'}>
                    <i class="bi bi-lock-fill"></i> Cerrar lote
                </button>
                ${lote.todos_devueltos ? '' :
                    '<span class="egresos-cerrar-nota">El lote se cierra cuando regresan todos</span>'}
            </footer>
        </section>`;
}

function pintar() {
    const bloques = [];
    _lotes.forEach(lote => {
        const visibles = filtrarDetalles(lote.detalles);
        if (visibles.length) bloques.push(loteHtml(lote, visibles));
    });
    $('#rec-contenedor').html(bloques.join(''));
    $('#rec-vacio').toggle(bloques.length === 0);
}

// Actualiza el estado local de un lote y repinta.
function refrescarLoteLocal(loteId) {
    const lote = _lotes.find(l => l.lote_id === loteId);
    if (!lote) return;
    lote.devueltos = lote.detalles.filter(x => x.devuelto).length;
    lote.todos_devueltos = lote.total > 0 && lote.devueltos === lote.total;
    pintar();
}

// Seleccionar todos los pendientes de un lote.
$(document).on('click', '.egresos-btn-selall', function () {
    $(this).closest('.egresos-lote').find('.rec-sel').prop('checked', true);
});

// Marcar los seleccionados como devueltos (varios de una vez).
$(document).on('click', '.egresos-btn-marcar', function () {
    const loteId = $(this).data('lote');
    const $sec = $(this).closest('.egresos-lote');
    const ids = $sec.find('.rec-sel:checked').map(function () {
        return parseInt(this.dataset.detalle, 10);
    }).get();
    if (!ids.length) { toastr.warning('Seleccione al menos un expediente que haya regresado.'); return; }

    $.ajax({
        url: urlConId(window.urls.egresos_marcar_devueltos_api, loteId),
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ detalle_ids: ids })
    }).done(function (resp) {
        if (!resp.success) return;
        toastr.success(`${resp.marcados} expediente(s) marcados como devueltos.`);
        const lote = _lotes.find(l => l.lote_id === loteId);
        if (lote) lote.detalles.forEach(d => { if (ids.indexOf(d.detalle_id) >= 0) d.devuelto = true; });
        refrescarLoteLocal(loteId);
    }).fail(function (xhr) {
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudo marcar';
        toastr.error(err);
    });
});

// Deshacer una devolución (regresa el expediente a Estadística).
$(document).on('click', '.rec-deshacer', function () {
    const detalleId = parseInt(this.dataset.detalle, 10);
    $.ajax({
        url: urlConId(window.urls.egresos_marcar_devuelto_api, detalleId),
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ devuelto: 'no' })
    }).done(function (resp) {
        if (!resp.success) return;
        toastr.info('Devolución deshecha.');
        _lotes.forEach(lote => {
            const d = lote.detalles.find(x => x.detalle_id === detalleId);
            if (d) { d.devuelto = false; refrescarLoteLocal(lote.lote_id); }
        });
    }).fail(function (xhr) {
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudo deshacer';
        toastr.error(err);
    });
});

// Cerrar lote (solo si están todos devueltos).
$(document).on('click', '.egresos-btn-cerrar', function () {
    const loteId = $(this).data('lote');
    Swal.fire({
        title: `¿Cerrar lote #${loteId}?`,
        html: 'Se registrará la recepción por Admisión. Esta acción finaliza el lote.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-lock-fill"></i> Sí, cerrar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contenedor-modal',
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
            url: urlConId(window.urls.egresos_cerrar_lote_api, loteId),
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        }).done(function (resp) {
            if (!resp.success) return;
            toastr.success(`Lote #${loteId} cerrado.`);
            cargarLotes();
        }).fail(function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudo cerrar el lote';
            toastr.error(err);
        });
    });
});
