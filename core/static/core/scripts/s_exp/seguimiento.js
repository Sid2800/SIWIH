/**
 * Seguimiento de Solicitudes - s_exp
 * Muestra las solicitudes del usuario con timeline visual.
 */
$(document).ready(function () {
    cargarMisSolicitudes();
    // Refresco cada 30 segundos
    setInterval(cargarMisSolicitudes, 30000);
});

function cargarMisSolicitudes() {
    $.ajax({
        url: window.urls.s_exp_mis_solicitudes_api,
        method: 'GET',
        success: function (resp) {
            renderSolicitudes(resp.data);
        },
        error: function () {
            toastr.error("Error al cargar solicitudes");
        }
    });
}

function renderSolicitudes(data) {
    const container = $('#timeline-solicitudes');

    if (!data.length) {
        container.html('<p style="opacity:0.5; text-align:center;">No tiene solicitudes registradas. <a href="' + window.urls.s_exp_buscador + '" style="color:var(--negro);">Crear una nueva</a></p>');
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
            'sol_incompleta': 'background:rgba(249,115,22,0.2);color:var(--negro);',
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

        const exps = s.expedientes.map(n => `<span class="sexp-exp-tag">#${n}</span>`).join(' ');
        const badgeEstilo = badgeEstilos[claseEstado] || '';
        const borderColor = borderColors[claseEstado] || '#6366f1';

        html += `
        <div class="sexp-sol-card" style="border-left-color:${borderColor};">
            <div class="sexp-sol-header">
                <h3><i class="bi bi-file-text"></i> Solicitud #${s.id}</h3>
                <span class="sexp-sol-badge" style="${badgeEstilo}padding:0.25rem 0.8rem;border-radius:20px;font-size:1.2rem;font-weight:700;">${s.estado_flujo_nombre}</span>
            </div>
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

                // Botón devolver
                html += `<button class="sexp-devolver-btn" onclick="solicitarDevolucion(${s.id})">
                    <i class="bi bi-arrow-return-left"></i> Solicitar Devolución
                </button>`;
            }
            if (p.comentarios) {
                html += `<div style="margin-top:0.5rem;font-size:1.3rem;opacity:0.7;"><i class="bi bi-chat-text"></i> ${p.comentarios}</div>`;
            }
        }

        html += `</div>`;
    });

    container.html(html);
}

function solicitarDevolucion(solicitudId) {
    Swal.fire({
        color: 'var(--negro)',
        background: 'var(--blanco)',
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
