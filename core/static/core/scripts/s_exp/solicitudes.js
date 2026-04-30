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

$(document).ready(function () {
    initTabla();
    initFiltros();

    $('#btn-refresh-solicitudes').on('click', function () {
        tablaSolicitudes.ajax.reload();
    });
});

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
                data: 'expedientes',
                render: function (data) {
                    return data.map(e => {
                        const num = typeof e === 'object' ? e.numero : e;
                        const noAprobado = e.aprobado === false;
                        const esFuera = e.fuera_de_tiempo;
                        let cls = 'sexp-exp-tag';
                        let title = '';
                        if (noAprobado) {
                            cls = 'sexp-exp-tag sexp-exp-tag--rechazado';
                            title = e.motivo_rechazo_individual ? `No prestado: ${e.motivo_rechazo_individual}` : 'No prestado';
                        } else if (esFuera) {
                            cls = 'sexp-exp-tag sexp-exp-tag--late';
                            title = 'Entregado fuera de tiempo';
                        }
                        return `<span class="${cls}" title="${title}">#${num}</span>`;
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
                        return `
                            <div class="sexp-action-group">
                                ${btnImprimir}
                                <button class="sexp-action-btn sexp-action-btn--revisar" onclick="revisarEntrega(${data.id})">
                                    <i class="bi bi-clipboard-check"></i> Revisión de Entrega
                                </button>
                                <button class="sexp-action-btn sexp-action-btn--listo" onclick="marcarListo(${data.id})">
                                    <i class="bi bi-bell"></i> Listo para entregar
                                </button>
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
    const expHtml = expedientes.map(function (exp) {
        const nombre = exp.paciente_nombre ? `<span class="sexp-exp-lista-patient">${exp.paciente_nombre}</span>` : '';
        return `
        <div class="sexp-exp-lista-item" id="sexp-dec-row-${exp.detalle_id}">
            <div class="sexp-exp-lista-content">
                <span class="sexp-exp-tag">#${exp.numero}</span>
                ${nombre}
            </div>
            <label class="sexp-exp-dec-check" title="Marcado = aprobado, desmarcado = rechazado">
                <input type="checkbox" id="exp-check-${exp.detalle_id}" data-detalle="${exp.detalle_id}" checked>
                <span class="sexp-exp-dec-checkmark"></span>
            </label>
        </div>`;
    }).join('');

    // Texto del tiempo sugerido por el solicitante (si existe)
    let sugeridoBlock = '';
    if (meta.tiempo_sugerido_horas && meta.tiempo_sugerido_horas > 0) {
        const h = meta.tiempo_sugerido_horas;
        let txt;
        if (h % 24 === 0) {
            const d = h / 24;
            txt = `${d} día${d === 1 ? '' : 's'} (${h}h)`;
        } else {
            txt = `${h} hora${h === 1 ? '' : 's'}`;
        }
        sugeridoBlock = `
            <div class="sexp-modal-sugerido">
                <i class="bi bi-lightbulb"></i>
                <span><strong>Tiempo sugerido por el solicitante:</strong> ${txt}</span>
            </div>`;
    }

    Swal.fire({
        title: 'Aprobar Solicitud #' + id,
        width: 950,
        html: `<div style="text-align:left; display:grid; grid-template-columns: 1.5fr 280px; gap: 15px;">
            <div>
                <label style="display:block; font-weight:600; margin-bottom:4px;">
                    Total de expedientes: <strong>${expedientes.length}</strong>
                    <small style="font-weight:normal; opacity:.75; display:block; font-size:12px;">(desmarca los que NO se prestarán)</small>
                </label>
                <div id="swal-exp-list" style="border: 1px solid #ddd; border-radius: 6px; padding: 10px; max-height: 350px; overflow-y: auto; background:#f9fafb;">${expHtml}</div>
            </div>
            <div style="border-left:1px solid #ccc; padding-left:15px;">
                ${sugeridoBlock}
                <div class="sexp-modal-campo">
                    <label>Tiempo de entrega</label>
                <div class="sexp-modal-tiempo-row">
                    <input type="number" id="swal-tiempo" value="1" min="1" class="sexp-modal-input">
                    <select id="swal-unidad" class="sexp-modal-select">
                        <option value="dias" selected>Días</option>
                        <option value="horas">Horas</option>
                        <option value="minutos">Minutos</option>
                    </select>
                </div>
                <small id="swal-tiempo-hint" class="sexp-modal-hint">De 1 a 3 días. Vencimiento a las 4:00 PM del último día.</small>
                </div>
            </div>
        </div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-lg"></i> Aprobar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#16a34a',
        didOpen: () => {
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
            actualizarHintTiempo();

            // Toggle aprobar/rechazar por expediente
            document.getElementById('swal-exp-list').addEventListener('change', function (e) {
                if (e.target.type !== 'checkbox') return;
                const detId = e.target.dataset.detalle;
                const row = document.getElementById(`sexp-dec-row-${detId}`);
                if (e.target.checked) {
                    row.classList.remove('sexp-exp-lista-item--rechazado');
                } else {
                    row.classList.add('sexp-exp-lista-item--rechazado');
                }
            });
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

            // Recolectar decisiones por expediente (solo checkbox)
            const decisiones = [];
            for (const exp of expedientes) {
                const check = document.getElementById(`exp-check-${exp.detalle_id}`);
                const aprobado = check.checked;
                decisiones.push({
                    detalle_id: exp.detalle_id,
                    aprobado: aprobado,
                    observaciones: ''
                });
            }

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
        html: `<div style="text-align:left;">
            <div class="sexp-modal-campo">
                <label>Motivo de Rechazo *</label>
                <textarea id="swal-motivo" rows="3" placeholder="Ingrese el motivo del rechazo (obligatorio)..." class="sexp-modal-input"></textarea>
            </div></div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-x-lg"></i> Rechazar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#dc2626',
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
        text: 'La solicitud #' + id + ' pasará a "Listo para entregar" y se notificará al usuario para que pase a recoger los expedientes.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, notificar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#059669'
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
        <div class="sexp-revision-row" id="rev-row-${exp.detalle_id}">
            <label class="sexp-exp-dec-check" title="Marcado = encontrado, desmarcado = NO encontrado">
                <input type="checkbox" class="sexp-revision-check" data-detalle="${exp.detalle_id}" checked>
                <span class="sexp-exp-dec-checkmark"></span>
            </label>
            <div class="sexp-revision-info">
                <span class="sexp-exp-tag">#${exp.numero}</span>
                <span class="sexp-revision-id">${identidad || 'S/ID'}</span>
                <span class="sexp-revision-nombre">${nombre || 'N/A'}</span>
            </div>
            <input type="text" class="sexp-revision-comentario" data-detalle="${exp.detalle_id}"
                   placeholder="Comentario (obligatorio si se desmarca)" maxlength="200">
        </div>`;
    }).join('');

    Swal.fire({
        title: 'Revisión de Entrega — Solicitud #' + id,
        width: 900,
        html: `
            <div class="sexp-revision-modal">
                <p class="sexp-revision-help">
                    <i class="bi bi-info-circle"></i>
                    Marque los que encontró físicamente. Desmarque los que <strong>NO</strong> se encontraron y agregue un comentario.
                </p>
                <div class="sexp-revision-list">${filasHtml}</div>
            </div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-save"></i> Guardar Revisión',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#059669',
        didOpen: () => {
            document.querySelectorAll('.sexp-revision-check').forEach(chk => {
                chk.addEventListener('change', function () {
                    const det = this.dataset.detalle;
                    const row = document.getElementById('rev-row-' + det);
                    if (this.checked) {
                        row.classList.remove('sexp-revision-row--rechazado');
                    } else {
                        row.classList.add('sexp-revision-row--rechazado');
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
                    } else {
                        toastr.success(`Revisión guardada (${resp.cambios} cambio${resp.cambios === 1 ? '' : 's'}).`);
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
        text: `Al confirmar, se inicia el conteo del tiempo límite para la solicitud #${solicitudId}.`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-box-arrow-up-right"></i> Sí, entregar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#0d9488'
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
