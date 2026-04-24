/**
 * Reportes - s_exp
 * Reporte unificado con KPIs, rankings, incidencias y exportación a Excel/PDF.
 */
let reporteData = null; // Cache global de los últimos datos cargados

$(document).ready(function () {
    initTabs();
    initRangos();
    $('#btn-generar-reporte').on('click', generarReportes);
    $('#btn-exportar-excel').on('click', exportarExcel);
    $('#btn-exportar-pdf').on('click', exportarPDF);

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
            inicio = new Date(hoy);
            break;
        case 'semanal':
            inicio.setDate(hoy.getDate() - hoy.getDay());
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

    $.ajax({
        url: window.urls.s_exp_reportes_data_api,
        method: 'GET',
        data: { fecha_inicio: fechaInicio, fecha_fin: fechaFin },
        success: function (data) {
            reporteData = data;
            renderKPIs(data.resumen);
            renderAreas(data.demanda_area);
            renderMotivos(data.motivos);
            renderExpedientesTop(data.expedientes_top);
            renderUsuariosTop(data.usuarios_top);
            renderRechazos(data.rechazos);
            renderMorosidad(data.morosidad);
            renderInconsistencias(data.inconsistencias);
        },
        error: function () {
            toastr.error("Error al cargar los reportes");
        }
    });
}

/* ========== RENDERERS ========== */

function renderKPIs(r) {
    $('#kpi-total-solicitudes').text(r.total_solicitudes);
    $('#kpi-total-expedientes').text(r.total_expedientes);
    $('#kpi-aprobadas').text(r.aprobadas);
    $('#kpi-rechazadas').text(r.rechazadas);
    $('#kpi-pendientes').text(r.pendientes);
}

function renderAreas(data) {
    let html = '';
    (data || []).forEach(function (a) {
        html += `<tr><td>${a.area_destino || 'Sin especificar'}</td><td><strong>${a.total}</strong></td></tr>`;
    });
    $('#tbody-areas').html(html || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');
}

function renderMotivos(data) {
    let html = '';
    (data || []).forEach(function (m) {
        html += `<tr><td>${m.nombre || 'Sin especificar'}</td><td><strong>${m.total}</strong></td></tr>`;
    });
    $('#tbody-motivos').html(html || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');
}

function renderExpedientesTop(data) {
    let html = '';
    (data || []).forEach(function (e, i) {
        const medal = i < 3 ? ['🥇', '🥈', '🥉'][i] + ' ' : '';
        html += `<tr><td>${medal}#${e.numero}</td><td><strong>${e.total}</strong></td></tr>`;
    });
    $('#tbody-expedientes-top').html(html || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');
}

function renderUsuariosTop(data) {
    let html = '';
    (data || []).forEach(function (u, i) {
        const medal = i < 3 ? ['🥇', '🥈', '🥉'][i] + ' ' : '';
        html += `<tr><td>${medal}${u.nombre} <small style="opacity:0.5">(${u.username})</small></td><td><strong>${u.total}</strong></td></tr>`;
    });
    $('#tbody-usuarios-top').html(html || '<tr><td colspan="2" style="opacity:0.5;">Sin datos</td></tr>');
}

function renderRechazos(data) {
    let html = '';
    (data || []).forEach(function (r) {
        html += `<tr>
            <td>#${r.solicitud_id}</td>
            <td>${r.usuario}</td>
            <td>${r.fecha}</td>
            <td>${r.motivo_rechazo || '-'}</td>
        </tr>`;
    });
    $('#tbody-rechazos').html(html || '<tr><td colspan="4" style="opacity:0.5;">Sin rechazos</td></tr>');
}

function renderMorosidad(data) {
    let html = '';
    (data || []).forEach(function (m) {
        html += `<tr>
            <td>#${m.prestamo_id}</td>
            <td>${m.usuario}</td>
            <td>${m.area || '-'}</td>
            <td style="color:#ef4444;font-weight:600;">${m.dias_vencido} días</td>
        </tr>`;
    });
    $('#tbody-morosidad').html(html || '<tr><td colspan="4" style="opacity:0.5;">Sin morosidad</td></tr>');
}

function renderInconsistencias(data) {
    let html = '';
    (data || []).forEach(function (i) {
        html += `<tr>
            <td>#${i.prestamo_id}</td>
            <td>${i.usuario}</td>
            <td>${i.total_expedientes}</td>
            <td>${i.devueltos}</td>
            <td style="color:#f97316;font-weight:600;">${i.faltantes}</td>
        </tr>`;
    });
    $('#tbody-inconsistencias').html(html || '<tr><td colspan="5" style="opacity:0.5;">Sin inconsistencias</td></tr>');
}

/* ========== EXPORTACIÓN ========== */

function getRangoTexto() {
    const inicio = $('#filtro-fecha-inicio').val();
    const fin = $('#filtro-fecha-fin').val();
    return `Período: ${inicio} al ${fin}`;
}

function exportarExcel() {
    const fechaInicio = $('#filtro-fecha-inicio').val();
    const fechaFin = $('#filtro-fecha-fin').val();

    // Llamar API para descargar Excel
    const url = new URL(window.urls.s_exp_exportar_excel, window.location.origin);
    url.searchParams.append('fecha_inicio', fechaInicio);
    url.searchParams.append('fecha_fin', fechaFin);

    window.location.href = url.toString();
}

function exportarPDF() {
    const fechaInicio = $('#filtro-fecha-inicio').val();
    const fechaFin = $('#filtro-fecha-fin').val();

    // Llamar API para descargar PDF
    const url = new URL(window.urls.s_exp_exportar_pdf, window.location.origin);
    url.searchParams.append('fecha_inicio', fechaInicio);
    url.searchParams.append('fecha_fin', fechaFin);

    window.location.href = url.toString();
}
