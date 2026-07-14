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

    // ===== Auto-refresh AUTOMÁTICO (sin banner) =====
    // Para los usuarios solicitantes, la tabla se actualiza sola cuando un
    // admin hace algo con SUS solicitudes (aprobar, marcar listo, entregar,
    // procesar devolución). Sección 'mis_solicitudes' es específica para esto.
    if (window.RealtimeSExp) {
        RealtimeSExp.registrarConAutoReload('mis-solicitudes', 'mis_solicitudes', function () {
            cargarMisSolicitudes(filtroActual, fechaInicioActual, fechaFinActual, true);
        }, 5);
    }

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
function cargarMisSolicitudes(filtro = '', fechaInicio = '', fechaFin = '', esPolling = false) {
    const params = {};
    if (filtro) params.filtro = filtro;
    if (fechaInicio) params.fecha_inicio = fechaInicio;
    if (fechaFin) params.fecha_fin = fechaFin;

    const headers = {};
    if (esPolling) headers['X-Polling-Request'] = 'true';

    $.ajax({
        url: window.urls.s_exp_mis_solicitudes_api,
        method: 'GET',
        data: params,
        headers: headers,
        success: function (resp) {
            renderSolicitudes(resp.data, filtro);
        },
        error: function () {
            // Solo notificar en cargas iniciales, no en polling silencioso
            if (!esPolling) toastr.error("Error al cargar solicitudes");
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
    // Guardamos las solicitudes por id para que el modal de "Devolución parcial"
    // pueda leer sus expedientes sin volver a consultar al servidor.
    window.__sexpMisSolic = {};
    data.forEach(function (s) {
        window.__sexpMisSolic[s.id] = s;
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

        const sanitize = (txt) => (txt || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        // Estados en los que ya hay un préstamo activo y aplica el AMARILLO de "pendiente"
        const enPrestamo = ['SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA'].includes(s.estado_flujo);
        const exps = s.expedientes.map(e => {
            const num = typeof e === 'object' ? e.numero : e;
            if (typeof e !== 'object') {
                return `<span class="sexp-exp-tag" onclick="mostrarInfoExpediente(${JSON.stringify({numero: num, estado: 'normal'}).replace(/"/g,'&quot;')})">#${num}</span>`;
            }
            // Construir objeto info para el popup
            let estadoTag = 'normal';
            if (e.aprobado === false) estadoTag = 'rechazado';
            else if (enPrestamo && e.devuelto === false) estadoTag = 'pendiente';
            else if (e.fuera_de_tiempo) estadoTag = 'late';
            else if (e.devuelto) estadoTag = 'devuelto';

            const info = {
                numero: num,
                estado: estadoTag,
                aprobado: e.aprobado,
                devuelto: e.devuelto,
                motivo_rechazo: e.motivo_rechazo_individual || '',
                comentario_devolucion: e.comentario_devolucion || '',
                paciente_nombre: e.paciente_nombre || '',
                paciente_identidad: e.paciente_identidad || '',
                fuera_de_tiempo: !!e.fuera_de_tiempo
            };
            const infoAttr = sanitize(JSON.stringify(info));
            const onClick = `onclick="mostrarInfoExpediente(JSON.parse(this.getAttribute('data-info')))"`;
            const dataAttr = `data-info="${infoAttr}"`;

            // ROJO: no se prestó (rechazado / no encontrado)
            if (e.aprobado === false) {
                const motivo = e.motivo_rechazo_individual || 'No se prestó este expediente';
                return `<span class="sexp-exp-tag sexp-exp-tag--rechazado" title="${sanitize(motivo)}" ${dataAttr} ${onClick}>#${num}</span>`;
            }
            // AMARILLO: en préstamo activo y aún no devuelto
            if (enPrestamo && e.devuelto === false) {
                return `<span class="sexp-exp-tag sexp-exp-tag--pendiente" title="Pendiente de devolver" ${dataAttr} ${onClick}>#${num}</span>`;
            }
            // ESTANDAR (con fuera de tiempo si aplica)
            if (e.fuera_de_tiempo) {
                return `<span class="sexp-exp-tag sexp-exp-tag--late" title="Entregado fuera de tiempo${e.comentario_devolucion ? ' — ' + sanitize(e.comentario_devolucion) : ''}" ${dataAttr} ${onClick}>#${num}</span>`;
            }
            const tooltip = e.devuelto ? (e.comentario_devolucion ? sanitize(e.comentario_devolucion) : 'Devuelto correctamente') : '';
            return `<span class="sexp-exp-tag" title="${tooltip}" ${dataAttr} ${onClick}>#${num}</span>`;
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

                // Botones de devolución (solo en préstamo normal; no mostrar si ya
                // está en devolución o si la solicitud está incompleta, ahí aplica
                // el bloque de "Faltantes" más abajo).
                const esIncompleta = s.estado_flujo === 'SOL_INCOMPLETA' || p.estado === 'DevolucionParcial';
                if (s.estado_flujo !== 'SOL_EN_DEVOLUCION' && !esIncompleta) {
                    html += botonesDevolucion(s.id);
                } else if (s.estado_flujo === 'SOL_EN_DEVOLUCION') {
                    html += `<div style="margin-top:0.6rem;font-size:1.5rem;opacity:0.85;display:flex;align-items:center;gap:0.5rem;"><i class="bi bi-hourglass-split" style="font-size:1.6rem;"></i><span>Devolución en proceso de revisión por el administrador.</span></div>`;
                }
            }
            // Solicitud incompleta: hay expedientes sin devolver
            if (s.estado_flujo === 'SOL_INCOMPLETA') {
                html += `<div style="margin-top:0.8rem;padding:0.6rem 1rem;background:rgba(249,115,22,0.1);border-left:3px solid #f97316;border-radius:4px;font-size:1.3rem;">
                    <i class="bi bi-exclamation-triangle" style="color:#f97316;"></i>
                    <strong>Devolución incompleta</strong>: Aún hay expedientes sin entregar. Pregüntele al administrador o entregue los faltantes.
                </div>`;
                if (s.prestamo && s.prestamo.estado === 'DevolucionParcial') {
                    html += botonesDevolucion(s.id);
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

// customClass reutilizable para los modales de devolución (estilo del sistema).
const _SEXP_DEV_MODAL_CLASS = {
    icon: 'contenedor-modal-icon',
    popup: 'contenedor-modal',
    title: 'contener-modal-titulo',
    confirmButton: 'contener-modal-boton-confirmar',
    cancelButton: 'contener-modal-boton-cancelar',
};

function _sexpDevModalDidOpen() {
    const actionsContainer = document.querySelector('.swal2-actions');
    if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones-min');
    const htmlContainer = document.querySelector('.swal2-html-container');
    if (htmlContainer) htmlContainer.classList.add('contener-modal-contenedor-html');
}

/**
 * ¿Está permitido el horario de "devolución fuera de horario"?
 * Regla: habilitado de 4:00 pm (16:00) hasta 7:00 am (07:00).
 * Se evalúa con la hora local del navegador (el proceso backend queda pendiente).
 */
function _devolucionFueraHorarioPermitida() {
    const h = new Date().getHours();
    return (h >= 16 || h < 7);
}

/**
 * HTML de los 3 botones de devolución del usuario. Se usa tanto en préstamo
 * normal como al entregar faltantes de una solicitud incompleta.
 */
function botonesDevolucion(solicitudId) {
    const fueraOK = _devolucionFueraHorarioPermitida();
    const disF = fueraOK ? '' : 'disabled';
    const titF = fueraOK
        ? 'Devolución fuera de horario (proceso en construcción)'
        : 'Disponible solo de 4:00 pm a 7:00 am';
    return `
        <div class="sexp-devolucion-botones">
            <button class="sexp-devolver-btn sexp-devolver-btn--completa" onclick="devolucionCompleta(${solicitudId})">
                <i class="bi bi-arrow-return-left"></i> Devolución completa
            </button>
            <button class="sexp-devolver-btn sexp-devolver-btn--parcial" onclick="devolucionParcial(${solicitudId})">
                <i class="bi bi-list-check"></i> Devolución parcial
            </button>
            <button class="sexp-devolver-btn sexp-devolver-btn--fuera" onclick="devolucionFueraHorario(${solicitudId})" ${disF} title="${titF}">
                <i class="bi bi-moon-stars"></i> Devolución fuera de horario
            </button>
        </div>`;
}

/** Envía la devolución al backend (completa o parcial) y refresca la lista. */
function _enviarDevolucion(solicitudId, tipo, decisiones) {
    $.ajax({
        url: window.urls.s_exp_solicitar_devolucion_api,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({ solicitud_id: solicitudId, tipo: tipo, decisiones: decisiones || [] }),
        success: function (resp) {
            if (resp.success) {
                toastr.success('Devolución enviada. Entregue los expedientes al administrador para su revisión.');
                cargarMisSolicitudes();
            } else {
                toastr.error(resp.error || 'No se pudo procesar la devolución.');
            }
        },
        error: function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
            toastr.error(err);
        }
    });
}

/** Devolución completa: se devuelven TODOS los expedientes. */
function devolucionCompleta(solicitudId) {
    Swal.fire({
        title: 'Devolución completa',
        html: '¿Desea devolver <strong>todos</strong> los expedientes? Entréguelos al administrador para su revisión.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, devolver todos',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: _SEXP_DEV_MODAL_CLASS,
        didOpen: _sexpDevModalDidOpen
    }).then((result) => {
        if (result.isConfirmed) _enviarDevolucion(solicitudId, 'completa', []);
    });
}

/**
 * Devolución parcial: abre un modal con los expedientes pendientes. Todos
 * arrancan como "No devolver" con el comentario "Todavía en uso" (editable);
 * el usuario marca "Devolver" los que sí entregará.
 */
function devolucionParcial(solicitudId) {
    const s = (window.__sexpMisSolic || {})[solicitudId];
    if (!s) { toastr.error('No se pudieron cargar los expedientes de la solicitud.'); return; }

    const exps = (s.expedientes || []).filter(e => e.aprobado && !e.devuelto);
    if (!exps.length) { toastr.info('No hay expedientes pendientes por devolver.'); return; }

    const cards = exps.map(e => {
        const ident = e.paciente_identidad || 'S/ID';
        const nom = e.paciente_nombre || 'N/A';
        // Texto para el buscador local (identidad, número y nombre).
        const buscar = `${ident} ${e.numero} ${nom}`.toLowerCase().replace(/"/g, '&quot;');
        // Arranca en "No devolver" -> tarjeta amarilla.
        return `
            <div class="sexp-devparcial-card sexp-devparcial-card--no" id="devp-card-${e.detalle_id}" data-buscar="${buscar}">
                <div class="sexp-devparcial-head">
                    <span class="sexp-exp-tag">#${e.numero}</span>
                    <div class="sexp-devparcial-pac">
                        <span class="sexp-devparcial-id">${ident}</span>
                        <span class="sexp-devparcial-nom">${nom}</span>
                    </div>
                </div>
                <div class="sexp-devparcial-radios">
                    <label class="sexp-devparcial-radio sexp-devparcial-radio--ok">
                        <input type="radio" name="dev_${e.detalle_id}" value="devolver" data-detalle="${e.detalle_id}">
                        <i class="bi bi-arrow-return-left"></i> Devolver
                    </label>
                    <label class="sexp-devparcial-radio sexp-devparcial-radio--no">
                        <input type="radio" name="dev_${e.detalle_id}" value="no_devolver" data-detalle="${e.detalle_id}" checked>
                        <i class="bi bi-hourglass-split"></i> No devolver
                    </label>
                </div>
                <input type="text" class="sexp-modal-input sexp-devparcial-coment" data-detalle="${e.detalle_id}"
                       maxlength="200" value="Todavía en uso"
                       placeholder="Comentario (irá al PDF si no se devuelve)">
            </div>`;
    }).join('');

    Swal.fire({
        title: 'Devolución parcial',
        width: '90%',
        html: `
            <div class="sexp-devparcial-wrap">
                <p class="sexp-auditoria-help">
                    <i class="bi bi-info-circle"></i>
                    Marque cuáles va a <strong>devolver</strong>. Los que siga usando quedan como
                    "No devolver" con su comentario (por defecto "Todavía en uso").
                </p>
                <div class="sexp-modal-buscador-row">
                    <div class="sexp-modal-buscador-input">
                        <i class="bi bi-search"></i>
                        <input type="search" id="sexp-devp-buscar" class="sexp-modal-input"
                               placeholder="Filtrar por identidad, nombre o número de expediente..."
                               autocomplete="off">
                        <button type="button" class="sexp-modal-buscador-clear" id="sexp-devp-buscar-clear"
                                title="Limpiar filtro" aria-label="Limpiar filtro">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                    <span class="sexp-modal-buscador-info" id="sexp-devp-buscar-info"></span>
                </div>
                <div class="sexp-devparcial-grid">${cards}</div>
            </div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Devolver expedientes',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contenedor-modal sexp-modal-grande',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones');

            // Color de la tarjeta + comentario según Devolver / No devolver:
            //  - Devolver    -> quita el amarillo y BORRA el comentario (queda en blanco).
            //  - No devolver -> amarillo y comentario editable (default si está vacío).
            document.querySelectorAll('.sexp-devparcial-card input[type="radio"]').forEach(rad => {
                rad.addEventListener('change', function () {
                    const card = document.getElementById('devp-card-' + this.dataset.detalle);
                    if (!card) return;
                    const coment = card.querySelector('.sexp-devparcial-coment');
                    if (this.value === 'devolver') {
                        card.classList.remove('sexp-devparcial-card--no');
                        card.classList.add('sexp-devparcial-card--ok');
                        if (coment) { coment.value = ''; coment.disabled = true; }
                    } else {
                        card.classList.remove('sexp-devparcial-card--ok');
                        card.classList.add('sexp-devparcial-card--no');
                        if (coment) {
                            coment.disabled = false;
                            if (!coment.value.trim()) coment.value = 'Todavía en uso';
                        }
                    }
                });
            });

            // Buscador local — solo filtra las tarjetas de esta ventana.
            const inp = document.getElementById('sexp-devp-buscar');
            const btnClear = document.getElementById('sexp-devp-buscar-clear');
            const info = document.getElementById('sexp-devp-buscar-info');
            const cardsEl = document.querySelectorAll('.sexp-devparcial-card');
            function filtrar() {
                const q = (inp.value || '').trim().toLowerCase();
                let vis = 0;
                cardsEl.forEach(card => {
                    const match = !q || (card.dataset.buscar || '').indexOf(q) >= 0;
                    card.style.display = match ? '' : 'none';
                    if (match) vis++;
                });
                if (info) info.textContent = q ? `${vis} de ${cardsEl.length} expediente(s)` : `${cardsEl.length} expediente(s)`;
                if (btnClear) btnClear.style.display = q ? '' : 'none';
            }
            inp.addEventListener('input', filtrar);
            btnClear.addEventListener('click', function () { inp.value = ''; filtrar(); inp.focus(); });
            filtrar();
        },
        preConfirm: () => {
            // Recorre TODAS las tarjetas (incluidas las ocultas por el filtro).
            const decisiones = [];
            document.querySelectorAll('.sexp-devparcial-card').forEach(card => {
                const did = parseInt(card.id.replace('devp-card-', ''), 10);
                const sel = card.querySelector('input[type="radio"]:checked');
                const devolver = !!sel && sel.value === 'devolver';
                const coment = (card.querySelector('.sexp-devparcial-coment').value || '').trim();
                decisiones.push({ detalle_id: did, devolver: devolver, comentario: devolver ? '' : coment });
            });
            return decisiones;
        }
    }).then((result) => {
        if (result.isConfirmed) _enviarDevolucion(solicitudId, 'parcial', result.value);
    });
}

/**
 * Devolución fuera de horario (4pm–7am). El proceso backend queda PENDIENTE:
 * por ahora el botón solo se habilita en el horario y muestra un aviso.
 */
function devolucionFueraHorario(solicitudId) {
    if (!_devolucionFueraHorarioPermitida()) {
        toastr.warning('La devolución fuera de horario solo está disponible de 4:00 pm a 7:00 am.');
        return;
    }
    Swal.fire({
        title: 'Devolución fuera de horario',
        html: 'Este proceso está <strong>en construcción</strong> y estará disponible próximamente.',
        icon: 'info',
        confirmButtonText: 'Entendido',
        customClass: _SEXP_DEV_MODAL_CLASS,
        didOpen: _sexpDevModalDidOpen
    });
}

/**
 * Alterna el estado colapsado/expandido de una tarjeta en móviles.
 * @param {HTMLElement} headerEl - El elemento header que recibió el click.
 */
function toggleCard(headerEl) {
    // Colapso disponible en todos los tamaños de pantalla
    const card = $(headerEl).closest('.sexp-card-collapsible');
    card.toggleClass('sexp-collapsed');
}

/**
 * Muestra un popup con la información del expediente al tocar/clickear el tag.
 * Útil en móvil/tablet donde el tooltip nativo no aparece sin mouse.
 * @param {Object} info - Datos del expediente y su estado.
 */
function mostrarInfoExpediente(info) {
    if (!info) return;
    info = info || {};
    const num = info.numero || '—';
    const estado = info.estado || 'normal';

    const labelEstado = {
        'rechazado': '<span class="sexp-exp-info-estado--rec"><i class="bi bi-x-circle-fill"></i> No prestado</span>',
        'pendiente': '<span class="sexp-exp-info-estado--pend"><i class="bi bi-hourglass-split"></i> Pendiente de devolver</span>',
        'late': '<span class="sexp-exp-info-estado--late"><i class="bi bi-exclamation-triangle-fill"></i> Devuelto fuera de tiempo</span>',
        'devuelto': '<span class="sexp-exp-info-estado--ok"><i class="bi bi-check-circle-fill"></i> Devuelto correctamente</span>',
        'normal': '<span class="sexp-exp-info-estado--ok"><i class="bi bi-circle-fill"></i> En proceso</span>'
    };

    let filas = `
        <div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Expediente:</span>
            <span class="sexp-exp-info-valor"><strong>#${num}</strong></span>
        </div>
        <div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Estado:</span>
            <span class="sexp-exp-info-valor">${labelEstado[estado] || labelEstado.normal}</span>
        </div>`;

    if (info.paciente_identidad) {
        filas += `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Identidad:</span>
            <span class="sexp-exp-info-valor">${info.paciente_identidad}</span>
        </div>`;
    }
    if (info.paciente_nombre) {
        filas += `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Paciente:</span>
            <span class="sexp-exp-info-valor">${info.paciente_nombre}</span>
        </div>`;
    }
    if (info.motivo_rechazo) {
        filas += `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Motivo:</span>
            <span class="sexp-exp-info-valor">${info.motivo_rechazo}</span>
        </div>`;
    }
    if (info.comentario_devolucion) {
        filas += `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">Comentario:</span>
            <span class="sexp-exp-info-valor">${info.comentario_devolucion}</span>
        </div>`;
    }

    Swal.fire({
        title: `Expediente #${num}`,
        html: `<div class="sexp-exp-info-popup">${filas}</div>`,
        showCancelButton: false,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Cerrar',
        customClass: {
            popup: 'contenedor-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones-min');
        }
    });
}
