/**
 * Captura de Expedientes para Egresos (solo Estadística/staff).
 *
 * Doble lista al estilo de la Recepción SDGI: a la izquierda los ingresos
 * abiertos con expediente disponible, a la derecha los que se van a capturar.
 * Al confirmar se crea un lote y esos expedientes quedan prestados a Estadística.
 *
 * Estado en memoria:
 *   _todos      -> catálogo devuelto por la API (fuente de la verdad)
 *   _idsDerecha -> Set con los expediente_id "Por Capturar"
 *   La selección se conserva aunque se filtre (el filtro solo decide qué se PINTA).
 */
let _todos = [];
const _idsDerecha = new Set();   // expediente_id elegidos
const _selIzq = new Set();       // marcados (resaltados) en la izquierda
const _selDer = new Set();

// Por defecto se cargan los ingresos de AYER (normalmente se llena lo del día anterior).
let _periodo = 'ayer';

// La fecha de referencia solo aplica a semana/mes/año.
function _usaFechaRef(p) { return p === 'semana' || p === 'mes' || p === 'anio'; }

$(document).ready(function () {
    $('#cap-fecha').val(new Date().toLocaleString('es-HN', { hour12: false }));
    // Fecha de referencia por defecto: hoy (oculta salvo semana/mes/año).
    $('#cap-fecha-ref').val(new Date().toISOString().slice(0, 10));
    $('#cap-fecha-ref-cont').hide();
    cargarIngresos();

    // Filtro por período (ayer/hoy/semana/mes/año/rango/todos).
    $('.egresos-periodo').on('click', function () {
        _periodo = $(this).data('periodo');
        $('.egresos-periodo').removeClass('egresos-periodo--activa');
        $(this).addClass('egresos-periodo--activa');
        // Rango muestra desde/hasta; semana/mes/año usan la fecha de referencia.
        $('.egresos-rango-campo').toggle(_periodo === 'rango');
        $('#cap-fecha-ref-cont').toggle(_usaFechaRef(_periodo));
        cargarIngresos();
    });
    $('#cap-fecha-ref, #cap-fecha-desde, #cap-fecha-hasta').on('change', cargarIngresos);

    $('#cap-buscar-izq').on('input', pintarIzquierda);
    $('#cap-filtro-area').on('change', pintarIzquierda);
    $('#cap-buscar-der').on('input', pintarDerecha);

    $('#cap-mover-der').on('click', () => { _selIzq.forEach(id => _idsDerecha.add(id)); _selIzq.clear(); repintar(); });
    $('#cap-mover-izq').on('click', () => { _selDer.forEach(id => _idsDerecha.delete(id)); _selDer.clear(); repintar(); });
    $('#cap-mover-todo-der').on('click', () => { visiblesIzq().forEach(e => _idsDerecha.add(e.expediente_id)); _selIzq.clear(); repintar(); });
    $('#cap-mover-todo-izq').on('click', () => { visibles(seleccionados(), '#cap-buscar-der').forEach(e => _idsDerecha.delete(e.expediente_id)); _selDer.clear(); repintar(); });

    $('#cap-confirmar').on('click', confirmarCaptura);
});

function cargarIngresos() {
    const data = { periodo: _periodo };
    if (_periodo === 'rango') {
        data.desde = $('#cap-fecha-desde').val();
        data.hasta = $('#cap-fecha-hasta').val();
    } else {
        data.fecha = $('#cap-fecha-ref').val();
    }
    $.ajax({
        url: window.urls.egresos_ingresos_para_egreso_api,
        method: 'GET',
        cache: false,
        data: data,
        success: function (resp) {
            // Solo los que tienen expediente y están disponibles se pueden capturar.
            _todos = (resp.data || []).filter(e => e.expediente_id && e.disponible);
            _todos.forEach(e => {
                e._buscar = `${e.identidad || ''} ${e.numero_expediente || ''} ${e.nombre || ''}`.toLowerCase();
            });
            _poblarAreas();
            repintar();
        },
        error: function (xhr) {
            const err = xhr.responseJSON ? xhr.responseJSON.error : 'No se pudieron cargar los ingresos';
            toastr.error(err);
        }
    });
}

/** Llena el filtro de área con las áreas presentes en los ingresos. */
function _poblarAreas() {
    const areas = Array.from(new Set(_todos.map(e => e.area_ingreso).filter(Boolean))).sort();
    const $sel = $('#cap-filtro-area');
    $sel.find('option:not(:first)').remove();
    areas.forEach(a => $sel.append(`<option value="${a.replace(/"/g, '&quot;')}">${a}</option>`));
}

function disponibles() { return _todos.filter(e => !_idsDerecha.has(e.expediente_id)); }
function seleccionados() { return _todos.filter(e => _idsDerecha.has(e.expediente_id)); }

function visibles(lista, selectorInput) {
    const q = ($(selectorInput).val() || '').trim().toLowerCase();
    if (!q) return lista;
    return lista.filter(e => e._buscar.indexOf(q) >= 0);
}

/** Izquierda: aplica buscador + filtro de área. */
function visiblesIzq() {
    let lista = visibles(disponibles(), '#cap-buscar-izq');
    const area = $('#cap-filtro-area').val();
    if (area) lista = lista.filter(e => e.area_ingreso === area);
    return lista;
}

function itemHtml(e, marcado) {
    const s = (t) => (t || '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    const tip = [
        `Exp #${e.numero_expediente} — ${s(e.nombre)}`,
        `Ingreso: ${e.fecha_ingreso || '—'} · Área: ${s(e.area_ingreso)}`,
    ].join('&#10;');
    return `
        <li class="egresos-item${marcado ? ' selected' : ''}" data-id="${e.expediente_id}" title="${tip}">
            <span class="egresos-c egresos-c--exp">#${e.numero_expediente}</span>
            <span class="egresos-c egresos-c--id">${s(e.identidad) || 'S/ID'}</span>
            <span class="egresos-c egresos-c--nom">${s(e.nombre) || 'N/A'}</span>
            <span class="egresos-c egresos-c--ing">${e.fecha_ingreso || '—'}</span>
            <span class="egresos-c egresos-c--area">${s(e.area_ingreso) || '—'}</span>
        </li>`;
}

function pintarIzquierda() {
    const lista = visiblesIzq();
    $('#cap-lista-izq').html(lista.map(e => itemHtml(e, _selIzq.has(e.expediente_id))).join('')
        || '<li class="egresos-vacio">Sin ingresos disponibles</li>');
    $('#cap-total-izq').text(disponibles().length);
    $('#cap-sub-izq').text(lista.length);
}

function pintarDerecha() {
    const lista = visibles(seleccionados(), '#cap-buscar-der');
    $('#cap-lista-der').html(lista.map(e => itemHtml(e, _selDer.has(e.expediente_id))).join('')
        || '<li class="egresos-vacio">Seleccione los expedientes a capturar</li>');
    $('#cap-total-der').text(seleccionados().length);
    $('#cap-sub-der').text(lista.length);
    // Confirmar habilitado solo si hay algo elegido.
    $('#cap-confirmar').prop('disabled', seleccionados().length === 0);
}

function repintar() { pintarIzquierda(); pintarDerecha(); }

// Click = marcar/desmarcar; doble click = mover.
$(document).on('click', '#cap-lista-izq .egresos-item', function () {
    const id = parseInt(this.dataset.id, 10);
    _selIzq.has(id) ? _selIzq.delete(id) : _selIzq.add(id);
    pintarIzquierda();
});
$(document).on('click', '#cap-lista-der .egresos-item', function () {
    const id = parseInt(this.dataset.id, 10);
    _selDer.has(id) ? _selDer.delete(id) : _selDer.add(id);
    pintarDerecha();
});
$(document).on('dblclick', '#cap-lista-izq .egresos-item', function () {
    _idsDerecha.add(parseInt(this.dataset.id, 10)); _selIzq.clear(); repintar();
});
$(document).on('dblclick', '#cap-lista-der .egresos-item', function () {
    _idsDerecha.delete(parseInt(this.dataset.id, 10)); _selDer.clear(); repintar();
});

function confirmarCaptura() {
    const elegidos = seleccionados();
    if (!elegidos.length) { toastr.warning('Seleccione al menos un expediente.'); return; }

    Swal.fire({
        title: '¿Confirmar captura?',
        html: `Se tomarán <strong>${elegidos.length}</strong> expediente(s) y quedarán
               <strong>prestados a Estadística</strong> para llenar sus egresos.`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Sí, capturar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contenedor-modal',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
        },
        didOpen: () => {
            const a = document.querySelector('.swal2-actions');
            if (a) a.classList.add('contener-modal-contenedor-botones');
        }
    }).then(function (result) {
        if (!result.isConfirmed) return;
        $.ajax({
            url: window.urls.egresos_crear_lote_captura_api,
            method: 'POST',
            headers: { 'X-CSRFToken': window.CSRF_TOKEN },
            contentType: 'application/json',
            data: JSON.stringify({
                seleccion: elegidos.map(e => ({ expediente_id: e.expediente_id, paciente_id: e.paciente_id })),
                observaciones: ($('#cap-observaciones').val() || '').trim(),
            }),
            success: function (resp) {
                if (!resp.success) return;
                toastr.success(`${resp.capturados} expediente(s) capturados (lote #${resp.lote_id}). Redirigiendo al llenado…`);
                _idsDerecha.clear(); _selIzq.clear(); _selDer.clear();
                $('#cap-observaciones').val('');
                // Al capturar, se pasa directo a la pantalla de llenado de datos.
                setTimeout(function () {
                    window.location.href = window.urls.egresos_llenado;
                }, 900);
            },
            error: function (xhr) {
                const err = xhr.responseJSON ? xhr.responseJSON.error : 'Error desconocido';
                toastr.error(err);
            }
        });
    });
}
