// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {
    
    const API_REFERENCIA = {
        listarReferenciasAPI: urls["listarReferenciasAPI"],
        agregarReferencia: urls["agregarReferencia"],
        editarReferencia: urls["editarReferencia"],
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
        infoEmpty: "0 a 0 de 0 refencias",
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
        titleAttr: 'Nueva Referencia',
        action: function ( e, dt, button, config ) {
            window.location.href = API_REFERENCIA.agregarReferencia;
        }
        },
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Referencia',
        action: function ( e, dt, button, config ) {
            editarReferencia();
    
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
        title: 'Refencias',
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: { columns: ':visible' },
        }, 
        {
        text: '<i class="bi bi-printer boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Imprimir Referencia',
        action: function ( e, dt, button, config ) {
            imprimirFormatoReferencia();
        }
        },
        
    ],
    
    };

    const refenciaColumnas = [
            {
                data: "id",
                responsivePriority: 1,
            },
            {
                data: "tipo",
                title: "Tp",
                responsivePriority: 2,
                render: function (data) {
                    if (data == 1) {
                        return `
                            <span title="Enviada" class="DatatableIconoRefenciaEnviada">
                                <i class="bi bi-arrow-up-square-fill"></i>
                            </span>
                        `;
                    } else {
                        return `
                            <span title="Recibida" class="DatatableIconoRefenciaRecibida">
                                <i class="bi bi-arrow-down-square-fill"></i>
                            </span>
                        `;
                    }
                },
            },
            {
                data: "fecha_filtro",
                title: "Fecha",
                responsivePriority: 3,
                render: function (data) {
                    let fecha = data ? formatoFecha_dd_mm_yy_hh_mm(data, false) : "---";
                    return `${fecha}`;
                },
            },
            {
                data: "institucion",
                title: "Institucion Dest/Orig",
            },

            {
                data: "primer_diagnostico",
                title: "Diagnostico",
            },


            {
                data: "paciente__expediente_numero",
                title: "Exp",
                render: function (data) {
                    return data ? data.toString().padStart(6, '0') : "---";
                }
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

                        return nombre ? nombre.substring(0, 30) : "---";
                    }
                    return "---";
                }
            },

            {
                data: null,
                title: "Indicadores",
                orderable: false,
                searchable: false,
                render: function (row) {

                    let iconos = `<div class="DatatableIndicadores-ref">`;

                    iconos += `
                        <i class="bi bi-reply-all-fill DatatableIconoRefenciaIcono ${row.tiene_respuesta ? 'Encendido' : 'Apagado'}"
                        title="${row.tiene_respuesta ? 'Tiene respuesta' : 'Sin respuesta'}"></i>
                    `;

                    iconos += `
                        <i class="bi bi-person-check-fill DatatableIconoRefenciaIcono ${row.tiene_seguimiento ? 'Encendido' : 'Apagado'}"
                        title="${row.tiene_seguimiento ? 'Tiene seguimiento TIC' : 'Sin seguimiento TIC'}"></i>
                    `;

                    iconos += `
                        <i class="bi bi-slash-circle-fill DatatableIconoRefenciaIcono ${row.tiene_no_atencion ? 'Encendido' : 'Apagado'}"
                        title="${row.tiene_no_atencion ? 'Motivo de no atención' : 'Sin motivo de no atención'}"></i>
                    `;

                    iconos += `</div>`;

                    return iconos;
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
                    { targets: 1, className: 'ColumnaCheck' },
                    { targets: 2, className: 'ColumnaFechaCortaIngreso' },
                    { targets: 5, className: 'ColumnaDNI' },
                    { targets: 6, className: 'ColumnaNombre' },

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
                { value: '3', text: 'Nombre' },
                { value: '4', text: 'Diagnostico'},
                { value: '5', text: 'Institucion'}

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
                    var editarUrl = API_REFERENCIA.editarReferencia.replace('0', id).replace('slug', nombreSlug);
                    window.location.href = editarUrl;
                }
            });

            

            // ==== Atajos de teclado (comentados) ====

            
            // Escucha para el atajo Ctrl + 1
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '1') {
                    event.preventDefault();
                    //window.location.href = API_URLS.agregarEvaluacionrx;
                }
            });
            
            
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    event.preventDefault();
                    //editarEvaluacion();
                }
            });


        }
    };
    



    // Inicializar tabla de evaluacionrx
    initDataTable("data_table_referencias", API_REFERENCIA.listarReferenciasAPI, refenciaColumnas);



    
    function editarReferencia(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
                
                let nombreSlug = slugify(
                    `${selectedRow.paciente__primer_nombre}-${selectedRow.paciente__primer_apellido}`
                ).substring(0, 30);
                
            var editarUrl = API_REFERENCIA.editarReferencia.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    function imprimirFormatoReferencia(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
            imprimirFormatoGenerico(selectedRow.id,API_URLS.reporteFormatoReferencia,"Referencia");
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }



});