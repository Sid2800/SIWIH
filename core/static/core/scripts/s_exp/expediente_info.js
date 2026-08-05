/**
 * expediente_info.js — Popup con la información de un expediente (s_exp).
 *
 * Se carga globalmente (base.html), igual que realtime.js, para que cualquier
 * pantalla del módulo pueda usarlo: Gestión de Solicitudes, Mis Solicitudes y
 * Monitoreo.
 *
 * Antes esta función estaba DUPLICADA en solicitudes.js y seguimiento.js (con
 * campos distintos cada una) y no existía en prestamos.js, por lo que en
 * Monitoreo no se podía tocar un expediente para ver su info. Aquí queda una
 * sola versión con el superconjunto de campos; cada pantalla envía los que
 * tenga y los ausentes simplemente no se pintan.
 *
 * Uso:
 *   <span class="sexp-exp-tag" data-info="{...json...}"
 *         onclick="mostrarInfoExpediente(JSON.parse(this.getAttribute('data-info')))">#123</span>
 *
 * @param {Object} info - {numero, estado, paciente_identidad, paciente_nombre,
 *                         fecha_solicitud, fecha_entrega, fecha_devolucion,
 *                         motivo_rechazo, comentario_pendiente,
 *                         comentario_devolucion}
 */
function mostrarInfoExpediente(info) {
    if (!info) return;
    const num = info.numero || '—';
    const estado = info.estado || 'normal';

    const labelEstado = {
        'rechazado': '<span class="sexp-exp-info-estado--rec"><i class="bi bi-x-circle-fill"></i> No prestado</span>',
        'pendiente': '<span class="sexp-exp-info-estado--pend"><i class="bi bi-hourglass-split"></i> Pendiente de devolver</span>',
        // Préstamo pendiente: encontrado pero aún no entregado (reservado).
        'prestamo_pendiente': '<span class="sexp-exp-info-estado--prest-pend"><i class="bi bi-clock-history"></i> Pendiente de entrega</span>',
        'late': '<span class="sexp-exp-info-estado--late"><i class="bi bi-exclamation-triangle-fill"></i> Devuelto fuera de tiempo</span>',
        'devuelto': '<span class="sexp-exp-info-estado--ok"><i class="bi bi-check-circle-fill"></i> Devuelto correctamente</span>',
        'normal': '<span class="sexp-exp-info-estado--ok"><i class="bi bi-circle-fill"></i> En proceso</span>'
    };

    // Helper: agrega una fila solo si hay valor (o si se fuerza con vacío).
    const fila = (label, valor) =>
        `<div class="sexp-exp-info-fila">
            <span class="sexp-exp-info-label">${label}</span>
            <span class="sexp-exp-info-valor">${valor}</span>
        </div>`;

    let filas = fila('Expediente:', `<strong>#${num}</strong>`)
              + fila('Estado:', labelEstado[estado] || labelEstado.normal);

    if (info.paciente_identidad) filas += fila('Identidad:', info.paciente_identidad);
    if (info.paciente_nombre) filas += fila('Paciente:', info.paciente_nombre);

    // ---- Trazabilidad de horas ----
    // Son POR expediente: con préstamos pendientes y devoluciones parciales
    // cada uno puede tener su propia fecha. Se pintan solo si la pantalla las
    // envía (la clave existe), usando un texto claro cuando aún no ocurren.
    const sinDato = (t) => `<span class="sexp-opacity-5">${t}</span>`;
    if (info.fecha_solicitud) filas += fila('Solicitado:', info.fecha_solicitud);
    if ('fecha_entrega' in info) {
        filas += fila('Recibido (entrega):', info.fecha_entrega || sinDato('Sin entregar'));
    }
    if ('fecha_devolucion' in info) {
        filas += fila('Devuelto:', info.fecha_devolucion || sinDato('Sin devolver'));
    }

    if (info.motivo_rechazo) filas += fila('Motivo:', info.motivo_rechazo);
    if (info.comentario_pendiente) filas += fila('Pendiente:', info.comentario_pendiente);
    if (info.comentario_devolucion) filas += fila('Comentario:', info.comentario_devolucion);

    Swal.fire({
        title: `Expediente #${num}`,
        html: `<div class="sexp-exp-info-popup">${filas}</div>`,
        width: '46rem',
        showCancelButton: false,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Cerrar',
        customClass: {
            popup: 'contenedor-modal sexp-modal-grande',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones-min');
        }
    });
}
