/**
 * Dashboard Admin - s_exp
 * Carga los KPIs del dashboard mediante AJAX + polling en tiempo real.
 */
$(document).ready(function () {
    cargarKPIs(false);

    // ===== Auto-refresh inteligente (solo si hay cambios reales) =====
    if (window.RealtimeSExp) {
        RealtimeSExp.registrarConTrigger('dashboard-kpis', 'global', function () {
            cargarKPIs(true);
        }, 10);
    }
});

function cargarKPIs(esPolling = false) {
    const headers = {};
    if (esPolling) headers['X-Polling-Request'] = 'true';

    $.ajax({
        url: window.urls.s_exp_dashboard_stats_api,
        method: 'GET',
        headers: headers,
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
            if (!esPolling) toastr.error("Error al cargar estadísticas del dashboard");
        }
    });
}
