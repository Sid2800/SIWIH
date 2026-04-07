document.addEventListener('DOMContentLoaded', function () {

    const API_URLS = {
        listadoIngresoPaciente: urls["listadoIngresosPaciente"],
        agregarIngreso: urls["agregarIngreso"],
        editarIngreso: urls["editarIngreso"],
        listadoAtencionesPaciente: urls["listadoAtencionesPaciente"],
        listadoEvaluacionesPaciente: urls["listadoEvaluacionesPaciente"],
        listadoDispensacionPaciente: urls["listadoDispensacionPaciente"],
        editarEvaluacionrx: urls["editarEvaluacionrx"],

    };


    /*Datas tables */
    const commonOptionsIngreso = {
        responsive: true,
        processing: true,
        serverSide: false,  
        lengthMenu: [5, 10],
        select: {
            style: 'single'
        },
        language: {
            lengthMenu: "Mostrar _MENU_ por página",
            zeroRecords: "No se encontraron resultados",
            info: "_START_ a _END_ de _TOTAL_ registros",
            infoEmpty: "0 a 0 de 0 registros",
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
            emptyTable: "No hay ingresos disponibles",
        },
        dom: '<"superior"Bf>t<"inferior"lip><"clear">',
        buttons: [
            {
                text: '<i class="bi bi-plus-square boton-exportacion"></i>',
                titleAttr: 'Nuevo Ingreso',
                action: function (e, dt, button, config) {
                    agregarIngreso();
                }
            },
            {
                text: '<i class="bi bi-pencil boton-exportacion"></i>',
                titleAttr: 'Editar Ingreso',
                action: function (e, dt, button, config) {
                    editarIngreso();
                }
            },
            {
                text: '<i class="bi bi-printer boton-exportacion"></i>',
                titleAttr: 'Imprimir Ingreso',
                action: function (e, dt, button, config) {
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
                extend: 'excelHtml5',
                titleAttr: 'Exportar a Excel',
                title: `Ingresos-${nombrePaciente ? nombrePaciente : 'Paciente'}`,
                text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
                exportOptions: {
                    columns: ':visible'
                }
            },
        ],
    };

    const commonOptionsAtencion = {
        responsive: true,
        processing: true,
        serverSide: false,
        lengthMenu: [5, 10],
        select: {
        style: 'single'  // Permitir solo la selección de una fila a la vez
        },
        language: { // mensajes ene español
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 registros",
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
        emptyTable: "No hay atenciones disponibles",
    },
    dom: '<"superior"Bf>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    buttons: [
        
        {
        text: '<i class="bi bi-plus-square boton-exportacion"></i>',  // Icono o texto para el botón
        titleAttr: 'Nueva Atencion',
        action: function ( e, dt, button, config ) {
            llamarAgregarAtencion();
        }
        },
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Atencion',
        action: function ( e, dt, button, config ) {
            verEditarAtencion();
        }
        }, 
        
        {
        extend: 'excelHtml5',
        titleAttr: 'Exportar a Excel',
        title: `Atenciones-${nombrePaciente ? nombrePaciente : 'Paciente'}`,
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: {
            columns: ':visible',
            modifier: {
                page: 'all'  // Exportar todas las páginas, no solo la visible
            }
        },
        }, 
    ],
    
    };

    const commonOptionsDispensaciones = {
        responsive: true,
        processing: true,
        serverSide: false,
        lengthMenu: [5, 10],
        select: {
        style: 'single'  // Permitir solo la selección de una fila a la vez
        },
        language: { // mensajes ene español
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 registros",
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
        emptyTable: "No hay dispensaciones disponibles",
    },
    dom: '<"superior"Bf>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    buttons: [
        {
        extend: 'excelHtml5',
        titleAttr: 'Exportar a Excel',
        title: `Dispensaciones-${nombrePaciente ? nombrePaciente : 'Paciente'}`,
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: {
            columns: ':visible',
            modifier: {
                page: 'all'  // Exportar todas las páginas, no solo la visible
            }
        },
        }, 
    ],
    
    };

    const commonOptionsEvaluaciones = {
        responsive: true,
        processing: true,
        serverSide: false,
        lengthMenu: [5, 10],
        select: {
        style: 'single'  // Permitir solo la selección de una fila a la vez
        },
        language: { // mensajes ene español
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 registros",
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
        emptyTable: "No hay evaluaciones disponibles",
    },
    dom: '<"superior"Bf>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    buttons: [
        {
        extend: 'excelHtml5',
        titleAttr: 'Exportar a Excel',
        title: `Evaluacion-${nombrePaciente ? nombrePaciente : 'Paciente'}`,
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: {
            columns: ':visible',
            modifier: {
                page: 'all'  // Exportar todas las páginas, no solo la visible
            }
        },
        },
        {
                text: '<i class="bi bi-pencil boton-exportacion"></i>',
                titleAttr: 'Editar Evalucion',
                action: function (e, dt, button, config) {
                    verGaleriaEvaluacionRx();
                }
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
            responsivePriority: 4,
            render: function (data) {
                let fecha = data.fecha_ingreso ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_ingreso, true) : "---";
                return `${fecha}`;
            },
        },
        { 
            data: null,
            responsivePriority: 5,
            render: function (data) {
                let fecha = data.fecha_egreso ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_egreso, true) : "---";
                let recibido = data.usuario_recibio_egreso ? data.usuario_recibio_egreso : "---";
                return `${fecha} | ${recibido}`;
            },
        },
        { 
            data: null,
            responsivePriority: 6,
            render: function (data) {
                let fecha = data.fecha_recepcion_sdgi ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_recepcion_sdgi, true) : "---";
                let recibido = data.usuario_recibio_sdgi ? data.usuario_recibio_sdgi : "---";
                return `${fecha} | ${recibido}`;
            },
        },
        {
            data: null,
            responsivePriority: 3,
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
            data: null,
            render: function (data) {
                let fecha = data.fecha_modificado ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_modificado, true) : "---";
                let modificado = data.modificado_por__username ? data.modificado_por__username : "---";
                return `${fecha} | ${modificado}`;
            },
        },
    ];

    const atencionColumnas = [
        {
            data: "id",
            responsivePriority: 1,
        },
        { 
            data: null,
            responsivePriority: 2,
            render: function (data) {
                let fecha = data.fecha_atencion ? formatearFechaLocal(data.fecha_atencion) : "---";
                return `${fecha}`;
            },
        },
        { 
            data: null,
            responsivePriority: 3,
            render: function (data) {
                let fecha = data.fecha_recepcion ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_recepcion,true) : "---";
                let recibido = data.usuario_recibio ? data.usuario_recibio : "---";
                return `${fecha} | ${recibido}`;
            },
        },
        {
            data: null,
            render: function (data) {
                if (data) {
                    // Obtenemos el nombre de la especialidad y lo limitamos a 20 caracteres
                    let especialidad = data.especialidad__nombre_especialidad	;
                    especialidad = especialidad.substring(0, 21);
                    
                    // Concatenamos la sala truncada con el nombre corto del servicio, usando concatenarLimpio
                    data = concatenarLimpio(especialidad);
                }
                return data;
            }
        },
        {
            data: null,
            render: function (data) {
                let fecha = data.fecha_modificado ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_modificado,true) : "---";
                let modificado = data.modificado_por__username ? data.modificado_por__username : "---";
                return `${fecha} | ${modificado}`;
            },
        },
    ];

    const DispensacionColumnas = [
    {
        data: 2,  // Fecha (índice 2)
        responsivePriority: 1,
        render: function (data) {
            let fecha = data ? formatearFechaYYYYMMDD_a_DDMMYYYY(data) : "---";
            return `${fecha}`;
        },
    },
    {
        data: 7,  // Medicamento (índice 7)
        responsivePriority: 2,
        render: function (data) {
            return data.toUpperCase();
        },
    },
    {
        data: 9,  // Prescrito
    },
    {
        data: 8,  // Dispensado
    },
    {
        data: 6,  // Servicio
    },
    {
        data: 5,  // Medico
    },

    

    ];

    const EvaluacionesColumnas = [
        {
            data: "id",
            responsivePriority: 1,
        },
        { 
            data: null,
            responsivePriority: 2,
            render: function (data) {
                let fecha = data.fecha ? formatearFechaYYYYMMDD_a_DDMMYYYY(data.fecha) : "---";
                return `${fecha}`;
            },
        },
        {
            data: null,
            responsivePriority: 3,
            render: function (data) {
                if (data) {
                    // Obtenemos el nombre de la especialidad y lo limitamos a 20 caracteres
                    let dependencia = data.nombre_dependencia	;
                    dependencia = dependencia.substring(0, 21);
                    let tipo_dependencia = data.tipo_dependencia;
                    
                    // Concatenamos la sala truncada con el nombre corto del servicio, usando concatenarLimpio
                    data = concatenarLimpio(dependencia," | ",tipo_dependencia);
                }
                return data;
            }
        },
        {
            data: "maquinarx__descripcion_maquina",
        },
        {
            data: "total_estudios",
        },
        {
            data: null,
            render: function (data) {
                let fecha = data.fecha_modificado ? formatoFecha_dd_mm_yy_hh_mm(data.fecha_modificado,true) : "---";
                let modificado = data.modificado_por__username ? data.modificado_por__username : "---";
                return `${fecha} | ${modificado}`;
            },
        },

    ];




    let tableIngresos;
    function inicializarTablaHistorialIngresos() {
        const tableId = "historialTablaIngresos";
        const ajaxUrl = `${API_URLS.listadoIngresoPaciente}?id_paciente=${idPaciente}`;
        const columns = ingresoColumnas;

        if (document.getElementById(tableId)) {
            $.get(ajaxUrl, function (response) {
                const ingresos = response.data || response;
                tableIngresos = $(`#${tableId}`).DataTable({
                    ...commonOptionsIngreso,
                    data: ingresos,
                    columns: columns,
                    columnDefs: [
                        { targets: 0, className: 'PrimerColumnaAliIzq' },
                        { targets: 1, className: 'ColumnaFechaCortaIngreso' },
                        //{ targets: 2, className: 'ColumnaFechaCortaIngreso' },
                        //{ targets: 3, className: 'ColumnaFechaCortaIngreso' },
                        { targets: 4, className: 'ColumnaSalaServicioIngreso' },
                    ],
                    order: [[0, "desc"]],
                });

                tableIngresos.on('dblclick', 'tr', function () {
                    const data = tableIngresos.row(this).data();
                    if (data) {
                        tableIngresos.$('tr.selected').removeClass('selected');
                        $(this).addClass('selected');
                        editarIngreso();
                    }
                });

                tableIngresos.on('click', 'tbody tr', (e) => {
                    let classList = e.currentTarget.classList;
                    if (classList.contains('child')) return;
                    if (classList.contains('selected')) {
                        classList.remove('selected');
                    } else {
                        tableIngresos.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                        classList.add('selected');
                    }
                });
            });
        }
    }

    let tableAtenciones;
    function inicializarTablaHistorialAtenciones() {
        const tableId = "historialTablaConsultas";
        const ajaxUrl = `${API_URLS.listadoAtencionesPaciente}?id_paciente=${idPaciente}`;
        const columns = atencionColumnas;

        if (document.getElementById(tableId)) {
            $.get(ajaxUrl, function (response) {
                const atenciones = response.data || response;
                tableAtenciones = $(`#${tableId}`).DataTable({
                    ...commonOptionsAtencion,
                    data: atenciones,
                    columns: columns,
                    columnDefs: [
                        { targets: 0, className: 'PrimerColumnaAliIzq' },
                        { targets: 1, className: 'ColumnaFechaCortaIngreso' },
                        { targets: 2, className: 'ColumnaFechaCortaIngreso' },
                        { targets: 3, className: 'ColumnaSalaServicioIngreso' },
                    ],
                    order: [[0, "desc"]],
                });


                tableAtenciones.on('dblclick', 'tr', function () {
                    const data = tableAtenciones.row(this).data();
                    if (data) {
                        tableAtenciones.$('tr.selected').removeClass('selected');
                        $(this).addClass('selected');
                        
                        verEditarAtencion();
                    }
                });

                tableAtenciones.on('click', 'tbody tr', (e) => {
                    let classList = e.currentTarget.classList;
                    if (classList.contains('child')) return;
                    if (classList.contains('selected')) {
                        classList.remove('selected');
                    } else {
                        tableAtenciones.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                        classList.add('selected');
                    }
                });
            });
        }
    }

    let tableDispensaciones;
    function inicializarTablaHistorialDispensaciones() {
        const tableId = "historialTablaDispensaciones";
        const ajaxUrl = `${API_URLS.listadoDispensacionPaciente}?id_paciente=${idPaciente}`;
        const columns = DispensacionColumnas;

        if (document.getElementById(tableId)) {
            $.get(ajaxUrl, function (response) {
                const dispensaciones = response.data || response;

                tableDispensaciones = $(`#${tableId}`).DataTable({
                    ...commonOptionsDispensaciones,
                    data: dispensaciones,
                    columns: columns,
                    columnDefs: [
                        { targets: 0, className: 'PrimerColumnaAliIzq' },
                        //{ targets: 1, className: 'ColumnaFechaCortaIngreso' },
                        { targets: 2, className: 'ColumnaCantCorta' },
                        { targets: 3, className: 'ColumnaCantCorta' },
                    ],
                    order: [[0, "desc"]],
                });

                tableDispensaciones.on('click', 'tbody tr', (e) => {
                    let classList = e.currentTarget.classList;
                    if (classList.contains('child')) return;
                    if (classList.contains('selected')) {
                        classList.remove('selected');
                    } else {
                        tableDispensaciones.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                        classList.add('selected');
                    }
                });

            });
        }
    }

    let tableEvaluaciones;
    function inicializarTablaHistorialEvaluaciones() {
        const tableId = "historialTablaEvaluacionesRx";
        const ajaxUrl = `${API_URLS.listadoEvaluacionesPaciente}?id_paciente=${idPaciente}`;
        const columns = EvaluacionesColumnas;

        if (document.getElementById(tableId)) {
            $.get(ajaxUrl, function (response) {
                const evaluaciones = response.data || response;

                tableEvaluaciones = $(`#${tableId}`).DataTable({
                    ...commonOptionsEvaluaciones,
                    data: evaluaciones,
                    columns: columns,
                    columnDefs: [
                        { targets: 0, className: 'ColumnaFechaFormateada' },
                        //{ targets: 1, className: 'ColumnaFechaCortaIngreso' },
                        //{ targets: 2, className: 'ColumnaCantCorta' },
                        //{ targets: 3, className: 'ColumnaCantCorta' },
                    ],
                    order: [[0, "desc"]],
                });

                tableEvaluaciones.on('dblclick', 'tr', function () {
                    const data = tableEvaluaciones.row(this).data();
                    
                    if (data) {
                        
                        tableEvaluaciones.$('tr.selected').removeClass('selected');
                        $(this).addClass('selected');
                        
                        verGaleriaEvaluacionRx();
                    }
                });

                tableEvaluaciones.on('click', 'tbody tr', (e) => {
                    let classList = e.currentTarget.classList;
                    if (classList.contains('child')) return;
                    if (classList.contains('selected')) {
                        classList.remove('selected');
                    } else {
                        tableEvaluaciones.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                        classList.add('selected');
                    }
                });

            });
        }
    }



    inicializarTablaHistorialIngresos();
    inicializarTablaHistorialAtenciones();
    inicializarTablaHistorialDispensaciones();
    inicializarTablaHistorialEvaluaciones();

    // Lógica del tab
    document.querySelectorAll('.historialTabsBoton').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.historialTabsBoton').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.historial-tab-contenido').forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            const tabContenido = document.getElementById(tabId);
            tabContenido.classList.add('active');

            // Forzar ajuste de columnas de DataTables visibles
            setTimeout(() => {
                // Solo ajusta las tablas que están visibles
                $($.fn.dataTable.tables(true)).DataTable().columns.adjust().draw();
            }, 100); // Pequeño retraso para asegurar que ya se hizo visible
        });
    });



    /**
     *  AGREGAR UN NUEVO INGRESO
     */
    async function agregarIngreso() {

        if (idPaciente === undefined || idPaciente === null || idPaciente === '') {
            toastr.error("Existe un problema en localizar al paciente");
            return;
        }
            
        try {
            // Verificar ingreso activo
            
            const ingresoActivo = await verificarIngreso(idPaciente);
            if (ingresoActivo) {
                toastr.warning("Este paciente ya tiene un ingreso activo.");
                return;
            }
            
            // Verificar defunción
            
            const estaMuerto = await verificarDefuncion(idPaciente);
            if (estaMuerto) {
                toastr.warning("No se puede ingresar un paciente fallecido.");
                return;
            }

            const inactivo = await verificarPacienteInactivo(idPaciente);
            if (inactivo) {
                toastr.warning("No se puede ingresar un paciente inactivo.");
                return;
            }
            
            let nomprePaciente = document.getElementById('historialNombrePaciente').value;
            const nombreSlug = slugify(`${nomprePaciente}`);
            if (!nombreSlug) {
                toastr.error("Hubo un problema al generar la URL.");
                return;
            }
            
            const ingresoUrl = API_URLS.agregarIngreso
                .replace('0', idPaciente)
                .replace('slug', nombreSlug);
    
            window.location.href = ingresoUrl;
        } catch (error) {
            toastr.error("Ocurrió un error inesperado: " + error.message);
        }
    }

    //tableIngresos
    function editarIngreso(){
        const selectedRow = tableIngresos.row('.selected').data();

        if (selectedRow) {
                let nomprePaciente = document.getElementById('historialNombrePaciente').value;
                let nombreSlug = slugify(
                    `${nomprePaciente}`
                ).substring(0, 30);
                
            var editarUrl = API_URLS.editarIngreso.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    function imprimirIngreso(){
        const selectedRow = tableIngresos.row('.selected').data();

        if (selectedRow) {
            imprimirHojaHospitalizacion(selectedRow.id);
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }

    async function inactivarIngresoDatatable(){

        const selectedRow = tableIngresos.row('.selected').data();

        if (selectedRow.id) {
            const titulo = `Desactivar ingreso`;
            const mensaje = `¿ Realmente desea desactivar el ingreso, es un proceso irreversible ?`;

            const resultado = await confirmarAccion(titulo, mensaje);
            if (!resultado) return;

            try {
                await inactivarIngreso(selectedRow.id);
                if (tableIngresos){
                    recargarTablaIngresos();
                }
            } catch (error) {
                console.error("Error al procesar la solicitud:", error);
            }
            
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
    }


    async function llamarAgregarAtencion() {

        if (idPaciente === undefined || idPaciente === null || idPaciente === '') {
            toastr.error("Existe un problema en localizar al paciente");
            return;
        }

        let nomprePaciente = document.getElementById('historialNombrePaciente').value;

        const paciente = {
        id: idPaciente,
        nombre: nomprePaciente,
        };

        // Hacemos la llamada al backend
        // trasmnutar zona por setvicio para ficlicita digidtacion
        let servicio = 0;

        if(zona){
            if (zona==1){
                servicio = 50;
            }else if (zona==2){
                servicio = 1000;
            }else if (zona==3){
                servicio = 700;
            }
        }else
        {
            servicio = 50;
        }

        let resultado = await agregarAtencion(paciente,servicio,null);
        if(resultado){
            setTimeout(() => {
                recargarTablaAtenciones();
            }, 500);
        }

    }
    

    async function verEditarAtencion() {
        const selectedRow = tableAtenciones.row('.selected').data();
    
        // Verificar si se ha seleccionado una fila
        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }
        
        let resultado = await AgregarAtencionModal(null,null,selectedRow.id);

        if (resultado?.guardo === true) {
            toastr.info(`Atencion procesada correctamente`, "Cambios realizados");
            setTimeout(() => {
                recargarTablaAtenciones();
            }, 500);
            
        } else if (resultado?.guardo === false) {
            toastr.alert(`No se procesó correctamente la atencion`, 'No se guardaron cambios');
        }
    }

    function recargarTablaAtenciones() {
    if (!idPaciente) {
        console.error("ID de paciente no proporcionado para recargar la tabla.");
        return;
    }
    const ajaxUrl = `${API_URLS.listadoAtencionesPaciente}?id_paciente=${idPaciente}`;
    fetch(ajaxUrl)
        .then(response => response.json())
        .then(data => {
            tableAtenciones.clear();
            tableAtenciones.rows.add(data.data);
            tableAtenciones.draw();
        })
        .catch(error => {
            console.error("Error al recargar tabla:", error);
            toastr.error("No se pudo recargar la tabla de atenciones");
        });
    }

    function recargarTablaIngresos() {
        if (!idPaciente) {
            console.error("ID de paciente no proporcionado para recargar la tabla.");
            return;
        }
        const ajaxUrl = `${API_URLS.listadoIngresoPaciente}?id_paciente=${idPaciente}`;

        fetch(ajaxUrl)
            .then(response => response.json())
            .then(data => {
                if (!tableIngresos) {
                    console.error("La tabla de ingresos no está inicializada.");
                    return;
                }
                tableIngresos.clear();
                tableIngresos.rows.add(data.data || data);
                tableIngresos.draw();
            })
            .catch(error => {
                console.error("Error al recargar tabla de ingresos:", error);
                toastr.error("No se pudo recargar la tabla de ingresos");
            });
    }

    function verGaleriaEvaluacionRx(){
        const selectedRow = tableEvaluaciones.row('.selected').data();
        if (!selectedRow) {
            toastr.warning("Debe seleccionar una evaluación");
            return;
        }
        ModalGaleria.open({
        titulo: "Evaluación",
            

        datos: {
            "Paciente": document.getElementById('historialNombrePaciente').value,
            "Sala": selectedRow.nombre_dependencia,
            "Fecha": formatearFechaSimple(selectedRow.fecha),
            "Maquina": selectedRow.maquinarx__descripcion_maquina,
            "Usuario": selectedRow.modificado_por__username
        },

        parametros: {
            "idPaciente": idPaciente,
            "idEvaluacion": selectedRow.id,
            "tituloAlbum": document.getElementById('historialNombrePaciente').value
        },



        });



    }

    


});