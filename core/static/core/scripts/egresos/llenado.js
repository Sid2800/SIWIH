/**
 * Lista de llenado de egresos.
 *
 * Muestra, agrupados por lote, los expedientes que Estadística tomó. Cada
 * renglón enlaza al formulario de egreso; si ya se llenó aparece COMPLETADO.
 */
let _lotes = [];

$(document).ready(function () {
    cargarPendientes();
    $('#llen-buscar').on('input', pintar);
    $('#llen-solo-pendientes').on('change', pintar);
});

function cargarPendientes() {
    $.ajax({
        url: window.urls.egresos_pendientes_llenado_api,
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
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los pendientes';
            toastr.error(err);
        }
    });
}

function urlLlenar(detalleId) {
    // Molde .../llenar/0/  ->  .../llenar/<id>/
    return window.EGRESOS_LLENAR_URL.replace(/\/0\/$/, '/' + detalleId + '/');
}

function esc(t) {
    return (t || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function filtrarDetalles(detalles) {
    const q = ($('#llen-buscar').val() || '').trim().toLowerCase();
    const soloPend = $('#llen-solo-pendientes').is(':checked');
    return detalles.filter(d => {
        if (soloPend && d.completado) return false;
        if (q && d._buscar.indexOf(q) < 0) return false;
        return true;
    });
}

function filaHtml(d) {
    const badge = d.completado
        ? '<span class="egresos-badge egresos-badge--ok"><i class="bi bi-check-circle-fill"></i> Completado</span>'
        : '<span class="egresos-badge egresos-badge--pend"><i class="bi bi-hourglass-split"></i> Pendiente</span>';
    const boton = d.completado
        ? `<i class="bi bi-pencil"></i> Editar`
        : `<i class="bi bi-clipboard-plus"></i> Llenar`;
    return `
        <li class="egresos-item egresos-llenado-item${d.completado ? ' egresos-item--ok' : ''}">
            <span class="egresos-c egresos-c--exp">#${d.numero_expediente || '—'}</span>
            <span class="egresos-c egresos-c--id">${esc(d.identidad) || 'S/ID'}</span>
            <span class="egresos-c egresos-c--nom">${esc(d.nombre) || 'N/A'}</span>
            <span class="egresos-c egresos-c--estado">${badge}</span>
            <a href="${urlLlenar(d.detalle_id)}" class="formularioBotones-boton egresos-btn-llenar">
                ${boton}
            </a>
        </li>`;
}

function loteHtml(lote, detallesVisibles) {
    const filas = detallesVisibles.map(filaHtml).join('');
    return `
        <section class="egresos-lote">
            <header class="egresos-lote__cab">
                <div>
                    <strong>Lote #${lote.lote_id}</strong>
                    <span class="egresos-lote__meta">${lote.fecha} · ${esc(lote.responsable)}</span>
                </div>
                <div class="egresos-lote__prog">
                    <span>${lote.completados}/${lote.total} completados</span>
                    <div class="egresos-prog"><div class="egresos-prog__barra"
                         style="width:${lote.total ? Math.round(lote.completados / lote.total * 100) : 0}%"></div></div>
                </div>
            </header>
            <ul class="listbox sin-margen">${filas}</ul>
        </section>`;
}

function pintar() {
    const bloques = [];
    _lotes.forEach(lote => {
        const visibles = filtrarDetalles(lote.detalles);
        if (visibles.length) bloques.push(loteHtml(lote, visibles));
    });
    $('#llen-contenedor').html(bloques.join(''));
    $('#llen-vacio').toggle(bloques.length === 0);
}
