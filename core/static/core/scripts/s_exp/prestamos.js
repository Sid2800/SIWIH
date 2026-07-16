/**
 * Monitoreo de Préstamos - s_exp
 * Utiliza DataTables con procesamiento en servidor y cronómetros dinámicos.
 */
let tablaPrestamos;
let estadoFiltro = '';

$(document).ready(function () {
    initTabla();
    initFiltros();

    // ===== Auto-refresh inteligente (banner cuando hay cambios) =====
    if (window.RealtimeSExp) {
        RealtimeSExp.registrarConTrigger('monitoreo-prestamos', 'prestamos', function () {
            window.__sexp_polling_actual = true;
            tablaPrestamos.ajax.reload(function () {
                window.__sexp_polling_actual = false;
            }, false);
        }, 5, { etiqueta: 'préstamos' });
    }
});

/**
 * Inicializa el DataTable de monitoreo de préstamos.
 */
function initTabla() {
    tablaPrestamos = $('#tabla_prestamos').DataTable({
        // responsive: en pantallas chicas la tabla NO se estira; las columnas que
        // no caben se colapsan y se ven tocando/clickeando la fila (fila hija),
        // igual que el resto de tablas del sistema.
        responsive: true,
        processing: true,
        serverSide: true,
        ajax: {
            url: window.urls.s_exp_prestamos_activos_api,
            data: function (d) {
                d.estado = estadoFiltro;
            },
            beforeSend: function (xhr) {
                if (window.__sexp_polling_actual) {
                    xhr.setRequestHeader('X-Polling-Request', 'true');
                }
            }
        },
        columns: [
            // responsivePriority: menor número = se conserva visible por más tiempo.
            // Lo esencial (préstamo, solicitante, cronómetro y acciones) permanece;
            // el resto (expedientes, área, motivo) se colapsa en la fila hija.
            { data: 'id', responsivePriority: 1, render: (data) => `#${data}` },
            {
                data: null,
                responsivePriority: 2,
                render: function (data) {
                    return `<div><strong>${data.usuario_nombre}</strong><br><small class="sexp-opacity-6">${data.usuario}</small></div>`;
                }
            },
            { data: 'area_destino' },
            {
                data: 'expedientes',
                render: function (data) {
                    // La API manda detalles ENRIQUECIDOS para poder colorear cada
                    // expediente según su estado real (antes venían solo números,
                    // por eso salían todos sin color). Se mantiene compatibilidad
                    // por si llegara un número suelto.
                    return (data || []).map(e => {
                        if (typeof e !== 'object') return `<span class="sexp-exp-tag">#${e}</span>`;
                        const sanitize = (t) => (t || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                        let cls = 'sexp-exp-tag';
                        let title = '';
                        let estadoTag = 'normal';
                        if (e.prestamo_pendiente) {
                            // Morado: encontrado pero aún no entregado (reservado).
                            cls += ' sexp-exp-tag--prestamo-pendiente';
                            title = e.comentario_pendiente
                                ? `Pendiente de entrega: ${e.comentario_pendiente}`
                                : 'Pendiente de entrega';
                            estadoTag = 'prestamo_pendiente';
                        } else if (e.fuera_de_tiempo) {
                            cls += ' sexp-exp-tag--late';
                            title = 'Devuelto fuera de tiempo';
                            estadoTag = 'late';
                        } else if (e.devuelto) {
                            // Ya devuelto (p. ej. en una devolución parcial previa).
                            title = e.comentario_devolucion || 'Devuelto correctamente';
                            estadoTag = 'devuelto';
                        } else {
                            // Sigue prestado: el tiempo le corre.
                            cls += ' sexp-exp-tag--pendiente';
                            title = 'Pendiente de devolver';
                            estadoTag = 'pendiente';
                        }
                        // Tocar/clickear el expediente abre su info (mostrarInfoExpediente
                        // vive en expediente_info.js, cargado globalmente). Necesario
                        // sobre todo en móvil, donde no hay tooltip al pasar el mouse.
                        const info = {
                            numero: e.numero,
                            estado: estadoTag,
                            paciente_nombre: e.paciente_nombre || '',
                            paciente_identidad: e.paciente_identidad || '',
                            fecha_entrega: e.fecha_entrega || '',
                            fecha_devolucion: e.fecha_devolucion || '',
                            motivo_rechazo: e.motivo_rechazo_individual || '',
                            comentario_devolucion: e.comentario_devolucion || '',
                            comentario_pendiente: e.comentario_pendiente || ''
                        };
                        const dataAttr = `data-info="${sanitize(JSON.stringify(info))}"`;
                        const onClick = `onclick="mostrarInfoExpediente(JSON.parse(this.getAttribute('data-info')))"`;
                        return `<span class="${cls}" title="${sanitize(title)}" ${dataAttr} ${onClick}>#${e.numero}</span>`;
                    }).join(' ');
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
                responsivePriority: 3,
                render: function (p) {
                    // El cronómetro sigue corriendo mientras haya expedientes fuera
                    // del archivo. Incluye DevolucionParcial: en una parcial solo
                    // regresaron algunos, la solicitud NO terminó y el tiempo debe
                    // continuar (antes solo se contemplaba 'Entregado' y por eso el
                    // tiempo desaparecía al hacer una devolución parcial).
                    const CON_CRONOMETRO = ['Entregado', 'Vencido', 'DevolucionParcial'];
                    if (CON_CRONOMETRO.includes(p.estado) && p.fecha_limite) {
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
                responsivePriority: 2,
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
            // Recalcular tiempo restante una sola vez por cada fila renderizada
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

/**
 * Renderiza el "tiempo restante" como texto estático — SIN cronómetro.
 * Formato: "1 día restante", "23 horas restantes", "10 minutos restantes", "VENCIDO".
 * El valor se calcula al cargar la tabla; el reload del DataTable refresca todo.
 */
function iniciarCronometro(prestamoId, fechaLimiteISO, porcentaje) {
    const timerEl = document.getElementById('timer-' + prestamoId);
    const progressEl = document.getElementById('progress-' + prestamoId);
    if (!timerEl) return;

    const fechaLimite = new Date(fechaLimiteISO);
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

    const totalMin = Math.ceil(diff / 60000);
    const totalHoras = Math.floor(totalMin / 60);
    const totalDias = Math.floor(totalHoras / 24);

    let texto;
    if (totalDias >= 1) {
        texto = `${totalDias} día${totalDias === 1 ? '' : 's'} restante${totalDias === 1 ? '' : 's'}`;
    } else if (totalHoras >= 1) {
        texto = `${totalHoras} hora${totalHoras === 1 ? '' : 's'} restante${totalHoras === 1 ? '' : 's'}`;
    } else {
        texto = `${totalMin} minuto${totalMin === 1 ? '' : 's'} restante${totalMin === 1 ? '' : 's'}`;
    }
    timerEl.textContent = texto;

    if (porcentaje >= 90 || totalMin <= 10) {
        timerEl.className = 'sexp-timer sexp-timer--danger';
        if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--danger';
    } else if (porcentaje >= 70 || totalMin <= 30) {
        timerEl.className = 'sexp-timer sexp-timer--warn';
        if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--warn';
    } else {
        timerEl.className = 'sexp-timer sexp-timer--ok';
        if (progressEl) progressEl.className = 'sexp-progress-fill sexp-progress-fill--ok';
    }
}

function marcarEntregado(prestamoId) {
    Swal.fire({
        title: 'Confirmar entrega',
        html: 'Se iniciará el cronómetro del préstamo al confirmar.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, Entregar',
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
