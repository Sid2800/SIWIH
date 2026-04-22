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
                        const esFuera = e.fuera_de_tiempo;
                        const cls = esFuera ? 'sexp-exp-tag sexp-exp-tag--late' : 'sexp-exp-tag';
                        const title = esFuera ? 'Entregado fuera de tiempo' : '';
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
 * Abre el modal de aprobación de una solicitud.
 * Permite configurar el tiempo límite en horas (producción) o minutos (pruebas).
 * Al cambiar la unidad, el valor y la validación se actualizan dinámicamente.
 * 
 * @param {number} id - ID de la solicitud a aprobar.
 */
function aprobarSolicitud(id) {
    Swal.fire({
        title: 'Aprobar Solicitud #' + id,
        html: `<div style="text-align:left;">
            <div class="sexp-modal-campo">
                <label>Tiempo límite</label>
                <div class="sexp-modal-tiempo-row">
                    <input type="number" id="swal-tiempo" value="5" min="1" class="sexp-modal-input">
                    <select id="swal-unidad" class="sexp-modal-select">
                        <option value="minutos" selected>Minutos (Pruebas)</option>
                        <option value="horas">Horas</option>
                    </select>
                </div>
                <small id="swal-tiempo-hint" class="sexp-modal-hint">Modo pruebas: ingrese el tiempo en minutos.</small>
            </div>
            <div class="sexp-modal-campo">
                <label>Comentarios (opcional)</label>
                <textarea id="swal-comentarios" rows="2" class="sexp-modal-input"></textarea>
            </div></div>`,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-lg"></i> Aprobar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#16a34a',
        didOpen: () => {
            // Al cambiar la unidad, actualizar hint y valor por defecto
            const selUnidad = document.getElementById('swal-unidad');
            const inputTiempo = document.getElementById('swal-tiempo');
            const hint = document.getElementById('swal-tiempo-hint');

            selUnidad.addEventListener('change', function () {
                if (this.value === 'minutos') {
                    inputTiempo.value = '5';
                    inputTiempo.min = '1';
                    hint.textContent = 'Modo pruebas: ingrese el tiempo en minutos.';
                } else {
                    inputTiempo.value = '24';
                    inputTiempo.min = '24';
                    hint.textContent = 'Mínimo 24 horas para producción.';
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

            if (unidad === 'horas' && tiempo < 24) {
                Swal.showValidationMessage('El tiempo mínimo en horas es de 24');
                return false;
            }

            return {
                tiempo: tiempo,
                es_minutos: (unidad === 'minutos'),
                comentarios: document.getElementById('swal-comentarios').value
            };
        }
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_aprobar_solicitud_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({
                    solicitud_id: id,
                    tiempo_limite_horas: result.value.tiempo,
                    es_minutos: result.value.es_minutos,
                    comentarios: result.value.comentarios
                }),
                success: function (resp) {
                    if (resp.success) {
                        toastr.success('Solicitud aprobada exitosamente');
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
