// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {
    
    const API_PERIODO = {
        listarAgendaMedicaAPI: API_URLS.listarAgendaMedicaAPI,
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
    dom: '<"superior "B<"contenedorSegmentacion">>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: [
        
        {
        text: '<i class="bi bi-plus-square boton-exportacion"></i>',  // Icono o texto para el botón
        titleAttr: 'Agregar Periodo Laboral',
        action: function ( e, dt, button, config ) {
            ManejarPeriodoLaboral.open();
        }
        },
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Periodo Laboral',
        action: function ( e, dt, button, config ) {
            editarPeriodo();
    
        }
        },  
        {
        text: '<i class="bi-gear-fill boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Periodo Laboral',
        action: function ( e, dt, button, config ) {
            configurarPeriodo();
    
        }
        },  

        
    ],
    
    };

    const periodoColumnas = [
            {
                data: null,
                responsivePriority: 1,
                render: function (data) {
                    if (data) {
                        let nombre = concatenarLimpio(
                            data.personal_salud__empleado__primer_nombre,
                            data.personal_salud__empleado__segundo_nombre,
                            data.personal_salud__empleado__primer_apellido,
                            data.personal_salud__empleado__segundo_apellido
                        );

                        return nombre ? `${nombre.substring(0, 30)}` : "---";
                    }
                    return "---";
                }
            },
            {
                data: "personal_salud__especialidad__nombre_especialidad",
                title: "Especialidad",
                responsivePriority: 3,
            },
            {
                data: "periodo",
                title: "Periodo laboral",
                responsivePriority: 4,
            },
            {
                data: "jornada_laboral__nombre_jornada_laboral",
                title: "Jornada Laboral",
                responsivePriority: 5,
            },
            {
                data: "estado_temporal",
                title: "Estado",
                responsivePriority: 6,
                render: function (data) {
                    if (data === "F") {
                        return `
                            <span title="Finalizado" class="DatatableIconoAgendaEstado">
                                <i class="bi bi-circle-fill icon-rojo"></i> FINALIZADO
                            </span>
                        `;
                    } else if (data === "E") {
                        return `
                            <span title="Ejecucion" class="DatatableIconoAgendaEstado">
                                <i class="bi bi-circle-fill icon-amarillo"></i> EJECUCION
                            </span>
                        `;
                    } else if (data === "U") {
                        return `
                            <span title="Futuro" class="DatatableIconoAgendaEstado">
                                <i class="bi bi-circle-fill icon-verde"></i> FUTURO
                            </span>
                        `;
                    }
                },
            },
            {
                data: null,
                title: "Acciones",
                orderable: false,
                searchable: false,
                render: function (data) {
                    return `
                    <div class="datatable-agenda-acciones-wrapper">
                        <button class="datatable-agenda-boton" title="Editar"  data-action="editar" data-id="${data.id}">
                            <i class="bi bi-pencil"></i>
                        </button>

                        <button class="datatable-agenda-boton" title="Configurar" data-action="configurar" data-id="${data.id}">
                            <i class="bi-gear-fill"></i>
                        </button>
                    </div>
                    `;
            }
            },
            {
                data: "id",
                visible: false
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
                        d.search_value = document.getElementById('busquedaListadoPeriodoLaboral')?.value || '';
                        d.anio = document.getElementById('selectAnio')?.value || '';
                        d.estado = document.getElementById('selectEstado')?.value || '';
                    }
                },
                columns: columns,
                /*
                columnDefs: [
                    { targets: 5, className: 'datatable-agenda-celda-boton' },

                ],*/
                order: [[0, "desc"]],
            });

            const hoyDate = new Date();

            const hoy = hoyDate.toISOString().split('T')[0];

            const contenedorSegmentacion = document.querySelector('.contenedorSegmentacion');

            // Label y input anio 
            const label1 = document.createElement('label');
            label1.textContent = "Año";
            label1.htmlFor = 'selectAnio';
            contenedorSegmentacion.appendChild(label1);

            const selectAnio = document.createElement('select');
            selectAnio.id = 'selectAnio';
            selectAnio.name = 'selectAnio';
            selectAnio.className = 'formularioCampo-select';
            contenedorSegmentacion.appendChild(selectAnio);


            if (typeof anios !== 'undefined' && anios.length > 0) {
                anios.forEach((anio, index) => {
                    const option = document.createElement('option');
                    option.value = anio;
                    option.textContent = anio;
                    if (index === 0) {
                        option.selected = true;
                    }
                    selectAnio.appendChild(option);
                });
            }



            // Label y input fecha fin
            const label2 = document.createElement('label');
            label2.textContent = "Estado";
            label2.htmlFor = 'selectEstado';
            contenedorSegmentacion.appendChild(label2);

            const selectEstado = document.createElement('select');
            selectEstado.id = 'selectEstado';
            selectEstado.name = 'selectEstado';
            selectEstado.className = 'formularioCampo-select';
            contenedorSegmentacion.appendChild(selectEstado);

            const opciones = [
                { value: 'T', text: 'TODOS' },
                { value: 'U', text: 'FUTURO' },
                { value: 'E', text: 'EJECUCION' },
                { value: 'F', text: 'FINALIZADO' },
            ];

            const defaultValue = 'T';

            opciones.forEach(op => {
                const option = document.createElement('option');
                option.value = op.value;
                option.textContent = op.text;

                if (op.value === defaultValue) {
                    option.selected = true;
                }

                selectEstado.appendChild(option);
            });



            // Input de texto para búsqueda
            const inputBusqueda = document.createElement('input');
            inputBusqueda.type = 'text';
            inputBusqueda.id = 'busquedaListadoPeriodoLaboral';
            inputBusqueda.name = 'busquedaListadoPeriodoLaboral';
            inputBusqueda.className = 'formularioCampo-text';
            inputBusqueda.placeholder = 'Busqueda';
            contenedorSegmentacion.appendChild(inputBusqueda);

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
                let row = e.currentTarget;
                let classList = row.classList;

                if (classList.contains('child')) return;

                // limpiar selección anterior
                table.rows('.selected').nodes().each((r) => {
                    r.classList.remove('selected');
                });

                // toggle selección
                if (!classList.contains('selected')) {
                    classList.add('selected');
                } else {
                    classList.remove('selected');
                }
            });
            

            // Doble clic en fila para redirección
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                console.log(data);
                /*
                if (data) {
                    
                    const id = data.id;
                    let nombreSlug = slugify(
                        `${data.paciente__primer_nombre}-${data.paciente__primer_apellido}`
                    ).substring(0, 30);
                    var editarUrl = API_REFERENCIA.editarReferencia.replace('0', id).replace('slug', nombreSlug);
                    window.location.href = editarUrl;
                }*/
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
    initDataTable("data_table_agenda_medica", API_PERIODO.listarAgendaMedicaAPI, periodoColumnas);


    const tbody = document.querySelector('#data_table_agenda_medica tbody');

    tbody.addEventListener('click', function (e) {
        const boton = e.target.closest('.datatable-agenda-boton');

        if (!boton) return;

        e.stopPropagation(); // evita que dispare selección de fila

        const accion = boton.dataset.action;
        const id = boton.dataset.id;

        console.log('Acción:', accion, 'ID:', id);

        if (accion === 'editar') {
            alert(id);
        }

        if (accion === 'configurar') {
            alert(id);
        }
    });


    
    function editarPeriodo(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
                
            ManejarPeriodoLaboral.open({
                "titulo":"Editar Periodo Laboral",
                "periodoID": selectedRow.id
            });
            /*
            let nombreSlug = slugify(
                    `${selectedRow.paciente__primer_nombre}-${selectedRow.paciente__primer_apellido}`
                ).substring(0, 30);
                
            var editarUrl = API_REFERENCIA.editarReferencia.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;*/
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    
    function configurarPeriodo(){
        const selectedRow = table.row('.selected').data();

        if (selectedRow) {
            console.log(selectedRow.id);
            // imprimirFormatoGenerico(selectedRow.id,API_URLS.reporteFormatoReferencia,"Referencia");
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }



});