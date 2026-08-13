document.addEventListener('DOMContentLoaded', function () {
    // Django resuelve filtros y paginacion. DataTables solo adapta columnas.
    const tabla = document.querySelector('.equipos-listado__tabla');
    const hayEquipos = tabla && tabla.querySelector('.equipos-listado__fila');

    if (hayEquipos && window.jQuery && $.fn && $.fn.DataTable) {
        const tablaDatos = $(tabla).DataTable({
            responsive: true,
            paging: false,
            searching: false,
            info: false,
            ordering: false,
            autoWidth: false,
            columnDefs: [
                { targets: 0, className: 'dtr-control', orderable: false },
                { targets: 8, className: 'all' },
                { targets: 1, responsivePriority: 1 },
                { targets: 7, responsivePriority: 2 },
                { targets: 2, responsivePriority: 3 },
                { targets: 6, responsivePriority: 4 },
                { targets: 3, responsivePriority: 5 },
                { targets: 4, responsivePriority: 6 },
                { targets: 5, responsivePriority: 7 }
            ],
            language: {
                emptyTable: 'No hay equipos que mostrar',
                zeroRecords: 'No hay equipos que mostrar'
            }
        });

        let recalculoPendiente;

        function recalcularTabla() {
            clearTimeout(recalculoPendiente);
            recalculoPendiente = setTimeout(function () {
                tablaDatos.columns.adjust().responsive.recalc();
            }, 150);
        }

        window.addEventListener('resize', recalcularTabla);
        window.addEventListener('orientationchange', recalcularTabla);
    }

    const menusAcciones = document.querySelectorAll(
        '.equipos-listado__acciones-menu'
    );
    const filasEditables = document.querySelectorAll(
        '.equipos-listado__fila--editable[data-edit-url]'
    );

    function cerrarMenus(excepto) {
        menusAcciones.forEach(function (menu) {
            if (menu !== excepto) {
                menu.removeAttribute('open');
            }
        });
    }

    menusAcciones.forEach(function (menu) {
        menu.addEventListener('toggle', function () {
            if (menu.open) {
                cerrarMenus(menu);
            }
        });
    });

    document.addEventListener('click', function (event) {
        if (!event.target.closest('.equipos-listado__acciones-menu')) {
            cerrarMenus();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            cerrarMenus();
        }
    });

    filasEditables.forEach(function (fila) {
        fila.addEventListener('dblclick', function (event) {
            if (event.target.closest(
                'a, button, input, select, textarea, summary, details, label, '
                + '.equipos-listado__acciones-menu, .equipos-listado__acciones'
            )) {
                return;
            }

            window.location.href = fila.dataset.editUrl;
        });
    });
});
