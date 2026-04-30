/**
 * Módulo s_exp — Buscador de Expedientes y Selección de Solicitud
 * - Filtro Identidad por defecto con máscara ____-____-_____
 * - Layout responsivo de 3 columnas en pantallas grandes
 * - Display "Identidad - Nombre"
 * - Modal de confirmación reutilizando confirmarAccion() de helpers.js
 */

let carrito = [];
let mascaraIdentidadInstance = null;

$(document).ready(function () {
    $('#btn-buscar').on('click', buscarExpedientes);

    // Buscar al presionar Enter (sin generar espacios extra)
    $('#busqueda-input').on('keydown', function (e) {
        if (e.key === 'Enter' || e.which === 13) {
            e.preventDefault();
            e.stopPropagation();
            // Limpiar espacios y placeholders de máscara
            const valorActual = $(this).val().replace(/_/g, '').trim();
            $(this).val(valorActual);
            buscarExpedientes();
        }
    });

    // Cambiar máscara según tipo de búsqueda
    $('#tipo-busqueda').on('change', actualizarMascaraInput);

    $('#btn-enviar-solicitud').on('click', enviarSolicitud);
    $('#solicitud-motivo').on('change', validarFormulario);

    // Aplicar máscara inicial (Identidad por defecto)
    actualizarMascaraInput();

    // Cargar motivos y unidad del usuario
    cargarMotivos();
    cargarInfoUsuario();
});


/**
 * Aplica la máscara correcta al input según el tipo de búsqueda seleccionado.
 * Identidad usa el formato estándar de SIWI (regexIdentidad de helpers.js).
 */
function actualizarMascaraInput() {
    const tipo = $('#tipo-busqueda').val();
    const $input = $('#busqueda-input');

    // Remover máscara anterior si existe
    if (mascaraIdentidadInstance) {
        try { mascaraIdentidadInstance.remove(); } catch (e) {}
        mascaraIdentidadInstance = null;
    }
    $input.val('');

    if (tipo === 'identidad') {
        // Misma máscara que el módulo Editar Pacientes
        mascaraIdentidadInstance = Inputmask({
            regex: typeof regexIdentidad !== 'undefined'
                ? regexIdentidad
                : "^([0-3][0-9])([0-9][0-9])-(1|2)[0-9]{3}-[0-9]{5}$",
            placeholder: typeof formatoIdentidad !== 'undefined'
                ? formatoIdentidad
                : "____-____-_____",
            showMaskOnHover: false,
        });
        mascaraIdentidadInstance.mask($input[0]);
        $input.attr('placeholder', 'Ingrese identidad: ____-____-_____');
    } else if (tipo === 'nombre') {
        $input.attr('placeholder', 'Ingrese nombre o apellido del paciente...');
    } else {
        $input.attr('placeholder', 'Ingrese N° de expediente...');
    }
}


function cargarMotivos() {
    $.ajax({
        url: window.urls.s_exp_motivos_api,
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
        url: window.urls.s_exp_info_usuario_api,
        method: 'GET',
        success: function (resp) {
            if (resp.unidad) {
                $('#info-unidad').text('Destino: ' + resp.unidad);
            }
        }
    });
}


function buscarExpedientes() {
    let query = $('#busqueda-input').val();
    const tipo = $('#tipo-busqueda').val();

    // Limpiar placeholders de máscara y espacios extra
    query = query.replace(/_/g, '').trim();

    if (!query) {
        toastr.warning('Ingrese un criterio de búsqueda');
        return;
    }

    // Para identidad, validar formato mínimo (con o sin guiones)
    if (tipo === 'identidad') {
        const sinGuiones = query.replace(/-/g, '');
        if (sinGuiones.length < 6) {
            toastr.warning('Ingrese al menos 6 dígitos de la identidad');
            return;
        }
    }

    $('#resultados-busqueda').html(
        '<p class="sexp-grid-empty"><i class="bi bi-hourglass-split"></i> Buscando expedientes...</p>'
    );

    $.ajax({
        url: window.urls.s_exp_buscar_expedientes_api,
        method: 'GET',
        data: { q: query, tipo: tipo },
        success: function (resp) {
            renderResultados(resp.data);
        },
        error: function () {
            toastr.error('Error al buscar expedientes');
            $('#resultados-busqueda').html(
                '<p class="sexp-grid-empty">Error al buscar. Intente nuevamente.</p>'
            );
        }
    });
}


function renderResultados(data) {
    const container = $('#resultados-busqueda');

    if (!data.length) {
        container.html('<p class="sexp-grid-empty">No se encontraron resultados.</p>');
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
            botonHtml = '<span class="sexp-badge--en-carrito"><i class="bi bi-check-circle"></i> Seleccionado</span>';
        } else {
            botonHtml = '<button class="sexp-add-btn" disabled>No disponible</button>';
        }

        // Display: "Identidad - Nombre" como título principal
        const identidad = item.paciente_dni || 'Sin identidad';
        const nombre = item.paciente_nombre || 'Sin paciente asignado';

        html += `
        <div class="sexp-resultado sexp-resultado--card">
            <div class="sexp-resultado__info">
                <h4 class="sexp-resultado-id-nombre">
                    <i class="bi bi-person-badge"></i>
                    <span class="sexp-id">${identidad}</span>
                    <span class="sexp-sep">—</span>
                    <span class="sexp-nombre">${nombre}</span>
                </h4>
                <p class="sexp-resultado-exp">
                    <i class="bi bi-folder2"></i> Expediente #${item.numero_expediente}
                </p>
                <p class="sexp-resultado-ubic">
                    <i class="bi bi-geo-alt"></i> ${item.ubicacion_fisica || 'Archivo Central'}
                </p>
            </div>
            <div class="sexp-resultado-acciones">
                <span class="sexp-badge ${badgeClass}">${badgeText}</span>
                ${botonHtml}
            </div>
        </div>`;
    });

    container.html(html);
}


function agregarAlCarrito(item) {
    if (carrito.some(c => c.expediente_id === item.expediente_id)) {
        toastr.info('Este expediente ya está en la lista');
        return;
    }

    carrito.push(item);
    renderCarrito();
    // Refrescar para actualizar badges sin perder la búsqueda
    const queryActual = $('#busqueda-input').val().replace(/_/g, '').trim();
    if (queryActual) buscarExpedientes();

    toastr.success(`Expediente agregado: ${item.paciente_dni || ''} - ${item.paciente_nombre || ''}`);
}


function removerDelCarrito(expediente_id) {
    carrito = carrito.filter(c => c.expediente_id !== expediente_id);
    renderCarrito();
    const queryActual = $('#busqueda-input').val().replace(/_/g, '').trim();
    if (queryActual) buscarExpedientes();
}


function renderCarrito() {
    const container = $('#carrito-items');
    const count = $('#carrito-count');
    const form = $('#carrito-form');

    count.text(carrito.length);

    if (!carrito.length) {
        container.html('<div class="sexp-carrito-empty"><i class="bi bi-folder-x" style="font-size:1.4rem;"></i><br>No hay expedientes seleccionados</div>');
        form.hide();
        return;
    }

    let html = '';
    carrito.forEach(function (item) {
        const identidad = item.paciente_dni || 'Sin ID';
        const nombre = item.paciente_nombre || 'N/A';
        html += `
        <div class="sexp-carrito-item">
            <div>
                <strong>${identidad}</strong>
                <span class="sexp-carrito-item-nombre"> — ${nombre}</span>
                <span class="sexp-carrito-item-exp"> (#${item.numero_expediente})</span>
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


/**
 * Envía la solicitud usando el modal estándar `confirmarAccion()` de helpers.js.
 */
async function enviarSolicitud() {
    const motivoId = $('#solicitud-motivo').val();
    const motivoText = $('#solicitud-motivo option:selected').text();
    const obs = $('#solicitud-observaciones').val();

    if (!motivoId) {
        toastr.warning('Seleccione un motivo');
        return;
    }
    if (!carrito.length) {
        toastr.warning('Agregue al menos un expediente a la lista');
        return;
    }

    // Listado breve para el modal
    const lista = carrito
        .slice(0, 5)
        .map(c => `<li><strong>${c.paciente_dni || 'S/ID'}</strong> — ${c.paciente_nombre || 'N/A'}</li>`)
        .join('');
    const resto = carrito.length > 5 ? `<li><em>...y ${carrito.length - 5} más</em></li>` : '';

    const mensaje = `
        <div class="sexp-modal-confirm">
            <p>Está a punto de solicitar <strong>${carrito.length}</strong> expediente(s).</p>
            <p><strong>Motivo:</strong> ${motivoText}</p>
            <ul class="sexp-modal-lista">${lista}${resto}</ul>
            <p>¿Desea continuar?</p>
        </div>`;

    // Reutilizar el modal estándar de helpers.js
    const confirmado = await confirmarAccion(
        'Confirmar Solicitud',
        mensaje,
        'Enviar solicitud',
        'Cancelar'
    );

    if (!confirmado) return;

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
            toastr.success(resp.mensaje || 'Solicitud enviada correctamente');
            carrito = [];
            renderCarrito();
            $('#solicitud-motivo').val('');
            $('#solicitud-observaciones').val('');
            $('#busqueda-input').val('');
            $('#resultados-busqueda').html(
                '<p class="sexp-grid-empty">Ingrese un criterio de búsqueda para encontrar expedientes.</p>'
            );
        },
        error: function (xhr) {
            const msg = xhr.responseJSON?.error || 'Error al crear la solicitud';
            toastr.error(msg);
        }
    });
}
