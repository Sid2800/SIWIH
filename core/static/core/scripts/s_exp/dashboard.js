/**
 * Dashboard Admin - s_exp
 * Carga los KPIs del dashboard mediante AJAX.
 */
$(document).ready(function () {
    cargarKPIs();
    // Refresco automático cada 60 segundos
    setInterval(cargarKPIs, 60000);
});

function cargarKPIs() {
    $.ajax({
        url: window.urls.s_exp_dashboard_stats_api,
        method: 'GET',
        success: function (data) {
            $('#kpi-total').text(data.total_expedientes);
            $('#kpi-disponibles').text(data.disponibles);
            $('#kpi-prestados').text(data.prestados);
            $('#kpi-baja').text(data.baja);
            $('#kpi-pendientes').text(data.solicitudes_pendientes);
            $('#kpi-vencidos').text(data.prestamos_vencidos);
            $('#kpi-proximos').text(data.proximos_vencer);
            $('#kpi-parciales').text(data.devoluciones_parciales);
        },
        error: function () {
            toastr.error("Error al cargar estadísticas del dashboard");
        }
    });
}
