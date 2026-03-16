// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

    const API_URLS = {
        listarEvalucionesrxAPI: urls["listarEvalucionesrxAPI"],
        agregarEvaluacionrx: urls["agregarEvaluacionrx"],
        editarEvaluacionrx: urls["editarEvaluacionrx"],
    };

    const commonOptions = {
        responsive: true,
        processing: true,
        serverSide: true,
        lengthMenu: [10, 25, 50, 100],
        select: {
        style: 'single'  // Permitir solo la selección de una fila a la vez
        },
        language: { // mensajes ene español
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 pacientes",
        infoFiltered: "(filtrado de _MAX_)",
        search: "Buscar:",
        paginate: {
        first: "<<",
        last: ">>",
        next: ">",
        previous: "<",
        },
        loadingRecords: "Cargando...",
        processing: "Procesando...",
        emptyTable: "No hay datos disponibles en la tabla",
    },
    dom: '<"superior "B<"fechasfiltro">>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: [
        
        {
        text: '<i class="bi bi-plus-square boton-exportacion"></i>',  // Icono o texto para el botón
        titleAttr: 'Nueva Evaluacion',
        action: function ( e, dt, button, config ) {
            window.location.href = API_URLS.agregarEvaluacionrx;
        }
        },
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Evaluacion',
        action: function ( e, dt, button, config ) {
            editarEvaluacion();
    
        }
        }, 
        {
        text: '<i class="bi bi-dash-circle boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Inactivar Ingreso',
        action: async function ( e, dt, button, config ) {
            await inactivarEvaluacionDatatable();
    
        }
        }, 
        {
        extend: 'excelHtml5',
        titleAttr: 'Exportar a Excel',
        title: 'Pacientes',
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: { columns: ':visible' },
        }, 
    ],
    
    };

    const evaluacionrxColumnas = [
        {
                        data: "id",
                        responsivePriority: 1,
                    },
                    {
                        data: "fecha",
                        title: "Fecha",
                        responsivePriority: 3,
                        render: function (data) {
                            let fecha = data ? formatearFechaYYYYMMDD_a_DDMMYYYY(data) : "---";
                            return `${fecha}`;
                        },
                    },
                    {
                        data: null,
                        render: function (data) {
                            if (data && data.nombre_dependencia && data.tipo_dependencia) {
                                return `${data.nombre_dependencia} <small class="text-muted">(${data.tipo_dependencia})</small>`;
                            }
                            return "---";
                        }
                    },
                    {
                        data: "maquinarx__descripcion_maquina",
                    },
                    {
                        data: "total_estudios"
                    },
                    {
                        data: "paciente__expediente_numero",
                        render: function (data) {
                            return data ? data.toString().padStart(6, '0') : "---";
                        }
                    },
                    {
                        data: null,
                        render: function (data) {
                            // Usamos DNI de paciente interno si existe
                            if (data && data.paciente__dni) {
                                return data.paciente__dni.substring(0, 13);
                            }
                            // Sino usamos DNI de paciente externo si existe
                            if (data && data.paciente_externo__dni) {
                                return data.paciente_externo__dni.substring(0, 13);
                            }
                            return "---";
                        }
                    },
                    {
                        data: null,
                        responsivePriority: 2,
                        render: function (data) {
                            if (data) {
                                // Primero intentamos con paciente interno
                                let nombre = concatenarLimpio(
                                    data.paciente__primer_nombre,
                                    data.paciente__segundo_nombre,
                                    data.paciente__primer_apellido,
                                    data.paciente__segundo_apellido
                                );

                                // Si el nombre interno está vacío o nulo, usamos paciente externo
                                if (!nombre || nombre.trim() === "") {
                                    nombre = concatenarLimpio(
                                        data.paciente_externo__primer_nombre,
                                        data.paciente_externo__segundo_nombre,
                                        data.paciente_externo__primer_apellido,
                                        data.paciente_externo__segundo_apellido
                                    );
                                }

                                return nombre ? nombre.substring(0, 30) : "---";
                            }
                            return "---";
                        }
                    },
                    {
                        data: "fecha_modificado",
                        render: function (data) {
                            let fecha = data ? formatFecha(data) : "---";
                            return `<span>📅 ${fecha}</span>`;
                        },
                    },
    ];


    let table;
    const initDataTable = (tableId, ajaxUrl, columns) => {
        if (document.getElementById(tableId)) {

            // Inicialización de la tabla
            table = $(`#${tableId}`).DataTable({
                ...commonOptions,
                ajax: {
                    url: ajaxUrl,
                    type: 'GET',
                    data: function(d) {
                        d.search_value = document.getElementById('busquedaListadoEvaluacionrx')?.value || '';
                        d.search_column = document.getElementById('column-selector')?.value || '';
                        d.fecha_inicio = document.getElementById('fechaInicio')?.value || '';
                        d.fecha_fin = document.getElementById('fechaFin')?.value || '';
                    }
                },
                columns: columns,
                columnDefs: [
                    { targets: 0, className: 'PrimerColumnaAliIzq' },
                    { targets: 1, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 3, className: 'ColumnaCantCorta' },
                    { targets: 4, className: 'ColumnaCantCorta' },
                    { targets: 6, className: 'ColumnaDNI' },
                    { targets: 7, className: 'ColumnaNombre' },

                ],
                order: [[8, "desc"]],
            });

            const hoyDate = new Date();
            const hace30DiasDate = new Date();
            hace30DiasDate.setDate(hoyDate.getDate() - 30);

            const hoy = hoyDate.toISOString().split('T')[0];
            const hace30Dias = hace30DiasDate.toISOString().split('T')[0];

            const fechasFiltro = document.querySelector('.fechasfiltro');

            // Label y input fecha inicio
            const label1 = document.createElement('label');
            label1.textContent = "Fecha Ini";
            label1.htmlFor = 'fechaInicio';
            fechasFiltro.appendChild(label1);

            const inputFecha1 = document.createElement('input');
            inputFecha1.type = 'date';
            inputFecha1.id = 'fechaInicio';
            inputFecha1.name = 'fechaInicio';
            inputFecha1.className = 'formularioCampo-date';
            inputFecha1.value = hace30Dias;
            fechasFiltro.appendChild(inputFecha1);

            // Label y input fecha fin
            const label2 = document.createElement('label');
            label2.textContent = "Fecha Fin";
            label2.htmlFor = 'fechaFin';
            fechasFiltro.appendChild(label2);

            const inputFecha2 = document.createElement('input');
            inputFecha2.type = 'date';
            inputFecha2.id = 'fechaFin';
            inputFecha2.name = 'fechaFin';
            inputFecha2.className = 'formularioCampo-date';
            inputFecha2.value = hoy;
            fechasFiltro.appendChild(inputFecha2);

            // Select búsqueda rápida
            const select = document.createElement('select');
            select.id = 'column-selector';
            select.className = 'formularioCampo-select';

            const defaultOption = document.createElement('option');
            defaultOption.value = '0';
            defaultOption.textContent = 'Numero';
            select.appendChild(defaultOption);

            const opciones = [
                { value: '1', text: 'Expediente' },
                { value: '2', text: 'Identidad' },
                { value: '3', text: 'Nombre' }
            ];

            opciones.forEach(op => {
                const option = document.createElement('option');
                option.value = op.value;
                option.textContent = op.text;
                select.appendChild(option);
            });

            fechasFiltro.appendChild(select);

            // Input de texto para búsqueda
            const inputBusqueda = document.createElement('input');
            inputBusqueda.type = 'text';
            inputBusqueda.id = 'busquedaListadoEvaluacionrx';
            inputBusqueda.name = 'busquedaListadoEvaluacionrx';
            inputBusqueda.className = 'formularioCampo-text';
            inputBusqueda.placeholder = 'Busqueda';
            fechasFiltro.appendChild(inputBusqueda);

            // Botón de búsqueda
            const buscarBtn = document.createElement('a');
            buscarBtn.id = 'buscarBtn';
            buscarBtn.className = 'formularioBotones-boton';
            buscarBtn.innerHTML = '<i class="bi bi-search"></i><span>Buscar</span>';
            document.querySelector('.superior').appendChild(buscarBtn);

            buscarBtn.addEventListener('click', function () {
                table.ajax.reload();
            });

            // Selección de fila al hacer clic
            table.on('click', 'tbody tr', (e) => {
                let classList = e.currentTarget.classList;
                if (classList.contains('child')) return;
                if (classList.contains('selected')) {
                    classList.remove('selected');
                } else {
                    table.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                    classList.add('selected');
                }
            });
            

            // Doble clic en fila para redirección
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                if (data) {
                    
                    const id = data.id;
                    let nombreSlug = slugify(
                        `${data.paciente__primer_nombre}-${data.paciente__primer_apellido}`
                    ).substring(0, 30);
                    var editarUrl = API_URLS.editarEvaluacionrx.replace('0', id).replace('slug', nombreSlug);
                    window.location.href = editarUrl;
                }
            });

            

            // ==== Atajos de teclado (comentados) ====

            
            // Escucha para el atajo Ctrl + 1
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '1') {
                    event.preventDefault();
                    window.location.href = API_URLS.agregarEvaluacionrx;
                }
            });
            
            
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    event.preventDefault();
                    editarEvaluacion();
                }
            });

            /*
            // Escucha para el atajo Ctrl + 3
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '3') {
                    event.preventDefault();
                    //imprimirIngreso();
                }
            });
            */

        }
    };
    // Inicializar tabla de evaluacionrx
    initDataTable("data_table_evaluacionrx", API_URLS.listarEvalucionesrxAPI, evaluacionrxColumnas);


    function editarEvaluacion(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
                
                let nombreSlug = slugify(
                    `${selectedRow.paciente__primer_nombre}-${selectedRow.paciente__primer_apellido}`
                ).substring(0, 30);
                
            var editarUrl = API_URLS.editarEvaluacionrx.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    async function inactivarEvaluacionDatatable(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
            if (!selectedRow.id) return;

            const titulo = `Desactivar evaluacion`;
            const mensaje = `¿ Realmente desea desactivar la evaluacion, es un proceso irreversible ?`;

            const resultado = await confirmarAccion(titulo, mensaje);
            if (!resultado) return;

            try {
                
                const inactivo = await inactivarEvalucionRX(selectedRow.id);
                if (table && inactivo){
                    window.location.reload();
                }
                else{
                    return;
                }
            } catch (error) {
                console.error("Error al procesar la desactivacion:", error);
            }
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

});