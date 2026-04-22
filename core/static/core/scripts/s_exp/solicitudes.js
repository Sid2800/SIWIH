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
                    if (data.estado_flujo === 'SOL_APROBADA_ORGANIZANDO') {
                        return `
                            <button class="sexp-action-btn sexp-action-btn--listo" onclick="marcarListo(${data.id})">
                                <i class="bi bi-box-seam"></i> Marcar Listo
                            </button>`;
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
            _mostrarModalAprobacion(id, resp.expedientes || []);
        },
        error: function () {
            Swal.close();
            toastr.error('No se pudieron cargar los expedientes de la solicitud');
        }
    });
}

/**
 * Construye y muestra el modal de aprobación con la lista de expedientes.
 * Cada expediente puede aprobarse o rechazarse individualmente.
 * Si alguno se rechaza, el campo de motivo se vuelve obligatorio.
 *
 * @param {number} id          - ID de la solicitud.
 * @param {Array}  expedientes - Lista de objetos {detalle_id, numero, paciente_nombre}.
 */
function _mostrarModalAprobacion(id, expedientes) {
    const expHtml = expedientes.map(function (exp) {
        const nombre = exp.paciente_nombre ? `<span class="sexp-exp-dec-nombre">${exp.paciente_nombre}</span>` : '';
        return `
        <div class="sexp-exp-dec-row" id="sexp-dec-row-${exp.detalle_id}">
            <div class="sexp-exp-dec-head">
                <label class="sexp-exp-dec-check" title="Marcado = aprobado, desmarcado = rechazado">
                    <input type="checkbox" id="exp-check-${exp.detalle_id}" data-detalle="${exp.detalle_id}" checked>
                    <span class="sexp-exp-dec-checkmark"></span>
                </label>
                <span class="sexp-exp-tag">#${exp.numero}</span>
                ${nombre}
                <span class="sexp-exp-dec-estado" id="exp-estado-${exp.detalle_id}">Aprobado</span>
            </div>
            <textarea id="exp-obs-${exp.detalle_id}" rows="2" class="sexp-modal-input sexp-exp-dec-obs"
                placeholder="Observaciones / motivos de rechazo..."></textarea>
        </div>`;
    }).join('');

    Swal.fire({
        title: 'Aprobar Solicitud #' + id,
        width: 680,
        html: `<div style="text-align:left;">
            <div class="sexp-modal-campo">
                <label><strong>Expedientes solicitados</strong> <small style="font-weight:normal; opacity:.75;">(desmarca los que NO se prestarán)</small></label>
                <div id="swal-exp-list">${expHtml}</div>
            </div>
            <hr style="margin:10px 0; opacity:.2;">
            <div class="sexp-modal-campo">
                <label>Tiempo límite</label>
                <div class="sexp-modal-tiempo-row">
                    <input type="number" id="swal-tiempo" value="5" min="1" class="sexp-modal-input">
                    <select id="swal-unidad" class="sexp-modal-select">
                        <option value="minutos" selected>Minutos</option>
                        <option value="horas">Horas</option>
                        <option value="dias">Días</option>
                    </select>
                </div>
                <small id="swal-tiempo-hint" class="sexp-modal-hint">Ingrese el tiempo en minutos.</small>
            </div>
            <div class="sexp-modal-campo">
                <label>Comentarios generales (opcional)</label>
                <textarea id="swal-comentarios" rows="2" class="sexp-modal-input"></textarea>
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

            // Calcula horas disponibles hasta las 4 PM de hoy
            function horasHastaCuatroPM() {
                const ahora = new Date();
                const limite = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate(), 16, 0, 0);
                const diffMs = limite - ahora;
                return diffMs > 0 ? Math.floor(diffMs / (1000 * 60 * 60)) : 0;
            }

            function actualizarHintTiempo() {
                const unidad = selUnidad.value;
                if (unidad === 'minutos') {
                    inputTiempo.min = '1';
                    inputTiempo.max = '';
                    if (!inputTiempo.value || parseInt(inputTiempo.value) < 1) inputTiempo.value = '5';
                    hint.textContent = 'Ingrese el tiempo en minutos.';
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

            // Toggle aprobar/rechazar por expediente
            document.getElementById('swal-exp-list').addEventListener('change', function (e) {
                if (e.target.type !== 'checkbox') return;
                const detId = e.target.dataset.detalle;
                const row = document.getElementById(`sexp-dec-row-${detId}`);
                const estado = document.getElementById(`exp-estado-${detId}`);
                if (e.target.checked) {
                    row.classList.remove('sexp-exp-dec-row--rechazado');
                    estado.textContent = 'Aprobado';
                    estado.className = 'sexp-exp-dec-estado sexp-exp-dec-estado--apr';
                } else {
                    row.classList.add('sexp-exp-dec-row--rechazado');
                    estado.textContent = 'Rechazado';
                    estado.className = 'sexp-exp-dec-estado sexp-exp-dec-estado--rec';
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

            // Recolectar decisiones + observaciones por expediente
            const decisiones = [];
            for (const exp of expedientes) {
                const check = document.getElementById(`exp-check-${exp.detalle_id}`);
                const obs = document.getElementById(`exp-obs-${exp.detalle_id}`).value.trim();
                const aprobado = check.checked;
                if (!aprobado && !obs) {
                    Swal.showValidationMessage(`El expediente #${exp.numero} está rechazado: debe ingresar motivo en observaciones.`);
                    return false;
                }
                decisiones.push({
                    detalle_id: exp.detalle_id,
                    aprobado: aprobado,
                    observaciones: obs
                });
            }

            // Convertir valor a horas si se eligieron días
            const tiempoHoras = (unidad === 'dias') ? tiempo * 24 : tiempo;
            const esMinutos = (unidad === 'minutos');

            return {
                tiempo_horas: tiempoHoras,
                es_minutos: esMinutos,
                comentarios: document.getElementById('swal-comentarios').value,
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
                comentarios: result.value.comentarios,
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
 * Confirma que los expedientes de una solicitud están organizados y listos para recoger.
 * Cambia el estado de la solicitud a 'SOL_LISTO_RECOGER'.
 * 
 * @param {number} id - ID de la solicitud a marcar como lista.
 */
function marcarListo(id) {
    Swal.fire({
        title: '¿Confirmar que están listos?',
        text: 'La solicitud #' + id + ' pasará a "Listo para recoger".',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, confirmar',
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
                        toastr.success('Solicitud marcada como lista');
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
