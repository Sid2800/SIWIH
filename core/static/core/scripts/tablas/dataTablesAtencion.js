// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

    const API_URLS = {
        listado_atencion: urls["listadoAtencion"],
        recibirAtencion: urls["recibirAtencion"],
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
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Atencion',
        action: function ( e, dt, button, config ) {
            verEditarAtencion();
    
        }
        }, 

        {
        text: '<i class="bi bi-clipboard-pulse boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Recibir atenciones',
            action: function ( e, dt, button, config ) {
                window.location.href = API_URLS.recibirAtencion;
            }
        },  
        {
        extend: 'pdfHtml5',
        titleAttr: 'Exportar a PDF',
        text: '<i class="bi bi-file-earmark-pdf boton-exportacion"></i>',
        exportOptions: { columns: ':visible' },
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

    const atencionColumnas = [
        {
            data: "id",
            responsivePriority: 1,
        },
        { 
            data: null,
            responsivePriority: 2,
            render: function (data) {
                let fecha = data.fecha_atencion ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_atencion) : "---";
                return `${fecha}`;
            },
        },
        { 
            data: null,
            responsivePriority: 3,
            render: function (data) {
                let fecha = data.fecha_recepcion ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_recepcion) : "---";
                return `${fecha}`;
            },
        },
        {
            data: null,
            render: function (data) {
                if (data) {
                    let sala = data.especialidad__nombre_especialidad	;
                    sala = sala.substring(0, 21);
                    data = concatenarLimpio(sala, "-", data.especialidad__servicio__nombre_corto);
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
                    //{ targets: 3, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 3, className: 'ColumnaSalaServicioIngreso' },
                    { targets: 5, className: 'ColumnaDNI' },
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
            
            // Doble clic en fila para redirección
            table.on('dblclick', 'tr', function () {
                // Marcar la fila como seleccionada para que verEditarAtencion() funcione igual
                table.$('tr.selected').removeClass('selected');
                $(this).addClass('selected');

                verEditarAtencion();
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

            
            
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    event.preventDefault();
                    verEditarAtencion();
                }
            });

            
            // Escucha para el atajo Ctrl + 3
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '3') {
                    event.preventDefault();
                    //imprimirIngreso();
                }
            });
            

        }
    };


        // Inicializar tabla de ingresos
    initDataTable("data_table_atencion", API_URLS.listado_atencion, atencionColumnas);


    
    async function verEditarAtencion() {
        const selectedRow = table.row('.selected').data();
    
        // Verificar si se ha seleccionado una fila
        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }
        
        let resultado = await AgregarAtencionModal(null,null,selectedRow.id);

        if (resultado?.guardo === true) {
            toastr.info(`Atencion procesada correctamente`, "Cambios realizados");
            setTimeout(() => {
                table.ajax.reload(null, false); // false evita que regrese a la página 1
            }, 500);
            
        } else if (resultado?.guardo === false) {
            toastr.alert(`No se procesó correctamente la atencion`, 'No se guardaron cambios');
        }
    }



    /*    
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
            var URLreporte = API_URLS.reporteHojaHospitalizacion.replace('0', selectedRow.id);
                const nuevaVentana = window.open(URLreporte, "_blank");
                if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                    toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                }
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }
*/

});