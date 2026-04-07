/**
 * Gestión de Solicitudes - s_exp
 * DataTable con server-side processing y acciones de aprobación/rechazo.
 */
let tablaSolicitudes;
let estadoFiltro = '';

$(document).ready(function () {
    initTabla();
    initFiltros();
});

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
                    return `<div><strong>${data.usuario_nombre}</strong><br><small style="opacity:0.6;">${data.usuario}</small></div>`;
                }
            },
            { data: 'fecha_creacion' },
            {
                data: 'expedientes',
                render: function (data) {
                    return data.map(n => `<span class="sexp-exp-tag">#${n}</span>`).join(' ');
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
                render: function (data) {
                    const clases = {
                        'Pendiente': 'background:rgba(99,102,241,0.2);color:var(--negro);',
                        'Aprobado': 'background:rgba(34,197,94,0.2);color:var(--negro);',
                        'Rechazado': 'background:rgba(239,68,68,0.2);color:var(--negro);',
                        'EnPrestamo': 'background:rgba(245,158,11,0.2);color:var(--negro);',
                        'Devuelto': 'background:rgba(100,116,139,0.2);color:var(--negro);',
                        'DevolucionParcial': 'background:rgba(249,115,22,0.2);color:var(--negro);'
                    };
                    const estilo = clases[data] || '';
                    return `<span style="padding:0.25rem 0.6rem;border-radius:20px;font-size:1.2rem;font-weight:600;${estilo}">${data}</span>`;
                }
            },
            {
                data: null,
                orderable: false,
                render: function (data) {
                    if (data.estado_flujo !== 'Pendiente') return '';
                    return `
                        <div style="display:flex;gap:0.3rem;">
                            <button class="formularioBotones-boton" style="background:#22c55e;color:var(--negro);border:none;padding:0.3rem 0.6rem;border-radius:6px;cursor:pointer;font-size:1.3rem;" onclick="aprobarSolicitud(${data.id})">
                                <i class="bi bi-check-lg"></i> Aprobar
                            </button>
                            <button class="formularioBotones-boton" style="background:#ef4444;color:var(--negro);border:none;padding:0.3rem 0.6rem;border-radius:6px;cursor:pointer;font-size:1.3rem;" onclick="rechazarSolicitud(${data.id})">
                                <i class="bi bi-x-lg"></i> Rechazar
                            </button>
                        </div>`;
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

function initFiltros() {
    $('.sexp-filtro-btn').on('click', function () {
        $('.sexp-filtro-btn').removeClass('active');
        $(this).addClass('active');
        estadoFiltro = $(this).data('estado');
        tablaSolicitudes.ajax.reload();
    });
}

function aprobarSolicitud(id) {
    Swal.fire({
        color: 'var(--negro)',
        background: 'var(--blanco)',
        title: 'Aprobar Solicitud #' + id,
        html: `<div style="color:var(--negro);">
            <div class="sexp-modal-campo">
                <label>Tiempo límite (horas, mínimo 24)</label>
                <input type="number" id="swal-tiempo" min="24" value="24" style="width:100%;padding:0.5rem;border-radius:6px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:white;">
            </div>
            <div class="sexp-modal-campo">
                <label>Comentarios (opcional)</label>
                <textarea id="swal-comentarios" rows="2" style="width:100%;padding:0.5rem;border-radius:6px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:white;"></textarea>
            </div></div>`,
        showCancelButton: true,
        confirmButtonText: 'Aprobar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#22c55e',
        preConfirm: () => {
            const tiempo = parseInt(document.getElementById('swal-tiempo').value);
            if (tiempo < 24) {
                Swal.showValidationMessage('El tiempo mínimo es de 24 horas');
                return false;
            }
            return {
                tiempo: tiempo,
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

function rechazarSolicitud(id) {
    Swal.fire({
        color: 'var(--negro)',
        background: 'var(--blanco)',
        title: 'Rechazar Solicitud #' + id,
        html: `<div style="color:var(--negro);">
            <div class="sexp-modal-campo">
                <label>Motivo de Rechazo *</label>
                <textarea id="swal-motivo" rows="3" placeholder="Ingrese el motivo del rechazo (obligatorio)..." style="width:100%;padding:0.5rem;border-radius:6px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:white;"></textarea>
            </div></div>`,
        showCancelButton: true,
        confirmButtonText: 'Rechazar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#ef4444',
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
