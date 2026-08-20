/**
 * Pestaña "Encuestas": al elegir el servicio se cargan sus preguntas al
 * instante (fragmento) y se pueden guardar. Sirve también para la página
 * independiente /encuestas/nueva/<servicio>/ (el fragmento ya viene renderizado).
 */
$(document).ready(function () {
    ponerFechaHoy();

    // Cargar preguntas al elegir el servicio (sin botón intermedio).
    $(document).on('change', '#enc-servicio', function () {
        const servicio = $(this).val();
        const $cont = $('#enc-form-cont');
        if (!servicio) { $cont.empty(); return; }
        const url = window.urls.encuestas_fragmento.replace(/\/0\/$/, '/' + servicio + '/');
        $cont.html('<p class="encuestas-cargando"><i class="bi bi-hourglass-split"></i> Cargando preguntas…</p>');
        $.ajax({ url: url, method: 'GET' })
            .done(function (html) { $cont.html(html); ponerFechaHoy(); })
            .fail(function () { $cont.html('<p class="encuestas-vacio">No se pudieron cargar las preguntas.</p>'); });
    });

    // Guardar (delegado: el botón puede venir de un fragmento cargado luego).
    $(document).on('click', '#enc-guardar', guardarEncuesta);
});

function ponerFechaHoy() {
    const $f = $('#enc-fecha');
    if ($f.length && !$f.val()) $f.val(new Date().toISOString().slice(0, 10));
}

function recogerRespuestas() {
    const resp = {};
    $('.encuestas-pregunta').each(function () {
        const codigo = $(this).data('codigo');
        const $txt = $(this).find('.encuestas-resp-texto');
        if ($txt.length) {
            const v = ($txt.val() || '').trim();
            if (v) resp[codigo] = v;
        } else {
            const v = $(this).find('input[type=radio]:checked').val();
            if (v) resp[codigo] = v;
        }
    });
    return resp;
}

function guardarEncuesta() {
    const servicio = $('.encuestas-form-cont').data('servicio');
    if (!servicio) { toastr.warning('Elija primero el servicio.'); return; }
    if (!$('#enc-fecha').val()) { toastr.warning('Indique la fecha de la encuesta.'); return; }

    const payload = {
        servicio: servicio,
        fecha: $('#enc-fecha').val(),
        subservicio: $('#enc-subservicio').val() || '',
        tipo_encuestado: $('#enc-tipo').val() || '',
        identidad: $('#enc-identidad').val() || '',
        respuestas: recogerRespuestas(),
    };

    const $btn = $('#enc-guardar').prop('disabled', true);
    $.ajax({
        url: window.urls.encuestas_guardar_api,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify(payload),
    }).done(function (resp) {
        if (!resp.success) { $btn.prop('disabled', false); return; }
        const s = resp.porcentaje_satisfaccion;
        toastr.success('Encuesta guardada' + (s != null ? ` (satisfacción ${s}%).` : '.'));
        setTimeout(function () { window.location.href = window.urls.encuestas_lista; }, 900);
    }).fail(function (xhr) {
        $btn.prop('disabled', false);
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error al guardar';
        toastr.error(err);
    });
}
