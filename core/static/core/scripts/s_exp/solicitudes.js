/**
 * Gestión de Solicitudes - s_exp
 * DataTable con server-side processing y acciones de aprobación/rechazo.
 * 
 * Funciones principales:
 *   initTabla()           - Inicializa el DataTable con columnas y server-side processing.
 *   initFiltros()         - Configura los botones de filtro de estado.
 *   aprobarSolicitud(id)  - Abre modal para aprobar con tiempo configurable (horas/minutos).
 *   rechazarSolicitud(id) - Abre modal para rechazar con motivo obligatorio.
 *   marcarListo(id)       - Confirma que los expedientes están organizados para recoger.
 */
let tablaSolicitudes;
let estadoFiltro = '';

/**
 * Almacenamiento local del flujo de aprobación:
 * - Imprimir habilita Revisión de Entrega
 * - Revisar habilita Listo para entregar
 * Se persiste en sessionStorage para que sobreviva a recargas de la tabla.
 */
const sexpFlujoLocal = {
    _key: 'sexp_flujo_solicitud',
    _get: function () {
        try { return JSON.parse(sessionStorage.getItem(this._key) || '{}'); } catch (e) { return {}; }
    },
    _set: function (data) {
        sessionStorage.setItem(this._key, JSON.stringify(data));
    },
    marcarImpreso: function (id) {
        const data = this._get();
        data[id] = data[id] || {};
        data[id].impreso = true;
        this._set(data);
    },
    marcarRevisado: function (id) {
        const data = this._get();
        data[id] = data[id] || {};
        data[id].revisado = true;
        this._set(data);
    },
    haImpreso: function (id) {
        const data = this._get();
        return !!(data[id] && data[id].impreso);
    },
    haRevisado: function (id) {
        const data = this._get();
        return !!(data[id] && data[id].revisado);
    },
    limpiar: function (id) {
        const data = this._get();
        delete data[id];
        this._set(data);
    }
};

$(document).ready(function () {
    initTabla();
    initFiltros();

    $('#btn-refresh-solicitudes').on('click', function () {
        tablaSolicitudes.ajax.reload();
    });
});

/**
 * Muestra un popup con la información del expediente al tocar/clickear el tag.
 * Útil en móvil/tablet donde el tooltip nativo no aparece sin mouse.
 * @param {Object} info - Datos del expediente y su estado.
 */
function mostrarInfoExpediente(info) {
    if (!info) return;
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

/**
 * Inicializa el DataTable de gestión de solicitudes.
 * Carga datos desde el servidor con paginación, ordenamiento y búsqueda.
 */
function initTabla() {
    tablaSolicitudes = $('#tabla_solicitudes').DataTable({
        processing: true,
        serverSide: true,
        ajax: {
            url: window.urls.s_exp_listar_solicitudes_api,
            data: function (d) {
                d.estado = estadoFiltro;
            }
        },
        columns: [
            { data: 'id' },
            {
                data: null,
                render: function (data) {
                    return `<div><strong>${data.usuario_nombre}</strong><br><small class="sexp-opacity-6">${data.usuario}</small></div>`;
                }
            },
            { data: 'fecha_creacion' },
            {
                data: null,
                render: function (row) {
                    const enPrestamo = ['SOL_LISTO_RECOGER', 'SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_INCOMPLETA'].includes(row.estado_flujo);
                    return (row.expedientes || []).map(e => {
                        const num = typeof e === 'object' ? e.numero : e;
                        const noAprobado = e.aprobado === false;
                        const esFuera = e.fuera_de_tiempo;
                        const sanitize = (t) => (t || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                        let cls = 'sexp-exp-tag';
                        let title = '';
                        let estadoTag = 'normal';
                        if (noAprobado) {
                            cls = 'sexp-exp-tag sexp-exp-tag--rechazado';
                            title = e.motivo_rechazo_individual ? `No prestado: ${e.motivo_rechazo_individual}` : 'No prestado';
                            estadoTag = 'rechazado';
                        } else if (enPrestamo && e.devuelto === false) {
                            cls = 'sexp-exp-tag sexp-exp-tag--pendiente';
                            title = 'Pendiente de devolver';
                            estadoTag = 'pendiente';
                        } else if (esFuera) {
                            cls = 'sexp-exp-tag sexp-exp-tag--late';
                            title = 'Entregado fuera de tiempo';
                            estadoTag = 'late';
                        } else if (e.devuelto) {
                            estadoTag = 'devuelto';
                        }
                        const info = {
                            numero: num,
                            estado: estadoTag,
                            paciente_nombre: e.paciente_nombre || '',
                            paciente_identidad: e.paciente_identidad || '',
                            motivo_rechazo: e.motivo_rechazo_individual || '',
                            comentario_devolucion: e.comentario_devolucion || ''
                        };
                        const dataAttr = `data-info="${sanitize(JSON.stringify(info))}"`;
                        const onClick = `onclick="mostrarInfoExpediente(JSON.parse(this.getAttribute('data-info')))"`;
                        return `<span class="${cls}" title="${sanitize(title)}" ${dataAttr} ${onClick}>#${num}</span>`;
                    }).join(' ');
                }
            },
            {
                data: 'motivo',
                render: function (data) {
                    return data.length > 40 ? data.substring(0, 40) + '...' : data;
                }
            },
            { data: 'area_destino' },
            {
                data: 'estado_flujo',
                render: function (data, type, row) {
                    const nombre = row.estado_flujo_nombre || data;
                    const cls = 'sexp-estado-badge sexp-estado-badge--' + data.toLowerCase().replace('sol_', '');
                    return `<span class="${cls}">${nombre}</span>`;
                }
            },
            {
                data: null,
                orderable: false,
                render: function (data) {
                    if (data.estado_flujo === 'SOL_PENDIENTE') {
                        return `
                            <div class="sexp-action-group">
                                <button class="sexp-action-btn sexp-action-btn--aprobar" onclick="aprobarSolicitud(${data.id})">
                                    <i class="bi bi-check-lg"></i> Aprobar
                                </button>
                                <button class="sexp-action-btn sexp-action-btn--rechazar" onclick="rechazarSolicitud(${data.id})">
                                    <i class="bi bi-x-lg"></i> Rechazar
                                </button>
                            </div>`;
                    }
                    const btnImprimir = `
                        <button class="sexp-action-btn sexp-action-btn--imprimir" onclick="imprimirSolicitud(${data.id})">
                            <i class="bi bi-printer"></i> Imprimir
                        </button>`;
                    if (data.estado_flujo === 'SOL_APROBADA_ORGANIZANDO') {
                        const haImpreso = sexpFlujoLocal.haImpreso(data.id);
                        const haRevisado = sexpFlujoLocal.haRevisado(data.id);
                        const btnRevisar = `
                            <button class="sexp-action-btn sexp-action-btn--revisar"
                                    ${haImpreso ? '' : 'disabled title="Primero imprima la solicitud"'}
                                    onclick="revisarEntrega(${data.id})">
                                <i class="bi bi-clipboard-check"></i> Revisión de Entrega
                            </button>`;
                        const btnListo = `
                            <button class="sexp-action-btn sexp-action-btn--listo"
                                    ${haRevisado ? '' : 'disabled title="Primero realice la revisión de entrega"'}
                                    onclick="marcarListo(${data.id})">
                                <i class="bi bi-bell"></i> Listo para entregar
                            </button>`;
                        return `
                            <div class="sexp-action-group">
                                ${btnImprimir}
                                ${btnRevisar}
                                ${btnListo}
                            </div>`;
                    }
                    if (data.estado_flujo === 'SOL_LISTO_RECOGER') {
                        return `
                            <div class="sexp-action-group">
                                ${btnImprimir}
                                <button class="sexp-action-btn sexp-action-btn--entregar" onclick="entregarPrestamoDesdeGestion(${data.prestamo_id || 0}, ${data.id})">
                                    <i class="bi bi-box-arrow-up-right"></i> Entregar
                                </button>
                            </div>`;
                    }
                    const estadosImprimibles = ['SOL_EN_PRESTAMO', 'SOL_EN_DEVOLUCION', 'SOL_FINALIZADA', 'SOL_INCOMPLETA'];
                    if (estadosImprimibles.includes(data.estado_flujo)) {
                        return btnImprimir;
                    }
                    return '';
                }
            }
        ],
        order: [[2, 'desc']],
        language: {
            processing: "Cargando...",
            search: "Buscar:",
            lengthMenu: "Mostrar _MENU_ registros",
            info: "Mostrando _START_ a _END_ de _TOTAL_",
            infoEmpty: "Sin registros disponibles",
            infoFiltered: "(filtrado de _MAX_ registros totales)",
            loadingRecords: "Cargando registros...",
            zeroRecords: "No se encontraron resultados",
            paginate: { first: "Primero", last: "Último", next: "→", previous: "←" },
            emptyTable: "No hay solicitudes"
        },
        responsive: true
    });
}

/**
 * Configura los botones de filtro de estado en la barra superior.
 * Al hacer clic en un filtro, recarga el DataTable con el estado seleccionado.
 */
function initFiltros() {
    $('.sexp-filtro-btn').on('click', function () {
        $('.sexp-filtro-btn').removeClass('active');
        $(this).addClass('active');
        estadoFiltro = $(this).data('estado');
        tablaSolicitudes.ajax.reload();
    });
}

/**
 * Carga los expedientes de la solicitud y abre el modal de aprobación.
 * @param {number} id - ID de la solicitud a aprobar.
 */
function aprobarSolicitud(id) {
    Swal.fire({
        title: 'Cargando expedientes...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    $.ajax({
        url: window.urls.s_exp_expedientes_solicitud_api + id + '/',
        method: 'GET',
        success: function (resp) {
            Swal.close();
            _mostrarModalAprobacion(id, resp.expedientes || [], {
                tiempo_sugerido_horas: resp.tiempo_sugerido_horas,
                motivo: resp.motivo
            });
        },
        error: function () {
            Swal.close();
            toastr.error('No se pudieron cargar los expedientes de la solicitud');
        }
    });
}

/**
 * Valida si la hora actual está en horario laboral (6 AM - 4 PM).
 */
function estaEnHorarioLaboral() {
    const ahora = new Date();
    const hora = ahora.getHours();
    return hora >= 6 && hora < 16;
}

/**
 * Calcula horas disponibles hasta las 4 PM de hoy.
 */
function horasHastaCuatroPM() {
    const ahora = new Date();
    const limite = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate(), 16, 0, 0);
    const diffMs = limite - ahora;
    return diffMs > 0 ? Math.floor(diffMs / (1000 * 60 * 60)) : 0;
}

/**
 * Construye y muestra el modal de aprobación con la lista de expedientes.
 * Cada expediente puede aprobarse o rechazarse individualmente.
 * Si alguno se rechaza, el campo de motivo se vuelve obligatorio.
 *
 * @param {number} id          - ID de la solicitud.
 * @param {Array}  expedientes - Lista de objetos {detalle_id, numero, paciente_nombre}.
 */
function _mostrarModalAprobacion(id, expedientes, meta) {
    meta = meta || {};
    // Solo nombres + identidad — sin checkboxes (la decisión por expediente se hace en Revisión de Entrega)
    const expHtml = expedientes.map(function (exp) {
        const nombre = exp.paciente_nombre || '—';
        const ident = exp.paciente_identidad ? `<span class="sexp-modal-aprob-id">${exp.paciente_identidad}</span>` : '';
        return `<div class="sexp-modal-aprob-item">${ident}<span class="sexp-modal-aprob-nombre">${nombre}</span></div>`;
    }).join('');

    // Mostrar colapsado por defecto si hay muchos expedientes (>= 9)
    const esLargo = expedientes.length >= 9;
    const claseInicial = esLargo ? ' is-collapsed' : '';
    const claseInicialResumen = esLargo ? ' is-collapsed' : '';
    const iconoInicial = esLargo ? 'bi-chevron-down' : 'bi-chevron-up';
    const textoInicial = esLargo ? 'Mostrar' : 'Ocultar';

    // Tiempo sugerido por el solicitante: pre-cargar como valor por defecto
    let prefillValor = 1;
    let prefillUnidad = 'dias';
    let sugeridoBlock = '';
    if (meta.tiempo_sugerido_horas && meta.tiempo_sugerido_horas > 0) {
        const h = meta.tiempo_sugerido_horas;
        if (h % 24 === 0) {
            prefillUnidad = 'dias';
            prefillValor = h / 24;
        } else {
            prefillUnidad = 'horas';
            prefillValor = h;
        }
        const txt = prefillUnidad === 'dias'
            ? `${prefillValor} día${prefillValor === 1 ? '' : 's'} (${h}h)`
            : `${h} hora${h === 1 ? '' : 's'}`;
        sugeridoBlock = `
            <div class="sexp-modal-sugerido">
                <i class="bi bi-lightbulb"></i>
                <span><strong>Tiempo sugerido por el solicitante:</strong> ${txt}. Acepta o cambia el valor.</span>
            </div>`;
    }

    Swal.fire({
        title: 'Aprobar Solicitud #' + id,
        width: '95%',
        html: `<div style="text-align:left;">
            <p class="sexp-modal-aprob-resumen${claseInicialResumen}">
                <span class="sexp-modal-aprob-resumen-info">
                    <i class="bi bi-folder2-open"></i>
                    Total de expedientes solicitados: <strong>${expedientes.length}</strong>
                </span>
                <button type="button" class="sexp-modal-aprob-toggle" id="swal-toggle-lista">
                    <i class="bi ${iconoInicial}"></i> <span>${textoInicial}</span>
                </button>
            </p>
            <div class="sexp-modal-aprob-lista${claseInicial}" id="swal-lista-exp">${expHtml}</div>
            ${sugeridoBlock}
            <div class="sexp-modal-campo">
                <label>Tiempo de entrega (puede ajustarlo)</label>
                <div class="sexp-modal-tiempo-row">
                    <div class="sexp-tiempo-stepper">
                        <button type="button" class="sexp-stepper-btn" id="swal-tiempo-menos" aria-label="Disminuir">−</button>
                        <input type="number" id="swal-tiempo" value="${prefillValor}" min="1" max="3" inputmode="numeric" pattern="[0-9]*" class="sexp-modal-input">
                        <button type="button" class="sexp-stepper-btn" id="swal-tiempo-mas" aria-label="Aumentar">+</button>
                    </div>
                    <select id="swal-unidad" class="sexp-modal-select">
                        <option value="dias"${prefillUnidad === 'dias' ? ' selected' : ''}>Días</option>
                        <option value="horas"${prefillUnidad === 'horas' ? ' selected' : ''}>Horas</option>
                        <option value="minutos">Minutos</option>
                    </select>
                </div>
                <small id="swal-tiempo-hint" class="sexp-modal-hint">De 1 a 3 días. Vencimiento a las 4:00 PM del último día.</small>
            </div>
        </div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aprobar',
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

            // Toggle colapsar/expandir lista
            const btnToggle = document.getElementById('swal-toggle-lista');
            const lista = document.getElementById('swal-lista-exp');
            if (btnToggle && lista) {
                btnToggle.addEventListener('click', function () {
                    const colapsado = lista.classList.toggle('is-collapsed');
                    const i = btnToggle.querySelector('i');
                    const sp = btnToggle.querySelector('span');
                    if (colapsado) {
                        i.className = 'bi bi-chevron-down';
                        sp.textContent = 'Mostrar';
                    } else {
                        i.className = 'bi bi-chevron-up';
                        sp.textContent = 'Ocultar';
                    }
                });
            }

            // Stepper buttons (arregla problema en táctil donde el spinner nativo no funciona)
            const btnMenos = document.getElementById('swal-tiempo-menos');
            const btnMas = document.getElementById('swal-tiempo-mas');
            if (btnMenos && btnMas) {
                btnMenos.addEventListener('click', function () {
                    const inp = document.getElementById('swal-tiempo');
                    const min = parseInt(inp.min || '1', 10);
                    const v = Math.max(min, (parseInt(inp.value, 10) || min) - 1);
                    inp.value = v;
                });
                btnMas.addEventListener('click', function () {
                    const inp = document.getElementById('swal-tiempo');
                    const max = parseInt(inp.max || '999', 10) || 999;
                    const v = Math.min(max, (parseInt(inp.value, 10) || 0) + 1);
                    inp.value = v;
                });
            }
            const selUnidad = document.getElementById('swal-unidad');
            const inputTiempo = document.getElementById('swal-tiempo');
            const hint = document.getElementById('swal-tiempo-hint');

            function actualizarHintTiempo() {
                const unidad = selUnidad.value;
                if (unidad === 'minutos') {
                    if (!estaEnHorarioLaboral()) {
                        hint.textContent = 'Fuera de horario (6:00 AM - 4:00 PM). Use "Días" o vuelva en horario.';
                        hint.style.color = '#dc2626';
                        inputTiempo.disabled = true;
                    } else {
                        inputTiempo.disabled = false;
                        hint.style.color = 'inherit';
                        inputTiempo.min = '1';
                        inputTiempo.max = '';
                        if (!inputTiempo.value || parseInt(inputTiempo.value) < 1) inputTiempo.value = '5';
                        hint.textContent = 'Ingrese el tiempo en minutos.';
                    }
                } else if (unidad === 'horas') {
                    const maxH = horasHastaCuatroPM();
                    inputTiempo.min = '1';
                    inputTiempo.max = String(maxH);
                    if (maxH <= 0) {
                        hint.textContent = 'Ya pasó la hora límite (4:00 PM). Use "Días" o "Minutos".';
                        inputTiempo.value = '';
                    } else {
                        inputTiempo.value = String(maxH);
                        hint.textContent = `Horas solo el mismo día, máximo hasta las 4:00 PM (disponible: ${maxH}h).`;
                    }
                } else if (unidad === 'dias') {
                    inputTiempo.min = '1';
                    inputTiempo.max = '3';
                    inputTiempo.value = '1';
                    hint.textContent = 'De 1 a 3 días. Vencimiento a las 4:00 PM del último día.';
                }
            }
            selUnidad.addEventListener('change', actualizarHintTiempo);
            // No reset del valor pre-cargado en didOpen (respeta el sugerido)
        },
        preConfirm: () => {
            const tiempo = parseInt(document.getElementById('swal-tiempo').value);
            const unidad = document.getElementById('swal-unidad').value;

            if (isNaN(tiempo) || tiempo < 1) {
                Swal.showValidationMessage('Ingrese un tiempo válido');
                return false;
            }

            // Validación de minutos: solo en horario laboral
            if (unidad === 'minutos' && !estaEnHorarioLaboral()) {
                Swal.showValidationMessage('Minutos solo disponible entre 6:00 AM y 4:00 PM. Use "Días" o espere el horario laboral.');
                return false;
            }

            // Validación de horas: mismo día, no pasar 4 PM
            if (unidad === 'horas') {
                const ahora = new Date();
                const limite = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate(), 16, 0, 0);
                const maxH = limite > ahora ? Math.floor((limite - ahora) / (1000 * 60 * 60)) : 0;
                if (maxH <= 0) {
                    Swal.showValidationMessage('Ya pasó la hora límite (4:00 PM). Use "Días" o "Minutos".');
                    return false;
                }
                if (tiempo > maxH) {
                    Swal.showValidationMessage(`Máximo ${maxH} hora(s) hoy (tope 4:00 PM). Si necesita más, use "Días".`);
                    return false;
                }
            }

            if (unidad === 'dias' && (tiempo < 1 || tiempo > 3)) {
                Swal.showValidationMessage('Días debe estar entre 1 y 3 (máx. 72 horas).');
                return false;
            }

            // Aprobar la solicitud completa — la decisión por expediente se hace en Revisión de Entrega.
            const decisiones = expedientes.map(exp => ({
                detalle_id: exp.detalle_id,
                aprobado: true,
                observaciones: ''
            }));

            // Convertir valor a horas si se eligieron días
            const tiempoHoras = (unidad === 'dias') ? tiempo * 24 : tiempo;
            const esMinutos = (unidad === 'minutos');

            return {
                tiempo_horas: tiempoHoras,
                es_minutos: esMinutos,
                decisiones: decisiones
            };
        }
    }).then((result) => {
        if (!result.isConfirmed) return;

        $.ajax({
            url: window.urls.s_exp_aprobar_solicitud_api,
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            contentType: 'application/json',
            data: JSON.stringify({
                solicitud_id: id,
                tiempo_limite_horas: result.value.tiempo_horas,
                es_minutos: result.value.es_minutos,
                expedientes_decisiones: result.value.decisiones
            }),
            success: function (resp) {
                if (resp.success) {
                    const msg = resp.todos_rechazados
                        ? 'Todos los expedientes rechazados. Solicitud marcada como rechazada.'
                        : 'Solicitud aprobada exitosamente';
                    toastr.success(msg);
                    tablaSolicitudes.ajax.reload();
                }
            },
            error: function (xhr) {
                const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                toastr.error(err);
            }
        });
    });
}

/**
 * Abre el modal de rechazo de una solicitud.
 * Requiere motivo obligatorio. Al rechazar, los expedientes apartados se liberan automáticamente.
 * 
 * @param {number} id - ID de la solicitud a rechazar.
 */
function rechazarSolicitud(id) {
    Swal.fire({
        title: 'Rechazar Solicitud #' + id,
        width: '60rem',
        html: `<div style="text-align:left;">
            <div class="sexp-modal-campo">
                <label>Motivo de Rechazo *</label>
                <textarea id="swal-motivo" rows="4" placeholder="Ingrese el motivo del rechazo (obligatorio)..." class="sexp-modal-input"></textarea>
            </div></div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-x-circle-fill"></i> Rechazar',
        cancelButtonText: '<i class="bi bi-arrow-left-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contenedor-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones');
        },
        preConfirm: () => {
            const motivo = document.getElementById('swal-motivo').value.trim();
            if (!motivo) {
                Swal.showValidationMessage('El motivo de rechazo es obligatorio');
                return false;
            }
            return { motivo: motivo };
        }
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_rechazar_solicitud_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({
                    solicitud_id: id,
                    motivo_rechazo: result.value.motivo
                }),
                success: function (resp) {
                    if (resp.success) {
                        toastr.success('Solicitud rechazada');
                        tablaSolicitudes.ajax.reload();
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
 * Abre el PDF de la solicitud en una nueva pestaña para imprimir.
 * @param {number} id - ID de la solicitud.
 */
function imprimirSolicitud(id) {
    const url = window.urls.s_exp_imprimir_solicitud_pdf + id + '/';
    window.open(url, '_blank');
    sexpFlujoLocal.marcarImpreso(id);
    if (typeof tablaSolicitudes !== 'undefined' && tablaSolicitudes) {
        tablaSolicitudes.ajax.reload(null, false);
    }
}

/**
 * Confirma que los expedientes de una solicitud están organizados y listos para recoger.
 * Cambia el estado de la solicitud a 'SOL_LISTO_RECOGER'.
 * 
 * @param {number} id - ID de la solicitud a marcar como lista.
 */
function marcarListo(id) {
    Swal.fire({
        title: '¿Listo para entregar?',
        html: 'La solicitud <strong>#' + id + '</strong> pasará a "Listo para entregar" y se notificará al usuario para que pase a recoger los expedientes.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, notificar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            icon: 'contenedor-modal-icon',
            popup: 'contenedor-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones-min');
            const htmlContainer = document.querySelector('.swal2-html-container');
            if (htmlContainer) htmlContainer.classList.add('contener-modal-contenedor-html');
        }
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_marcar_listo_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({ solicitud_id: id }),
                success: function (resp) {
                    if (resp.success) {
                        toastr.success('Solicitud marcada como lista. Usuario notificado.');
                        sexpFlujoLocal.limpiar(id);
                        tablaSolicitudes.ajax.reload();
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
 * Modal de Revisión de Entrega:
 * El admin verifica físicamente cada expediente antes de marcar listo.
 * Permite desmarcar expedientes no encontrados y registrar comentario por expediente.
 */
function revisarEntrega(id) {
    Swal.fire({
        title: 'Cargando expedientes...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    $.ajax({
        url: window.urls.s_exp_expedientes_revision_api + id + '/',
        method: 'GET',
        success: function (resp) {
            Swal.close();
            _mostrarModalRevision(id, resp.expedientes || []);
        },
        error: function (xhr) {
            Swal.close();
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los expedientes';
            toastr.error(err);
        }
    });
}


function _mostrarModalRevision(id, expedientes) {
    if (!expedientes.length) {
        toastr.warning('No hay expedientes aprobados para revisar');
        return;
    }
    const filasHtml = expedientes.map(function (exp) {
        const identidad = exp.paciente_identidad || exp.identidad || '';
        const nombre = exp.paciente_nombre || exp.nombre || '';
        return `
        <div class="sexp-revision-card" id="rev-row-${exp.detalle_id}">
            <div class="sexp-revision-card-header">
                <label class="sexp-exp-dec-check" title="Marcado = encontrado, desmarcado = NO encontrado">
                    <input type="checkbox" class="sexp-revision-check" data-detalle="${exp.detalle_id}" checked>
                    <span class="sexp-exp-dec-checkmark"></span>
                </label>
                <span class="sexp-exp-tag">#${exp.numero}</span>
                <div class="sexp-revision-paciente">
                    <span class="sexp-revision-id">${identidad || 'S/ID'}</span>
                    <span class="sexp-revision-nombre">${nombre || 'N/A'}</span>
                </div>
            </div>
            <div class="sexp-revision-card-comentario">
                <label class="sexp-revision-card-label">Comentario:</label>
                <input type="text" class="sexp-revision-comentario" data-detalle="${exp.detalle_id}"
                       placeholder="Obligatorio si se desmarca" maxlength="200">
            </div>
        </div>`;
    }).join('');

    Swal.fire({
        title: 'Revisión de Entrega — Solicitud #' + id,
        width: '95%',
        html: `
            <div class="sexp-revision-modal">
                <p class="sexp-revision-help">
                    <i class="bi bi-info-circle"></i>
                    Marque los que encontró físicamente. Desmarque los que <strong>NO</strong> se encontraron y agregue un comentario.
                </p>
                <div class="sexp-revision-grid">${filasHtml}</div>
            </div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-save"></i> Guardar Revisión',
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
            document.querySelectorAll('.sexp-revision-check').forEach(chk => {
                chk.addEventListener('change', function () {
                    const det = this.dataset.detalle;
                    const row = document.getElementById('rev-row-' + det);
                    if (this.checked) {
                        row.classList.remove('sexp-revision-card--rechazado');
                    } else {
                        row.classList.add('sexp-revision-card--rechazado');
                    }
                });
            });
        },
        preConfirm: () => {
            const decisiones = [];
            const desmarcadosSinComentario = [];
            document.querySelectorAll('.sexp-revision-check').forEach(chk => {
                const det = parseInt(chk.dataset.detalle, 10);
                const encontrado = chk.checked;
                const com = (document.querySelector(`.sexp-revision-comentario[data-detalle="${det}"]`).value || '').trim();
                if (!encontrado && !com) desmarcadosSinComentario.push(det);
                decisiones.push({ detalle_id: det, encontrado: encontrado, comentario: com });
            });
            if (desmarcadosSinComentario.length) {
                Swal.showValidationMessage('Agregue un comentario para cada expediente desmarcado.');
                return false;
            }
            return { decisiones };
        }
    }).then(function (result) {
        if (!result.isConfirmed) return;
        $.ajax({
            url: window.urls.s_exp_revisar_entrega_api,
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            contentType: 'application/json',
            data: JSON.stringify({ solicitud_id: id, decisiones: result.value.decisiones }),
            success: function (resp) {
                if (resp.success) {
                    if (resp.todos_rechazados) {
                        toastr.warning('Todos los expedientes fueron rechazados. Solicitud cerrada.');
                        sexpFlujoLocal.limpiar(id);
                    } else {
                        toastr.success(`Revisión guardada (${resp.cambios} cambio${resp.cambios === 1 ? '' : 's'}).`);
                        sexpFlujoLocal.marcarRevisado(id);
                    }
                    tablaSolicitudes.ajax.reload();
                }
            },
            error: function (xhr) {
                const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                toastr.error(err);
            }
        });
    });
}


/**
 * Confirmar y entregar el préstamo desde la vista de Gestión.
 * Usa la API existente de marcar_entregado_api (window.urls.s_exp_marcar_entregado_api).
 */
function entregarPrestamoDesdeGestion(prestamoId, solicitudId) {
    if (!prestamoId) {
        toastr.error('No se encontró el préstamo asociado a la solicitud');
        return;
    }
    Swal.fire({
        title: '¿Entregar expedientes?',
        html: `Al confirmar, se inicia el conteo del tiempo límite para la solicitud <strong>#${solicitudId}</strong>.`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, entregar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            icon: 'contenedor-modal-icon',
            popup: 'contenedor-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones-min');
            const htmlContainer = document.querySelector('.swal2-html-container');
            if (htmlContainer) htmlContainer.classList.add('contener-modal-contenedor-html');
        }
    }).then(function (result) {
        if (!result.isConfirmed) return;
        $.ajax({
            url: window.urls.s_exp_marcar_entregado_api,
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            contentType: 'application/json',
            data: JSON.stringify({ prestamo_id: prestamoId }),
            success: function (resp) {
                if (resp.success) {
                    toastr.success('Préstamo entregado. Cronómetro iniciado.');
                    tablaSolicitudes.ajax.reload();
                }
            },
            error: function (xhr) {
                const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                toastr.error(err);
            }
        });
    });
}
