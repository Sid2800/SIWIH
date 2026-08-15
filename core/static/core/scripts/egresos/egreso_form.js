/**
 * Formulario de egreso (un expediente tomado = un detalle de lote).
 *
 * Precarga los datos del paciente y del ingreso, calcula los días de estancia,
 * muestra los campos de observación solo cuando el área es OA/OP y maneja los
 * diagnósticos ilimitados con búsqueda de CIE10.
 */
const _areasTipo = {};      // area_id -> 'CENSO' | 'OBSERVACION'

$(document).ready(function () {
    cargarAreas().then(cargarDatos);

    $('#eg-fecha-ingreso, #eg-fecha-egreso').on('change', calcularDias);
    $('#eg-area').on('change', toggleObservacion);
    $('#eg-op-codigo').on('blur', clasificarOperacion);

    $('.egresos-btn-add').on('click', function () {
        agregarFilaDiag($(this).data('tipo'), {});
    });

    $('#eg-guardar').on('click', guardar);
});

/** Carga el combobox de áreas. Devuelve una promesa. */
function cargarAreas() {
    return $.ajax({ url: window.urls.egresos_areas_api, method: 'GET' })
        .then(function (resp) {
            const $sel = $('#eg-area');
            $sel.empty().append('<option value="">— Seleccione el área —</option>');
            (resp.data || []).forEach(a => {
                _areasTipo[a.id] = a.tipo;
                $sel.append(`<option value="${a.id}">${a.nombre}</option>`);
            });
        });
}

/** Precarga paciente/ingreso y, si existe, el egreso a editar. */
function cargarDatos() {
    $.ajax({ url: window.urls_egreso.datos, method: 'GET', cache: false })
        .done(function (resp) {
            const p = resp.paciente || {};
            const ing = resp.ingreso || {};
            const det = resp.detalle || {};

            $('#eg-expediente').val(det.numero_expediente ? '#' + det.numero_expediente : '—');
            $('#eg-identidad').val(p.identidad || '');
            $('#eg-nombre').val(p.nombre || '');

            const eg = resp.egreso;
            if (eg) {
                // Edición: se cargan los valores guardados.
                $('#eg-area').val(eg.area_id || '');
                $('#eg-numero').val(eg.numero || '');
                $('#eg-pagina').val(eg.pagina || '');
                $('#eg-fecha-ingreso').val(eg.fecha_ingreso || ing.fecha_ingreso || '');
                $('#eg-fecha-egreso').val(eg.fecha_egreso || '');
                $('#eg-edad').val(eg.edad != null ? eg.edad : (p.edad != null ? p.edad : ''));
                $('#eg-sexo').val(eg.sexo || p.sexo || '');
                $('#eg-condicion').val(eg.condicion || '');
                $('#eg-peso').val(eg.peso_gramos != null ? eg.peso_gramos : '');
                $('#eg-op-codigo').val(eg.operacion_codigo || '');
                $('#eg-op-desc').val(eg.operacion_descripcion || '');
                $('#eg-tipo-ref').val(eg.tipo_referencia || '');
                $('#eg-ref-texto').val(eg.referencia_texto || '');
                $('#eg-epicrisis').val(triStr(eg.epicrisis));
                $('#eg-ir-sala').val(triStr(eg.deberia_ir_sala));
                $('#eg-procedencia').val(eg.procedencia || '');
                $('#eg-en-censo').prop('checked', !!eg.en_censo);
                $('#eg-comentario').val(eg.comentario || '');
                cargarDiagnosticos(eg.diagnosticos || []);
            } else {
                // Nuevo: se prellena con lo que se sabe del paciente/ingreso.
                $('#eg-fecha-ingreso').val(ing.fecha_ingreso || '');
                $('#eg-fecha-egreso').val(hoyISO());
                $('#eg-edad').val(p.edad != null ? p.edad : '');
                $('#eg-sexo').val(p.sexo || '');
                $('#eg-en-censo').prop('checked', true);
                // Filas vacías de arranque.
                agregarFilaDiag('INGRESO', {});
                agregarFilaDiag('EGRESO', {});
            }
            calcularDias();
            toggleObservacion();
        })
        .fail(function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los datos';
            toastr.error(err);
        });
}

function cargarDiagnosticos(diags) {
    const ingreso = diags.filter(d => d.tipo === 'INGRESO');
    const egreso = diags.filter(d => d.tipo === 'EGRESO');
    (ingreso.length ? ingreso : [{}]).forEach(d => agregarFilaDiag('INGRESO', d));
    (egreso.length ? egreso : [{}]).forEach(d => agregarFilaDiag('EGRESO', d));
}

// ---- Días de estancia (automático) --------------------------------------
function calcularDias() {
    const fi = $('#eg-fecha-ingreso').val();
    const fe = $('#eg-fecha-egreso').val();
    if (fi && fe) {
        const dias = Math.round((new Date(fe) - new Date(fi)) / 86400000);
        $('#eg-dias').val(isNaN(dias) ? '' : dias);
    } else {
        $('#eg-dias').val('');
    }
}

// ---- Mostrar campos de observación solo en OA/OP ------------------------
function toggleObservacion() {
    const tipo = _areasTipo[$('#eg-area').val()];
    $('.egresos-solo-observacion').toggle(tipo === 'OBSERVACION');
}

// ---- Clasificar operación por código ------------------------------------
function clasificarOperacion() {
    const codigo = ($('#eg-op-codigo').val() || '').trim();
    if (!codigo) return;
    $.ajax({
        url: window.urls.egresos_buscar_procedimiento_api,
        method: 'GET', data: { codigo: codigo }
    }).done(function (resp) {
        if (resp.data && resp.data.descripcion && !$('#eg-op-desc').val().trim()) {
            $('#eg-op-desc').val(resp.data.descripcion);
        }
    });
}

// ---- Diagnósticos (filas + autocompletado CIE10) ------------------------
function agregarFilaDiag(tipo, datos) {
    const tpl = document.getElementById('eg-diag-tpl');
    const frag = tpl.content.cloneNode(true);
    const $fila = $(frag.querySelector('.egresos-diag-fila'));
    $fila.attr('data-tipo', tipo);
    $fila.find('.egresos-diag-codigo').val(datos.codigo || '');
    $fila.find('.egresos-diag-desc').val(datos.descripcion || '');
    const destino = tipo === 'INGRESO' ? '#eg-diag-ingreso' : '#eg-diag-egreso';
    $(destino).append($fila);
}

$(document).on('click', '.egresos-diag-quitar', function () {
    const $lista = $(this).closest('.egresos-diag-lista');
    $(this).closest('.egresos-diag-fila').remove();
    // Siempre queda al menos una fila por grupo.
    if ($lista.children('.egresos-diag-fila').length === 0) {
        const tipo = $lista.attr('id') === 'eg-diag-ingreso' ? 'INGRESO' : 'EGRESO';
        agregarFilaDiag(tipo, {});
    }
});

// Búsqueda CIE10 (debounced) por fila.
let _cieTimer = null;
$(document).on('input', '.egresos-diag-codigo', function () {
    const $input = $(this);
    const $sug = $input.siblings('.egresos-diag-sugerencias');
    const q = ($input.val() || '').trim();
    clearTimeout(_cieTimer);
    if (q.length < 2) { $sug.hide().empty(); return; }
    _cieTimer = setTimeout(function () {
        $.ajax({
            url: window.urls.egresos_buscar_cie10_api,
            method: 'GET', data: { q: q }
        }).done(function (resp) {
            const items = resp.data || [];
            if (!items.length) { $sug.hide().empty(); return; }
            $sug.html(items.map(it =>
                `<div class="egresos-diag-sug" data-codigo="${it.codigo}"
                      data-desc="${(it.descripcion || '').replace(/"/g, '&quot;')}">
                    <strong>${it.codigo}</strong> ${it.descripcion || ''}
                 </div>`).join('')).show();
        });
    }, 250);
});

$(document).on('click', '.egresos-diag-sug', function () {
    const $fila = $(this).closest('.egresos-diag-fila');
    $fila.find('.egresos-diag-codigo').val($(this).data('codigo'));
    $fila.find('.egresos-diag-desc').val($(this).data('desc'));
    $fila.find('.egresos-diag-sugerencias').hide().empty();
});

// Cerrar sugerencias al hacer clic fuera.
$(document).on('click', function (e) {
    if (!$(e.target).closest('.egresos-diag-buscador').length) {
        $('.egresos-diag-sugerencias').hide().empty();
    }
});

// ---- Guardar ------------------------------------------------------------
function recogerDiagnosticos() {
    const diags = [];
    $('.egresos-diag-lista').each(function () {
        const tipo = $(this).attr('id') === 'eg-diag-ingreso' ? 'INGRESO' : 'EGRESO';
        let orden = 1;
        $(this).find('.egresos-diag-fila').each(function () {
            const codigo = ($(this).find('.egresos-diag-codigo').val() || '').trim();
            const desc = ($(this).find('.egresos-diag-desc').val() || '').trim();
            if (!codigo && !desc) return;
            diags.push({ tipo: tipo, orden: orden++, codigo: codigo, descripcion: desc });
        });
    });
    return diags;
}

function guardar() {
    if (!$('#eg-area').val()) { toastr.warning('Seleccione el área del censo.'); return; }
    if (!$('#eg-fecha-egreso').val()) { toastr.warning('La fecha de egreso es obligatoria.'); return; }

    const payload = {
        area_id: $('#eg-area').val(),
        numero: $('#eg-numero').val() || null,
        pagina: $('#eg-pagina').val(),
        fecha_ingreso: $('#eg-fecha-ingreso').val(),
        fecha_egreso: $('#eg-fecha-egreso').val(),
        edad: $('#eg-edad').val() || null,
        sexo: $('#eg-sexo').val(),
        condicion: $('#eg-condicion').val(),
        peso_gramos: $('#eg-peso').val() || null,
        operacion_codigo: $('#eg-op-codigo').val(),
        operacion_descripcion: $('#eg-op-desc').val(),
        tipo_referencia: $('#eg-tipo-ref').val(),
        referencia_texto: $('#eg-ref-texto').val(),
        epicrisis: $('#eg-epicrisis').val(),
        deberia_ir_sala: $('#eg-ir-sala').val(),
        procedencia: $('#eg-procedencia').val(),
        en_censo: $('#eg-en-censo').is(':checked') ? 'si' : 'no',
        comentario: $('#eg-comentario').val(),
        diagnosticos: recogerDiagnosticos()
    };

    const $btn = $('#eg-guardar').prop('disabled', true);
    $.ajax({
        url: window.urls_egreso.guardar,
        method: 'POST',
        headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        contentType: 'application/json',
        data: JSON.stringify(payload)
    }).done(function (resp) {
        if (!resp.success) { $btn.prop('disabled', false); return; }
        toastr.success(`Egreso guardado (${resp.dias_estancia != null ? resp.dias_estancia + ' días de estancia' : 'sin fechas completas'}).`);
        setTimeout(function () { window.location.href = window.urls.egresos_llenado; }, 800);
    }).fail(function (xhr) {
        $btn.prop('disabled', false);
        const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error al guardar';
        toastr.error(err);
    });
}

// ---- Utilidades ---------------------------------------------------------
function hoyISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function triStr(v) { return v === true ? 'si' : (v === false ? 'no' : ''); }
