/**
 * Recepción de Egresos (Admisión).
 *
 * Lista los lotes que Estadística envió. Admisión marca los expedientes que
 * regresaron (cada uno vuelve a Admisión) y cierra el lote cuando están todos.
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

function urlConId(molde, id) {
    return molde.replace(/\/0\/$/, '/' + id + '/');
}

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
    return `
        <li class="egresos-item egresos-recepcion-item${d.devuelto ? ' egresos-item--ok' : ''}">
            <span class="egresos-c egresos-c--exp">#${d.numero_expediente || '—'}</span>
            <span class="egresos-c egresos-c--id">${esc(d.identidad) || 'S/ID'}</span>
            <span class="egresos-c egresos-c--nom">${esc(d.nombre) || 'N/A'}</span>
            <span class="egresos-c egresos-c--estado">${badgeEgreso}</span>
            <label class="egresos-check-inline egresos-rec-check">
                <input type="checkbox" class="rec-devuelto" data-detalle="${d.detalle_id}"
                       ${d.devuelto ? 'checked' : ''}> Regresó
            </label>
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
                    <span class="egresos-lote__meta">Capturó ${esc(lote.responsable)} ·
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
                <button type="button" class="formularioBotones-boton egresos-btn-cerrar"
                        data-lote="${lote.lote_id}" ${lote.todos_devueltos ? '' : 'disabled'}>
                    <i class="bi bi-lock-fill"></i> Cerrar lote
                </button>
                ${lote.todos_devueltos ? '' :
                    '<span class="egresos-cerrar-nota">Faltan expedientes por devolver</span>'}
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

// Marcar/desmarcar devuelto.
$(document).on('change', '.rec-devuelto', function () {
    const $chk = $(this);
    const detalleId = $chk.data('detalle');
    const devuelto = $chk.is(':checked');
    $chk.prop('disabled', true);
    $.ajax({
        url: urlConId(window.urls.egresos_marcar_devuelto_api, detalleId),
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ devuelto: devuelto ? 'si' : 'no' })
    }).done(function (resp) {
        if (!resp.success) { $chk.prop('checked', !devuelto); $chk.prop('disabled', false); return; }
        // Actualizar estado local y repintar (progreso + habilitar cerrar).
        _lotes.forEach(lote => {
            const d = lote.detalles.find(x => x.detalle_id === detalleId);
            if (d) {
                d.devuelto = resp.devuelto;
                lote.devueltos = lote.detalles.filter(x => x.devuelto).length;
                lote.todos_devueltos = lote.total > 0 && lote.devueltos === lote.total;
            }
        });
        pintar();
    }).fail(function (xhr) {
        $chk.prop('checked', !devuelto).prop('disabled', false);
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudo actualizar';
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
