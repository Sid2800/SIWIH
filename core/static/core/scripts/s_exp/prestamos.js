/**
 * Monitoreo de Préstamos - s_exp
 * Carga préstamos activos y maneja cronómetros dinámicos.
 */
let timerIntervals = {};

$(document).ready(function () {
    cargarPrestamos();
    initFiltros();
    // Actualizar datos cada 2 minutos
    setInterval(cargarPrestamos, 120000);
});

function initFiltros() {
    $('.sexp-filtro-btn').on('click', function () {
        $('.sexp-filtro-btn').removeClass('active');
        $(this).addClass('active');
        cargarPrestamos($(this).data('estado'));
    });
}

function cargarPrestamos(estado) {
    // Limpiar timers anteriores
    Object.values(timerIntervals).forEach(clearInterval);
    timerIntervals = {};

    let url = window.urls.s_exp_prestamos_activos_api;
    if (estado) url += '?estado=' + estado;

    $.ajax({
        url: url,
        method: 'GET',
        success: function (resp) {
            renderPrestamos(resp.data);
        },
        error: function () {
            toastr.error("Error al cargar préstamos");
        }
    });
}

function renderPrestamos(data) {
    const tbody = $('#tabla_prestamos tbody');
    tbody.empty();

    if (!data.length) {
        tbody.html('<tr><td colspan="7" style="text-align:center;opacity:0.5;">No hay préstamos activos</td></tr>');
        return;
    }

    data.forEach(function (p) {
        const exps = p.expedientes.map(n => `<span class="sexp-exp-tag" style="background:rgba(99,102,241,0.2);color:#a5b4fc;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:600;">#${n}</span>`).join(' ');

        let estadoBadge = '';
        const estilosBadge = {
            'Activo': 'background:rgba(99,102,241,0.2);color:#a5b4fc;',
            'Entregado': 'background:rgba(245,158,11,0.2);color:#f59e0b;',
            'Vencido': 'background:rgba(239,68,68,0.2);color:#ef4444;',
            'DevolucionParcial': 'background:rgba(249,115,22,0.2);color:#f97316;'
        };
        estadoBadge = `<span style="padding:0.25rem 0.6rem;border-radius:20px;font-size:0.75rem;font-weight:600;${estilosBadge[p.estado] || ''}">${p.estado}</span>`;

        let timerHtml = '';
        if (p.estado === 'Entregado' && p.fecha_limite) {
            const timerId = 'timer-' + p.id;
            timerHtml = `<div>
                <span class="sexp-timer" id="${timerId}">--:--:--</span>
                <div class="sexp-progress-bar">
                    <div class="sexp-progress-fill" id="progress-${p.id}" style="width:${p.porcentaje_tiempo_usado}%"></div>
                </div>
            </div>`;
            // Iniciar cronómetro
            setTimeout(() => iniciarCronometro(p.id, p.fecha_limite, p.porcentaje_tiempo_usado), 100);
        } else if (p.estado === 'Activo') {
            timerHtml = '<span style="opacity:0.5;font-size:0.8rem;">Sin entregar</span>';
        } else {
            timerHtml = '<span style="opacity:0.5;font-size:0.8rem;">-</span>';
        }

        let acciones = '';
        if (p.estado === 'Activo') {
            acciones = `<button style="background:#22c55e;color:#fff;border:none;padding:0.3rem 0.6rem;border-radius:6px;cursor:pointer;font-size:0.8rem;font-weight:600;" onclick="marcarEntregado(${p.id})">
                <i class="bi bi-check2-square"></i> Entregar
            </button>`;
        }

        tbody.append(`
            <tr>
                <td>#${p.id}</td>
                <td><strong>${p.usuario_nombre}</strong><br><small style="opacity:0.6">${p.usuario}</small></td>
                <td>${p.area_destino || '-'}</td>
                <td>${exps}</td>
                <td>${estadoBadge}</td>
                <td>${timerHtml}</td>
                <td>${acciones}</td>
            </tr>
        `);
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
            // Vencido
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

        // Calcular porcentaje y color
        // Necesitamos saber el total, lo estimamos con fecha_limite y tiempo actual
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
        title: '¿Confirmar Entrega?',
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
                        cargarPrestamos();
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
