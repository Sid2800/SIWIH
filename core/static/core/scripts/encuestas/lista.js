/**
 * Lista de encuestas ingresadas + detalle (solo lectura).
 * Cada usuario ve las suyas; la supervisión (is_staff) ve todas.
 */
const _veTodas = $('.encuestas-lista-page').data('ve-todas') === 1;

$(document).ready(function () {
    cargar();
    $('#lst-servicio, #lst-desde, #lst-hasta').on('change', cargar);
    $('#enc-detalle-cerrar, #enc-detalle-overlay').on('click', function (e) {
        if (e.target === this) cerrarDetalle();
    });
});

function esc(t) {
    return (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
}

function colorPct(p) {
    if (p == null) return '';
    if (p >= 85) return 'encuestas-pct--ok';
    if (p >= 70) return 'encuestas-pct--med';
    return 'encuestas-pct--bajo';
}

function cargar() {
    $.ajax({
        url: window.urls.encuestas_mis_encuestas_api,
        method: 'GET',
        data: {
            servicio: $('#lst-servicio').val() || '',
            desde: $('#lst-desde').val() || '',
            hasta: $('#lst-hasta').val() || '',
        },
    }).done(function (resp) {
        const filas = (resp.data || []).map(function (e) {
            const pct = e.porcentaje != null ? e.porcentaje + '%' : '—';
            return `<tr>
                <td>${e.id}</td>
                <td>${esc(e.servicio_nombre)}</td>
                <td>${esc(e.subservicio) || '—'}</td>
                <td>${e.fecha}</td>
                <td><span class="encuestas-pct ${colorPct(e.porcentaje)}">${pct}</span></td>
                ${_veTodas ? '<td>' + esc(e.encuestador) + '</td>' : ''}
                <td><button type="button" class="formularioBotones-boton encuestas-btn-ver"
                        data-id="${e.id}"><i class="bi bi-eye"></i> Ver</button></td>
            </tr>`;
        }).join('');
        $('#lst-cuerpo').html(filas);
        $('#lst-vacio').toggle((resp.data || []).length === 0);
    }).fail(function (xhr) {
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar las encuestas';
        toastr.error(err);
    });
}

// Ver detalle.
$(document).on('click', '.encuestas-btn-ver', function () {
    const id = $(this).data('id');
    $.ajax({
        url: window.urls.encuestas_detalle_api.replace(/\/0\/$/, '/' + id + '/'),
        method: 'GET',
    }).done(function (d) {
        $('#enc-detalle-titulo').text(`Encuesta #${d.id} — ${d.servicio_nombre}`);
        const meta = [
            ['Fecha', d.fecha],
            ['Sub-servicio', d.subservicio || '—'],
            ['Encuestado', d.tipo_encuestado || '—'],
            ['Identidad', d.identidad || '—'],
            ['Satisfacción', d.porcentaje != null ? d.porcentaje + '%' : '—'],
            ['Encuestador', d.encuestador],
        ].map(m => `<div class="encuestas-meta"><b>${m[0]}:</b> ${esc(String(m[1]))}</div>`).join('');

        const filas = (d.respuestas || []).map(function (r) {
            const et = (r.numero ? r.numero + '. ' : '') + esc(r.texto);
            const pt = r.puntaje != null ? `<span class="encuestas-pt">${r.puntaje}</span>` : '';
            return `<tr><td>${et}</td><td>${esc(r.respuesta)} ${pt}</td></tr>`;
        }).join('');

        $('#enc-detalle-cuerpo').html(
            `<div class="encuestas-meta-fila">${meta}</div>
             <table class="encuestas-tabla encuestas-tabla-detalle">
                <thead><tr><th>Pregunta</th><th>Respuesta</th></tr></thead>
                <tbody>${filas}</tbody>
             </table>`);
        $('#enc-detalle-overlay').css('display', 'flex');
    }).fail(function (xhr) {
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudo cargar el detalle';
        toastr.error(err);
    });
});

function cerrarDetalle() { $('#enc-detalle-overlay').hide(); }
