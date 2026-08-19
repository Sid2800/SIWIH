/**
 * Formulario de encuesta (genérico). Recoge las respuestas por código y las
 * envía. El servicio va en data-servicio del contenedor.
 */
$(document).ready(function () {
    // Fecha por defecto: hoy.
    $('#enc-fecha').val(new Date().toISOString().slice(0, 10));
    $('#enc-guardar').on('click', guardarEncuesta);
});

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
    const $page = $('.encuestas-form-page');
    const servicio = $page.data('servicio');
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
        setTimeout(function () { window.location.href = window.urls.encuestas_inicio; }, 900);
    }).fail(function (xhr) {
        $btn.prop('disabled', false);
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error al guardar';
        toastr.error(err);
    });
}
