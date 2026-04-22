/**
 * Monitoreo de Préstamos - s_exp
 * Utiliza DataTables con procesamiento en servidor y cronómetros dinámicos.
 */
let tablaPrestamos;
let timerIntervals = {};
let estadoFiltro = '';

$(document).ready(function () {
    initTabla();
    initFiltros();

    $('#btn-refresh-prestamos').on('click', function () {
        tablaPrestamos.ajax.reload();
    });
});

/**
 * Inicializa el DataTable de monitoreo de préstamos.
 */
function initTabla() {
    tablaPrestamos = $('#tabla_prestamos').DataTable({
        processing: true,
        serverSide: true,
        ajax: {
            url: window.urls.s_exp_prestamos_activos_api,
            data: function (d) {
                d.estado = estadoFiltro;
            }
        },
        columns: [
            { data: 'id', render: (data) => `#${data}` },
            {
                data: null,
                render: function (data) {
                    return `<div><strong>${data.usuario_nombre}</strong><br><small class="sexp-opacity-6">${data.usuario}</small></div>`;
                }
            },
            { data: 'area_destino' },
            {
                data: 'expedientes',
                render: function (data) {
                    return data.map(n => `<span class="sexp-exp-tag">#${n}</span>`).join(' ');
                }
            },
            {
                data: 'estado',
                render: function (data) {
                    const estilos = {
                        'Activo': 'background:rgba(99,102,241,0.2);color:var(--negro);',
                        'Entregado': 'background:rgba(34,197,94,0.2);color:var(--negro);',
                        'Vencido': 'background:rgba(239,68,68,0.2);color:var(--negro);',
                        'DevolucionParcial': 'background:rgba(249,115,22,0.2);color:var(--negro);',
                        'DevueltoVencido': 'background:rgba(239,68,68,0.15);color:var(--negro);border:1px solid #ef4444;',
                        'Cerrado': 'background:rgba(100,116,139,0.2);color:var(--negro);'
                    };
                    const labels = {
                        'Activo': 'Aprobado',
                        'Entregado': 'En Préstamo',
                        'Vencido': 'Vencido',
                        'DevolucionParcial': 'Devolución Parcial',
                        'DevueltoVencido': 'Devuelto Tarde',
                        'Cerrado': 'Cerrado'
                    };
                    return `<span class="sexp-estado-badge" style="${estilos[data] || ''}">${labels[data] || data}</span>`;
                }
            },
            {
                data: null,
                render: function (p) {
                    if (p.estado === 'Entregado' && p.fecha_limite) {
                        const timerId = 'timer-' + p.id;
                        return `<div>
                            <span class="sexp-timer" id="${timerId}" data-limite="${p.fecha_limite}" data-porcentaje="${p.porcentaje_tiempo_usado}">--:--:--</span>
                            <div class="sexp-progress-bar">
                                <div class="sexp-progress-fill" id="progress-${p.id}" style="width:${p.porcentaje_tiempo_usado}%"></div>
                            </div>
                        </div>`;
                    } else if (p.estado === 'Activo') {
                        return '<span class="sexp-opacity-5">Sin entregar</span>';
                    }
                    return '<span class="sexp-opacity-5">-</span>';
                }
            },
            {
                data: null,
                orderable: false,
                render: function (p) {
                    if (p.estado === 'Activo' && p.solicitud_estado_flujo === 'SOL_LISTO_RECOGER') {
                        return `<button class="sexp-action-btn sexp-action-btn--aprobar" onclick="marcarEntregado(${p.id})">
                            <i class="bi bi-check2-square"></i> Entregar
                        </button>`;
                    } else if (p.estado === 'Activo') {
                        return `<span class="sexp-status-hint"><i class="bi bi-hourglass-split"></i> Preparando...</span>`;
                    }
                    return '';
                }
            }
        ],
        order: [[0, 'desc']],
        language: {
            processing: "Cargando...",
            search: "Buscar usuario/ID:",
            lengthMenu: "Mostrar _MENU_",
            info: "Mostrando _START_ a _END_ de _TOTAL_",
            infoEmpty: "Sin préstamos",
            infoFiltered: "(filtrado de _MAX_)",
            paginate: { first: "Primero", last: "Último", next: "→", previous: "←" },
            zeroRecords: "No se encontraron resultados"
        },
        drawCallback: function () {
            // Reiniciar todos los cronómetros después de cada redibujado de la tabla
            Object.values(timerIntervals).forEach(clearInterval);
            timerIntervals = {};

            $('.sexp-timer[data-limite]').each(function () {
                const id = $(this).attr('id').replace('timer-', '');
                const limite = $(this).data('limite');
                const porcentaje = $(this).data('porcentaje');
                iniciarCronometro(id, limite, porcentaje);
            });
        }
    });
}

function initFiltros() {
    $('.sexp-filtro-btn').on('click', function () {
        $('.sexp-filtro-btn').removeClass('active');
        $(this).addClass('active');
        estadoFiltro = $(this).data('estado');
        tablaPrestamos.ajax.reload();
    });
}

function iniciarCronometro(prestamoId, fechaLimiteISO, porcentaje) {
    const timerEl = document.getElementById('timer-' + prestamoId);
    const progressEl = document.getElementById('progress-' + prestamoId);
    if (!timerEl) return;

    const fechaLimite = new Date(fechaLimiteISO);

    function actualizar() {
        const ahora = new Date();
        const diff = fechaLimite - ahora;

        if (diff <= 0) {
            timerEl.textContent = 'VENCIDO';
            timerEl.className = 'sexp-timer sexp-timer--expired';
            if (progressEl) {
                progressEl.style.width = '100%';
                progressEl.className = 'sexp-progress-fill sexp-progress-fill--danger';
            }
            return;
        }

        const horas = Math.floor(diff / 3600000);
        const minutos = Math.floor((diff % 3600000) / 60000);
        const segundos = Math.floor((diff % 60000) / 1000);
        timerEl.textContent = `${String(horas).padStart(2, '0')}:${String(minutos).padStart(2, '0')}:${String(segundos).padStart(2, '0')}`;

        if (porcentaje >= 90) {
            timerEl.className = 'sexp-timer sexp-timer--danger';
            if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--danger';
        } else if (porcentaje >= 70) {
            timerEl.className = 'sexp-timer sexp-timer--warn';
            if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--warn';
        } else {
            timerEl.className = 'sexp-timer sexp-timer--ok';
            if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--ok';
        }
    }

    actualizar();
    timerIntervals[prestamoId] = setInterval(actualizar, 1000);
}

function marcarEntregado(prestamoId) {
    Swal.fire({
        title: 'Confirmar entrega',
        text: 'Se iniciará el cronómetro del préstamo al confirmar.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, Entregar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#22c55e'
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_marcar_entregado_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({ prestamo_id: prestamoId }),
                success: function (resp) {
                    if (resp.success) {
                        toastr.success('Préstamo entregado. Cronómetro iniciado.');
                        tablaPrestamos.ajax.reload();
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
