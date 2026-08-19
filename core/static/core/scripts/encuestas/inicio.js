/**
 * Inicio del módulo de Encuestas: elegir servicio y continuar al formulario.
 */
$(document).ready(function () {
    $('#enc-continuar').on('click', function () {
        const servicio = $('#enc-servicio').val();
        if (!servicio) { toastr.warning('Seleccione el servicio a encuestar.'); return; }
        window.location.href = '/encuestas/nueva/' + servicio + '/';
    });
});
