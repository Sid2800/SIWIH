document.addEventListener('DOMContentLoaded', function () {
    // Django conserva los filtros y DataTables adapta las cinco columnas.
    const tabla = document.querySelector('.equipos-garantias__tabla');
    const hayEquipos = tabla && tabla.querySelector('.equipos-listado__fila');

    if (hayEquipos && window.jQuery && $.fn && $.fn.DataTable) {
        const tablaDatos = $(tabla).DataTable({
            responsive: {
                details: {
                    type: 'inline',
                    target: 0
                }
            },
            paging: false,
            searching: false,
            info: false,
            ordering: false,
            autoWidth: false,
            columnDefs: [
                { targets: 0, className: 'dtr-control', responsivePriority: 1 },
                { targets: 2, responsivePriority: 2 },
                { targets: 1, responsivePriority: 3 },
                { targets: 3, responsivePriority: 4 },
                { targets: 4, responsivePriority: 5 }
            ],
            language: {
                emptyTable: 'No hay garantías que mostrar',
                zeroRecords: 'No hay garantías que mostrar'
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

    document.querySelectorAll(
        '.equipos-listado__fila--editable[data-edit-url]'
    ).forEach(function (fila) {
        fila.addEventListener('dblclick', function (event) {
            if (event.target.closest('a, button, input, select, textarea, label')) {
                return;
            }

            window.location.href = fila.dataset.editUrl;
        });
    });
});
