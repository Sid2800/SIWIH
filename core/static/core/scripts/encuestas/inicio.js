/**
 * Inicio del módulo de Encuestas: elegir servicio y continuar al formulario.
 *
 * (Fase 1) Los formularios por servicio se construyen en la siguiente fase; por
 * ahora se valida la selección y se avisa. Cuando existan, "Continuar" navegará
 * a /encuestas/nueva/<servicio>/.
 */
$(document).ready(function () {
    $('#enc-continuar').on('click', function () {
        const servicio = $('#enc-servicio').val();
        if (!servicio) { toastr.warning('Seleccione el servicio a encuestar.'); return; }
        // TODO (fase 2): window.location.href = '/encuestas/nueva/' + servicio + '/';
        toastr.info('Formulario en construcción para el servicio seleccionado.');
    });
});
