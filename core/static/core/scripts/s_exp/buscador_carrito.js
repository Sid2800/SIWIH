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
            buscarExpedientes();
        }
    });

    // Cambiar máscara según tipo de búsqueda
    $('#tipo-busqueda').on('change', actualizarMascaraInput);

    $('#btn-enviar-solicitud').on('click', enviarSolicitud);
    $('#solicitud-motivo').on('change', validarFormulario);

    // Sugerir tiempo de entrega
    $('#solicitud-sugerir-tiempo').on('change', toggleSugerirTiempo);
    $('#solicitud-tiempo-cuando').on('change', actualizarLimitesTiempo);
    $('#solicitud-tiempo-valor').on('input', validarValorTiempo);

    // Stepper táctil (− N +)
    $('#solicitud-tiempo-menos').on('click', function () {
        const $inp = $('#solicitud-tiempo-valor');
        const min = parseInt($inp.attr('min'), 10) || 1;
        const v = Math.max(min, (parseInt($inp.val(), 10) || min) - 1);
        $inp.val(v);
    });
    $('#solicitud-tiempo-mas').on('click', function () {
        const $inp = $('#solicitud-tiempo-valor');
        const max = parseInt($inp.attr('max'), 10) || 999;
        const v = Math.min(max, (parseInt($inp.val(), 10) || 0) + 1);
        $inp.val(v);
    });

    // Aplicar máscara inicial (Identidad por defecto)
    actualizarMascaraInput();

    // Cargar motivos y unidad del usuario
    cargarMotivos();
    cargarInfoUsuario();
});


/**
 * Habilita/deshabilita el panel de sugerencia de tiempo según el checkbox.
 */
function toggleSugerirTiempo() {
    const activo = $('#solicitud-sugerir-tiempo').is(':checked');
    $('#sugerir-tiempo-panel').toggle(activo);
    if (activo) {
        actualizarLimitesTiempo();
    }
}


/**
 * Calcula horas desde ahora hasta las 4:00 PM del mismo día.
 */
function _horasHastaCuatroPM() {
    const ahora = new Date();
    const limite = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate(), 16, 0, 0);
    const diffMs = limite - ahora;
    return diffMs > 0 ? Math.floor(diffMs / (1000 * 60 * 60)) : 0;
}


/**
 * Actualiza límites min/max y texto informativo según "cuando" (hoy / días posteriores).
 * - hoy → unidad forzada a HORAS, máx hasta las 4:00 PM
 * - dias → unidad forzada a DÍAS, máx 3 días
 * El select de unidad queda disabled (cambia automáticamente).
 */
function actualizarLimitesTiempo() {
    const cuando = $('#solicitud-tiempo-cuando').val();
    const $valor = $('#solicitud-tiempo-valor');
    const $unidadSel = $('#solicitud-tiempo-unidad');
    const $hint = $('#sugerir-tiempo-hint span');

    // El select de unidad SIEMPRE va sincronizado con "cuando" y queda disabled
    $unidadSel.prop('disabled', true);

    if (cuando === 'hoy') {
        // Mismo día → siempre en horas, máximo hasta las 4 PM
        $unidadSel.val('horas');
        const maxH = _horasHastaCuatroPM();
        $valor.attr('min', 1);
        $valor.attr('max', Math.max(maxH, 1));
        if (maxH <= 0) {
            $valor.val('').prop('disabled', true);
            $hint.html('<strong>Ya pasó la hora límite (4:00 PM).</strong> Use "Días posteriores" o solicite sin sugerir tiempo.');
        } else {
            $valor.prop('disabled', false);
            const valorActual = parseInt($valor.val(), 10);
            if (!valorActual || valorActual > maxH) $valor.val(maxH);
            $hint.html(`Mismo día: máximo <strong>${maxH} hora(s)</strong> disponibles hasta las 4:00 PM. Es solo una sugerencia; el administrador define el tiempo final.`);
        }
    } else {
        // Días posteriores → siempre DÍAS, máximo 3
        $unidadSel.val('dias');
        $valor.prop('disabled', false);
        $valor.attr('min', 1);
        $valor.attr('max', 3);
        const valorActual = parseInt($valor.val(), 10);
        if (!valorActual || valorActual > 3) $valor.val(1);
        $hint.html('Días posteriores: <strong>de 1 a 3 días</strong>. Es solo una sugerencia; el administrador define el tiempo final.');
    }
}


/**
 * Saneamiento al teclear: clamp al rango actual.
 */
function validarValorTiempo() {
    const $valor = $('#solicitud-tiempo-valor');
    const min = parseInt($valor.attr('min'), 10) || 1;
    const max = parseInt($valor.attr('max'), 10);
    const v = parseInt($valor.val(), 10);
    if (isNaN(v)) return;
    if (v < min) $valor.val(min);
    if (max && v > max) $valor.val(max);
}


/**
 * Devuelve el tiempo sugerido en horas, o null si el checkbox está desactivado.
 * Lanza Error con mensaje legible si los datos son inválidos.
 */
function _obtenerTiempoSugeridoHoras() {
    if (!$('#solicitud-sugerir-tiempo').is(':checked')) return null;

    const cuando = $('#solicitud-tiempo-cuando').val();
    const unidad = $('#solicitud-tiempo-unidad').val();
    const valor = parseInt($('#solicitud-tiempo-valor').val(), 10);

    if (isNaN(valor) || valor < 1) {
        throw new Error('Ingrese un tiempo sugerido válido');
    }

    if (cuando === 'hoy') {
        const maxH = _horasHastaCuatroPM();
        if (maxH <= 0) {
            throw new Error('Ya pasó la hora límite (4:00 PM). Use "Días posteriores" o desactive la sugerencia.');
        }
        if (valor > maxH) {
            throw new Error(`Para el mismo día, el máximo son ${maxH} hora(s) hasta las 4:00 PM.`);
        }
        return valor;
    }

    if (unidad === 'dias') {
        if (valor > 3) throw new Error('Para días posteriores, el máximo son 3 días (72 horas).');
        return valor * 24;
    }
    if (valor > 72) throw new Error('Para días posteriores, el máximo son 72 horas.');
    return valor;
}


/**
 * Aplica la máscara correcta al input según el tipo de búsqueda seleccionado.
 * SOLO se aplica máscara cuando el tipo es "identidad".
 * Para "nombre" y "expediente" el input es libre.
 */
function actualizarMascaraInput() {
    const tipo = $('#tipo-busqueda').val();
    const $input = $('#busqueda-input');
    const inputDom = $input[0];

    // Remover SIEMPRE cualquier máscara residual antes de aplicar la nueva
    try {
        if (typeof Inputmask !== 'undefined' && Inputmask.remove) {
            Inputmask.remove(inputDom);
        }
    } catch (e) {}
    if (mascaraIdentidadInstance) {
        try { mascaraIdentidadInstance.remove(); } catch (e) {}
        mascaraIdentidadInstance = null;
    }
    // Limpiar atributos residuales
    inputDom.removeAttribute('data-inputmask');
    inputDom.removeAttribute('data-inputmask-regex');
    inputDom.removeAttribute('data-inputmask-placeholder');
    inputDom.removeAttribute('readonly');
    $input.val('');
    // Quitar el handler de pegado de identidad; se re-agrega solo si aplica.
    $input.off('paste.mascaraIdentidad');

    if (tipo === 'identidad') {
        // Solo aquí se aplica la máscara — misma del módulo Editar Pacientes
        mascaraIdentidadInstance = Inputmask({
            regex: typeof regexIdentidad !== 'undefined'
                ? regexIdentidad
                : "^([0-3][0-9])([0-9][0-9])-(1|2)[0-9]{3}-[0-9]{5}$",
            placeholder: typeof formatoIdentidad !== 'undefined'
                ? formatoIdentidad
                : "____-____-_____",
            showMaskOnHover: false,
        });
        mascaraIdentidadInstance.mask(inputDom);
        $input.attr('placeholder', 'Ingrese identidad: ____-____-_____');

        // Al PEGAR: tomar solo los dígitos y dejar que la máscara los formatee.
        // Sin esto, pegar una identidad con guiones/espacios dejaba el campo con
        // caracteres sueltos y no dejaba buscar. Evento con namespace para no
        // acumular handlers al recrear la máscara.
        $input.off('paste.mascaraIdentidad').on('paste.mascaraIdentidad', function (e) {
            e.preventDefault();
            const cb = (e.originalEvent || e).clipboardData || window.clipboardData;
            const digitos = ((cb && cb.getData('text')) || '').replace(/\D/g, '');
            if (inputDom.inputmask) {
                inputDom.inputmask.setValue(digitos);
            } else {
                inputDom.value = digitos;
            }
        });
    } else if (tipo === 'nombre') {
        // Input libre, sin máscara
        $input.attr('placeholder', 'Ingrese nombre o apellido del paciente...');
    } else {
        // Input libre, sin máscara
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

    if (tipo === 'identidad') {
        // Solo dígitos: robusto ante lo pegado (guiones, espacios) y los
        // placeholders "_" de la máscara. El backend busca por dígitos.
        query = query.replace(/\D/g, '');
        if (query.length < 6) {
            toastr.warning('Ingrese al menos 6 dígitos de la identidad');
            return;
        }
    } else {
        query = query.trim();
    }

    if (!query) {
        toastr.warning('Ingrese un criterio de búsqueda');
        return;
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
            const dataItem = JSON.stringify(item).replace(/"/g, '&quot;');
            botonHtml = `<button type="button" class="sexp-add-btn" data-item="${dataItem}" data-exp-id="${item.expediente_id}" onclick="agregarAlCarrito(JSON.parse(this.getAttribute('data-item')))">
                <i class="bi bi-plus-circle"></i> Agregar
            </button>`;
        } else if (enCarrito) {
            botonHtml = '<span class="sexp-badge--en-carrito"><i class="bi bi-check-circle"></i> Seleccionado</span>';
        } else {
            botonHtml = '<button type="button" class="sexp-add-btn" disabled>No disponible</button>';
        }

        // Display: "Identidad - Nombre" como título principal
        const identidad = item.paciente_dni || 'Sin identidad';
        const nombre = item.paciente_nombre || 'Sin paciente asignado';

        html += `
        <div class="sexp-resultado sexp-resultado--card" data-exp-id="${item.expediente_id}">
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

    // Actualizar SOLO el botón del item agregado (sin re-fetch que causa "refresh")
    const $card = $(`.sexp-resultado[data-exp-id="${item.expediente_id}"]`);
    if ($card.length) {
        $card.find('.sexp-add-btn').replaceWith(
            '<span class="sexp-badge--en-carrito"><i class="bi bi-check-circle"></i> Seleccionado</span>'
        );
    }

    toastr.success(`Expediente agregado: ${item.paciente_dni || ''} - ${item.paciente_nombre || ''}`);

    document.getElementById('busqueda-input').inputmask.setValue('');
    document.getElementById('busqueda-input').focus();

}


function removerDelCarrito(expediente_id) {
    carrito = carrito.filter(c => c.expediente_id !== expediente_id);
    renderCarrito();
    const tipoActual = $('#tipo-busqueda').val();
    let queryActual = $('#busqueda-input').val();
    queryActual = (tipoActual === 'identidad' ? queryActual.replace(/_/g, '') : queryActual).trim();
    if (queryActual) buscarExpedientes();
}


function renderCarrito() {
    const container = $('#carrito-items');
    const count = $('#carrito-count');
    const form = $('#carrito-form');

    count.text(carrito.length);

    if (!carrito.length) {
        container.removeClass('sexp-carrito-grid');
        container.html('<div class="sexp-carrito-empty"><i class="bi bi-folder-x" style="font-size:1.4rem;"></i><br>No hay expedientes seleccionados</div>');
        form.hide();
        return;
    }

    // Aplicar grid responsivo de 3 columnas al contenedor
    container.addClass('sexp-carrito-grid');

    let html = '';
    carrito.forEach(function (item) {
        const identidad = item.paciente_dni || 'Sin ID';
        const nombre = item.paciente_nombre || 'N/A';
        html += `
        <div class="sexp-carrito-item">
            <div class="sexp-carrito-item-info">
                <strong class="sexp-carrito-item-id">${identidad}</strong>
                <span class="sexp-carrito-item-nombre">${nombre}</span>
                <span class="sexp-carrito-item-exp">Expediente #${item.numero_expediente}</span>
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

    // Validar y obtener el tiempo sugerido (si aplica)
    let tiempoSugeridoHoras = null;
    try {
        tiempoSugeridoHoras = _obtenerTiempoSugeridoHoras();
    } catch (err) {
        toastr.warning(err.message);
        return;
    }

    // Texto legible del tiempo sugerido para el modal
    let tiempoSugeridoTexto = '';
    if (tiempoSugeridoHoras !== null) {
        const cuando = $('#solicitud-tiempo-cuando').val();
        const unidad = $('#solicitud-tiempo-unidad').val();
        const valor = parseInt($('#solicitud-tiempo-valor').val(), 10);
        const unidadTxt = (cuando === 'hoy' || unidad === 'horas')
            ? (valor === 1 ? 'hora' : 'horas')
            : (valor === 1 ? 'día' : 'días');
        const cuandoTxt = cuando === 'hoy' ? 'mismo día' : 'días posteriores';
        tiempoSugeridoTexto = `<p class="sexp-modal-resumen"><strong>Tiempo sugerido:</strong> ${valor} ${unidadTxt} (${cuandoTxt})</p>`;
    }

    // Listado de todos los expedientes — grid responsivo de columnas con tipografía uniforme
    const itemsHtml = carrito
        .map(c => `<div class="sexp-modal-item">
            <span class="sexp-modal-item-id">${c.paciente_dni || 'S/ID'}</span>
            <span class="sexp-modal-item-nombre">${c.paciente_nombre || 'N/A'}</span>
            <span class="sexp-modal-item-exp">Expediente #${c.numero_expediente}</span>
        </div>`)
        .join('');

    const mensaje = `
        <div class="sexp-modal-confirm">
            <p class="sexp-modal-resumen">
                Está a punto de solicitar <strong>${carrito.length}</strong> expediente(s).
            </p>
            <p class="sexp-modal-resumen"><strong>Motivo:</strong> ${motivoText}</p>
            ${tiempoSugeridoTexto}
            <div class="sexp-modal-lista-grid">${itemsHtml}</div>
            <p class="sexp-modal-resumen">¿Desea continuar?</p>
        </div>`;

    // Modal con styling del sistema (light/dark) pero más ancho y texto más grande
    const resultado = await Swal.fire({
        title: 'Confirmar Solicitud',
        html: mensaje,
        icon: 'question',
        width: '95%',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            icon: 'contenedor-modal-icon',
            popup: 'contenedor-modal sexp-modal-grande',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) actionsContainer.classList.add('contener-modal-contenedor-botones');
        }
    });
    const confirmado = resultado.isConfirmed;

    if (!confirmado) return;

    $.ajax({
        url: window.urls.s_exp_crear_solicitud_api,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify({
            expedientes: carrito.map(c => c.expediente_id),
            motivo_id: parseInt(motivoId),
            observaciones: obs || '',
            tiempo_sugerido_horas: tiempoSugeridoHoras
        }),
        success: function (resp) {
            toastr.success(resp.mensaje || 'Solicitud enviada correctamente');
            carrito = [];
            renderCarrito();
            $('#solicitud-motivo').val('');
            $('#solicitud-observaciones').val('');
            $('#solicitud-sugerir-tiempo').prop('checked', false);
            $('#sugerir-tiempo-panel').hide();
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
