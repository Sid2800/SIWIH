/**
 * Seguimiento de Solicitudes - s_exp
 * Muestra las solicitudes del usuario con timeline visual y filtros de fecha.
 */

// Estado actual del filtro
let filtroActual = '';
let fechaInicioActual = '';
let fechaFinActual = '';

$(document).ready(function () {
    cargarMisSolicitudes();

    // Manejadores de botones de filtro
    $(document).on('click', '.sexp-filtro-btn[data-filtro]', function () {
        const filtro = $(this).data('filtro');

        // Actualizar botón activo
        $('.sexp-filtro-btn[data-filtro]').removeClass('sexp-filtro-btn--active');
        $(this).addClass('sexp-filtro-btn--active');

        // Mostrar/ocultar panel de rango
        if (filtro === 'rango') {
            $('#rango-fechas').show();
            return; // No cargar aún, esperar que aplique el rango
        } else {
            $('#rango-fechas').hide();
            fechaInicioActual = '';
            fechaFinActual = '';
        }

        filtroActual = filtro;
        cargarMisSolicitudes(filtro);
    });

    // Aplicar rango de fechas personalizado
    $('#btn-aplicar-rango').on('click', function () {
        fechaInicioActual = $('#fecha-inicio').val();
        fechaFinActual = $('#fecha-fin').val();
        filtroActual = 'rango';
        cargarMisSolicitudes('rango', fechaInicioActual, fechaFinActual);
    });
});

/**
 * Carga y renderiza las solicitudes del usuario, opcionalmente filtradas por fecha.
 * @param {string} filtro - 'hoy', 'semana', 'mes', 'rango' o '' para todas.
 * @param {string} fechaInicio - Fecha inicio (YYYY-MM-DD) cuando filtro='rango'.
 * @param {string} fechaFin - Fecha fin (YYYY-MM-DD) cuando filtro='rango'.
 */
function cargarMisSolicitudes(filtro = '', fechaInicio = '', fechaFin = '') {
    const params = {};
    if (filtro) params.filtro = filtro;
    if (fechaInicio) params.fecha_inicio = fechaInicio;
    if (fechaFin) params.fecha_fin = fechaFin;

    $.ajax({
        url: window.urls.s_exp_mis_solicitudes_api,
        method: 'GET',
        data: params,
        success: function (resp) {
            renderSolicitudes(resp.data, filtro);
        },
        error: function () {
            toastr.error("Error al cargar solicitudes");
        }
    });
}

function renderSolicitudes(data, filtro = '') {
    const container = $('#timeline-solicitudes');

    if (!data.length) {
        const msgFiltro = filtro
            ? `No hay solicitudes para el período seleccionado.`
            : `No tiene solicitudes registradas. <a href="${window.urls.s_exp_buscador}" style="color:var(--negro);">Crear una nueva</a>`;
        container.html(`<p style="opacity:0.5; text-align:center;">${msgFiltro}</p>`);
        return;
    }

    let html = '';
    data.forEach(function (s) {
        const claseEstado = s.estado_flujo.toLowerCase();
        const badgeEstilos = {
            'sol_pendiente': 'background:rgba(99,102,241,0.2);color:var(--negro);',
            'sol_aprobada_organizando': 'background:rgba(34,197,94,0.2);color:var(--negro);',
            'sol_rechazada': 'background:rgba(239,68,68,0.2);color:var(--negro);',
            'sol_en_prestamo': 'background:rgba(245,158,11,0.2);color:var(--negro);',
            'sol_finalizada': 'background:rgba(100,116,139,0.2);color:var(--negro);',
            'sol_incompleta': 'background:rgba(249,115,22,0.3);color:var(--negro);border:1px solid #f97316;',
            'sol_listo_recoger': 'background:rgba(16,185,129,0.2);color:var(--negro);',
            'sol_en_devolucion': 'background:rgba(139,92,246,0.2);color:var(--negro);'
        };
        const borderColors = {
            'sol_pendiente': '#6366f1',
            'sol_aprobada_organizando': '#22c55e',
            'sol_rechazada': '#ef4444',
            'sol_en_prestamo': '#f59e0b',
            'sol_finalizada': '#64748b',
            'sol_incompleta': '#f97316',
            'sol_listo_recoger': '#10b981',
            'sol_en_devolucion': '#8b5cf6'
        };

        const exps = s.expedientes.map(e => {
            const claseExtra = e.fuera_de_tiempo ? 'sexp-exp-tag--late' : '';
            const title = e.fuera_de_tiempo ? 'Entregado fuera de tiempo' : '';
            const num = typeof e === 'object' ? e.numero : e;
            return `<span class="sexp-exp-tag ${claseExtra}" title="${title}">#${num}</span>`;
        }).join(' ');
        const badgeEstilo = badgeEstilos[claseEstado] || '';
        const borderColor = borderColors[claseEstado] || '#6366f1';

        html += `
        <div class="sexp-sol-card sexp-card-collapsible sexp-collapsed" style="border-left-color:${borderColor};">
            <div class="sexp-sol-header" onclick="toggleCard(this)">
                <h3><i class="bi bi-file-text"></i> Solicitud #${s.id}</h3>
                <div style="display:flex; align-items:center; gap:0.8rem;">
                    <span class="sexp-sol-badge" style="${badgeEstilo}padding:0.25rem 0.8rem;border-radius:20px;font-size:1.2rem;font-weight:700;">${s.estado_flujo_nombre}</span>
                    <i class="bi bi-chevron-down sexp-card-toggle"></i>
                </div>
            </div>
            <div class="sexp-card-body">
                <div class="sexp-sol-info">
                    <div><label>Fecha</label>${s.fecha_creacion}</div>
                    <div><label>Motivo</label>${s.motivo}</div>
                    <div><label>Área</label>${s.area_destino || '-'}</div>
                    <div><label>Expedientes</label>${s.cant_expedientes}</div>
                </div>
                <div class="sexp-sol-exps">${exps}</div>`;

        // Info del préstamo si existe
        if (s.prestamo) {
            const p = s.prestamo;
            if (p.motivo_rechazo) {
                html += `<div class="sexp-sol-rechazo"><i class="bi bi-x-circle" style="color:var(--negro);"></i> <strong>Motivo de rechazo:</strong> ${p.motivo_rechazo}</div>`;
            }
            if (p.estado === 'Entregado' || p.estado === 'Vencido' || p.estado === 'DevolucionParcial') {
                // Timer
                if (p.tiempo_restante_segundos !== null) {
                    const timerClass = p.esta_vencido ? 'color:var(--negro);' : (p.porcentaje_tiempo_usado >= 90 ? 'color:var(--negro);' : 'color:var(--negro);');
                    let timerText = '';
                    if (p.esta_vencido) {
                        timerText = 'VENCIDO';
                    } else {
                        const h = Math.floor(p.tiempo_restante_segundos / 3600);
                        const m = Math.floor((p.tiempo_restante_segundos % 3600) / 60);
                        timerText = `${h}h ${m}m restantes`;
                    }
                    html += `<div class="sexp-sol-timer" style="${timerClass}"><i class="bi bi-clock"></i> ${timerText}</div>`;
                }

                // Botón devolver (solo en préstamo normal; no mostrar si ya está en devolución
                // o si la solicitud está incompleta, en ese caso solo aplica "Entregar Faltantes")
                const esIncompleta = s.estado_flujo === 'SOL_INCOMPLETA' || p.estado === 'DevolucionParcial';
                if (s.estado_flujo !== 'SOL_EN_DEVOLUCION' && !esIncompleta) {
                    html += `<button class="sexp-devolver-btn" onclick="solicitarDevolucion(${s.id})">
                        <i class="bi bi-arrow-return-left"></i> Solicitar Devolución
                    </button>`;
                } else if (s.estado_flujo === 'SOL_EN_DEVOLUCION') {
                    html += `<div style="margin-top:0.5rem;font-size:1.2rem;opacity:0.7;"><i class="bi bi-hourglass-split"></i> Devolución en proceso de revisión por el administrador.</div>`;
                }
            }
            // Solicitud incompleta: hay expedientes sin devolver
            if (s.estado_flujo === 'SOL_INCOMPLETA') {
                html += `<div style="margin-top:0.8rem;padding:0.6rem 1rem;background:rgba(249,115,22,0.1);border-left:3px solid #f97316;border-radius:4px;font-size:1.3rem;">
                    <i class="bi bi-exclamation-triangle" style="color:#f97316;"></i>
                    <strong>Devolución incompleta</strong>: Aún hay expedientes sin entregar. Pregüntele al administrador o entregue los faltantes.
                </div>`;
                if (s.prestamo && s.prestamo.estado === 'DevolucionParcial') {
                    html += `<button class="sexp-devolver-btn sexp-entregar-faltantes-btn" onclick="solicitarDevolucion(${s.id})">
                        <i class="bi bi-arrow-return-left"></i> Entregar Faltantes
                    </button>`;
                }
            }
            if (p.comentarios) {
                html += `<div style="margin-top:0.5rem;font-size:1.3rem;opacity:0.7;"><i class="bi bi-chat-text"></i> ${p.comentarios}</div>`;
            }
        }

        html += `</div></div>`;
    });

    container.html(html);
}

function solicitarDevolucion(solicitudId) {
    Swal.fire({
        title: 'Solicitar Devolución',
        text: '¿Desea iniciar el proceso de devolución? Entregue los expedientes físicos al administrador para su revisión.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, Devolver',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#f59e0b'
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_solicitar_devolucion_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({ solicitud_id: solicitudId }),
                success: function (resp) {
                    if (resp.success) {
                        toastr.success('Solicitud de devolución enviada. Por favor, entregue los expedientes.');
                        cargarMisSolicitudes();
                    }
                },
                error: function (xhr) {
                    const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                    toastr.error(err);
                }
            });
        }
    });
}

/**
 * Alterna el estado colapsado/expandido de una tarjeta en móviles.
 * @param {HTMLElement} headerEl - El elemento header que recibió el click.
 */
function toggleCard(headerEl) {
    if (window.innerWidth <= 768) {
        const card = $(headerEl).closest('.sexp-card-collapsible');
        card.toggleClass('sexp-collapsed');
    }
}
