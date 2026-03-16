// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

    const API_URLS = {
        // camas_disponibles: urls["camasDisponibles"],
        listado_pacientes: urls["listadoPacientes"],
        agregar_paciente: urls["agregarPaciente"],
        editar_paciente: urls["editarPaciente"],
        agregarIngreso: urls["agregarIngreso"],
        //evalucionrx
        agregarEvaluacionrx: urls["agregarEvaluacionrx"],
        //referencia
        agregarReferencia: urls["agregarReferencia"]
    };

    const allButtons = {
    crear_paciente: {
    text: '<i class="bi bi-plus-square boton-exportacion"></i>',
    titleAttr: 'Nuevo Paciente',
        action: function () {
            window.location.href = API_URLS.agregar_paciente;
        }
    },
    editar_paciente: {
    text: '<i class="bi bi-pencil boton-exportacion"></i>',
    titleAttr: 'Editar Paciente',
        action: function () {
            editarPaciente();
        }
    },
    crear_ingreso: {
    text: '<i class="bi bi-building boton-exportacion"></i>',
    titleAttr: 'Agregar Ingreso',
        action: function () {
            agregarIngreso();
        }
    },
    crear_atencion: {
    text: '<i class="bi bi-thermometer-half boton-exportacion"></i>',
    titleAttr: 'Agregar Atención',
        action: function () {
            llamarAgregarAtencion();
        }
    },
    crear_evaluacionrx: {
    text: '<i class="bi bi-radioactive boton-exportacion"></i>',
    titleAttr: 'Agregar Evaluación RX',
        action: function () {
            agregarEvaluacionrx();
        }
    },
    crear_referencia: {
    text: '<i class="bi bi-link-45deg boton-exportacion"></i>',
    titleAttr: 'Agregar Referencia',
        action: function () {
            agregarReferencia();
        }
    }
    };

    // Botones de exportación (siempre visibles)
    const exportButtons = [
    {
        extend: 'copyHtml5',
        text: '<i class="bi bi-clipboard boton-exportacion"></i>',
        titleAttr: 'Copiar al portapapeles',
        exportOptions: { columns: ':visible' },
            action: function (e, dt, button, config) {
            $.fn.dataTable.ext.buttons.copyHtml5.action.call(this, e, dt, button, config);
            toastr.info('¡Datos copiados exitosamente!');
            }
    },
    {
        extend: 'excelHtml5',
        titleAttr: 'Exportar a Excel',
        title: 'Pacientes',
        text: '<i class="bi bi-file-earmark-excel boton-exportacion"></i>',
        exportOptions: { columns: ':visible' }
    }
    ];


    let botonesFinal = [];

    if (botonesUnidad.includes("todos")) {
    botonesFinal = Object.values(allButtons);
    } else {
    botonesUnidad.forEach(key => {
        if (allButtons[key]) {
        botonesFinal.push(allButtons[key]);
        }
    });
    }

    // Agregar los botones de exportación al final
    botonesFinal.push(...exportButtons);


    //#region Elemntos comunes entre las datatables
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
        infoFiltered: "",
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
    dom: '<"superior "B<"checkbox-container"><"column-select">f>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: botonesFinal
    
    };


    
    const pacienteColumnas = [
            {
                data: "expediente_numero",
                responsivePriority: 2,
                render: function (data) {
                    if (data) {
                        data = data.toString().padStart(6, '0');
                    }
                    return data; 
                },
            },

            {   data: "dni", 
                ordenable: true,
                responsivePriority: 2 ,  
                width: "6px",
                render: function(data){
                    if (data) {
                        return data.substring(0, 13); // Retorna solo los primeros 13 caracteres
                    }
                    return "";
                }
            },      
            {   data: "tipo_id",
                width: "6px" ,
                render: function (data, type, row) {
                    
                    let map = {
                        "1": "DNI",  
                        "2": "PAS",   
                        "3": "RN",  
                        "4": "HD",   
                        "5": "DESC",    
                    };
    
                    let tipo = map[data] || "##";
                    return tipo;
                }
            },
            {
            data: null,
            responsivePriority: 1,
            render: function (data) {
                let nombre1 = data.primer_nombre || "";
                let nombre2 = data.segundo_nombre || "";
                return nombre1 + " " + nombre2;
            },
            },
            {
                data: null,
                responsivePriority: 1,
                render: function (data) {
                    let apellido1 = data.primer_apellido || "";
                    let apellido2 = data.segundo_apellido || "";
                    return apellido1+ " " + apellido2;
                },
                },

            { 
            data: "fecha_nacimiento",
            width: "7px",
            render: function (data) {
                if (data) {
                    let parts = data.split('-');
                    return `${parts[2]}/${parts[1]}/${parts[0]}`;  // Retorna en formato DD/MM/YYYY
                }
                return data; 
                },
            },
            
            

            { data: "sexo", width: "4px", },
            {
            data: null,
            ordenable: false,
            render: function (data) {
                let municipio = data.sector__aldea__municipio__nombre_municipio || "";
                let sector = data.sector__nombre_sector || "";
                return  municipio + ", " + sector;
            },
            
            },
            {
                data: 'clasificacion_id', // Aquí está la columna de clasificación
                render: function (data, type, row) {
                    
                    let colorMap = {
                        "5": "icon-amarillo",  // Amarillo
                        "4": "icon-azul",      // Azul
                        "2": "icon-morado",     // Morado (clase personalizada)
                        "6": "icon-naranja",    // Naranja (clase personalizada)
                        "3": "icon-rojo",       // Rojo
                        "1": "icon-verde",     // Verde
                    };
    
                    let colorClass = colorMap[data] || "icon-gris"; // Gris si no coincide
                    let titleText = data ? data : "N/A"; // Si data es null/undefined, usa "N/A"
                    return `<i class="bi bi-circle-fill ${colorClass}" title="${titleText}"></i>`;
    
                }
            },
            {
            data: null,
            ordenable: false,
            render: function (data) {
                let fecha = data.fecha_modificado ? formatFecha(data.fecha_modificado) : "No disponible";
                let usuario = data.modificado_por__username || "Desconocido";
                return `<span>📅 ${fecha} | 👤 ${usuario}</span>`;
            },
            
            }, 
    
            {data:"id", visible:false}, 
            
        ];


    let table;
    const initDataTable = (tableId, ajaxUrl, columns) => {
        if (document.getElementById(tableId)) {
            // Inicialización de la tabla con opciones comunes y específicas
            table = $(`#${tableId}`).DataTable({
                ...commonOptions,
                searchDelay: 900, 
                ajax: {
                    url: ajaxUrl,
                    type: 'GET',
                    data: function(d) {      // parametros de busqueda 
                    d.search_value = $('#search-input').val();
                    d.search_column = $('#column-selector').val();
                    d.activos_inactivos = $('#switchInactivosDatatable').is(':checked') ? "1" : "0";
                    d.defunciones = $('#switchDefuncionesDatatable').is(':checked') ? "1" : "0";
                    d.sai = $('#switchSAIDatatable').is(':checked') ? "1" : "0";
                    d.adolecente = $('#switchADODatatable').is(':checked') ? "1" : "0";

                    
                }
                },
                columns: columns,
                columnDefs: [
                    { targets: 0, className: 'PrimerColumnaAliIzq' },// agregamos una clase a la primer  columna
                    { targets: 1, className: 'ColumnaDNI' },
                    
                    { targets: 7, className: 'ColumnaDireccion' },
                    { targets: 3, className: 'ColumnaNombre' },
                    { targets: 4, className: 'ColumnaApellido' },

                ], //columna por la cual se orderna al cargar
                order: [[9, "desc"]]
            });
            

                // Selector de columna para búsqueda rápida
            const select = $('<select id="column-selector" class="formularioCampo-select"><option value="1">Identidad</option></select>')
            .appendTo($('.column-select'))
            .on('change', function () {
                const searchValue = $('#dt-search-0').val().trim();
                if (searchValue.length > 0) {
                    table.ajax.reload();
                }
            });
        
            select.append('<option value="0">Expediente</option>');
            select.append('<option value="2">Nombre</option>');
        
            // Check de activos e inacitvos 

            const switchInactivos = $(`
                <label class="ck-menu" for="switchInactivosDatatable">
                    <input type="checkbox" id="switchInactivosDatatable" class="ck-menu__checkbox" hidden>
                    <div class="ck-menu__base">
                        <div class="ck-menu__bolita"></div>
                    </div>
                    <span class="ck-menu__label">Inactivos</span>
                </label>
            `).appendTo($('.checkbox-container'));

            switchInactivos.find('input[type="checkbox"]').on('change', function() {
                if (this.checked) {
                    switchDefunciones.find('input[type="checkbox"]').prop('checked', false);
                    switchSAI.find('input[type="checkbox"]').prop('checked', false);
                    switchADO.find('input[type="checkbox"]').prop('checked', false);
                }
                table.ajax.reload();
            });

            const switchDefunciones = $(`
                <label class="ck-menu" for="switchDefuncionesDatatable">
                    <input type="checkbox" id="switchDefuncionesDatatable" class="ck-menu__checkbox" hidden>
                    <div class="ck-menu__base">
                        <div class="ck-menu__bolita"></div>
                    </div>
                    <span class="ck-menu__label">Defunciones</span>
                </label>
            `).appendTo($('.checkbox-container'));

            switchDefunciones.find('input[type="checkbox"]').on('change', function() {
                if (this.checked) {
                    switchInactivos.find('input[type="checkbox"]').prop('checked', false);
                    switchSAI.find('input[type="checkbox"]').prop('checked', false);
                    switchADO.find('input[type="checkbox"]').prop('checked', false);

                }
                table.ajax.reload();
            });

            const switchSAI = $(`
                <label class="ck-menu" for="switchSAIDatatable">
                    <input type="checkbox" id="switchSAIDatatable" class="ck-menu__checkbox" hidden>
                    <div class="ck-menu__base">
                        <div class="ck-menu__bolita"></div>
                    </div>
                    <span class="ck-menu__label">SAI</span>
                </label>
            `).appendTo($('.checkbox-container'));
            
            switchSAI.find('input[type="checkbox"]').on('change', function() {
                if (this.checked) {
                    switchInactivos.find('input[type="checkbox"]').prop('checked', false);
                    switchDefunciones.find('input[type="checkbox"]').prop('checked', false);
                    switchADO.find('input[type="checkbox"]').prop('checked', false);
                }
                table.ajax.reload();
            })

            const switchADO = $(`
                <label class="ck-menu" for="switchADODatatable">
                    <input type="checkbox" id="switchADODatatable" class="ck-menu__checkbox" hidden>
                    <div class="ck-menu__base">
                        <div class="ck-menu__bolita"></div>
                    </div>
                    <span class="ck-menu__label">Adolecente</span>
                </label>
            `).appendTo($('.checkbox-container'));

            switchADO.find('input[type="checkbox"]').on('change', function() {
                if (this.checked) {
                    switchInactivos.find('input[type="checkbox"]').prop('checked', false);
                    switchDefunciones.find('input[type="checkbox"]').prop('checked', false);
                    switchSAI.find('input[type="checkbox"]').prop('checked', false);
                }
                table.ajax.reload();
            })


            // Redirecciona al hacer doble clic en una fila
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                if (data) {
                    const id = data.id;
                    let nombreSlug = slugify(data.primer_nombre + "-" + data.primer_apellido); // Generar el slug a partir del nombre
                    // Redireccionar a la página de edición con el ID y el nombre en formato slug
                    var editarUrl = API_URLS.editar_paciente.replace('0', id).replace('slug', nombreSlug);
                    window.location.href = editarUrl;
                }
            });
        
            //funcion para aplicar la seleeccion
            table.on('click', 'tbody tr', (e) => {
                let classList = e.currentTarget.classList;
                
                // Verificar si la fila tiene la clase 'child' antes de proceder
                if (classList.contains('child')) {
                    return; // No hacer nada si tiene la clase 'child'
                }
            
                // Alternar la clase 'selected' solo si no es 'child'
                if (classList.contains('selected')) {
                    classList.remove('selected');
                } else {
                    table.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                    classList.add('selected');
                }
            });
 
            // Escucha para el atajo Ctrl + 1
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '1') {
                    event.preventDefault(); // Evitar el comportamiento predeterminado
                    window.location.href = API_URLS.agregar_paciente; // Redirigir a la URL especificada
                }
            });
        
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    event.preventDefault();
                    editarPaciente();

                }
            });
        
            // Escucha para el atajo Ctrl + 3
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '3') {
                    event.preventDefault();
                    agregarIngreso();
                    
                }
            });

            // Escucha para el atajo Ctrl + 4
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '4') {
                    event.preventDefault();
                    llamarAgregarAtencion();
                    
                }
            });
        
        
        
        
        }
        };
    
    // Inicializar tabla de pacientes
    initDataTable("data_table_paciente", API_URLS.listado_pacientes, pacienteColumnas);
    
    
    function editarPaciente() {
        const selectedRow = table.row('.selected').data();

            if (selectedRow) {
                let nombreSlug = slugify(
                    `${selectedRow.paciente__primer_nombre}-${selectedRow.paciente__primer_apellido}`
                ).substring(0, 30);
            var editarUrl = API_URLS.editar_paciente.replace('0', selectedRow.id).replace('slug', nombreSlug);
            window.location.href = editarUrl;
        } else {
            toastr.error("No hay ninguna fila seleccionada.");
        }
        }


    /**
     * Función modular para manejar la navegación a un nuevo formulario (excepto la verificación de Ingreso Activo).
     * @param {string} apiUrlKey - Clave de la URL en el objeto API_URLS (ej: 'agregarEvaluacionrx', 'agregarReferencia').
     * @param {string} actionName - Nombre de la acción para usar en los mensajes de advertencia (ej: 'una evaluación RX').
     */
    async function manejarAccionPaciente(apiUrlKey, actionName) {
        const selectedRow = table.row('.selected').data();

        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }

        try {
            const pacienteId = selectedRow.id;

            // 1. Verificar Defunción
            const estaMuerto = await verificarDefuncion(pacienteId);
            if (estaMuerto) {
                toastr.warning(`No se puede agregar ${actionName} a un paciente fallecido.`);
                return;
            }

            // 2. Verificar Paciente Inactivo
            const inactivo = await verificarPacienteInactivo(pacienteId);
            if (inactivo) {
                toastr.warning(`No se puede agregar ${actionName} a un paciente inactivo.`);
                return;
            }

            // 3. Generar URL
            const nombreSlug = slugify(`${selectedRow.primer_nombre}-${selectedRow.primer_apellido}`);
            if (!nombreSlug) {
                toastr.error("Hubo un problema al generar la URL.");
                return;
            }

            const destinoUrl = API_URLS[apiUrlKey]
                .replace('0', pacienteId)
                .replace('slug', nombreSlug);

            window.location.href = destinoUrl;

        } catch (error) {
            toastr.error("Ocurrió un error inesperado: " + error.message);
        }
    }

    async function agregarIngreso() {
        const selectedRow = table.row('.selected').data();

        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }

        try {
            // VERIFICACIÓN ÚNICA
            const ingresoActivo = await verificarIngreso(selectedRow.id);
            if (ingresoActivo) {
                toastr.warning("Este paciente ya tiene un ingreso activo.");
                return;
            }
            
            // El resto de verificaciones (defunción, inactivo) 
            await manejarAccionPaciente(
                'agregarIngreso', //llave del endpoint
                'un ingreso'
            );
            
        } catch (error) {
            toastr.error("Ocurrió un error inesperado: " + error.message);
        }
    }

    async function agregarEvaluacionrx() {
        await manejarAccionPaciente(
            'agregarEvaluacionrx', 
            'una evaluación RX'
        );
    }

    async function agregarReferencia() {
        await manejarAccionPaciente(
            'agregarReferencia', 
            'una referencia'
        );
    }


    async function llamarAgregarAtencion() {
        const selectedRow = table.row('.selected').data();
        // Verificar si se ha seleccionado una fila
        if (!selectedRow) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }

        const paciente = {
        id: selectedRow.id,
        dni: selectedRow.dni,
        nombre: concatenarLimpio(
            selectedRow.primer_nombre,
            selectedRow.segundo_nombre,
            selectedRow.primer_apellido,
            selectedRow.segundo_apellido
        ),
        numero: selectedRow.expediente_numero
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

        await agregarAtencion(paciente,servicio,null);
    }

    
});