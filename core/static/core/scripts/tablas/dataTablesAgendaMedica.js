// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {
    
    const API_PERIODO = {
        listarAgendaMedicaAPI: API_URLS.listarAgendaMedicaAPI,
        listarAusenciaAPI: API_URLS.listarAusenciasAPI
    };


    const botonesPeriodoLaboral = [
        {
            text: '<i class="bi bi-plus-lg boton-accion-principal"><span class="form-label">Nuevo periodo</span></i>',
            titleAttr: 'Agregar Periodo Laboral',
            action: async function (e, dt, button, config) {
                await ManejarPeriodoLaboral.open();
                table.ajax.reload(null, false);
            }
        },
        {
            text: '<i class="bi bi-pencil boton-exportacion"></i>',
            titleAttr: 'Editar Periodo Laboral',
            action: async function (e, dt, button, config) {
                await editarPeriodo();
            }
        },
        {
            text: '<i class="bi-gear-fill boton-exportacion"></i>',
            titleAttr: 'Configurar Periodo Laboral',
            action: function (e, dt, button, config) {
                configurarPeriodo();
            }
        }
    ];


    const botonesAusencia = [
        {
            text: '<i class="bi bi-plus-lg boton-accion-principal"><span class="form-label">Nueva ausencia</span></i>',
            titleAttr: 'Agregar Ausencia',
            action: async function (e, dt, button, config) {
                const resultado =await ManejarAusencia.open();

                if (!resultado || !resultado.isConfirmed) {
                    console.log("");
                    return;
                }

                const mensajes = construirMensajesCambios(resultado.value);


                await informarCambios({
                    titulo: "Ausencia creada correctamente",
                    mensajes: mensajes,
                    icono: "info"
                });
                AusenciaTable.ajax.reload(null, false);
            }
        },
        {
            text: '<i class="bi bi-pencil boton-exportacion"></i>',
            titleAttr: 'Editar Ausencia',
            action: async function (e, dt, button, config) {
                // await editarAusencia();
            }
        }
    ];


    const obtenerBotonesAgendaMedica = (esAusencia) => {
        return esAusencia ? botonesAusencia : botonesPeriodoLaboral;
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
    dom: '<"superior-agenda-medica"B<"contenedorSegmentacion">>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: obtenerBotonesAgendaMedica(esAusencia), // botones de la tabla
    
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
                title: "Jornada",
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
                                <i class="bi bi-circle-fill icon-gris"></i> FINALIZADO
                            </span>
                        `;
                    } else if (data === "E") {
                        return `
                            <span title="Ejecucion" class="DatatableIconoAgendaEstado">
                                <i class="bi bi-circle-fill icon-verde"></i> EJECUCION
                            </span>
                        `;
                    } else if (data === "U") {
                        return `
                            <span title="Futuro" class="DatatableIconoAgendaEstado">
                                <i class="bi bi-circle-fill icon-amarillo"></i> FUTURO
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

                        <a class="datatable-agenda-boton" title="Configurar" href="${data.url_configuracion}" >
                            <i class="bi-gear-fill"></i>
                        </a>
                    </div>
                    `;
            }
            },
            {
                data: "id",
                visible: false
            },
    ];

    const ausenciaColumnas =[
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
            data: "dias",
            title: "Dias",
            orderable: false,
            searchable: false,
            responsivePriority: 5,
        },
        {
            data: "tipo_label",
            title: "Tipo",
            responsivePriority: 2,

            render: function (data, type, row) {
                return `
                    <span
                        class="datatable-ausencia-tipo"
                        style="
                            background-color: ${row.colores_tipo.color};
                            border-color: ${row.colores_tipo.borderColor};
                        "
                    >
                        ${data}
                    </span>
                `;
            },
        },

        {
            data: "estado_temporal",
            title: "Estado",
            responsivePriority: 5,
            render: function (data) {
                if (data === "F") {
                    return `
                        <span title="Finalizado" class="DatatableIconoAgendaEstado">
                            <i class="bi bi-circle-fill icon-gris"></i> CONCLUIDO
                        </span>
                    `;
                } else if (data === "E") {
                    return `
                        <span title="Ejecucion" class="DatatableIconoAgendaEstado">
                            <i class="bi bi-circle-fill icon-verde"></i> EJECUCION
                        </span>
                    `;
                } else if (data === "U") {
                    return `
                        <span title="Futuro" class="DatatableIconoAgendaEstado">
                            <i class="bi bi-circle-fill icon-amarillo"></i> FUTURO
                        </span>
                    `;
                }
            },
        },

        {
            data: "id",
            visible: false
        },



    ];


    let AusenciaTable;
    const initAusenciaDataTable = (tableId, ajaxUrl, columns) => {
        if (document.getElementById(tableId)) {
            // Inicialización de la tabla
            AusenciaTable = $(`#${tableId}`).DataTable({
                ...commonOptions,
                ajax: {
                    url: ajaxUrl,
                    type: 'GET',
                    data: function(d) {
                        d.search_value = document.getElementById('busquedaListadoPeriodoLaboral')?.value || '';
                        d.anio = document.getElementById('selectAnio')?.value || '';
                        d.estado = document.getElementById('selectEstado')?.value || '';
                        d.tipo = document.getElementById('selectTipo')?.value || '';
                    }
                },
                columns: columns,
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


            if (typeof anios_ausencias !== 'undefined' && anios_ausencias.length > 0) {
                anios_ausencias.forEach((anio, index) => {
                    const option = document.createElement('option');
                    option.value = anio;
                    option.textContent = anio;
                    if (index === 0) {
                        option.selected = true;
                    }
                    selectAnio.appendChild(option);
                });
            }

            // Label y input tipo
            const label2 = document.createElement('label');
            label2.textContent = "Tipo";
            label2.htmlFor = 'selectTipo';
            contenedorSegmentacion.appendChild(label2);

            const selectTipo = document.createElement('select');
            selectTipo.id = 'selectTipo';
            selectTipo.name = 'selectTipo';
            selectTipo.className = 'formularioCampo-select';
            contenedorSegmentacion.appendChild(selectTipo);

            if (typeof tipos_ausencia !== 'undefined' && tipos_ausencia.length > 0) {

                const optionTodos = document.createElement('option');

                optionTodos.value = '0';
                optionTodos.textContent = 'Todos';
                optionTodos.selected = true;

                selectTipo.appendChild(optionTodos);

                tipos_ausencia.forEach((tipo, index) => {
                    const option = document.createElement('option');
                    option.value = tipo.value;
                    option.textContent = tipo.texto;
                    selectTipo.appendChild(option);
                });
            }

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
            document.querySelector('.superior-agenda-medica').appendChild(buscarBtn);

            buscarBtn.addEventListener('click', function () {
                AusenciaTable.ajax.reload();
            });
            
            // Selección de fila al hacer clic
            AusenciaTable.on('click', 'tbody tr', (e) => {
                let row = e.currentTarget;
                let classList = row.classList;

                if (classList.contains('child')) return;

                // limpiar selección anterior
                AusenciaTable.rows('.selected').nodes().each((r) => {
                    r.classList.remove('selected');
                });

                // toggle selección
                if (!classList.contains('selected')) {
                    classList.add('selected');
                } else {
                    classList.remove('selected');
                }
            });

            AusenciaTable.on('dblclick','tbody tr', async function name(params) {
                await editarAusencia();
            }

            )
            
        }
    }


    
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
            document.querySelector('.superior-agenda-medica').appendChild(buscarBtn);

            buscarBtn.addEventListener('click', function () {
                table.ajax.reload();
            });

            // Selección de fila al hacer clic
            table.on('click', 'tbody tr', (e) => {
                let row = e.currentTarget;
                let classList = row.classList;

                if (classList.contains('child')) return;

                table.rows('.selected').nodes().each((r) => {
                    r.classList.remove('selected');
                });

                if (!classList.contains('selected')) {
                    classList.add('selected');
                } else {
                    classList.remove('selected');
                }
            });


            // Doble clic en fila para configurar período
            table.on('dblclick', 'tbody tr', function () {
                const data = table.row(this).data();
                if (data) {
                    configurarPeriodo();
                }
            });


            // Acciones de la fila
            table.on('click', 'tbody .datatable-agenda-boton', async function (e) {
                e.stopPropagation();
                const accion = this.dataset.action;
                const id = this.dataset.id;

                if (accion === 'editar') {

                    await ManejarPeriodoLaboral.open({
                        titulo: "Editar Periodo Laboral",
                        periodoID: id
                    });

                    table.ajax.reload(null, false);
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
    initDataTable("data_table_agenda_medica", API_PERIODO.listarAgendaMedicaAPI, periodoColumnas);
    initAusenciaDataTable("data_table_agenda_medica_ausencia",API_PERIODO.listarAusenciaAPI,ausenciaColumnas);



    async function editarAusencia(){

        const selectedRow = AusenciaTable.row('.selected').data();

        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }
    
        const resultado = await ManejarAusencia.open({
            titulo: "Editar Ausencia",
            ausenciaID: selectedRow.id
        });


        if (!resultado || !resultado.isConfirmed) {
            return;
        }


        console.log(resultado);

        const mensajes = construirMensajesCambios(resultado.value);

        await informarCambios({
                titulo: "Ausencia editada correctamente",
                mensajes: mensajes,
                icono: "info"
            });



        AusenciaTable.ajax.reload(null, false);
    }


    
    async function editarPeriodo(){

        const selectedRow = table.row('.selected').data();

        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }
    
        await ManejarPeriodoLaboral.open({
            titulo: "Editar Periodo Laboral",
            periodoID: selectedRow.id
        });

        table.ajax.reload(null, false);
    }

    
    function configurarPeriodo(){
        const selectedRow = table.row('.selected').data();
        if (selectedRow) {
            let nombreSlug = slugify(
                    `${selectedRow.personal_salud__empleado__primer_nombre}-${selectedRow.personal_salud__empleado__primer_apellido}`
                ).substring(0, 30);

            window.location.href = API_URLS.configurarPeridoLaboral.replace('0', selectedRow.id).replace('slug',nombreSlug);
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }


});