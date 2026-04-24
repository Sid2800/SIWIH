$(document).ready(function () {
    
    const API_URLS = {
        // camas_disponibles: urls["camasDisponibles"],
        listar_expedientes_propietarios_API: urls["listarExpedientesPropietariosAPI"],
        editarPaciente: urls["editarPaciente"],

    };

    const commonOptions = {
        responsive: true,
        processing: false,
        serverSide: true,
        lengthMenu: [10, 25],
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
    dom: 't', // oraganizacion de la estructra de la tabla
    
    
    };

    
    const propietariosColumnas = [
        {
            data: "paciente__dni",
            responsivePriority: 1,
        },
        {
            data: "estado",
            render: function (data) {
                // Convertir a número si es un string
                let estado = parseInt(data, 10);
        
                if (estado === 0) {
                    return "Histórico";
                } else if (estado === 1) {
                    return "Actual";
                } else {
                    return "-"; // O algún otro valor por defecto
                }
            }
        },
    
        {
            data: "nombre_completo",
            responsivePriority: 2
        },
        {
            data: "fecha_asignacion",
            render: function (data) {
                if (data) {
                    let parts = data.split('-');
                    return `${parts[2]}/${parts[1]}/${parts[0]}`;  // Retorna en formato DD/MM/YYYY
                }
                return data; 
            },
        },
        {
            data: "fecha_liberacion",
            render: function (data) {
                if (data) {
                    let parts = data.split('-');
                    return `${parts[2]}/${parts[1]}/${parts[0]}`;  // Retorna en formato DD/MM/YYYY
                }
                return data; 
            },
        },
            
        { data: "paciente__id", visible: false }, 
        { data: "id", visible: false }, 

    ];

    let table;
    const initDataTable = (tableId, ajaxUrl, columns) => {
        if (document.getElementById(tableId)) {
            // Inicialización de la tabla con opciones comunes y específicas
            table = $(`#${tableId}`).DataTable({
                ...commonOptions,
                ajax: {
                    url: ajaxUrl,
                    type: 'GET',
                    data: function(d) {      // parametros de busqueda 
                    d.id_expediente = idExpediente;
                    }
                },
                columns: columns,
                
                columnDefs: [
                    { targets: 0, className: 'ColumnaDNI' },

                ],
                order: [[1, "desc"]], //columna por la cual se orderna al cargar
            });
        

            // Redirecciona al hacer doble clic en una fila
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                if (data) {
                    const id = data.paciente__id;
                    const nombreSlug = slugify(data.nombre_completo);
                    if (id && nombreSlug) {
                        let verUrl = API_URLS.editarPaciente.replace('0', id).replace('slug', nombreSlug);
                        
                        // Cambiar el cursor para mostrar que la acción está en progreso
                        document.body.style.cursor = 'progress';
                        
                        // Redirigir
                        window.location.href = verUrl;
                    } 
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
        
        
        }
        };
        

       // Inicializar tabla de pacientes
    initDataTable("data_table_expediente_propietarios", API_URLS.listar_expedientes_propietarios_API, propietariosColumnas);

    // Lógica de préstamos (Nueva)
    let tablePrestamos;
    function inicializarTablaHistorialPrestamos() {
        const tableId = "historialTablaPrestamos";
        const ajaxUrl = `/s_exp/api/historial-prestamos-expediente/${idExpediente}/`;

        if (document.getElementById(tableId)) {
            $.get(ajaxUrl, function (response) {
                const prestamos = response.data || [];

                // Mostrar badge de estado actual
                const badgeContainer = document.getElementById('prestamos-estado-badge');
                if (badgeContainer) {
                    if (response.en_prestamo) {
                        badgeContainer.innerHTML = '<span style="background:rgba(245,158,11,0.2);color:var(--negro);padding:0.3rem 0.8rem;border-radius:20px;font-size:1.3rem;font-weight:600;"><i class="bi bi-exclamation-triangle"></i> Expediente actualmente en préstamo</span>';
                    } else if (prestamos.length > 0) {
                        badgeContainer.innerHTML = '<span style="background:rgba(34,197,94,0.2);color:var(--negro);padding:0.3rem 0.8rem;border-radius:20px;font-size:1.3rem;font-weight:600;"><i class="bi bi-check-circle"></i> Sin préstamos activos</span>';
                    }
                }

                tablePrestamos = $(`#${tableId}`).DataTable({
                    responsive: true,
                    processing: true,
                    serverSide: false,
                    lengthMenu: [5, 10],
                    data: prestamos,
                    columns: [
                        { data: 'numero_expediente' },
                        { data: 'fecha_solicitud' },
                        { data: 'motivo' },
                        { data: 'solicitante' },
                        { data: 'area_destino' },
                        {
                            data: 'estado',
                            render: function (data) {
                                const colores = {
                                    'Pendiente': 'background:rgba(99,102,241,0.2);color:var(--negro);',
                                    'Aprobado': 'background:rgba(34,197,94,0.2);color:var(--negro);',
                                    'Rechazado': 'background:rgba(239,68,68,0.2);color:var(--negro);',
                                    'EnPrestamo': 'background:rgba(245,158,11,0.2);color:var(--negro);',
                                    'Devuelto': 'background:rgba(100,116,139,0.2);color:var(--negro);',
                                    'DevolucionParcial': 'background:rgba(249,115,22,0.2);color:var(--negro);',
                                    'Anulado': 'background:rgba(107,114,128,0.2);color:var(--negro);'
                                };
                                const estilo = colores[data] || '';
                                return `<span style="padding:0.2rem 0.5rem;border-radius:12px;font-size:1.2rem;font-weight:600;${estilo}">${data}</span>`;
                            }
                        },
                        {
                            data: 'devuelto',
                            render: function (data) {
                                return data
                                    ? '<i class="bi bi-check-circle-fill" style="color:var(--negro);"></i> Sí'
                                    : '<i class="bi bi-clock" style="color:var(--negro);"></i> No';
                            }
                        }
                    ],
                    language: {
                        lengthMenu: "Mostrar _MENU_ por página",
                        zeroRecords: "No se encontraron préstamos",
                        info: "_START_ a _END_ de _TOTAL_ registros",
                        infoEmpty: "0 a 0 de 0 registros",
                        infoFiltered: "(filtrado de _MAX_)",
                        search: "Buscar:",
                        paginate: { first: "<<", last: ">>", next: ">", previous: "<" },
                        loadingRecords: "Cargando...",
                        processing: "Procesando...",
                        emptyTable: "No hay préstamos registrados"
                    },
                    dom: '<"superior"f>t<"inferior"lip><"clear">',
                    order: [[1, "desc"]],
                });

                // Ajustar columnas al cargar
                setTimeout(() => {
                    if(tablePrestamos) tablePrestamos.columns.adjust().draw();
                }, 200);

            }).fail(function() {
                console.log('No se pudo cargar historial de préstamos (API no disponible)');
            });
        }
    }

    inicializarTablaHistorialPrestamos();

});




