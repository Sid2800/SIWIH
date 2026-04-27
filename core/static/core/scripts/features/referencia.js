document.addEventListener('DOMContentLoaded', function () {

//#region Dclaraciones de variables y constantes
    // Contenedores y elementos del DOM
    const contenedorTipo = document.querySelector('.referencia-referencia-tipo');
    const Enviada = document.getElementById('referencia-tipo-enviada');
    const Recibida = document.getElementById('referencia-tipo-recibida');

    // Paciente
    const idPaciente = document.querySelector("#id_idPaciente");
    const dniPaciente = document.getElementById("id_dniPaciente");
    const numeroExpediente = document.querySelector("#id_numeroExpediente");
    const nombreCompleto = document.querySelector("#id_nombreCompletoPaciente");
    const fechaNac = document.querySelector("#id_fechaNacimientoPaciente");
    const edad = document.querySelector("#id_edadPaciente");
    const sexo = document.querySelector("#id_sexoPaciente");
    const telefonoPaciente = document.querySelector("#id_telefonoPaciente");
    const direccionPaciente = document.querySelector("#id_direccionPaciente");

    // Tabs
    let tabActiva = 'camposReferencia';
    const tabReferencia = document.getElementById("referenciaTabRespuesta");

    // Evaluación de la referencia
    const contenedorEvaluacion = document.getElementById("contenedor-evaluacion");
    const contenedorInteractivo = document.getElementById("contenedor-interactivo");
    const fechaRecepcion = document.getElementById("id_fecha_recepcion");

    // Botones
    const botonGuardar = document.getElementById("formularioReferencia-botonGuardar");
    const textoOriginal = botonGuardar.innerHTML;
    const botonImprimir = document.getElementById("formularioReferencia-botonImprimir");

    // Variables condicionales dependientes del tipo de respuesta y modo
    //fielset 
    const fielsetSeguimiento =  document.querySelector(".referenciaRespuestaSeguimiento");
    const seguimientoInstitucional = document.getElementById("referencia-respuesta-seguimiento-institucional");
    const seguimientoPrimerNivel = document.getElementById("referencia-respuesta-seguimiento-primer-nivel");
    const seguimientoReferencia = document.getElementById("referencia-respuesta-seguimiento-referencia");
    // controles
    const seguimientoCampoRecibido1 = document.getElementById("seguimiento-campo-institucional-1");
    const seguimientoCampoRecibido2 = document.getElementById("seguimiento-campo-institucional-2");
    const seguimientoCampoEnviado = document.getElementById("seguimiento-campo-primer-nivel");
    const seguimientoCampoReferencia1 = document.getElementById("seguimiento-campo-referencia-1");
    const seguimientoCampoReferencia2 = document.getElementById("seguimiento-campo-referencia-2");

    // Respuesta
    let selectsRespuesta;
    const idRespuesta = document.getElementById("respuesta_idRespuesta") 
                || document.getElementById("respuesta_idRespuesta_env"); // Caso 2
    const idReferencia = document.getElementById("id_idReferencia");
    const respuestaFechaCita = document.getElementById("respuesta_fecha_cita");

    // Formularios
    const formReferencia = document.getElementById("form-referencia");
    const formRespuesta = document.getElementById("form-respuesta");
    const formRespuestaEnv = document.getElementById("form-respuesta-env");

    // Seguimiento TIC
    const ckSeguimientoTIC = document.getElementById("switchSeguimiento");
    const ckNoAtencion = document.getElementById("switchNoAtencion");
    const idMotivoNoAtencion = document.getElementById("id_motivo_no_atencion");


    



    // TomSelects
    const institucionOrigenSelect = new TomSelect("#id_institucion_origen", {
        valueField: "id",
        labelField: "text",
        searchField: "text",
        placeholder: 'INSTITUCION ORIGEN',
    });
    const institucionDestinoSelect = new TomSelect("#id_institucion_destino", {
        valueField: "id",
        labelField: "text",
        searchField: "text",
        placeholder: 'INSTITUCION DESTINO',
    });
    const especialidadDestinoSelect = new TomSelect("#id_especialidad_destino", {
        maxItems: 1,
        dropdownParent: 'body',
        valueField: "id",
        labelField: "text",
        searchField: "text",
        placeholder: 'ESPECIALIDAD DESTINO',
        maxOptions: 4
    });
    const unidadClinicaRefiereSelect = new TomSelect("#id_unidad_clinica_refiere", {
        valueField: "id",
        dropdownParent: 'body',
        labelField: "text",
        searchField: "text",
        placeholder: 'AREA REFIERE',
        allowEmptyOption: true,
        maxOptions: 4

    });

    // Variables de estado
    let tableRefDiagnostico;
    let datosRefDiagnostico = [];
    let tableResDiagnostico;
    let datosResDiagnostico = [];
    let timeout;

    // Opciones comunes para DataTable
    const commonOptionsRefDiagnostico = {
        responsive: true,
        processing: true,
        serverSide: false,
        lengthMenu: [5, 10],
        select: { style: 'single' },
        language: {
            lengthMenu: "Mostrar _MENU_ por página",
            zeroRecords: "No se encontraron diagnosticos",
            info: "_START_ a _END_ de _TOTAL_ diagnosticos",
            infoEmpty: "0 a 0 de 0 registros",
            infoFiltered: "(filtrado de _MAX_)",
            search: "Buscar:",
            paginate: { first: "<<", last: ">>", next: ">", previous: "<" },
            loadingRecords: "Cargando...",
            processing: "Procesando...",
            emptyTable: "No hay diagnosticos disponibles",
        },
        dom: '<"superiorRefDiagnostico"B>t<"datatable-inferior-referencia"lip>',
        buttons: [
            { text: '<i class="bi bi-plus-square boton-exportacion"></i>', titleAttr: 'Agregar Diagnostico', action: (e, dt, button, config) => AgregarEditarReferenciaDiagnostico(1) },
            { text: '<i class="bi bi-pencil boton-exportacion" ></i>', titleAttr: 'Editar Diagnostico', action: (e, dt, button, config) => AgregarEditarReferenciaDiagnostico(2) },
            { text: '<i class="bi bi-eraser-fill boton-exportacion" ></i>', titleAttr: 'Eliminar Diagnostico', action: (e, dt, button, config) => eliminarDiagnosticoSeleccionado(tableRefDiagnostico, datosRefDiagnostico, refrescarTablaRefDiagnostico) },
        ],
    };

    const commonOptionsResDiagnostico = {
        ...commonOptionsRefDiagnostico,
        buttons: [
            { text: '<i class="bi bi-plus-circle boton-exportacion"></i>', titleAttr: 'Agregar Diagnostico', action: (e, dt, button, config) => AgregarEditarRespuestaDiagnostico(1) },
            { text: '<i class="bi bi-pencil boton-exportacion"></i>', titleAttr: 'Editar Diagnostico', action: (e, dt, button, config) => AgregarEditarRespuestaDiagnostico(2) },
            { text: '<i class="bi bi-eraser-fill boton-exportacion" ></i>', titleAttr: 'Eliminar Diagnostico', action: (e, dt, button, config) => eliminarDiagnosticoSeleccionado(tableResDiagnostico, datosResDiagnostico, refrescarTablaResDiagnostico) },
        ]
    };

    // Columnas para DataTable
    const refDiagnosticoColumnas = [
        { data: 'id', visible: false },
        { data: 'idDiagDB', visible: false },
        { data: 'diagnostico', title: 'Diagnostico', responsivePriority: 1 },
        { data: 'detalle', title: 'Detalle' },
        {
            data: 'confirmado',
            title: 'Conf.',
            className: 'ColumnaCheck',
            render: (data, type, row, meta) => {
                const checked = data ? 'checked' : '';
                return `<input type="checkbox" class="chk-confirmado" data-index="${meta.row}" ${checked}>`;
            }
        },
    ];

    const resDiagnosticoColumnas = [
        { data: 'id', visible: false },
        { data: 'idDiagDB', visible: false },
        { data: 'diagnostico', title: 'Diagnostico', responsivePriority: 1 },
        { data: 'detalle', title: 'Detalle' }
    ];

//#endregion


//#region Funciones Auxiliares

    /**
     * muestra el modal que agrega un diagnostico o lo edita
     */
    async function AgregarEditarReferenciaDiagnostico(modo=1){
        if (modo===1){
            await modalAgregarEditarDiagnosticoReferenciaRespuesta(modo, "Agregar", null);
        }
        else if (modo===2){
            const diagnostico = tableRefDiagnostico.row('.selected').data();
            
            if (diagnostico) {
                await modalAgregarEditarDiagnosticoReferenciaRespuesta(modo, "Editar", diagnostico)
            } else {
                toastr.error("No hay ninguna fila seleccionada.");
            }
        }
        else {
        // Opcional: manejar modos no esperados
        console.warn(`Modo no reconocido: ${modo}`);
        }
    }

    async function AgregarEditarRespuestaDiagnostico(modo=1) {
        if (modo===1){
            await modalAgregarEditarDiagnosticoReferenciaRespuesta(modo, "Agregar", null ,"Respuesta");
        }
        else if (modo===2){
            const diagnostico = tableResDiagnostico.row('.selected').data();
            
            if (diagnostico) {
                await modalAgregarEditarDiagnosticoReferenciaRespuesta(modo, "Editar", diagnostico, "Respuesta")
            } else {
                toastr.error("No hay ninguna fila seleccionada.");
            }
        }
        else {
        // Opcional: manejar modos no esperados
        console.warn(`Modo no reconocido: ${modo}`);
        }
    }


    /**
     * Elimina la fila seleccionada de una tabla y del array de datos correspondiente
     * @param {DataTable} tabla - Instancia del DataTable donde está la fila
     * @param {Array} datos - Array que contiene los objetos mostrados en la tabla
     * @param {Function} refrescarTabla - Función que refresca la tabla después de eliminar
     */
    function eliminarDiagnosticoSeleccionado(tabla, datos, refrescarTabla) {
        // Obtener la fila seleccionada
        const fila = tabla.row('.selected').data();

        if (!fila) {
            toastr.error("No hay ninguna fila seleccionada.");
            return;
        }

        // Eliminar el elemento del array
        const index = datos.findIndex(item => item.id === fila.id);
        if (index !== -1) {
            datos.splice(index, 1);
        }

        // Refrescar la tabla
        refrescarTabla();
        toastr.success(`Diagnóstico con ID ${fila.id} eliminado correctamente.`);
    }

    /**
     * Refresca el contenido del DataTable con los datos actuales del arreglo.
     */
    function refrescarTablaRefDiagnostico() {
        tableRefDiagnostico.clear();
        tableRefDiagnostico.rows.add(datosRefDiagnostico);
        tableRefDiagnostico.draw();
        tableRefDiagnostico.responsive.recalc();
    }

    /**
     * Agrega un nuevo estudio o actualiza uno existente en el arreglo y refresca la tabla.
     */
    function actualizarOAgregarRefDiagnostico(refDiagId, diagnostico, detalle, confirmado) {
        const idEntero = parseInt(refDiagId);

        const index = datosRefDiagnostico.findIndex(est => est.id === idEntero);
        if (index !== -1) {
            datosRefDiagnostico[index].diagnostico = diagnostico;
            datosRefDiagnostico[index].detalle = detalle;
            datosRefDiagnostico[index].confirmado = confirmado;
        } else {
            datosRefDiagnostico.push({ id: idEntero, idDiagDB:0, diagnostico, detalle, confirmado });
        }

        refrescarTablaRefDiagnostico();
    }

    
    /**
     * Inicializa el DataTable, controles personalizados, eventos y TomSelect.
     */
    function inicializarTablaRefDiagnostico() {
        const tableId = "referencia-tabla-referencia-diagnosticos";

        if (document.getElementById(tableId)) {
            tableRefDiagnostico = $(`#${tableId}`).DataTable({
                ...commonOptionsRefDiagnostico,
                data: datosRefDiagnostico,
                paging: false, 
                stripe: true,
                responsive: true,
                columns: refDiagnosticoColumnas,
                order: [[1, "asc"]],
                initComplete: function () {


                }
            });

            // Checkbox: actualizar valor impreso en el arreglo
            $('#referencia-tabla-referencia-diagnosticos tbody').on('change', '.chk-confirmado', function () {
                const row = tableRefDiagnostico.row($(this).closest('tr'));
                const data = row.data();
                if (data) data.confirmado = this.checked;
            });

            // Doble clic para editar estudio
            tableRefDiagnostico.on('dblclick', 'tr', async function () {
                
                const data = tableRefDiagnostico.row(this).data();
                if (data) {
                    tableRefDiagnostico.$('tr.selected').removeClass('selected');
                    $(this).addClass('selected');
                    await modalAgregarEditarDiagnosticoReferenciaRespuesta(2, "Editar", data)
                }
            });

            // Clic simple para selección visual
            tableRefDiagnostico.on('click', 'tbody tr', (e) => {
                let classList = e.currentTarget.classList;
                if (classList.contains('child')) return;
                if (classList.contains('selected')) {
                    classList.remove('selected');
                } else {
                    tableRefDiagnostico.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                    classList.add('selected');
                }
            });
        }
    }


    /**
     * Agrega un nuevo diagnostico o actualiza uno existente en el arreglo y refresca la tabla.
     */
    function actualizarOAgregarResDiagnostico(resDiagId, diagnostico, detalle) {
        const idEntero = parseInt(resDiagId);
        const index = datosResDiagnostico.findIndex(est => est.id === idEntero);
        if (index !== -1) {
            datosResDiagnostico[index].diagnostico = diagnostico;
            datosResDiagnostico[index].detalle = detalle;
        } else {
            datosResDiagnostico.push({ id: idEntero, idDiagDB:0, diagnostico, detalle });
        }

        refrescarTablaResDiagnostico();
    }

    function refrescarTablaResDiagnostico() {
        tableResDiagnostico.clear();
        tableResDiagnostico.rows.add(datosResDiagnostico);
        tableResDiagnostico.draw();
        tableResDiagnostico.responsive.recalc();
    }

    /**
     * Inicializa el DataTable de respuesta, controles personalizados, eventos y TomSelect.
     */
    function inicializarTablaResDiagnostico() {
        const tableId = "referencia-tabla-respuesta-diagnosticos";

        if (document.getElementById(tableId)) {
            tableResDiagnostico = $(`#${tableId}`).DataTable({
                ...commonOptionsResDiagnostico,
                data: datosResDiagnostico,
                paging: false, 
                stripe: true,
                responsive: true,
                columns: resDiagnosticoColumnas,
                order: [[1, "asc"]],
                initComplete: function () {

                }
            });


            // Doble clic para editar estudio
            tableResDiagnostico.on('dblclick', 'tr', async function () {
                
                const data = tableResDiagnostico.row(this).data();
                if (data) {
                    tableResDiagnostico.$('tr.selected').removeClass('selected');
                    $(this).addClass('selected');
                    await modalAgregarEditarDiagnosticoReferenciaRespuesta(2, "Editar", data, "Respuesta");
                }
            });

            // Clic simple para selección visual
            tableResDiagnostico.on('click', 'tbody tr', (e) => {
                let classList = e.currentTarget.classList;
                if (classList.contains('child')) return;
                if (classList.contains('selected')) {
                    classList.remove('selected');
                } else {
                    tableResDiagnostico.rows('.selected').nodes().each((row) => row.classList.remove('selected'));
                    classList.add('selected');
                }
            });
        }
    }


    function limpiarCamposPaciente() {
        idPaciente.value = "";
        dniPaciente.value = "";
        numeroExpediente.value = "";
        nombreCompleto.value = "";
        fechaNac.value = "";
        edad.value = "";
        sexo.value = "";
        telefonoPaciente.value = "";
        direccionPaciente.value = "";
    }

    /**
      * Llena o limpia los campos del formulario según los datos del paciente.
      * @param {object} paciente - Objeto con datos del paciente; si está vacío, se limpian los campos.
      */
    function llenarCamposPaciente(paciente) {
        idPaciente.value = paciente.id || "";
        numeroExpediente.value = paciente.numeroExp ? paciente.numeroExp.toString() : "";
        dniPaciente.value = paciente.dni || "";
        nombreCompleto.value = paciente.nombreCompleto || "";
        fechaNac.value = paciente.fechaNacimiento || "";
        edad.value = paciente.edad || "";
        sexo.value = paciente.sexo || "";
        telefonoPaciente.value = paciente.telefono || "";
        direccionPaciente.value = paciente.direccion || "";
    }


    /**
     * Maneja el resultado de la búsqueda de un paciente y actualiza la UI.
     * @param {string} numero El DNI o número de expediente.
     * @param {string} indicador El tipo de búsqueda: "DNI" o "EXP".
     */
    async function obtenerDatosPacienteExpedienteIdentidad(numero, indicador) {
        // Llama a la función de negocio para obtener los datos
        const data = await buscarPaciente(numero, indicador);
        
        if (data) {
            // Se encontraron datos, se actualiza la UI
            if (data.extrajero) {
                quitarMascaraIdentidad();
            } else {
                aplicarMascaraIdentidad();
            }
            llenarCamposPaciente(data);
        } else {
            // No se encontraron datos o hubo un error, se limpia la UI
            limpiarCamposPaciente();
            toastr.info("No se encontraron datos para el paciente.");
        }
    }

    /**
     * Aplicar las mascaras Identadad
     */
    function aplicarMascaraIdentidad() {
        Inputmask({
            regex: regexIdentidad,
            placeholder: formatoIdentidad,
            oncomplete: async function () {
                
                try {
                    await obtenerDatosPacienteExpedienteIdentidad(this.value, "DNI");
                } catch (error) {
                    console.error("Error en la llamada a obtenerDatosPacienteExpedienteIdentidad:", error);
                }
            },
            oncleared: function () {
                limpiarCamposPaciente();
            }
        }).mask(dniPaciente);
    }

    function quitarMascaraIdentidad() {
        if (dniPaciente) {
            Inputmask.remove(dniPaciente);
        }
    }
    
    // Función para mapear los datos del paciente
    function mapearDatosPaciente(data) {
        return {
            id: data.id,
            numeroExp: data.expediente_numero,
            dni: data.dni,
            nombreCompleto: concatenarLimpio(data.primer_nombre,data.segundo_nombre,data.primer_apellido,data.segundo_apellido),
            fechaNacimiento: formatearFechaSimple(data.fecha_nacimiento),
            edad: calcularEdadComoTexto(data.fecha_nacimiento),
            sexo: data.sexo === "H" ? "HOMBRE" : "MUJER",
            telefono: data.telefono,
            direccion: concatenarLimpio(data.sector__aldea__municipio__departamento__nombre_departamento,data.sector__aldea__municipio__nombre_municipio,data.sector__nombre_sector),
            extranjero: data.es_extranjero_pasaporte ? true : false   
        };
    }


    /**
     * establece un valor defecto a la insitucion destino
     * >>>>>  desbloquea algunos controles refentes
    */
    function modoReferenciaRecibida(){
        institucionDestinoSelect.setValue(65);  /*es el id del cerrato*/
        institucionDestinoSelect.disable();
        institucionOrigenSelect.clear(); 
        institucionOrigenSelect.enable();
        contenedorEvaluacion.classList.remove("oculto");
        contenedorInteractivo.classList.add("oculto");
        //limpiamos los select de ref enviada
        especialidadDestinoSelect.clear();
        unidadClinicaRefiereSelect.clear();

        fechaRecepcion.disabled = false;
    }

    /**
     * establece un valor defecto a la insitucion origen
     * >>>>>  desbloquea algunos controles refentes
    */
    function modoReferenciaEnviada(){
        institucionOrigenSelect.setValue(65);  /*es el id del cerrato*/
        institucionOrigenSelect.disable();
        institucionDestinoSelect.clear();
        institucionDestinoSelect.enable();
        contenedorEvaluacion.classList.add("oculto");
        //LIMPIAR LOS OBJETOS DE EVALUACION
        document.querySelector('input[name="justificada"][value="3"]').checked = true;
        document.querySelector('input[name="oportuna"][value="3"]').checked = true;
        contenedorInteractivo.classList.remove("oculto");
        fechaRecepcion.disabled = true;
    }

    
    /*Muestra un ventana flotante o modal que poermite agregar un diagnostico*/
    async function modalAgregarEditarDiagnosticoReferenciaRespuesta(
                                        modo=1,
                                        accion="Agregar", 
                                        diagnostico=null,
                                        modelo="Referencia"
                                        ){
        const incluirConfirmado = modelo === "Referencia";

        const modal = await Swal.fire({
            title: `${accion} diagnostico de ${modelo.toLowerCase()}`,
            html: `
                    <fieldset class="modalReferenciaDiagnosticoCampos">
                    <legend> Diagnostico</b></legend>

                    <div class="formularioCampoModal">
                        <label for="modal-referencia-diagnostico">Diagnostico</label>
                        <select id="modal-referencia-diagnostico" class="formularioCampo-select" name="diagnostico">
                            <option value="" disabled selected>Seleccione un diagnostico</option>
                        </select>
                    </div>

                    <div class="formularioCampoModal">
                        <label for="modal-referencia-diagnostico-detalle">Detalle</label>
                        <textarea id="modal-referencia-diagnostico-detalle" class="formularioCampo-select no-resize" rows=2></textarea>
                    </div>
                    ${incluirConfirmado ? `
                    <label id="modal-referencia-diagnostico-check" class="ck-formulario" for="referencia-diagnostico-confirmado">
                        <input type="checkbox" id="referencia-diagnostico-confirmado" class="ck-formulario__checkbox" hidden>
                        <div class="ck-formulario__base">
                            <div class="ck-formulario__bolita"></div>
                        </div>
                        <span class="ck-formulario__label">Confirmado</span>
                    </label>
                    ` : ""}
                    </fieldset>
                `,
            showCancelButton: true,
            showCloseButton: true,
            confirmButtonText: modo === 1 
                ? '<i class="bi bi-plus-circle-fill"></i> Agregar' 
                : '<i class="bi bi-floppy2-fill"></i> Guardar',
            cancelButtonText: modo === 1 
                ? '<i class="bi bi-check-circle-fill"></i> Finalizar' 
                : '<i class="bi bi-x-octagon-fill"></i> Cancelar',
            customClass: {
                popup: 'contener-modal-defuncion',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'
            },
            preConfirm: () => {
                const diagnosticoTom = document.getElementById('modal-referencia-diagnostico').tomselect;
                const id = diagnosticoTom.getValue();
                const datosItem = diagnosticoTom.options[id]; 
                const diagnostico = datosItem ? datosItem.text : '';
                
                const detalle = document.getElementById("modal-referencia-diagnostico-detalle").value.toUpperCase();
                
                const confirmado = incluirConfirmado 
                    ? document.getElementById("referencia-diagnostico-confirmado").checked 
                    : false;
                
                if (!id || id.length === 0) {
                    Swal.showValidationMessage('Debe seleccionar un diagnostico');
                    return false; // evita que cierre hasta que haya validación
                }

                return { id ,diagnostico, detalle, confirmado };
            },
            didOpen: async function () { 
                const diagnosticoSelect = document.getElementById("modal-referencia-diagnostico");
                const detalle = document.getElementById("modal-referencia-diagnostico-detalle");
                const confirmado = incluirConfirmado ? document.getElementById("referencia-diagnostico-confirmado") : null;

                // Cargar los diagnostico desde el backend
                try {
                    const data = await fetchData(urls["listarDiagnostico"]);
                    if (Array.isArray(data) && data.length > 0) {
                    data.forEach(item => {
                        const option = new Option(
                            concatenarLimpio(item.cie10__codigo, ' | ', item.nombre_diagnostico),
                            item.id
                        );
                        diagnosticoSelect.appendChild(option);
                    });
                    } else {
                    console.warn("No se encontraron salas.");
                    }
                } catch (error) {
                    console.error("Error al cargar salas:", error);
                }

                // Inicializar TomSelect
                const diagnosticoTomSelect = new TomSelect("#modal-referencia-diagnostico", {
                    placeholder: 'Seleccione una diagnostico',
                    allowEmptyOption: true
                });


                function llenarDiagnostico(diagnostico) {
                    detalle.value = diagnostico.detalle || "";
                    if (incluirConfirmado && confirmado ){confirmado.checked = diagnostico.confirmado;}
                    diagnosticoTomSelect.setValue(diagnostico.id); 
                }

                // manejar el modo 
                if (modo===1){
                    diagnosticoTomSelect.focus();
                } else if (modo === 2 && diagnostico != null) {
                    llenarDiagnostico(diagnostico);
                    detalle.focus();
                }

            }
        });
        if (modal.isConfirmed) {
            //resultado = modal.value;
            const { id ,diagnostico, detalle, confirmado } = modal.value;
            if (modo === 1) {
                // Agregar → mantener abierto
                
                if (incluirConfirmado){ // osea es referencia 
                 // es igual deriva de ->  const incluirConfirmado = modelo === "Referencia";
                    actualizarOAgregarRefDiagnostico(id, diagnostico, detalle, confirmado);
                    return await modalAgregarEditarDiagnosticoReferenciaRespuesta(1, "Agregar")
                }else{
                    actualizarOAgregarResDiagnostico(id, diagnostico, detalle);
                    return await modalAgregarEditarDiagnosticoReferenciaRespuesta(modo, "Agregar", null ,"Respuesta");
                }
            } else if (modo === 2) {
                //return resultado;
                if (incluirConfirmado){
                    actualizarOAgregarRefDiagnostico(id, diagnostico, detalle, confirmado);
                    return null;
                } else {
                    actualizarOAgregarResDiagnostico(id, diagnostico, detalle)
                    return null;
                }
            }
        } else if (modal.isDismissed) {
            return null;
                
        }
    }


    // Subfunción para restaurar el botón
    function habilitarBoton() {
        botonGuardar.disabled = false;
        botonGuardar.innerHTML = textoOriginal;
    }

    // metodo para ajustar el texto dinameincamente
    function ajustarTextoBotonGuardar(tab) {
        let modo = '';
        let model = '';
        if (tab === 'camposRespuesta' || tab === 'camposRespuestaEnv' ) {
            model = 'Respuesta';
            modo = (idRespuesta.value == 0) ? 'Registrar' : 'Actualizar';
        } else if (tab === 'camposReferencia') {
            model = 'Referencia';
            modo = (modoUso === 2) ? 'Actualizar' : 'Registrar';
        } 

        botonGuardar.innerHTML = `
            <i class="bi bi-floppy2-fill formularioBotones-icono"></i>
            <span>${modo} ${model}</span>
        `;
    }

    // metodo que cotrola el boton de imprimir
    function actualizarVisibilidadBotonImprimir(tabActiva) {
        if (!botonImprimir) return;

        const esTabRespuesta = tabActiva === 'camposRespuesta' || tabActiva === 'camposRespuestaEnv';

        let debeMostrarse = false;

        if (esTabRespuesta) {
            debeMostrarse = Number(idRespuesta.value) > 0;
        } else {
            debeMostrarse = Number(idReferencia.value) > 0;
        }

        if (debeMostrarse) {
            botonImprimir.classList.remove('oculto');
        } else {
            botonImprimir.classList.add('oculto');
        }
    }


    // Inicializador de selects de respuesta
    function inicializarFormRespuesta() {


        // Función helper para inicializar un select solo si existe
        function initTomSelect(id, placeholder, fueraDelContenedor = false) {
            const el = document.getElementById(id);
            if (!el) {
                console.warn(`⚠️ No se encontró el select con id "${id}"`);
                return null;
            }

            const options = {
                valueField: "id",
                labelField: "text",
                searchField: "text",
                placeholder: placeholder,
            };

            if (fueraDelContenedor) {
                options.dropdownParent = 'body';
            }

            return new TomSelect(`#${id}`, options);
        }

        // Declaración global de los selects (todas inicializadas en null)
        let respuestaAreaCaptaSelect = null;
        let respuestaUnidaClinicaRespondeSelect = null;
        let respuestaSeguimientoAreaAtencionSelect = null;
        let respuestaMotivoSelect = null;
        let respuestaElaboradaPorSelect = null;
        let respuestaAtencionRequeridaSelect = null;
        let respuestaInstitucionDestinoSelect = null;
        let respuestaSeguimientoReferenciaDestinoSelect = null;
        let respuestaSeguimientoReferenciaEspecialidadSelect = null;

        // Si el tipo es 0 (recibida), inicializamos campos exclusivos
        if (tipo === 0) {
            respuestaAreaCaptaSelect = initTomSelect("respuesta_area_capta", "ÁREA QUE CAPTA", true);
            respuestaUnidaClinicaRespondeSelect = initTomSelect("respuesta_unidad_clinica_responde", "ÁREA QUE RESPONDE", true);
            respuestaSeguimientoAreaAtencionSelect = initTomSelect("respuesta_area_seguimiento_area_atencion", "SEGUIMIENTO AREA ATENCION", true);
            respuestaSeguimientoReferenciaDestinoSelect = initTomSelect("respuesta_seguimiento_referencia_institucion_destino","INSTITUCION DESTINO", true);
            respuestaSeguimientoReferenciaEspecialidadSelect = initTomSelect("respuesta_seguimiento_referencia_especialidad_destino","ESPECIALIDAD DESTINO", true);
        }

        // Inicializamos los campos comunes
        respuestaMotivoSelect = initTomSelect("respuesta_motivo", "MOTIVO");
        respuestaElaboradaPorSelect = initTomSelect("respuesta_elaborada_por", "ELABORADO POR"); 
        respuestaAtencionRequeridaSelect = initTomSelect("respuesta_atencion_requerida", "ATENCIÓN REQUERIDA");
        respuestaInstitucionDestinoSelect = initTomSelect("respuesta_institucion_destino", "INSTITUCIÓN DESTINO",true);

        // Retornar todos los objetos 
        return {
            respuestaAreaCaptaSelect,
            respuestaUnidaClinicaRespondeSelect: respuestaUnidaClinicaRespondeSelect,
            respuestaMotivoSelect,
            respuestaElaboradaPorSelect,
            respuestaAtencionRequeridaSelect,
            respuestaInstitucionDestinoSelect,
            respuestaSeguimientoAreaAtencionSelect,
            respuestaSeguimientoReferenciaDestinoSelect,
            respuestaSeguimientoReferenciaEspecialidadSelect
        };
    }

    // verifiar paciente
    function verificarPaciente() {
            if (!idPaciente.value) {
                toastr.error("No se ha seleccionado un paciente válido. Por favor, indique un paciente para registrar la referencia.");
                dniPaciente.select();
                return false;
            }
            return true;
        }
    
    async function modalAgregarEditarSeguimientoTIC(idRef) {
        
        const idSeguimiento = document.getElementById("id_idSeguimiento")
        ? document.getElementById("id_idSeguimiento").value
        : 0;


        const resultado = await agregarEditarSeguimientoTIC(
            idSeguimiento ? idSeguimiento : 0,
            idRef,
            nombreCompleto.value ? nombreCompleto.value : "existe una inconveniencia con el nombre" 
        );

        
        if(resultado && resultado.guardo){
            document.getElementById("id_idSeguimiento").value = resultado.idSeguimiento
            ckSeguimientoTIC.checked=true;
        } else {
            toastr.warning("No se guardo el seguimiento", "Seguimiento TIC");
        }   


    }

    async function estableceNoAtencion(nombrePaciente, noAtencion) {
        let resultado = null;

        const modal = await Swal.fire({
            title: `<i class="bi-person-check"></i> Defina motivo de No Atención`,
            html: `
                <fieldset class="modalNoAtencion">
                    <legend>Motivo de no atención de: <b>${nombrePaciente}</b></legend>

                    <div class="modal-no-atencion-checks">
                        <label class="ck-formulario" for="chk-alta-exigida">
                            <input type="checkbox" id="chk-alta-exigida" class="ck-formulario__checkbox" hidden>
                            <div class="ck-formulario__base">
                                <div class="ck-formulario__bolita"></div>
                            </div>
                            <span class="ck-formulario__label">Alta Exigida</span>
                        </label>

                        <label class="ck-formulario" for="chk-fuga">
                            <input type="checkbox" id="chk-fuga" class="ck-formulario__checkbox" hidden>
                            <div class="ck-formulario__base">
                                <div class="ck-formulario__bolita"></div>
                            </div>
                            <span class="ck-formulario__label">Fuga</span>
                        </label>

                        <label class="ck-formulario" for="chk-otro">
                            <input type="checkbox" id="chk-otro" class="ck-formulario__checkbox" hidden>
                            <div class="ck-formulario__base">
                                <div class="ck-formulario__bolita"></div>
                            </div>
                            <span class="ck-formulario__label">Otro</span>
                        </label>
                    </div>
                </fieldset>
            `,
            showCancelButton: true,
            showCloseButton: true,
            confirmButtonText: '<i class="bi bi-floppy-fill"></i> Definir',
            cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
            customClass: {
                popup: 'contener-modal-defuncion',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'
            },

            preConfirm: () => {
                const altaExigida = document.getElementById("chk-alta-exigida");
                const fuga = document.getElementById("chk-fuga");
                const otro = document.getElementById("chk-otro");

                let motivo = 0;

                if (altaExigida.checked) motivo = 2;
                if (fuga.checked) motivo = 1;
                if (otro.checked) motivo = 3;

                return motivo;
            },

            didOpen: () => {
                const altaExigida = document.getElementById("chk-alta-exigida");
                const fuga = document.getElementById("chk-fuga");
                const otro = document.getElementById("chk-otro");

                const all = [altaExigida, fuga, otro];

                // solo uno marcado a la vez
                all.forEach(chk => {
                    chk.addEventListener("change", () => {
                        if (chk.checked) {
                            all.forEach(o => {
                                if (o !== chk) o.checked = false;
                            });
                        }
                    });
                });

                // Cargar selección cuando ya existía
                noAtencion = parseInt(noAtencion) || 0;

                if (noAtencion === 1) fuga.checked = true;
                if (noAtencion === 2) altaExigida.checked = true;
                if (noAtencion === 3) otro.checked = true;
            }
        });

        if (modal.isConfirmed) {
            resultado = modal.value;
        }

        return resultado;
    }


//#endregion


//#region manejo de eventos

    // disparador del chek enviada
    Enviada.addEventListener('change', (e) => {
        if (e.target.checked) {
            modoReferenciaEnviada();
        }
    });

    //  disparador del chek "Recibida"
    Recibida.addEventListener('change', (e) => {
        if (e.target.checked) {
            modoReferenciaRecibida();
        } 
    });


    /*Listener para la buscad de paciente por el campo expediente */
    numeroExpediente.addEventListener("input", function (event) {
        // Verifica que el campo no esté deshabilitado
        if (this.disabled) return;
    
        // Si el campo está vacío o contiene solo espacios, limpiamos los datos
        if (!this.value.trim()) {
            clearTimeout(timeout);
            limpiarCamposPaciente();

        } else {
            clearTimeout(timeout);
            timeout = setTimeout(function () {
                const query = event.target.value;
                // Realizar la búsqueda aquí (por ejemplo, con fetch)
                obtenerDatosPacienteExpedienteIdentidad(query,"EXP");            
            }, 1000);
        }
    });


    //Lisneter que despliega la busqueda 
    dniPaciente.addEventListener("dblclick", async function() {
        let data = await mostrasBusquedaPaciente();

        if (!data) {
            return; 
        }
        if (data.dni) {
            obtenerDatosPacienteExpedienteIdentidad(data.dni, "DNI");
        } else if (data.expediente_numero) {
            obtenerDatosPacienteExpedienteIdentidad(data.expediente_numero, "EXP");
        }
    });


    numeroExpediente.addEventListener("dblclick", async function(){
        let data = await mostrasBusquedaPaciente();
        if (!data) {
            return; 
        }

        if (data.dni){
            obtenerDatosPacienteExpedienteIdentidad(data.dni, "DNI")
        } else if (data.expediente_numero){
            obtenerDatosPacienteExpedienteIdentidad(data.expediente_numero, "EXP")
        }
    })


    // accion del boton
    botonGuardar.addEventListener("click", async function(){
        if (tabActiva==='camposReferencia'){
            await enviarFormularioReferencia();
        }else if(tabActiva==='camposRespuesta') {
            await enviarFormularioRespuesta(formRespuesta);
        }else if(tabActiva==='camposRespuestaEnv'){
            await enviarFormularioRespuesta(formRespuestaEnv);
        }

        
    });

    // accion del boton de imprimir
    if (botonImprimir) {
        botonImprimir.addEventListener("click", async function () {
            if (tabActiva==='camposReferencia'){
                imprimirFormatoGenerico(idReferencia.value,API_URLS.reporteFormatoReferencia,"Referencia")
            } else {
                imprimirFormatoGenerico(idRespuesta.value,API_URLS.ReporteFormatoRespuesta,"Respuesta")
            }
            console.table(API_URLS);
        });
    }



    // Función para mostrar y ocultar campos
    function toggleCampos({ mostrar = [], ocultar = [] }) {
        mostrar.forEach(el => el?.classList.remove("oculto"));
        ocultar.forEach(el => el?.classList.add("oculto"));
    }


    if (modoUso === 2 && seguimientoInstitucional) {
        seguimientoInstitucional.addEventListener("click", () => {
            toggleCampos({
                mostrar: [seguimientoCampoRecibido1, seguimientoCampoRecibido2],
                ocultar: [seguimientoCampoEnviado, seguimientoCampoReferencia1, seguimientoCampoReferencia2]
            });

            if (typeof tipo !== 'undefined' && tipo === 0) { // referencia recibida
                selectsRespuesta.respuestaInstitucionDestinoSelect.clear();
                selectsRespuesta.respuestaSeguimientoReferenciaDestinoSelect.clear();
                selectsRespuesta.respuestaSeguimientoReferenciaEspecialidadSelect.clear();
            }

            fielsetSeguimiento.classList.add("ajustado");
        });
    }

    if (modoUso === 2 && seguimientoPrimerNivel) {
        seguimientoPrimerNivel.addEventListener("click", () => {
            toggleCampos({
                mostrar: [seguimientoCampoEnviado],
                ocultar: [seguimientoCampoRecibido1, seguimientoCampoRecibido2, seguimientoCampoReferencia1, seguimientoCampoReferencia2]
            });

            if (typeof tipo !== 'undefined' && tipo === 0) { // referencia recibida
                selectsRespuesta.respuestaSeguimientoAreaAtencionSelect.clear();
                respuestaFechaCita.value = fechaActualParaInput(conHora=false);
                selectsRespuesta.respuestaSeguimientoReferenciaDestinoSelect.clear();
                selectsRespuesta.respuestaSeguimientoReferenciaEspecialidadSelect.clear();
            }
            fielsetSeguimiento.classList.remove("ajustado");
            
        });
    }

    if (modoUso === 2 && seguimientoReferencia) {
        seguimientoReferencia.addEventListener("click", () => {
            toggleCampos({
                mostrar: [seguimientoCampoReferencia1, seguimientoCampoReferencia2],
                ocultar: [seguimientoCampoRecibido1, seguimientoCampoRecibido2, seguimientoCampoEnviado]
            });

            fielsetSeguimiento.classList.add("ajustado");
            if (typeof tipo !== 'undefined' && tipo === 0) { // referencia recibida
                selectsRespuesta.respuestaSeguimientoAreaAtencionSelect.clear();
                respuestaFechaCita.value = fechaActualParaInput(conHora=false);
                selectsRespuesta.respuestaInstitucionDestinoSelect.clear();
            }

        });
    }
    
    
    if (modoUso === 2 && ckSeguimientoTIC){
        ckSeguimientoTIC.addEventListener("click", async function(e){
            e.preventDefault();
        if (idReferencia.value == 0 || tipo === 0) { 
            // Validar que exista referencia y que sea tipo enviada
            toastr.error("NO es posible registrar el seguimiento TIC de esta referencia ");
            return
        }
        // Abrir modal para agregar o editar el seguimiento TIC
        await modalAgregarEditarSeguimientoTIC(idReferencia.value);
    })
    }

    if (modoUso === 2 && ckNoAtencion){
        ckNoAtencion.addEventListener("click", async function(e){
            e.preventDefault();
        const nombre = nombreCompleto.value ? nombreCompleto.value : "existe una inconveniencia con el nombre";
        const idMotivo = idMotivoNoAtencion.value ? idMotivoNoAtencion.value : 0;

        if (tipo === 1 ) { 
            // Validar que exista referencia y que sea tipo enviada
            toastr.error("NO es posible registrar una no atenciona este tipo de referencia ");
            return
        }

        if (idRespuesta.value != 0 && idMotivo == 0) { 
            // Validar que exista referencia y que sea tipo enviada
            toastr.error("NO es posible registrar una no atencion a una referencia con repuesta");
            return
        }
        

        // Abrir modal para agregar o editar el seguimiento TIC
        const noAtencion = await estableceNoAtencion(nombre, idMotivo);
        if (noAtencion != null) idMotivoNoAtencion.value = noAtencion;
        ckNoAtencion.checked = Number(idMotivoNoAtencion.value) !== 0;
                

    })
    }

    



//#endregion


//#region /*Inicializacion de fromulario*/

    aplicarMascaraIdentidad();

    //numeroExp
    Inputmask({
        regex: regexNumeroExpediente, 
        placeholder: formatoNumeroExpediente,  
    }).mask(numeroExpediente);
    
    /*mascara telefono*/
    Inputmask({
            regex: regexTelefono,
            placeholder: formatoTelefono,
    }).mask(telefonoPaciente);

    inicializarTablaRefDiagnostico();



    // Lógica del tab
    document.querySelectorAll('.referenciaTabsBoton').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault(); // evita saltos del link

            const tabId = btn.dataset.tab;
            const motivoHidden = document.getElementById("id_motivo_no_atencion");
            const motivoValor = Number(motivoHidden ? motivoHidden.value : 0);

            // intenta ir al tab de respuesta y hay No Atención, solo advertencia
            if ((tabId === "camposRespuesta" || tabId === "camposRespuestaEnv") && motivoValor > 0) {
                Swal.fire({
                    title: `<i class="bi bi-exclamation-triangle-fill"></i> Atención`,
                    html: `Esta referencia tiene un motivo de <b>NO ATENCIÓN</b> registrado.<br>
                            Si registra una respuesta, la <b>No Atención será eliminada automáticamente</b>.`,
                    showCancelButton: false,
                    confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Entendido',
                    customClass: {
                        popup: 'contenedor-modal',
                        title: 'contener-modal-titulo',
                        htmlContainer: 'contener-modal-contenedor-html',
                        confirmButton: 'contener-modal-boton-confirmar',
                        actions: 'contener-modal-contenedor-botones-min'
                    }
                });
            }

            // Activación normal del tab
            document.querySelectorAll('.referenciaTabsBoton').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.referencia-tab-contenido').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const tabContenido = document.getElementById(tabId);
            tabContenido.classList.add('active');

            
            // Actualiza la variable global
            tabActiva = tabId;

            ajustarTextoBotonGuardar(tabActiva);
            actualizarVisibilidadBotonImprimir(tabActiva);

            
        });
    });



    // inizializar el tipo de referencia
    if (modoUso === 1) {
        if (typeof tipo !== 'undefined' && tipo === 0) {
            Recibida.checked = true;
            Recibida.dispatchEvent(new Event('change'));
        }
        unidadClinicaRefiereSelect.clear();
    } else if (modoUso === 2) { // Modo edicion de reerencia puede 
    // // ser modo add o edicion respuesta
        
        // iniciamos la referencia en modo edicion en primer lugar

        //manejo de los campos dependientes del tipo de referncia 
        if (typeof tipo !== 'undefined' && tipo === 0) { //recibida
            Recibida.checked = true;
            institucionDestinoSelect.disable();
            contenedorInteractivo.classList.add("oculto");
        } else if (typeof tipo !== 'undefined' && tipo === 1) { // enviada
            Enviada.checked = true;
            institucionOrigenSelect.disable();
            contenedorEvaluacion.classList.add("oculto");
            fechaRecepcion.disabled = true;
        }
        document.querySelector('.referencia-referencia-tipo').classList.add('bloqueado');

        /*bloqueo de los ck de tipo re refecnia no se permite cambiar el tipo     */
            document.querySelectorAll('.referencia-referencia-tipo .ck-formulario').forEach(label => {
            label.style.pointerEvents = 'none';
            label.style.opacity = '0.6';
        });
        
        /*carga de los diganosticos de refencia recibidos por constexto*/
        if (typeof diagnosticosReferenciaActuales !== 'undefined' && diagnosticosReferenciaActuales.length > 0  ) {
            diagnosticosReferenciaActuales.forEach(diagnostico => {
                datosRefDiagnostico.push({
                    id: diagnostico.diagnostico__id,
                    idDiagDB: diagnostico.id,
                    diagnostico: concatenarLimpio(diagnostico.diagnostico__cie10__codigo, ' | ', diagnostico.diagnostico__nombre_diagnostico),
                    detalle: diagnostico.detalle,
                    confirmado: diagnostico.confirmada
                });
            });
            refrescarTablaRefDiagnostico();
        }
        

        /*  Respuesta ahora bien en add o en edit */
        selectsRespuesta = inicializarFormRespuesta();

        if (typeof tipo !== 'undefined' && tipo === 0) {
            //para el seguimeito del paciente en la respuesta
            if (seguimiento === 1 ) {
                seguimientoInstitucional.checked = true;
                seguimientoInstitucional.dispatchEvent(new Event('click'));
            } else if (seguimiento === 0) {
                seguimientoPrimerNivel.checked = true;
                seguimientoPrimerNivel.dispatchEvent(new Event('click'));
            } else if (seguimiento === 2) {
                seguimientoReferencia.checked = true;
                seguimientoReferencia.dispatchEvent(new Event('click'));
                selectsRespuesta.respuestaSeguimientoReferenciaEspecialidadSelect.disable();
                selectsRespuesta.respuestaSeguimientoReferenciaDestinoSelect.disable();
                // desactivar los radios 
                const container = document.querySelector('.referencia-respuesta-seguimiento');
                if (container) {
                    container.querySelectorAll('.radio-personalizado').forEach(label => {
                        label.classList.add('bloqueado'); // bloquear solo este grupo
                    });
                }


            }
        }

        inicializarTablaResDiagnostico();
        if (typeof diagnosticosRespuestaActuales !== 'undefined' && diagnosticosRespuestaActuales.length > 0  ) {
            diagnosticosRespuestaActuales.forEach(diagnostico => {
                datosResDiagnostico.push({
                    id: diagnostico.diagnostico__id,
                    idDiagDB: diagnostico.id,
                    diagnostico: concatenarLimpio(diagnostico.diagnostico__cie10__codigo, ' | ', diagnostico.diagnostico__nombre_diagnostico),
                    detalle: diagnostico.detalle,
                });
            });
            refrescarTablaResDiagnostico();
        }
    }


    // Controlar el envío del formulario y evaluar la respuesta
    async function enviarFormularioReferencia() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        const formData = new FormData(formReferencia);

        // --- Validaciones previas ---
        if (!verificarPaciente()) return;
        formData.append("idPaciente", idPaciente.value);

        let valorSeleccionado;
        // Tipo de referencia e institución
        if (Recibida.checked) {
            valorSeleccionado = institucionOrigenSelect.getValue();
            if (!valorSeleccionado || valorSeleccionado.length === 0) {
                toastr.error("Debe indicar la institución de origen.");
                institucionOrigenSelect.focus();
                return;
            }
        } else if (Enviada.checked) {
            valorSeleccionado = institucionDestinoSelect.getValue();
            if (!valorSeleccionado || valorSeleccionado.length === 0) {
                toastr.error("Debe indicar la institución de destino.");
                institucionDestinoSelect.focus();
                return;
            }
            // ademas la data de destnio/*
        } else {
            toastr.error("Recuerda indicar el tipo de referencia.");
            return;
        }

        // Diagnósticos
        if (!Array.isArray(datosRefDiagnostico) || datosRefDiagnostico.length === 0) {
            toastr.error("Debe agregar al menos un diagnóstico antes de continuar.");
            return;
        }

        const diagnosticosEnviados = datosRefDiagnostico.map(est => ({
            id: est.id,
            idDiagDB: est.idDiagDB,
            detalle: est.detalle,
            confirmado: est.confirmado
        }));

        formData.append("diagnostico_json", JSON.stringify(diagnosticosEnviados));

        //no atencion
        if (idMotivoNoAtencion){
            formData.append("MotivoNoAtencion", idMotivoNoAtencion.value ? idMotivoNoAtencion.value : 0 );
        }
        
        // --- Envío ---
        botonGuardar.disabled = true;
        botonGuardar.innerHTML = `<span class="spinner"></span> Guardando...`;

        try {
            const response = await fetch(formReferencia.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken
                },
            });

            const data = await response.json();

            if (!response.ok && response.status === 400) {
                if (data.errors) {
                    Object.entries(data.errors).forEach(([campo, mensaje]) => {
                        toastr.error(concatenarLimpio(mensaje,campo), `Error de digitación`);

                    });
                } else {
                    toastr.error("Ocurrió un error de validación.");
                }
                return;
            }

            if (data.success) {
                toastr.success("Referencia registrada correctamente");
                if (data.redirect_url) {
                        setTimeout(() => {

                            if(modoUso == 1){
                                window.location.href = data.redirect_url;
                            }else {
                                location.reload();
                            }
                            
                        }, 600);
                    }
                return;
            } else {
                toastr.error(data.error || "Algo salió mal.");
                return;
            }

        } catch (error) {
            console.error("Error", error);
            toastr.error("Se presentó un error inesperado al registrar la referencia");
        } finally {
            habilitarBoton();
        }
    }



    async function enviarFormularioRespuesta(form) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        const formData = new FormData(form);

        function verificarIdReferencia(){
            const referenciaId = Number(idReferencia.value)
            if (referenciaId === 0){
                toastr.error("No se encontro la referencia, que deberia ser definida previamente, porfavor reinicie el proceso");
                return false
            }
            return true
        }

        
        function validarTomSelect(tomSelectObj, mensaje) {
            if (!tomSelectObj || !tomSelectObj.getValue()) {
                toastr.error(mensaje);
                return false; 
            }
            return true;
        }

        if (!verificarIdReferencia()) return;
        formData.append("idReferencia", idReferencia.value);

        if (!verificarPaciente()) return;
        formData.append("idPaciente", idPaciente.value);
        formData.append("tipo", tipo ?? 0);

        // Diagnósticos
        if (!Array.isArray(datosResDiagnostico) || datosResDiagnostico.length === 0) {
            toastr.error("Debe agregar al menos un diagnóstico antes de continuar.");
            return;
        }

        const diagnosticosEnviados = datosResDiagnostico.map(est => ({
            id: est.id,
            idDiagDB: est.idDiagDB,
            detalle: est.detalle,
        }));

        formData.append("diagnostico_json", JSON.stringify(diagnosticosEnviados));


        // inicia la diferenciacion en la validacion segun tipo de respuesta
        if (typeof tipo !== 'undefined' && tipo === 0){
            if (
                !validarTomSelect(selectsRespuesta.respuestaAreaCaptaSelect, "Seleccione el área que captó la referencia") ||
                !validarTomSelect(selectsRespuesta.respuestaUnidaClinicaRespondeSelect, "Seleccione la unidad clinica que brindó la respuesta") ||
                !validarTomSelect(selectsRespuesta.respuestaElaboradaPorSelect, "Seleccione el tipo de personal que escribió la respuesta")
            ) {
                return;
            }

            // Validar seguimiento según tipo
            if (seguimientoInstitucional.checked) {
    
                if (!validarTomSelect(selectsRespuesta.respuestaSeguimientoAreaAtencionSelect,
                    "Debe indicar el area de atencion de consulta externa para el seguimiento institucional")) return;
            } else if (seguimientoPrimerNivel.checked) {

                if (!validarTomSelect(selectsRespuesta.respuestaInstitucionDestinoSelect,
                    "Debe indicar la institución destino para el seguimiento en primer nivel")) return;
            } else if (seguimientoReferencia.checked) {

                if (!validarTomSelect(selectsRespuesta.respuestaSeguimientoReferenciaDestinoSelect,
                    "Debe indicar la institución destino para el seguimiento por referencia")) return;
                if (!validarTomSelect(selectsRespuesta.respuestaSeguimientoReferenciaEspecialidadSelect,
                    "Debe indicar la especialidad destino para el seguimiento por referencia")) return;
            } else {
                toastr.error("Debe indicar al menos un tipo de seguimiento");
                return;
            }
        }


        // --- Envío ---
        botonGuardar.disabled = true;
        botonGuardar.innerHTML = `<span class="spinner"></span> Guardando Respues...`;
        
        try{
            const response = await fetch(form.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken
                },
            });

            const data = await response.json();
            if (!response.ok && response.status === 400) {
                if (data.errors) {
                    Object.entries(data.errors).forEach(([campo, mensaje]) => {
                        if (campo !== '__all__') {
                            toastr.error(mensaje, campo);
                        } else {
                            toastr.error(mensaje, 'Error de digitación');
                        }
                    });
                } else {
                    toastr.error("Ocurrió un error de validación.");
                }
                return;
            }

            if (data.success) {
                toastr.success("Respuesta registrada correctamente");
                setTimeout(() => {
                    if (ckNoAtencion){
                        ckNoAtencion.checked = false;
                        idMotivoNoAtencion.value = 0; 
                    }
                    location.reload();
                }, 600);
                return;
            } else {
                toastr.error(data.error || "Algo salió mal.");
                return;
            }


        } catch (error) {
            console.error("Error", error);
            toastr.error("Se presentó un error inesperado al registrar la respuesta");
        } finally {
            habilitarBoton();
        }


    }

//#endregion


});