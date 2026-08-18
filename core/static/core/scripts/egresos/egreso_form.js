/**
 * Formulario de egreso (HC-13).
 *
 * Arriba, los datos de ingreso en solo lectura (incluyen edad y sexo del
 * paciente). Debajo, lo que Estadística completa de la hoja: diagnósticos de
 * ingreso/egreso (CIE10), causa/lugar de accidente, egreso de (servicio/sala +
 * fecha y hora), procedimientos quirúrgicos, condición/razón de egreso, referido
 * a, autopsia y los datos del producto del embarazo.
 *
 * El área del censo y el N.º correlativo NO se capturan aquí (van en el reporte
 * Excel). Edad y sexo son datos del paciente y se muestran solo como referencia.
 */
$(document).ready(function () {
    cargarServicios().then(cargarDatos);

    $('#eg-fecha-ingreso, #eg-fecha-egreso').on('change', calcularDias);
    $('#eg-egr-servicio').on('change', function () { cargarSalas($(this).val()); });

    $('.egresos-btn-add').on('click', function () { agregarFilaDiag($(this).data('tipo'), {}); });
    $('#eg-proc-add').on('click', function () { agregarFilaProc({}); });
    $('#eg-prod-add').on('click', function () { agregarFilaProd({}); });

    $('#eg-guardar').on('click', guardar);
});

// ---- Catálogos ----------------------------------------------------------
function cargarServicios() {
    return $.ajax({ url: window.urls.egresos_servicios_api, method: 'GET' })
        .then(function (resp) {
            const $sel = $('#eg-egr-servicio');
            $sel.empty().append('<option value="">— Servicio —</option>');
            (resp.data || []).forEach(s =>
                $sel.append(`<option value="${s.id}">${s.nombre_servicio}</option>`));
        });
}

/** Carga las salas de un servicio; opcionalmente selecciona una. Devuelve promesa. */
function cargarSalas(servicioId, salaSel) {
    const $sel = $('#eg-egr-sala');
    $sel.empty().append('<option value="">— Sala —</option>');
    if (!servicioId) return $.Deferred().resolve().promise();
    return $.ajax({ url: window.urls.egresos_salas_api, method: 'GET', data: { servicio_id: servicioId } })
        .then(function (resp) {
            (resp.data || []).forEach(s =>
                $sel.append(`<option value="${s.id}">${s.nombre_sala}</option>`));
            if (salaSel) $sel.val(salaSel);
        });
}

// ---- Precarga -----------------------------------------------------------
function cargarDatos() {
    $.ajax({ url: window.urls_egreso.datos, method: 'GET', cache: false })
        .done(function (resp) {
            const p = resp.paciente || {};
            const ing = resp.ingreso || {};
            const det = resp.detalle || {};

            // Datos de ingreso (solo lectura).
            $('#eg-expediente').val(det.numero_expediente ? '#' + det.numero_expediente : '—');
            $('#eg-identidad').val(p.identidad || '');
            $('#eg-nombre').val(p.nombre || '');
            $('#eg-fnac').val(p.fecha_nacimiento || '');
            $('#eg-edad-ing').val(p.edad != null ? p.edad : '');
            $('#eg-sexo-ing').val(p.sexo === 'H' ? 'Hombre' : (p.sexo === 'M' ? 'Mujer' : ''));
            $('#eg-tel').val(p.telefono || '');
            $('#eg-ecivil').val(p.estado_civil || '');
            $('#eg-ocup').val(p.ocupacion || '');
            $('#eg-fing').val(ing.fecha_ingreso || '');
            $('#eg-hing').val(ing.hora_ingreso || '');
            $('#eg-serv-ing').val(ing.servicio || '');
            $('#eg-sala-ing').val(ing.sala || '');
            $('#eg-cama').val(ing.cama || '');

            const eg = resp.egreso;
            if (eg) { prefillEgreso(eg, ing); }
            else { nuevoEgreso(ing); }
            calcularDias();
        })
        .fail(function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los datos';
            toastr.error(err);
        });
}

function nuevoEgreso(ing) {
    $('#eg-fecha-ingreso').val(ing.fecha_ingreso || '');
    $('#eg-fecha-egreso').val(hoyISO());
    $('#eg-autopsia').val('no');       // autopsia por defecto NO
    $('#eg-en-censo').prop('checked', true);
    agregarFilaDiag('INGRESO', {});
    agregarFilaDiag('EGRESO', {});
}

function prefillEgreso(eg, ing) {
    $('#eg-pagina').val(eg.pagina || '');
    $('#eg-causa').val(eg.causa_accidente || '');
    $('#eg-lugar').val(eg.lugar_accidente || '');
    $('#eg-egr-servicio').val(eg.egreso_servicio_id || '');
    cargarSalas(eg.egreso_servicio_id, eg.egreso_sala_id);
    $('#eg-fecha-egreso').val(eg.fecha_egreso || '');
    $('#eg-hora-egreso').val(eg.hora_egreso || '');
    $('#eg-fecha-ingreso').val(eg.fecha_ingreso || ing.fecha_ingreso || '');
    $('#eg-cond-num').val(eg.condicion_egreso_num != null ? eg.condicion_egreso_num : '');
    $('#eg-razon-num').val(eg.razon_egreso_num != null ? eg.razon_egreso_num : '');
    $('#eg-referido-id').val(eg.referido_institucion_id || '');
    $('#eg-referido').val(eg.referido_institucion_nombre || '');
    $('#eg-autopsia').val(eg.autopsia ? 'si' : 'no');
    $('#eg-en-censo').prop('checked', !!eg.en_censo);
    $('#eg-comentario').val(eg.comentario || '');

    // Diagnósticos.
    const diags = eg.diagnosticos || [];
    const dIng = diags.filter(d => d.tipo === 'INGRESO');
    const dEgr = diags.filter(d => d.tipo === 'EGRESO');
    (dIng.length ? dIng : [{}]).forEach(d => agregarFilaDiag('INGRESO', d));
    (dEgr.length ? dEgr : [{}]).forEach(d => agregarFilaDiag('EGRESO', d));

    // Procedimientos y productos.
    (eg.procedimientos_quirurgicos || []).forEach(agregarFilaProc);
    (eg.productos_embarazo || []).forEach(agregarFilaProd);
}

// ---- Días de estancia ---------------------------------------------------
function calcularDias() {
    const fi = $('#eg-fecha-ingreso').val();
    const fe = $('#eg-fecha-egreso').val();
    if (fi && fe) {
        const dias = Math.round((new Date(fe) - new Date(fi)) / 86400000);
        $('#eg-dias').val(isNaN(dias) ? '' : dias);
    } else { $('#eg-dias').val(''); }
}

// ---- Filas dinámicas ----------------------------------------------------
function _clonar(tplId, filaSel) {
    return $(document.getElementById(tplId).content.cloneNode(true).querySelector(filaSel));
}

function agregarFilaDiag(tipo, d) {
    const $f = _clonar('eg-diag-tpl', '.egresos-diag-fila');
    $f.attr('data-tipo', tipo);
    $f.find('.egresos-diag-codigo').val(d.codigo || '');
    $f.find('.egresos-diag-desc').val(d.descripcion || '');
    $(tipo === 'INGRESO' ? '#eg-diag-ingreso' : '#eg-diag-egreso').append($f);
}

function agregarFilaProc(pq) {
    const $f = _clonar('eg-proc-tpl', '.egresos-proc-fila');
    $f.find('.egresos-proc-dia').val(pq.dia || '');
    $f.find('.egresos-proc-mes').val(pq.mes || '');
    $f.find('.egresos-proc-anio').val(pq.anio || '');
    $f.find('.egresos-proc-codigo').val(pq.codigo || '');
    $f.find('.egresos-proc-desc').val(pq.descripcion || '');
    $('#eg-proc-lista').append($f);
}

function agregarFilaProd(pe) {
    const $f = _clonar('eg-prod-tpl', '.egresos-prod-fila');
    $f.find('.egresos-prod-sexo').val(pe.sexo || '');
    $f.find('.egresos-prod-cond').val(pe.condicion || '');
    $f.find('.egresos-prod-peso').val(pe.peso_gramos != null ? pe.peso_gramos : '');
    $('#eg-prod-lista').append($f);
}

// Quitar filas (diagnóstico conserva una por grupo; proc/prod pueden quedar en cero).
$(document).on('click', '.egresos-diag-quitar', function () {
    const $lista = $(this).closest('.egresos-diag-lista');
    $(this).closest('.egresos-diag-fila').remove();
    if ($lista.children('.egresos-diag-fila').length === 0) {
        agregarFilaDiag($lista.attr('id') === 'eg-diag-ingreso' ? 'INGRESO' : 'EGRESO', {});
    }
});
$(document).on('click', '.egresos-fila-quitar', function () {
    $(this).closest('.egresos-proc-fila, .egresos-prod-fila').remove();
});

// ---- Autocompletado CIE10 (por fila) ------------------------------------
let _cieTimer = null;
$(document).on('input', '.egresos-diag-codigo', function () {
    const $input = $(this);
    const $sug = $input.siblings('.egresos-diag-sugerencias');
    const q = ($input.val() || '').trim();
    clearTimeout(_cieTimer);
    if (q.length < 2) { $sug.hide().empty(); return; }
    _cieTimer = setTimeout(function () {
        $.ajax({ url: window.urls.egresos_buscar_cie10_api, method: 'GET', data: { q: q } })
            .done(function (resp) {
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

// ---- Autocompletado de institución (Referido a) -------------------------
let _instTimer = null;
$('#eg-referido').on('input', function () {
    const q = ($(this).val() || '').trim();
    $('#eg-referido-id').val('');   // al reescribir, se invalida la selección previa
    const $sug = $('#eg-referido-sug');
    clearTimeout(_instTimer);
    if (q.length < 2) { $sug.hide().empty(); return; }
    _instTimer = setTimeout(function () {
        $.ajax({ url: window.urls.egresos_buscar_institucion_api, method: 'GET', data: { q: q } })
            .done(function (resp) {
                const items = resp.data || [];
                if (!items.length) { $sug.hide().empty(); return; }
                $sug.html(items.map(it =>
                    `<div class="egresos-diag-sug" data-id="${it.id}"
                          data-nombre="${(it.nombre_institucion_salud || '').replace(/"/g, '&quot;')}">
                        ${it.nombre_institucion_salud}
                     </div>`).join('')).show();
            });
    }, 250);
});
$(document).on('click', '#eg-referido-sug .egresos-diag-sug', function () {
    $('#eg-referido-id').val($(this).data('id'));
    $('#eg-referido').val($(this).data('nombre'));
    $('#eg-referido-sug').hide().empty();
});
$(document).on('click', function (e) {
    if (!$(e.target).closest('.egresos-diag-buscador, .egresos-inst-campo').length) {
        $('.egresos-diag-sugerencias').hide().empty();
    }
});

// ---- Recolección y guardado ---------------------------------------------
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

function recogerProcedimientos() {
    const procs = [];
    let orden = 1;
    $('#eg-proc-lista .egresos-proc-fila').each(function () {
        const $f = $(this);
        const codigo = ($f.find('.egresos-proc-codigo').val() || '').trim();
        const desc = ($f.find('.egresos-proc-desc').val() || '').trim();
        const dia = $f.find('.egresos-proc-dia').val();
        const mes = $f.find('.egresos-proc-mes').val();
        const anio = $f.find('.egresos-proc-anio').val();
        if (!codigo && !desc && !dia && !mes && !anio) return;
        procs.push({ orden: orden++, dia: dia || null, mes: mes || null, anio: anio || null, codigo: codigo, descripcion: desc });
    });
    return procs;
}

function recogerProductos() {
    const prods = [];
    let numero = 1;
    $('#eg-prod-lista .egresos-prod-fila').each(function () {
        const $f = $(this);
        const sexo = $f.find('.egresos-prod-sexo').val();
        const cond = $f.find('.egresos-prod-cond').val();
        const peso = $f.find('.egresos-prod-peso').val();
        if (!sexo && !cond && !peso) return;
        prods.push({ numero: numero++, sexo: sexo, condicion: cond, peso_gramos: peso || null });
    });
    return prods;
}

function guardar() {
    if (!$('#eg-fecha-egreso').val()) { toastr.warning('La fecha de egreso es obligatoria.'); return; }

    const payload = {
        pagina: $('#eg-pagina').val(),
        causa_accidente: $('#eg-causa').val(),
        lugar_accidente: $('#eg-lugar').val(),
        egreso_servicio_id: $('#eg-egr-servicio').val() || null,
        egreso_sala_id: $('#eg-egr-sala').val() || null,
        fecha_egreso: $('#eg-fecha-egreso').val(),
        hora_egreso: $('#eg-hora-egreso').val(),
        fecha_ingreso: $('#eg-fecha-ingreso').val(),
        condicion_egreso_num: $('#eg-cond-num').val() || null,
        razon_egreso_num: $('#eg-razon-num').val() || null,
        referido_institucion_id: $('#eg-referido-id').val() || null,
        autopsia: $('#eg-autopsia').val(),
        en_censo: $('#eg-en-censo').is(':checked') ? 'si' : 'no',
        comentario: $('#eg-comentario').val(),
        diagnosticos: recogerDiagnosticos(),
        procedimientos_quirurgicos: recogerProcedimientos(),
        productos_embarazo: recogerProductos()
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
