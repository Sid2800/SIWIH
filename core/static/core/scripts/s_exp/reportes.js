/**
 * Reportes - s_exp
 * Reporte unificado con KPIs, rankings, incidencias y exportación a Excel/PDF.
 */
let reporteData = null; // Cache global de los últimos datos cargados
let _recargaTimer = null; // debounce de la recarga automática

$(document).ready(function () {
    initTabs();
    initFiltros();
    $('#btn-exportar-excel').on('click', exportarExcel);
    $('#btn-exportar-pdf').on('click', exportarPDF);

    // ===== Banner de novedades (no recarga sólo, sino ofrece al usuario) =====
    if (window.RealtimeSExp) {
        RealtimeSExp.registrarConTrigger('reportes', 'global', function () {
            generarReportes();
        }, 15, { etiqueta: 'eventos' });
    }
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

/* =============================================================================
 * FILTROS REACTIVOS
 * -----------------------------------------------------------------------------
 * El reporte se actualiza solo al cambiar cualquier filtro (no hay botón
 * "Generar"). El rango calcula las fechas y las pone en el calendario; si el
 * usuario toca el calendario, el rango pasa a "Personalizado". El año, el
 * trimestre y el semestre NO cambian a personalizado: solo recalculan las
 * fechas para el período elegido.
 * =========================================================================== */

// Bandera para distinguir un cambio de fecha hecho por el código (al aplicar un
// rango) de uno hecho por el usuario en el calendario. Solo el del usuario debe
// pasar el rango a "Personalizado".
let _aplicandoRango = false;

function initFiltros() {
    _poblarAnios();

    // Valores por defecto: año, trimestre y semestre actuales.
    const hoy = new Date();
    $('#filtro-anio').val(hoy.getFullYear());
    $('#filtro-trimestre').val(Math.floor(hoy.getMonth() / 3) + 1);
    $('#filtro-semestre').val(hoy.getMonth() < 6 ? 1 : 2);

    // Cambiar el rango: muestra/oculta sub-selectores y recalcula fechas.
    $('#filtro-rango').on('change', function () {
        _actualizarSubfiltros();
        _aplicarRangoYActualizar();
    });

    // Año / trimestre / semestre: recalculan sin salir del rango elegido.
    $('#filtro-anio, #filtro-trimestre, #filtro-semestre').on('change', _aplicarRangoYActualizar);

    // Calendario tocado por el usuario -> rango "Personalizado".
    $('#filtro-fecha-inicio, #filtro-fecha-fin').on('change', function () {
        if (_aplicandoRango) return; // fue el código, no el usuario
        $('#filtro-rango').val('');
        _actualizarSubfiltros();
        _actualizarBotonesExport();
        _recargarConDebounce();
    });

    // Carga inicial: mes actual, automático.
    _actualizarSubfiltros();
    _aplicarRangoYActualizar();
}

/** Llena el selector de año con el año actual y los 4 anteriores. */
function _poblarAnios() {
    const actual = new Date().getFullYear();
    let html = '';
    for (let a = actual; a >= actual - 4; a--) {
        html += `<option value="${a}">${a}</option>`;
    }
    $('#filtro-anio').html(html);
}

/** Muestra los sub-selectores solo cuando el rango los necesita. */
function _actualizarSubfiltros() {
    const rango = $('#filtro-rango').val();
    $('#grupo-anio').toggle(['trimestral', 'semestral', 'anual'].includes(rango));
    $('#grupo-trimestre').toggle(rango === 'trimestral');
    $('#grupo-semestre').toggle(rango === 'semestral');
}

/** Calcula {inicio, fin} del rango elegido, o null si es "Personalizado". */
function _calcularFechas() {
    const rango = $('#filtro-rango').val();
    if (!rango) return null; // personalizado: respeta lo que puso el usuario

    const hoy = new Date();
    const anio = parseInt($('#filtro-anio').val(), 10) || hoy.getFullYear();
    let inicio, fin;

    switch (rango) {
        case 'diario':
            inicio = new Date(hoy); fin = new Date(hoy);
            break;
        case 'semanal':
            inicio = new Date(hoy); inicio.setDate(hoy.getDate() - hoy.getDay());
            fin = new Date(hoy);
            break;
        case 'mensual':
            inicio = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
            fin = new Date(hoy);
            break;
        case 'trimestral': {
            // Los trimestres/semestres/años usan el período COMPLETO (no hasta
            // hoy), para poder revisar uno pasado de principio a fin.
            const q = parseInt($('#filtro-trimestre').val(), 10) || 1;
            inicio = new Date(anio, (q - 1) * 3, 1);
            fin = new Date(anio, (q - 1) * 3 + 3, 0); // último día del trimestre
            break;
        }
        case 'semestral': {
            const s = parseInt($('#filtro-semestre').val(), 10) || 1;
            inicio = new Date(anio, (s - 1) * 6, 1);
            fin = new Date(anio, (s - 1) * 6 + 6, 0);
            break;
        }
        case 'anual':
            inicio = new Date(anio, 0, 1);
            fin = new Date(anio, 11, 31);
            break;
    }
    return { inicio: formatDate(inicio), fin: formatDate(fin) };
}

/** Aplica el rango al calendario (si no es personalizado) y recarga. */
function _aplicarRangoYActualizar() {
    const f = _calcularFechas();
    if (f) {
        _aplicandoRango = true;              // este cambio de fecha es del código
        $('#filtro-fecha-inicio').val(f.inicio);
        $('#filtro-fecha-fin').val(f.fin);
        _aplicandoRango = false;
    }
    _actualizarBotonesExport();
    _recargarConDebounce();
}

/** Los botones de exportar solo se habilitan con ambas fechas puestas. */
function _actualizarBotonesExport() {
    const listo = !!$('#filtro-fecha-inicio').val() && !!$('#filtro-fecha-fin').val();
    $('#btn-exportar-excel, #btn-exportar-pdf').prop('disabled', !listo);
}

/** Evita recargar varias veces seguidas si se cambian varios filtros rápido. */
function _recargarConDebounce() {
    clearTimeout(_recargaTimer);
    _recargaTimer = setTimeout(generarReportes, 300);
}

/** Fecha local a 'YYYY-MM-DD' (sin pasar por UTC, que corría el día). */
function formatDate(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function generarReportes() {
    const fechaInicio = $('#filtro-fecha-inicio').val();
    const fechaFin = $('#filtro-fecha-fin').val();
    // Sin fechas no hay nada que consultar (p. ej. personalizado a medio llenar).
    if (!fechaInicio || !fechaFin) return;

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
        html += `<tr><td>${a.area_destino || 'Sin especificar'}</td><td><strong>${a.total}</strong></td><td><strong>${a.expedientes}</strong></td></tr>`;
    });
    $('#tbody-areas').html(html || '<tr><td colspan="3" style="opacity:0.5;">Sin datos</td></tr>');
}

function renderMotivos(data) {
    let html = '';
    (data || []).forEach(function (m) {
        html += `<tr><td>${m.nombre || 'Sin especificar'}</td><td><strong>${m.total}</strong></td><td><strong>${m.expedientes}</strong></td></tr>`;
    });
    $('#tbody-motivos').html(html || '<tr><td colspan="3" style="opacity:0.5;">Sin datos</td></tr>');
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

/**
 * Arma la URL de descarga (Excel o PDF) con el rango de fechas y el TIPO de
 * reporte elegido en el combobox. Ambas exportaciones comparten los mismos
 * parámetros; solo cambia el endpoint.
 */
function _urlExportacion(urlBase) {
    const url = new URL(urlBase, window.location.origin);
    url.searchParams.append('fecha_inicio', $('#filtro-fecha-inicio').val());
    url.searchParams.append('fecha_fin', $('#filtro-fecha-fin').val());
    // tipo: 'solicitudes' (por defecto) o 'expedientes'.
    url.searchParams.append('tipo', $('#filtro-tipo-reporte').val() || 'solicitudes');
    return url.toString();
}

function exportarExcel() {
    window.location.href = _urlExportacion(window.urls.s_exp_exportar_excel);
}

function exportarPDF() {
    window.location.href = _urlExportacion(window.urls.s_exp_exportar_pdf);
}
