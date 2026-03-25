/**
 * Reportes - s_exp
 * Filtros de fecha, tabs, carga de datos y tablas de reportes.
 */
$(document).ready(function () {
    initTabs();
    initRangos();
    $('#btn-generar-reporte').on('click', generarReportes);

    // Cargar con rango mensual por defecto
    aplicarRango('mensual');
    generarReportes();
});

function initTabs() {
    $('.sexp-tab').on('click', function () {
        $('.sexp-tab').removeClass('active');
        $(this).addClass('active');
        const tab = $(this).data('tab');
        $('.sexp-tab-content').removeClass('active');
        $('#tab-' + tab).addClass('active');
    });
}

function initRangos() {
    $('#filtro-rango').on('change', function () {
        const rango = $(this).val();
        if (rango) {
            aplicarRango(rango);
        }
    });
}

function aplicarRango(rango) {
    const hoy = new Date();
    let inicio = new Date();

    switch (rango) {
        case 'diario':
            inicio = hoy;
            break;
        case 'semanal':
            inicio.setDate(hoy.getDate() - hoy.getDay()); // Inicio de semana (domingo)
            break;
        case 'mensual':
            inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
            break;
        case 'trimestral':
            const trimestre = Math.floor(hoy.getMonth() / 3) * 3;
            inicio = new Date(hoy.getFullYear(), trimestre, 1);
            break;
        case 'semestral':
            const semestre = hoy.getMonth() < 6 ? 0 : 6;
            inicio = new Date(hoy.getFullYear(), semestre, 1);
            break;
        case 'anual':
            inicio = new Date(hoy.getFullYear(), 0, 1);
            break;
    }

    $('#filtro-fecha-inicio').val(formatDate(inicio));
    $('#filtro-fecha-fin').val(formatDate(hoy));
}

function formatDate(date) {
    return date.toISOString().split('T')[0];
}

function generarReportes() {
    const fechaInicio = $('#filtro-fecha-inicio').val();
    const fechaFin = $('#filtro-fecha-fin').val();

    // Cargar ambos tipos
    cargarMovimiento(fechaInicio, fechaFin);
    cargarIncidencias(fechaInicio, fechaFin);
}

function cargarMovimiento(fechaInicio, fechaFin) {
    $.ajax({
        url: window.urls.s_exp_reportes_data_api,
        method: 'GET',
        data: {
            fecha_inicio: fechaInicio,
            fecha_fin: fechaFin,
            tipo: 'movimiento'
        },
        success: function (data) {
            // Volumen
            $('#reporte-volumen').html(`
                <div style="font-size:2.5rem;font-weight:700;color:#6366f1;">${data.total_prestamos}</div>
                <div style="opacity:0.7;font-size:0.85rem;">préstamos en el período</div>
            `);

            // Áreas
            let areasHtml = '';
            (data.demanda_area || []).forEach(function (a) {
                areasHtml += `<tr><td>${a.area_destino || 'Sin especificar'}</td><td><strong>${a.total}</strong></td></tr>`;
            });
            $('#tbody-areas').html(areasHtml || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');

            // Motivos
            let motivosHtml = '';
            (data.motivos || []).forEach(function (m) {
                motivosHtml += `<tr><td>${m.motivo}</td><td><strong>${m.total}</strong></td></tr>`;
            });
            $('#tbody-motivos').html(motivosHtml || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');
        },
        error: function () {
            toastr.error("Error al cargar reporte de movimiento");
        }
    });
}

function cargarIncidencias(fechaInicio, fechaFin) {
    $.ajax({
        url: window.urls.s_exp_reportes_data_api,
        method: 'GET',
        data: {
            fecha_inicio: fechaInicio,
            fecha_fin: fechaFin,
            tipo: 'incidencias'
        },
        success: function (data) {
            // Morosidad
            let morosidadHtml = '';
            (data.morosidad || []).forEach(function (m) {
                morosidadHtml += `<tr>
                    <td>#${m.prestamo_id}</td>
                    <td>${m.usuario}</td>
                    <td>${m.area || '-'}</td>
                    <td style="color:#ef4444;font-weight:600;">${m.dias_vencido} días</td>
                </tr>`;
            });
            $('#tbody-morosidad').html(morosidadHtml || '<tr><td colspan="4" style="opacity:0.5;">Sin morosidad</td></tr>');

            // Inconsistencias
            let inconHtml = '';
            (data.inconsistencias || []).forEach(function (i) {
                inconHtml += `<tr>
                    <td>#${i.prestamo_id}</td>
                    <td>${i.usuario}</td>
                    <td>${i.total_expedientes}</td>
                    <td>${i.devueltos}</td>
                    <td style="color:#f97316;font-weight:600;">${i.faltantes}</td>
                </tr>`;
            });
            $('#tbody-inconsistencias').html(inconHtml || '<tr><td colspan="5" style="opacity:0.5;">Sin inconsistencias</td></tr>');

            // Rechazos
            let rechazosHtml = '';
            (data.rechazos || []).forEach(function (r) {
                rechazosHtml += `<tr>
                    <td>#${r.solicitud_id}</td>
                    <td>${r.usuario}</td>
                    <td>${r.fecha}</td>
                    <td>${r.motivo_rechazo || '-'}</td>
                </tr>`;
            });
            $('#tbody-rechazos').html(rechazosHtml || '<tr><td colspan="4" style="opacity:0.5;">Sin rechazos</td></tr>');
        },
        error: function () {
            toastr.error("Error al cargar reporte de incidencias");
        }
    });
}
