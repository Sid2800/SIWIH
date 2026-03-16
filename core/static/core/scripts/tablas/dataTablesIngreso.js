// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

    const API_URLS = {
        listado_ingreso: urls["listadoIngresos"],
        agregar_ingreso: urls["agregarIngreso"],
        editar_ingreso: urls["editarIngreso"],
        
        recibirIngresosSala: urls["recibirIngresosSala"],
        recibirIngresosSDGI: urls["recibirIngresosSDGI"]

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
    //dom: '<"superior"Bf>t<"inferior"lip><"clear">',
    dom: '<"superior "B<"fechasfiltro">>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: [
        
        {
        text: '<i class="bi bi-plus-square boton-exportacion"></i>',  // Icono o texto para el botón
        titleAttr: 'Nuevo Ingreso',
        action: function ( e, dt, button, config ) {
            window.location.href = API_URLS.agregar_ingreso;
        }
        },
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Ingreso',
        action: function ( e, dt, button, config ) {
            editarIngreso();
    
        }
        }, 
        {
        text: '<i class="bi bi-printer boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Imprimir Ingreso',
        action: function ( e, dt, button, config ) {
            imprimirIngreso();
    
        }
        }, 
        {
        text: '<i class="bi bi-dash-circle boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Inactivar Ingreso',
        action: async function ( e, dt, button, config ) {
            await inactivarIngresoDatatable();
    
        }
        }, 
        {
        text: '<i class="bi bi-clipboard-pulse boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Recibir Egresos (Censo)',
            action: function ( e, dt, button, config ) {
                window.location.href = API_URLS.recibirIngresosSala;
            }
        }, 
        {
        text: '<i class="bi bi bi-archive boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Recibir Egresos Estadistica',
            action: function ( e, dt, button, config ) {
                window.location.href = API_URLS.recibirIngresosSDGI;
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

    const ingresoColumnas = [
        {
            data: "id",
            responsivePriority: 1,
        },
        { 
            data: null,
            responsivePriority: 2,
            render: function (data) {
                let fecha = data.fecha_ingreso ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_ingreso) : "---";
                return `${fecha}`;
            },
        },
        { 
            data: null,
            responsivePriority: 3,
            render: function (data) {
                let fecha = data.fecha_egreso ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_egreso) : "---";
                return `${fecha}`;
            },
        },
        { 
            data: null,
            responsivePriority: 4,
            render: function (data) {
                let fecha = data.fecha_recepcion_sdgi ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_recepcion_sdgi) : "---";
                return `${fecha}`;
            },
        },
        {
            data: null,
            render: function (data) {
                if (data) {
                    // Obtenemos el nombre de la sala y lo limitamos a 20 caracteres
                    let sala = data.sala__nombre_sala;
                    sala = sala.substring(0, 21);
                    
                    // Concatenamos la sala truncada con el nombre corto del servicio, usando concatenarLimpio
                    data = concatenarLimpio(sala, "-", data.sala__servicio__nombre_corto);
                }
                return data;
            }
        },
        {
            data: "paciente__expediente_numero",
            render: function (data) {
                if (data) {
                    data = data.toString().padStart(6, '0');
                }
                return data; 
            },
        },
        {
            data: "paciente__dni",
            render: function(data){
                if (data){
                    data = data.substring(0,13);
                }
                else{
                    data ="";
                }
                return data
            }
        },
        {
            data: null,
            render: function (data) {
                if (data){
                    data = concatenarLimpio(
                        data.paciente__primer_nombre,
                        data.paciente__segundo_nombre,
                        data.paciente__primer_apellido,
                        data.paciente__segundo_apellido,);
                        data = data.substring(0, 30);
                }
                return data;
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
                        d.search_value = document.getElementById('busquedaListadoIngreso')?.value || '';
                        d.search_column = document.getElementById('column-selector')?.value || '';
                        d.fecha_inicio = document.getElementById('fechaInicio')?.value || '';
                        d.fecha_fin = document.getElementById('fechaFin')?.value || '';
                    }
                },
                columns: columns,
                columnDefs: [
                    { targets: 0, className: 'PrimerColumnaAliIzq' },
                    { targets: 1, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 2, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 3, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 4, className: 'ColumnaSalaServicioIngreso' },
                    { targets: 6, className: 'ColumnaDNI' },
                ],
                order: [[0, "desc"]],
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
            inputBusqueda.id = 'busquedaListadoIngreso';
            inputBusqueda.name = 'busquedaListadoIngreso';
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

            // Doble clic en fila para redirección
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                if (data) {
                    
                    const id = data.id;
                    let nombreSlug = slugify(
                        `${data.paciente__primer_nombre}-${data.paciente__primer_apellido}`
                    ).substring(0, 30);


                        
                    var editarUrl = API_URLS.editar_ingreso.replace('0', id).replace('slug', nombreSlug);
                    window.location.href = editarUrl;


                }
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

            // ==== Atajos de teclado (comentados) ====

            
            // Escucha para el atajo Ctrl + 1
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '1') {
                    event.preventDefault();
                    window.location.href = API_URLS.agregar_ingreso;
                }
            });
            
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    event.preventDefault();
                    editarIngreso();
                }
            });

            
            // Escucha para el atajo Ctrl + 3
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '3') {
                    event.preventDefault();
                    imprimirIngreso();
                }
            });
            

        }
    };

        // Inicializar tabla de ingresos
    initDataTable("data_table_ingreso", API_URLS.listado_ingreso, ingresoColumnas);

    function editarIngreso(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
                let nombreSlug = slugify(
                    `${selectedRow.paciente__primer_nombre}-${selectedRow.paciente__primer_apellido}`
                ).substring(0, 30);
                
            var editarUrl = API_URLS.editar_ingreso.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    function imprimirIngreso(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
            imprimirHojaHospitalizacion(selectedRow.id);
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    async function inactivarIngresoDatatable(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
            if (!selectedRow.id) return;

            const titulo = `Desactivar ingreso`;
            const mensaje = `¿ Realmente desea desactivar el ingreso, es un proceso irreversible ?`;

            const resultado = await confirmarAccion(titulo, mensaje);
            if (!resultado) return;

            try {
                await inactivarIngreso(selectedRow.id);
                if (table){
                    table.ajax.reload();
                }
            } catch (error) {
                console.error("Error al procesar la solicitud:", error);
            }
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }


});