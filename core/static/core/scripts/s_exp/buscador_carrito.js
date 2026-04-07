/**
 * Módulo s_exp — Buscador de Expedientes y Carrito de Solicitud
 * Busca sobre la base SIWI (Paciente + Expediente) y muestra disponibilidad.
 */

let carrito = [];

$(document).ready(function () {
    $('#btn-buscar').on('click', buscarExpedientes);
    $('#busqueda-input').on('keypress', function (e) {
        if (e.which === 13) buscarExpedientes();
    });
    $('#btn-enviar-solicitud').on('click', enviarSolicitud);
    $('#solicitud-motivo').on('change', validarFormulario);

    // Cargar motivos y unidad del usuario
    cargarMotivos();
    cargarInfoUsuario();
});


function cargarMotivos() {
    $.ajax({
        url: urls.s_exp_motivos_api,
        method: 'GET',
        success: function (resp) {
            const select = $('#solicitud-motivo');
            select.html('<option value="">-- Seleccione motivo --</option>');
            resp.data.forEach(function (m) {
                select.append(`<option value="${m.id}">${m.nombre}</option>`);
            });
        },
        error: function () {
            toastr.error('Error al cargar motivos');
        }
    });
}


function cargarInfoUsuario() {
    $.ajax({
        url: urls.s_exp_info_usuario_api,
        method: 'GET',
        success: function (resp) {
            if (resp.unidad) {
                $('#info-unidad').text('Destino: ' + resp.unidad);
            }
        }
    });
}


function buscarExpedientes() {
    const query = $('#busqueda-input').val().trim();
    const tipo = $('#tipo-busqueda').val();

    if (!query) {
        toastr.warning('Ingrese un criterio de búsqueda');
        return;
    }

    $.ajax({
        url: urls.s_exp_buscar_expedientes_api,
        method: 'GET',
        data: { q: query, tipo: tipo },
        success: function (resp) {
            renderResultados(resp.data);
        },
        error: function () {
            toastr.error('Error al buscar expedientes');
        }
    });
}


function renderResultados(data) {
    const container = $('#resultados-busqueda');

    if (!data.length) {
        container.html('<p style="opacity:0.5; text-align:center;">No se encontraron resultados.</p>');
        return;
    }

    let html = '';
    data.forEach(function (item) {
        const enCarrito = carrito.some(c => c.expediente_id === item.expediente_id);
        const disponible = item.disponible;

        // Badge de disponibilidad
        const badgeClass = disponible ? 'sexp-badge--disponible' : 'sexp-badge--prestado';
        const badgeText = disponible ? 'Disponible' : 'Prestado';

        // Botón agregar
        let botonHtml = '';
        if (disponible && !enCarrito) {
            botonHtml = `<button class="sexp-add-btn" onclick='agregarAlCarrito(${JSON.stringify(item)})'>
                <i class="bi bi-plus-circle"></i> Agregar
            </button>`;
        } else if (enCarrito) {
            botonHtml = '<span class="sexp-badge--en-carrito"><i class="bi bi-check-circle"></i> En carrito</span>';
        } else {
            botonHtml = '<button class="sexp-add-btn" disabled>No disponible</button>';
        }

        html += `
        <div class="sexp-resultado">
            <div class="sexp-resultado__info">
                <h4><i class="bi bi-folder2"></i> Expediente #${item.numero_expediente}</h4>
                <p><strong>${item.paciente_nombre || 'Sin paciente asignado'}</strong></p>
                <p style="font-size:1.2rem;">${item.paciente_dni ? 'ID: ' + item.paciente_dni : ''}</p>
            </div>
            <div style="display:flex; align-items:center; gap:0.5rem;">
                <span class="sexp-badge ${badgeClass}">${badgeText}</span>
                ${botonHtml}
            </div>
        </div>`;
    });

    container.html(html);
}


function agregarAlCarrito(item) {
    if (carrito.some(c => c.expediente_id === item.expediente_id)) {
        toastr.info('Este expediente ya está en el carrito');
        return;
    }

    carrito.push(item);
    renderCarrito();
    buscarExpedientes(); // Refrescar para actualizar badges
    toastr.success(`Expediente #${item.numero_expediente} agregado al carrito`);
}


function removerDelCarrito(expediente_id) {
    carrito = carrito.filter(c => c.expediente_id !== expediente_id);
    renderCarrito();
    buscarExpedientes();
}


function renderCarrito() {
    const container = $('#carrito-items');
    const count = $('#carrito-count');
    const form = $('#carrito-form');

    count.text(carrito.length);

    if (!carrito.length) {
        container.html('<div class="sexp-carrito-empty"><i class="bi bi-cart-x" style="font-size:1.4rem;"></i><br>No hay expedientes seleccionados</div>');
        form.hide();
        return;
    }

    let html = '';
    carrito.forEach(function (item) {
        html += `
        <div class="sexp-carrito-item">
            <div>
                <strong>#${item.numero_expediente}</strong>
                <span style="opacity:0.6; font-size:1.3rem;"> — ${item.paciente_nombre || 'N/A'}</span>
            </div>
            <button class="sexp-remove-btn" onclick="removerDelCarrito(${item.expediente_id})" title="Quitar">
                <i class="bi bi-x-circle"></i>
            </button>
        </div>`;
    });

    container.html(html);
    form.show();
    validarFormulario();
}


function validarFormulario() {
    const motivo = $('#solicitud-motivo').val();
    $('#btn-enviar-solicitud').prop('disabled', !motivo || !carrito.length);
}


function enviarSolicitud() {
    const motivoId = $('#solicitud-motivo').val();
    const motivoText = $('#solicitud-motivo option:selected').text();
    const obs = $('#solicitud-observaciones').val();

    if (!motivoId) {
        toastr.warning('Seleccione un motivo');
        return;
    }
    if (!carrito.length) {
        toastr.warning('Agregue al menos un expediente al carrito');
        return;
    }

    Swal.fire({
        color: 'var(--negro)',
        background: 'var(--blanco)',
        title: 'Confirmar Solicitud',
        html: `<div style="color:var(--negro);"><p>Está a punto de solicitar <strong>${carrito.length}</strong> expediente(s).</p>
               <p><strong>Motivo:</strong> ${motivoText}</p>
               <p>¿Desea continuar?</p></div>`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#6366f1',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Enviar solicitud',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            $.ajax({
                url: window.urls.s_exp_crear_solicitud_api,
                method: 'POST',
                headers: { 'X-CSRFToken': window.CSRF_TOKEN },
                contentType: 'application/json',
                data: JSON.stringify({
                    expedientes: carrito.map(c => c.expediente_id),
                    motivo_id: parseInt(motivoId),
                    observaciones: obs || ''
                }),
                success: function (resp) {
                    Swal.fire({
        color: 'var(--negro)',
        background: 'var(--blanco)',
                        title: '¡Solicitud Enviada!',
                        text: resp.mensaje,
                        icon: 'success',
                        confirmButtonColor: '#6366f1',
                    }).then(() => {
                        carrito = [];
                        renderCarrito();
                        $('#solicitud-motivo').val('');
                        $('#solicitud-observaciones').val('');
                        $('#resultados-busqueda').html('<p style="opacity:0.5; text-align:center;">Ingrese un criterio de búsqueda para encontrar expedientes.</p>');
                    });
                },
                error: function (xhr) {
                    const msg = xhr.responseJSON?.error || 'Error al crear la solicitud';
                    toastr.error(msg);
                }
            });
        }
    });
}
