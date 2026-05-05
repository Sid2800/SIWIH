document.addEventListener('DOMContentLoaded', function () {
    

//#region Dclaraciones de variables y constantes


    const unidadClinica = document.getElementById('id_unidad_clinica');
    let TomUnidadClinica;
    const form = document.getElementById("form-evaluacionrx");

    //Paciente
    const idPaciente = document.querySelector("#id_idPaciente");
    const dniPaciente = document.getElementById("id_dniPaciente");
    const numeroExpediente = document.querySelector("#id_numeroExpediente");
    const nombreCompleto = document.querySelector("#id_nombreCompletoPaciente");
    const fechaNac = document.querySelector("#id_fechaNacimientoPaciente");
    const edad = document.querySelector("#id_edadPaciente");
    const sexo = document.querySelector("#id_sexoPaciente");
    const telefonoPaciente = document.querySelector("#id_telefonoPaciente");
    const direccionPaciente = document.querySelector("#id_direccionPaciente");
     //Paciente Externo
    const evalucionPacienteExternoCheck = document.getElementById('switchPacienteExterno');
    const pacienteInterno = document.getElementById('paciente-interno-fieldset');
    const pacienteExterno = document.getElementById('paciente-externo-fieldset');
    // campos PEXT
    const dniExterno = document.getElementById('paciente_externo_dni');
    const nombre1Externo = document.getElementById('paciente_externo_nombre1');
    const nombre2Externo = document.getElementById('paciente_externo_nombre2');
    const apellido1Externo = document.getElementById('paciente_externo_apellido1');
    const apellido2Externo = document.getElementById('paciente_externo_apellido2');
    const sexoExterno = document.getElementById('paciente_externo_sexo');
    const fechaNacimientoExterno = document.getElementById('paciente_externo_fecha_nacimiento');
    const pacienteExternoIdExterno = document.getElementById('id_paciente_externo')

    // Botones
    const botonGuardar = document.getElementById("formularioEvaluacionRX-botonGuardar");
    const botonInactivar = document.getElementById("formularioEvalucionRx-botonInactivar");
    
    
    // Guardamos el contenido original para restaurarlo luego
    const textoOriginal = botonGuardar.innerHTML;
    
    // estudios
    const grid = document.getElementById("evaluacion-estudios-grid-id");
    const tarjetaAgregarEstudio = document.getElementById("btnAgregarEstudio");



    // Variables de Estado 
    let datosEstudios = []; // Arreglo local que contiene los estudios agregados manualmente
    let timeout;


//#endregion


//#region Funciones Auxiliares
    

    function limpiarGridEstudios() {
        if (!grid) return;
        grid.replaceChildren();
    }

    
    function crearTarjetaEstudio(est) {

        let url = null;

        //  Imagen nueva (blob preview)
        if (est.archivo && est.url_imagen?.startsWith("blob:")) {
            url = est.url_imagen;
        }
        else if (est.url_imagen) {
            url = est.url_imagen;
        }
        else if (est.url_thumb) {
            url = est.url_thumb;
        }

        return `
            <div class="estudio-grid-tarjeta" data-id="${est.frontendId}">
                <button class="estudio-grid-tarjeta-btn-eliminar" type="button">
                    <i class="bi bi-trash"></i>
                </button>
                <div class="estudio-grid-tarjeta-imagen">
                    <img src="${url || window.APP_CONFIG.estudioDefaultImg}" 
                        alt="${est.texto}">
                </div>

                <div class="estudio-grid-tarjeta-info">
                    <div class="estudio-grid-tarjeta-nombre">
                        ${est.texto}
                    </div>

                    <label class="ck-formulario estudio-grid-switch">
                        <input 
                            type="checkbox"
                            class="ck-formulario__checkbox"
                            hidden
                            ${est.impreso ? "checked" : ""}
                        >
                        <div class="ck-formulario__base">
                            <div class="ck-formulario__bolita"></div>
                        </div>
                        <span class="ck-formulario__label">Impreso</span>
                    </label>
                </div>
            </div>
        `;
    }

    function crearTarjetaAgregarEstudio() {
        return `
            <div class="estudio-grid-tarjeta estudio-grid-tarjeta-agregar" id="btnAgregarEstudio" title="Agregar nuevo estudio">
                
                <div class="estudio-grid-tarjeta-contenido-agregar">
                    <i class="bi bi-plus-circle-dotted estudio-grid-agregar-icono"></i>
                    <span>
                    NUEVO ESTUDIO
                    </span>
                </div>
                

            </div>
        `;
    }
    

     // Refresca el contenido del contendor de tarjetas
    
    function refrescarGridEstudios() {
        limpiarGridEstudios();

        const fragment = document.createDocumentFragment();
        
        

        datosEstudios.forEach(est => {
                // No renderizar estudios marcados para eliminar
            if (est.accionEstudio === "DELETE") {
                return;
            }
            const wrapper = document.createElement("div");
            wrapper.innerHTML = crearTarjetaEstudio(est);
            fragment.appendChild(wrapper.firstElementChild);

        }); 

        const wrapperAgregar = document.createElement("div");
        wrapperAgregar.innerHTML = crearTarjetaAgregarEstudio();
        fragment.appendChild(wrapperAgregar.firstElementChild);

        grid.replaceChildren(fragment);

    }


    function agregarEstudio(registro) {

        const estudiosActivos = datosEstudios.filter(
            e => e.accionEstudio !== "DELETE"
        );

        if (estudiosActivos.length >= 10) {
            toastr.warning("No puede agregar más de 10 estudios por evaluación.");
            return;
        }


        const idEntero = parseInt(registro.idEstudio);
        datosEstudios.push({
            frontendId: Date.now() + Math.random(),  // o tu generador
            idDetalle: 0,
            id: idEntero,
            codigo: registro.codigo,
            texto: registro.texto,
            impreso: registro.impreso,
            url_imagen: registro.imagenUrl,
            url_thumb: null,
            archivo: registro.archivo,
            esImagenReal: registro.esImagenReal,
            accionImagen: registro.accionImagen,
            accionEstudio: "KEEP",
        });

        refrescarGridEstudios();
    }

    function actualizarEstudio(registroActualizado){


        const index = datosEstudios.findIndex(
            est => est.frontendId === registroActualizado.frontendId
        );

        if (index === -1) {
            console.warn("Estudio no encontrado para actualizar");
            return;
        }

        datosEstudios[index] = {
            ...datosEstudios[index],  // mantiene todo
            texto: registroActualizado.texto,
            impreso: registroActualizado.impreso,
            codigo: registroActualizado.codigo,
            archivo: registroActualizado.archivo,
            id: registroActualizado.idEstudio,
            url_imagen: registroActualizado.imagenUrl,
            esImagenReal: registroActualizado.esImagenReal,
            accionImagen: registroActualizado.accionImagen
        };
        refrescarGridEstudios();

    }

    function eliminarEstudio(frontendId){

        const index = datosEstudios.findIndex(
            est => est.frontendId === frontendId
        );

        if (index === -1) {
            console.warn("Estudio no encontrado para eliminar");
            return;
        }

        datosEstudios[index] = {
            ...datosEstudios[index],  // mantiene todo
            accionEstudio: "DELETE"
        };
        refrescarGridEstudios();

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

    // Subfunción para restaurar el botón
    function habilitarBoton() {
        botonGuardar.disabled = false;
        botonGuardar.innerHTML = textoOriginal;
    }

    // paciente externo
    function limpiarPacienteExterno() {
            nombre1Externo.value = '';
            nombre2Externo.value = '';
            apellido1Externo.value = '';
            apellido2Externo.value = '';
            fechaNacimientoExterno.value = '';
            sexoExterno.selectedIndex = 0; // Selecciona la primera opción ("Mujer")
            if (modoUso !=2){
                pacienteExternoIdExterno.value = '';
            }
    }

    /**
     * Llena los campos del formulario de paciente externo con los datos recibidos.
     * @param {object} paciente - Objeto con los datos del paciente (de la API).
     */
    function llenarPacienteExterno(paciente,censo=false) {
        // Si no hay datos, no hacemos nada
        if (!paciente) {
            return;
        }

        // ESTANB DECLARADOS AL INICIO
        if (!censo){
            pacienteExternoIdExterno.value = paciente.ID || '';
        }
        dniExterno.value = paciente.DNI || '';
        nombre1Externo.value = paciente.NOMBRE1 || '';
        nombre2Externo.value = paciente.NOMBRE2 || '';
        apellido1Externo.value = paciente.APELLIDO1 || '';
        apellido2Externo.value = paciente.APELLIDO2 || '';

        // La fecha ya viene en formato YYYY-MM-DD, así que se puede asignar directamente
        fechaNacimientoExterno.value = paciente.FECHA_NACIMIENTO || '';
        sexoExterno.value = paciente.SEXO;
    }

    function InicializarPacienteExterno(){
        Inputmask({
            regex: regexIdentidad,
            placeholder: formatoIdentidad,
                oncomplete: async function () {
                    try {
                        // en primer lugar buscamos si es un paciente externo
                        const externo = await buscarPacienteExterno(dniExterno.value);

                        if (externo){
                            //MAPEAMOS CONFORME A LA FUNCION LLENAR PACIENTE EXTERNO
                            const pacienteExterno = {
                                'ID': externo.id,
                                'DNI': externo.dni,
                                'NOMBRE1': externo.primer_nombre,
                                'NOMBRE2': externo.segundo_nombre,
                                'APELLIDO1': externo.primer_apellido,
                                'APELLIDO2': externo.segundo_apellido,
                                'SEXO':externo.sexo,
                                'FECHA_NACIMIENTO': externo.fecha_nacimiento
                            }
                
                            llenarPacienteExterno(pacienteExterno)


                        } else {
                            const resultado = await obtenerDatosPacienteCenso(dniExterno.value);
                            // Aquí puedes agregar la lógica para manejar el 'resultado'

                            if (resultado){
                                llenarPacienteExterno(resultado, true);
                            } else if (resultado === 0){
                                toastr.info("No se encontraron datos para el DNI descrito.");
                                limpiarPacienteExterno();
                            } else {
                                // El error ya está manejado en la función
                                toastr.warning("Error al obtener los datos de la persona.");
                            }
                        }


                        
                    } catch (error) {
                        console.error("Error en la llamada a obtenerDatosPacienteCenso:", error);
                        toastr.warning("Ocurrió un error inesperado al buscar al paciente.");
                    }
                },
                oncleared: function () {
                    limpiarPacienteExterno();
                }
            }).mask(dniExterno);


                //Lisneter que despliega la busqueda 
        dniExterno.addEventListener("dblclick", async function() {
            let data = await mostrasBusquedaPersonaCenso();
            if(data){
                //mpaear
                let fechaOriginal = data.FECHA_NACIMIENTO;  // Ej: "1978/07/19,,"

                fechaOriginal = fechaOriginal.replace(/[^0-9/]/g, ''); 
                let fechaFormateada = fechaOriginal.replace(/\//g, '-');  

                const paciente = {
                    DNI: data.NUMERO_IDENTIDAD,
                    NOMBRE1: data.PRIMER_NOMBRE,
                    NOMBRE2: data.SEGUNDO_NOMBRE,
                    APELLIDO1: data.PRIMER_APELLIDO,
                    APELLIDO2: data.SEGUNDO_APELLIDO,
                    SEXO: data.SEXO === 'HOMBRE' ? 'H' : 'M',
                    FECHA_NACIMIENTO: fechaFormateada
                };

                llenarPacienteExterno(paciente);
            };
        });

    }

    function verificarPacienteExternoLLeno() {
        const dni = dniExterno.value;
        const nombre1 = nombre1Externo.value.trim();
        const nombre2 = nombre2Externo.value.trim();
        const apellido1 = apellido1Externo.value.trim();
        const apellido2 = apellido2Externo.value.trim();
        const fechaNac = fechaNacimientoExterno.value;
        const id = pacienteExternoIdExterno.value;
        const sexo = sexoExterno.value;

        // Validación: nombre1, apellido1 y fechaNac son obligatorios
        if (!nombre1 || !apellido1 || !fechaNac) {
            toastr.warning("Faltan campos obligatorios para el Paciente externo");
            return null;
        }

        return {
            dni: dni || "",
            nombre1: nombre1,
            nombre2: nombre2 || "",
            apellido1: apellido1,
            apellido2: apellido2 || "",
            fechaNacimiento: fechaNac,
            sexo: sexo || "N",
            id: id || 0
        };
    }

    function ocultarPacienteExterno(){
        pacienteInterno.classList.add('evaluacionrxFielsetPacienteInternoExterno_Visible');
        pacienteInterno.classList.remove('evaluacionrxFielsetPacienteInternoExterno_Oculto');
        //-----
        pacienteExterno.classList.add('evaluacionrxFielsetPacienteInternoExterno_Oculto');
        pacienteExterno.classList.remove('evaluacionrxFielsetPacienteInternoExterno_Visible');

    }

    function mostrarPacienteExterno(){
        pacienteInterno.classList.add('evaluacionrxFielsetPacienteInternoExterno_Oculto');
        pacienteInterno.classList.remove('evaluacionrxFielsetPacienteInternoExterno_Visible');
        //-----
        pacienteExterno.classList.add('evaluacionrxFielsetPacienteInternoExterno_Visible');
        pacienteExterno.classList.remove('evaluacionrxFielsetPacienteInternoExterno_Oculto');
    }

    // SE VA SER NECESASIO SE PERMITIRA  MODIFICAR EL PACIENTE EXTERNO EN LA EDUCION DE LA EVALUCION
    function bloquearPacienteExterno(){
        const contenedor = document.getElementById('paciente-externo-fieldset');

        const inputsText = contenedor.querySelectorAll('input[type="text"]');
        const inputsDate = contenedor.querySelectorAll('input[type="date"]');
        const selects = contenedor.querySelectorAll('select');

        [...inputsText, ...inputsDate, ...selects].forEach(element => {
        element.disabled = true;
        });

        document.querySelectorAll('.ck-formulario').forEach(label => {
            label.style.pointerEvents = 'none';
            label.style.opacity = '0.6';
        });
        
    }

//#region 





//#region /*Inicializacion de fromulario*/

    // Evaluar y mostrar si el server media esta onlia
    if (MEDIA_SERVER_OFFLINE) {
        toastr.warning(
            "El sistema de imágenes está temporalmente no disponible."
        );
    }


    new TomSelect(unidadClinica, {
        placeholder: "Unidad Clinica",
    });


    //mostrar el paciente externo validando si viene 
    if (modoUso == 2 && pacienteExternoInfo && Pexterno !== '0'){// modo edicion y hay valor para el paciente externo
            //MAPEAMOS CONFORME A LA FUNCION LLENAR PACIENTE EXTERNO
            const pacienteExterno = {
                'ID': pacienteExternoInfo.id,
                'DNI': pacienteExternoInfo.dni,
                'NOMBRE1': pacienteExternoInfo.primer_nombre,
                'NOMBRE2': pacienteExternoInfo.segundo_nombre,
                'APELLIDO1': pacienteExternoInfo.primer_apellido,
                'APELLIDO2': pacienteExternoInfo.segundo_apellido,
                'SEXO':pacienteExternoInfo.sexo,
                'FECHA_NACIMIENTO': pacienteExternoInfo.fecha_nacimiento
            }
            evalucionPacienteExternoCheck.checked = true;
            //bloquearPacienteExterno()
            InicializarPacienteExterno();
            mostrarPacienteExterno();
            llenarPacienteExterno(pacienteExterno);
    }


    /**
     * Agregamos lo estudios que ya estan ligados a la evaluacion   
     * @param {Array} estudios - Array de objetos con los estudios ligados a la evaluacion
     */
    if (typeof estudiosActuales !== 'undefined' && estudiosActuales.length > 0 && modoUso == 2) {
        estudiosActuales.forEach(estudio => {
            datosEstudios.push({
                frontendId: Date.now() + Math.random(),
                idDetalle: estudio.id,
                id: estudio.estudio__id,
                codigo: estudio.estudio__codigo,
                texto: estudio.estudio__descripcion_estudio,
                impreso: estudio.impreso,
                url_imagen: estudio.url_imagen,
                url_thumb: estudio.url_thumb,
                archivo: null, 
                esImagenReal: !!estudio.url_imagen,
                accionImagen: "STAY",
                accionEstudio: "KEEP",
            });
        });
        refrescarGridEstudios();
    } else
    {
        refrescarGridEstudios();
    }


    //mascara 
    aplicarMascaraIdentidad();

    if (modoUso == 1 && Pexterno !== '0'){ // esta agregando y es permitido un paciente externo
        InicializarPacienteExterno();
        evalucionPacienteExternoCheck.checked = false;
    }

    if( modoUso == 2){
            if (botonInactivar) {
                botonInactivar.addEventListener("click", async function() {
                    if (idEvaluacion) {
                        const titulo = `Desactivar Evaluacion RX`;
                        const mensaje = `¿ Realmente desea desactivar la evalucion imagenologia, es un proceso irreversible ?`;
                        
                        const resultado = await confirmarAccion(titulo, mensaje);
                        
                        if (resultado) {
                            // Desactiva el botón aquí para evitar múltiples clics
                            botonInactivar.disabled = true;

                            try {
                                const inactivacionExitosa = await inactivarEvalucionRX(idEvaluacion);
                                if (inactivacionExitosa) {
                                    setTimeout(() => {
                                        window.location.href = API_URLS.listarEvalucionesrx;
                                    }, 1500);
                                } else {
                                    // Si algo falla, reactiva el botón para que el usuario pueda intentarlo de nuevo
                                    botonInactivar.disabled = false;
                                }
                            } catch (error) {
                                // Si ocurre un error, reactiva el botón
                                console.error("Error al procesar la solicitud:", error);
                                botonInactivar.disabled = false;
                            }
                        }
                    }
                });
            }
    }
    

//#endregion
    
//#region manejo de eventos
    // Controlar el envío del formulario y evaluar la respuesta
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const csrfToken = window.CSRF_TOKEN;

        // Verificación básica de paciente interno
        function verificarPacienteInterno() {
            if (!idPaciente.value) {
                toastr.error("No se ha seleccionado un paciente válido. Por favor, indique un paciente para registrar el ingreso.");
                dniPaciente.select();
                return false;  // false significa no válido
            }
            return true;
        }

        let externo = {};
        const formData = new FormData(form);

        // Verificamos que al menos un estudio haya sido agregado.
        if (!Array.isArray(datosEstudios) || datosEstudios.length === 0) {
            toastr.error("Debe agregar al menos un estudio antes de continuar.");
            return;
        }
        const estudiosEnviados = datosEstudios.map(est => ({
            id: est.id,
            impreso: est.impreso,
            idDetalle: est.idDetalle,
            accionImagen: est.accionImagen,
            accionEstudio: est.accionEstudio,
            frontendId: est.frontendId // se usa para mapear la imagen ya que vaiaja por separado

        }));
        formData.append("estudios_json", JSON.stringify(estudiosEnviados));

        datosEstudios.forEach((est) => {
            
            if (est.archivo instanceof File) {
                formData.append(`archivo__${est.frontendId}`, est.archivo);
            }
        });



        // --- Decidir si el backend permite paciente externo (1 = permitido, 0 = no permitido) ---
        const externoHabilitado = Number(Pexterno) === 1;
        
        // --- 1. Lógica inicial de validación del formulario ---
        if (externoHabilitado) {
            // Solo intentamos leer el checkbox si existe en el DOM
            if (evalucionPacienteExternoCheck?.checked) {
                const datosExterno = verificarPacienteExternoLLeno();
                if (!datosExterno) {
                    return;
                }
                externo = datosExterno;

                const pacienteInternoExistente = await buscarPaciente(externo.dni, "DNI");

                if (pacienteInternoExistente) {
                    const titulo = "Paciente Interno Encontrado";
                    const mensaje = `El DNI ${externo.dni} pertenece a ${pacienteInternoExistente.nombreCompleto}. ¿Desea ligar esta evaluación a su expediente?`;

                    const resultadoModal = await confirmarAccion(titulo, mensaje);

                    if (resultadoModal) {
                        formData.append("paciente_ligado_id", pacienteInternoExistente.id);
                    } else {
                        toastr.info("Proceso cancelado, no se ha realizado ninguna acción.");
                        return;
                    }   
                } else {
                    formData.append("paciente_externo_data", JSON.stringify(externo));
                }
            } else {
                // Paciente externo habilitado pero no marcado -> validar interno
                if (!verificarPacienteInterno()) {
                    return;
                }
            }
        } else {
            // Paciente externo no habilitado -> validar interno
            if (!verificarPacienteInterno()) {
                return;
            }
        }

        
        
        // ---  Envío final del formulario al backend ---
        botonGuardar.disabled = true;
        botonGuardar.innerHTML = `<span class="spinner"></span> Guardando...`;


        try {
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
                        toastr.error(mensaje, `Error de digitación`);
                    });
                } else {
                    toastr.error("Ocurrió un error de validación.");
                }
                return;
            }

            if (data.success) {
                toastr.success("Proceso realizado correctamente");
                setTimeout(() => {
                  window.location.href = data.redirect_url;
                }, 1000);
                return;
            } else {
                toastr.error(data.error || "Algo salió mal.");
                return;
            }

        } catch (error) {
            console.error("Error:", error);
            toastr.error("Se presento un error inesperado al registrar la evaluacion.");
        } finally {
            habilitarBoton();
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


    grid.addEventListener("click", async function (e) {

        if (e.target.closest(".estudio-grid-switch")) {
            return;
        }

        const btnEliminar = e.target.closest(".estudio-grid-tarjeta-btn-eliminar");

        if (btnEliminar) {
            e.stopPropagation();

            const tarjeta = btnEliminar.closest(".estudio-grid-tarjeta");
            const frontendId = Number(tarjeta.dataset.id);
            if (frontendId) {
                eliminarEstudio(frontendId);
            }
            return;
        }


        const btnAgregar = e.target.closest("#btnAgregarEstudio");
        if (btnAgregar) {
            // Llamamos con null para indicar que es nuevo
            let registro = await agregarEditarEstudioDetalle(null, estudios);
            
            if (registro) {
                agregarEstudio(registro);
            }

            return; 
        }

        // 2. tarjeta de ESTUDIO (para editar)?
        const tarjetaEstudio = e.target.closest(".estudio-grid-tarjeta");

        if (tarjetaEstudio) {

            const id = Number(tarjetaEstudio.dataset.id);
            const estudio = datosEstudios.find(est => est.frontendId === id);
            if (estudio) {

                estudio["paciente"]= nombreCompleto.value?.trim() || "";
                let registro = await agregarEditarEstudioDetalle(estudio, estudios);
                console.log(registro);
                if (registro) {
                    actualizarEstudio(registro);
                }
            }
        }
    });

    grid.addEventListener("change", function(e){

        const switchImpreso = e.target.closest(".estudio-grid-switch input");

        if (!switchImpreso) return;

        const tarjeta = switchImpreso.closest(".estudio-grid-tarjeta");
        const frontendId = Number(tarjeta.dataset.id);

        const estudio = datosEstudios.find(est => est.frontendId === frontendId);

        if (estudio) {
            estudio.impreso = switchImpreso.checked;
        }

    });


    // ACCION DE PACIENTE EXTERNO
    if (Pexterno !== '0'){
        evalucionPacienteExternoCheck.addEventListener('change', () =>  {
            if (evalucionPacienteExternoCheck.checked){
                mostrarPacienteExterno()
                limpiarCamposPaciente()
                dniExterno.select()
            } else {
                ocultarPacienteExterno()
                limpiarPacienteExterno()
                dniPaciente.select()
            }

        })
    }

//#endregion


}); 