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
    if (!reporteData) { toastr.warning('Primero genere el reporte'); return; }

    const d = reporteData;
    const r = d.resumen;
    const periodo = getRangoTexto();

    // Construir una tabla HTML temporal para exportar con DataTables buttons
    let html = `<table id="tabla-export-temp">
        <thead><tr><th colspan="4" style="font-size:18px;font-weight:bold;">Reporte de Préstamo de Expedientes</th></tr>
        <tr><th colspan="4">${periodo}</th></tr>
        <tr><th colspan="4"></th></tr>
        <tr><th colspan="4" style="font-weight:bold;">RESUMEN GENERAL</th></tr>
        <tr><th>Indicador</th><th>Cantidad</th><th></th><th></th></tr></thead><tbody>
        <tr><td>Total Solicitudes</td><td>${r.total_solicitudes}</td><td></td><td></td></tr>
        <tr><td>Expedientes Solicitados</td><td>${r.total_expedientes}</td><td></td><td></td></tr>
        <tr><td>Aprobadas</td><td>${r.aprobadas}</td><td></td><td></td></tr>
        <tr><td>Rechazadas</td><td>${r.rechazadas}</td><td></td><td></td></tr>
        <tr><td>Pendientes</td><td>${r.pendientes}</td><td></td><td></td></tr>
        <tr><td></td><td></td><td></td><td></td></tr>
        <tr><td style="font-weight:bold;">DEMANDA POR ÁREA</td><td></td><td></td><td></td></tr>
        <tr><td>Área</td><td>Solicitudes</td><td></td><td></td></tr>`;
    (d.demanda_area || []).forEach(a => {
        html += `<tr><td>${a.area_destino || 'Sin especificar'}</td><td>${a.total}</td><td></td><td></td></tr>`;
    });
    html += `<tr><td></td><td></td><td></td><td></td></tr>
        <tr><td style="font-weight:bold;">MOTIVOS DE USO</td><td></td><td></td><td></td></tr>
        <tr><td>Motivo</td><td>Cantidad</td><td></td><td></td></tr>`;
    (d.motivos || []).forEach(m => {
        html += `<tr><td>${m.nombre || 'Sin especificar'}</td><td>${m.total}</td><td></td><td></td></tr>`;
    });
    html += `<tr><td></td><td></td><td></td><td></td></tr>
        <tr><td style="font-weight:bold;">EXPEDIENTES MÁS SOLICITADOS</td><td></td><td></td><td></td></tr>
        <tr><td># Expediente</td><td>Veces</td><td></td><td></td></tr>`;
    (d.expedientes_top || []).forEach(e => {
        html += `<tr><td>#${e.numero}</td><td>${e.total}</td><td></td><td></td></tr>`;
    });
    html += `<tr><td></td><td></td><td></td><td></td></tr>
        <tr><td style="font-weight:bold;">USUARIOS CON MÁS SOLICITUDES</td><td></td><td></td><td></td></tr>
        <tr><td>Usuario</td><td>Solicitudes</td><td></td><td></td></tr>`;
    (d.usuarios_top || []).forEach(u => {
        html += `<tr><td>${u.nombre} (${u.username})</td><td>${u.total}</td><td></td><td></td></tr>`;
    });
    html += `<tr><td></td><td></td><td></td><td></td></tr>
        <tr><td style="font-weight:bold;">RECHAZOS</td><td></td><td></td><td></td></tr>
        <tr><td>Solicitud</td><td>Usuario</td><td>Fecha</td><td>Motivo</td></tr>`;
    (d.rechazos || []).forEach(r => {
        html += `<tr><td>#${r.solicitud_id}</td><td>${r.usuario}</td><td>${r.fecha}</td><td>${r.motivo_rechazo || '-'}</td></tr>`;
    });
    html += `</tbody></table>`;

    // Insertar tabla temporal, exportar y limpiar
    const $temp = $(html).appendTo('body').hide();
    const dt = $temp.DataTable({
        dom: 'Bfrtip',
        buttons: [{
            extend: 'excelHtml5',
            title: 'Reporte Préstamo de Expedientes',
            filename: 'reporte_expedientes_' + formatDate(new Date()),
        }]
    });
    dt.button(0).trigger();
    setTimeout(() => { dt.destroy(); $temp.remove(); }, 1000);
}

function exportarPDF() {
    if (!reporteData) { toastr.warning('Primero genere el reporte'); return; }

    const d = reporteData;
    const r = d.resumen;
    const periodo = getRangoTexto();

    // Construir contenido HTML para impresión (tamaño carta)
    let contenido = `
    <style>
        @page { size: letter; margin: 1.5cm; }
        body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
        h1 { font-size: 16pt; text-align: center; margin-bottom: 5px; }
        h2 { font-size: 13pt; margin: 18px 0 8px; border-bottom: 2px solid #6366f1; padding-bottom: 4px; }
        .periodo { text-align: center; font-size: 10pt; color: #666; margin-bottom: 20px; }
        .kpi-row { display: flex; gap: 15px; margin-bottom: 20px; }
        .kpi-box { flex:1; text-align:center; border:1px solid #ddd; border-radius:8px; padding:12px; }
        .kpi-box .valor { font-size: 22pt; font-weight: 800; color: #6366f1; }
        .kpi-box .label { font-size: 9pt; text-transform: uppercase; color: #666; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 10pt; }
        th { background: #f1f5f9; text-align: left; padding: 8px; border-bottom: 2px solid #e2e8f0; }
        td { padding: 8px; border-bottom: 1px solid #e2e8f0; }
    </style>
    <h1>Reporte de Préstamo de Expedientes</h1>
    <div class="periodo">${periodo}</div>

    <div class="kpi-row">
        <div class="kpi-box"><div class="valor">${r.total_solicitudes}</div><div class="label">Solicitudes</div></div>
        <div class="kpi-box"><div class="valor">${r.total_expedientes}</div><div class="label">Expedientes</div></div>
        <div class="kpi-box"><div class="valor" style="color:#22c55e;">${r.aprobadas}</div><div class="label">Aprobadas</div></div>
        <div class="kpi-box"><div class="valor" style="color:#ef4444;">${r.rechazadas}</div><div class="label">Rechazadas</div></div>
        <div class="kpi-box"><div class="valor" style="color:#8b5cf6;">${r.pendientes}</div><div class="label">Pendientes</div></div>
    </div>

    <h2>Demanda por Área</h2>
    <table><tr><th>Área</th><th>Solicitudes</th></tr>`;
    (d.demanda_area || []).forEach(a => {
        contenido += `<tr><td>${a.area_destino || 'Sin especificar'}</td><td>${a.total}</td></tr>`;
    });
    contenido += `</table>

    <h2>Motivos de Uso</h2>
    <table><tr><th>Motivo</th><th>Cantidad</th></tr>`;
    (d.motivos || []).forEach(m => {
        contenido += `<tr><td>${m.nombre || 'Sin especificar'}</td><td>${m.total}</td></tr>`;
    });
    contenido += `</table>

    <h2>Expedientes Más Solicitados</h2>
    <table><tr><th># Expediente</th><th>Veces Solicitado</th></tr>`;
    (d.expedientes_top || []).forEach(e => {
        contenido += `<tr><td>#${e.numero}</td><td>${e.total}</td></tr>`;
    });
    contenido += `</table>

    <h2>Usuarios con Más Solicitudes</h2>
    <table><tr><th>Usuario</th><th>Solicitudes</th></tr>`;
    (d.usuarios_top || []).forEach(u => {
        contenido += `<tr><td>${u.nombre} (${u.username})</td><td>${u.total}</td></tr>`;
    });
    contenido += `</table>

    <h2>Rechazos</h2>
    <table><tr><th>Solicitud</th><th>Usuario</th><th>Fecha</th><th>Motivo</th></tr>`;
    (d.rechazos || []).forEach(r => {
        contenido += `<tr><td>#${r.solicitud_id}</td><td>${r.usuario}</td><td>${r.fecha}</td><td>${r.motivo_rechazo || '-'}</td></tr>`;
    });
    contenido += `</table>`;

    // Abrir ventana de impresión
    const ventana = window.open('', '_blank', 'width=800,height=600');
    ventana.document.write(`<!DOCTYPE html><html><head><title>Reporte Expedientes</title></head><body>${contenido}</body></html>`);
    ventana.document.close();
    ventana.focus();
    setTimeout(() => { ventana.print(); }, 500);
}
