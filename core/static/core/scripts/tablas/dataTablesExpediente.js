// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

    const API_URLS = {
        // camas_disponibles: urls["camasDisponibles"],
        listado_expedientes: urls["listadoExpedientes"],
        //agregar_paciente: urls["agregarPaciente"],
        ver_expediente: urls["expedienteVer"],
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
    dom: '<"superior "B<"column-select">f>t<"inferior"lip><"clear">', // oraganizacion de la estructra de la tabla
    
    buttons: [
        /*
        {
        text: '<i class="bi bi-plus-square boton-exportacion"></i>',  // Icono o texto para el botón
        titleAttr: 'Nuevo Expediemte',
        action: function ( e, dt, button, config ) {
            //window.location.href = API_URLS.agregar_paciente;
        }
        },*/ 
        {
        text: '<i class="bi bi-pencil boton-exportacion" ></i>',  // Icono o texto para el botón
        titleAttr: 'Editar Expediente',
        action: function ( e, dt, button, config ) {
            //editarPaciente();
    
        }
        }, 
        {
        extend: 'copyHtml5',
        text: '<i class="bi bi-clipboard boton-exportacion"></i>',
        exportOptions: {
                columns: ':visible'
        },
        titleAttr: 'Copiar al portapapeles',
        // no encontre otra manera toco reescribir la funcion original de datatbles 
        action: function (e, dt, button, config) {
            // Llamamos a la función original de 'copyHtml5' y luego mostramos el mensaje
            $.fn.dataTable.ext.buttons.copyHtml5.action.call(this, e, dt, button, config);
            toastr.info('¡Datos copiados exitosamente!');
    
        }     
        },
        {
        extend: 'print',
        titleAttr: 'Imprimir',
        text: '<i class="bi bi-printer boton-exportacion"></i>',
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


    const expedienteColumnas = [
        {
            data: "numero",
            responsivePriority: 1,
            render: function (data) {
                return data ? data.toString().padStart(6, '0') : "000000";
            },
        },
        { 
            data: "localizacion__descripcion_localizacion",
            responsivePriority: 2
        },
    
        { 
            data: "estado", 
            with: 10, 
            render: function (data, type, row) {
                let color = "icon-gris";
                let titleText = data ? data : "N/A"; 
                if (data == "2"){
                    color = "icon-verde";
                    titleText = "Libre";
                }else if (data == "1"){
                    color = "icon-rojo";
                    titleText = "Ocupado";

                }

                return `<i class="bi bi-circle-fill ${color}" title="${titleText}"></i>`;
            }
        }, 
        
        {   data: "propietario_dni", 
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
        {
            data: "propietario_nombres",
            responsivePriority: 4
        },
        {
            data: "propietario_apellidos",
        },
        {
            data: null,
            render: function(data){
                let asignacion = data.asignacion_estado === null ? "LIB" : (data.asignacion_estado == 1 ? "ACT" : "HIS");
                return asignacion
            }
            //"asignacion_estado",
        },
        {
            data: null,
            orderable: false,  // CORREGIDO
            render: function (data) {
                let fecha = data.fecha_modificado ? formatFecha(data.fecha_modificado) : "No disponible";
                let usuario = data.modificado_por__username || "Desconocido";
                return `<span>📅 ${fecha} | 👤 ${usuario}</span>`;
            },
        }, 
    
        { data: "id", visible: false }, 
    ];


    let table;
    const initDataTable = (tableId, ajaxUrl, columns) => {
        if (document.getElementById(tableId)) {
            // Inicialización de la tabla con opciones comunes y específicas
            table = $(`#${tableId}`).DataTable({
                searchDelay: 900, 
                ...commonOptions,
                ajax: {
                    url: ajaxUrl,
                    type: 'GET',
                    data: function(d) {      // parametros de busqueda 
                    d.search_value = $('#search-input').val();
                    d.search_column = $('#column-selector').val();
                    }
                },
                columns: columns,
                columnDefs: [
                    { targets: 0, className: 'PrimerColumnaAliIzq' },
                    { targets: 3, className: 'ColumnaDNI' },

                ],
                order: [[7, "desc"]], //columna por la cual se orderna al cargar
            });
        
                // Selector de columna para búsqueda rápida
                const select = $('<select id="column-selector" class="formularioCampo-select"><option value="0">Numero</option></select>')
                .appendTo($('.column-select'))
                .on('change', function () {
                    const searchValue = $('#dt-search-0').val().trim();
                    if (searchValue.length > 0) {
                        table.ajax.reload();
                    }
                });
        
            select.append('<option value="1">Identidad</option>');
            select.append('<option value="2">Nombres</option>');
            select.append('<option value="3">Apellidos</option>');

        
            // Redirecciona al hacer doble clic en una fila
            table.on('dblclick', 'tr', function() {
                const data = table.row(this).data();
                if (data) {
                    const id = data.id;
                    var verUrl = API_URLS.ver_expediente.replace('0', id);
                    window.location.href = verUrl;
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
                   // event.preventDefault(); // Evitar el comportamiento predeterminado
                    // window.location.href = API_URLS.agregar_paciente; // Redirigir a la URL especificada
                }
            });
        
            // Escucha para el atajo Ctrl + 2
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '2') {
                    //event.preventDefault();
                    //editarPaciente();

                }
            });
        
        
        
        
            // Escucha para el atajo Ctrl + 3
            document.addEventListener('keydown', (event) => {
                if (event.ctrlKey && event.key === '3') {
                    //event.preventDefault();
                    //AgregarIngresoModal();
                    
                }
            });
        
        
        
        
        }
        };
        

    // Inicializar tabla de pacientes
    initDataTable("data_table_expediente", API_URLS.listado_expedientes, expedienteColumnas);

});