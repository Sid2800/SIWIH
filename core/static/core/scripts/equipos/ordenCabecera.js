/* El buscador de empleados de la cabecera de la orden de trabajo.
 *
 * El jefe que firma la hoja sale de la tabla de empleados, que es el hospital
 * entero. Dibujarla como <option> en cada carga son miles de lineas que el
 * navegador tira de todos modos, asi que el campo nace vacio y Select2 va
 * preguntando conforme se escribe, igual que en el alta de equipos.
 *
 * Si Select2 no estuviera cargado el campo sigue siendo un <select> normal:
 * vacio, pero la orden se puede abrir sin jefe y recoger la firma despues, que
 * es lo que pasa en papel.
 */

(function () {
    'use strict';

    const formulario = document.querySelector('[data-form-orden]');

    if (!formulario || typeof window.jQuery === 'undefined') {
        return;
    }

    const $ = window.jQuery;
    const campo = $('#jefe_servicio_orden');
    const url = formulario.dataset.urlEmpleados;

    if (!campo.length || !campo.select2 || !url) {
        return;
    }

    campo.select2({
        width: '100%',
        placeholder: 'Buscar por DNI o nombre',
        allowClear: true,
        minimumInputLength: 1,
        ajax: {
            url: url,
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return { q: params.term || '' };
            },
            processResults: function (data) {
                return data;
            },
            cache: true
        },
        language: {
            inputTooShort: function () {
                return 'Escriba el DNI o nombre del empleado';
            },
            noResults: function () {
                return 'No se encontraron empleados';
            },
            searching: function () {
                return 'Buscando...';
            }
        }
    });
}());
