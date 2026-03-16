document.addEventListener('DOMContentLoaded', function () {
    
    const API_URLS = {
        autocompleteCama: urls["autoCompleteCama"],
        municiposXdepto: urls["municipioXdepto"],
        obtenerSectores: urls["sectorAutocomplete"],
        obtenerPacienteIngresoExpediente: urls["obtenerPacienteIngresoExpediente"],
        obtenerPacienteIngresoDNI: urls["obtenerPacienteIngresoDNI"],
        busquedaAcompaniante: urls["busquedaAcompaniante"],
        reporteHojaHospitalizacion: urls["ReporteHojaHospitalizacion"],
        listarIngresos: urls["listarIngresos"]
    }


    // Selectore globales 
    //paciente
    const idPaciente = document.querySelector("#id_idPaciente");
    const dniPaciente = document.getElementById("id_dniPaciente");
    const numeroExpediente = document.querySelector("#id_numeroExpediente");
    const nombreCompleto = document.querySelector("#id_nombreCompletoPaciente");
    const fechaNac = document.querySelector("#id_fechaNacimientoPaciente");
    const edad = document.querySelector("#id_edadPaciente");
    const sexo = document.querySelector("#id_sexoPaciente");
    const telefonoPaciente = document.querySelector("#id_telefonoPaciente");
    const direccionPaciente = document.querySelector("#id_direccionPaciente");
    
    const idAcompaniante = document.querySelector("#id_acompaniante");
    const telefono = document.querySelector("#telefono");
    const dniAcompaniante = document.querySelector("#acompaniante_dni");
    const acompanianteNombre1 = document.querySelector("#acompaniante_nombre1");
    const acompanianteNombre2 = document.querySelector("#acompaniante_nombre2");
    const acompanianteApellido1 = document.querySelector("#acompaniante_apellido1");
    const acompanianteApellido2 = document.querySelector("#acompaniante_apellido2"); // Corregido
    const municipio = document.querySelector("#id_municipio");
    const departamento = document.querySelector("#id_departamento");

    const agregarSector = document.getElementById("agregar_ubicacion");
    const form = document.getElementById("form-ingreso");


    
    acompanianteNombre1.setAttribute('placeholder', 'Primer nombre');
    Inputmask({
        regex: regexNombreApellido,
    }).mask(acompanianteNombre1);

    // Para el segundo nombre
    acompanianteNombre2.setAttribute('placeholder', 'Segundo nombre');
    Inputmask({
        regex: regexNombreApellido,
    }).mask(acompanianteNombre2);

    // Para el primer apellido
    acompanianteApellido1.setAttribute('placeholder', 'Primer apellido');
    Inputmask({
        regex: regexNombreApellido,
    }).mask(acompanianteApellido1);

    // Para el segundo apellido
    acompanianteApellido2.setAttribute('placeholder', 'Segundo apellido');
    Inputmask({
        regex: regexNombreApellido,
    }).mask(acompanianteApellido2);
 

    //InputMask  controles
    Inputmask({
        regex: regexTelefono, 
        placeholder: formatoTelefono, 
    }).mask(telefono);

    Inputmask({
        regex: regexNumeroExpediente, 
        placeholder: formatoNumeroExpediente,  
    }).mask(numeroExpediente);;



    //#region  Trabajo con ingreso Campos

    /*Autocomplte que  muestra las camas segun criterios de buscada numero sala*/
        const camaSalaMap = {}; // Objeto para almacenar la relación cama → sala
        const camaSelect = new TomSelect("#id_cama", {
            valueField: "id",
            labelField: "text",
            searchField: "text",
            load: function (query, callback) {
                fetch(`${API_URLS.autocompleteCama}?q=${query}`)
                    .then(response => response.json())
                    .then(data => {
                        data.results.forEach(item => {
                            camaSalaMap[item.id] = item.id_sala; 
                        });
            
                        callback(data.results.map(item => ({
                            id: item.id,
                            text: item.text
                        })));
                    })
                    .catch(() => callback([]));
            },
            placeholder: "NUMERO DE CAMA",
        });

        camaSelect.on("change", function (value) {
            const parsedValue = parseInt(value); 
            const salaId = camaSalaMap[parsedValue];
            const salaSelect = document.querySelector("#id_sala").tomselect;
            if (salaId) {
                
                salaSelect.setValue(salaId);
            } else {
                salaSelect.clear(); 
            }
        });
        
        /*Auto complete para elemnto ya cargados en el control   salas*/
        const salaSelect = new TomSelect("#id_sala", {
            valueField: "id",
            labelField: "text",
            searchField: "text",
            placeholder: 'SALA',
        });

        
    //#endregion



    //#region Paciente
    
    /*Listener para la buscad de paciente por el campo expediente */
    let timeout;
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



    /**
     * Obtiene y actualiza los datos del paciente en el formulario.
     * @param {string} identidad - Identificador del paciente (DNI) sin guiones.
     */
    async function obtenerDatosPacienteExpedienteIdentidad(numero, indicador) {
        try {
            let URL = indicador === "DNI" ? API_URLS.obtenerPacienteIngresoDNI : API_URLS.obtenerPacienteIngresoExpediente;
            let parametros = {};

            if (indicador === "DNI") {
                parametros["DNI"] = numero.replace(/-/g, "");
            } else {
                parametros["numero"] = numero;
            }

            const data = await fetchData(URL, parametros);
    
            if (data && "mensaje" in data) { 
                limpiarCamposPaciente();
                toastr.info(data.mensaje, "Información");
            } else if (data) {
                if (data.extrajero){
                    quitarMascaraIdentidad();
                } else {
                    aplicarMascaraIdentidad();
                }
                
                llenarCamposPaciente(data);



            } else {
                limpiarCamposPaciente();
                toastr.info("No se encontraron datos para el paciente.");
            }
        } catch (error) {
            limpiarCamposPaciente();
            toastr.warning("Error al obtener los datos del paciente.");
            console.log(error.toString());
        }
    }
    
    // Máscara con validación y llamada a la función al completar el formato

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


    //Lisneter que despliega la busqueda 
    dniPaciente.addEventListener("dblclick", async function() {
        let data = await mostrasBusquedaPaciente();
        if(data){
            let paciente = mapearDatosPaciente(data);
            if (paciente.extranjero){
                quitarMascaraIdentidad();
            }else{
                aplicarMascaraIdentidad();
            }
            llenarCamposPaciente(paciente);
        };
    });



    numeroExpediente.addEventListener("dblclick", async function(){
        let data = await mostrasBusquedaPaciente();
        if (data.dni){
            obtenerDatosPacienteExpedienteIdentidad(data.dni, "DNI")
        } else if (data.expediente_numero){
            obtenerDatosPacienteExpedienteIdentidad(data.expediente_numero, "EXP")
        }
    })

    // Función para mapear los datos del paciente
    function mapearDatosPaciente(data) {
        return {
            id: data.id,
            numeroExp: data.expediente_numero,
            dni: data.dni,
            nombreCompleto: concatenarLimpio(data.primer_nombre, data.segundo_nombre, data.primer_apellido, data.segundo_apellido),
            fechaNacimiento: formatearFechaSimple(data.fecha_nacimiento),
            edad: calcularEdadComoTexto(data.fecha_nacimiento),
            sexo: data.sexo === "H" ? "HOMBRE" : "MUJER",
            telefono: data.telefono,
            direccion: concatenarLimpio(data.sector__aldea__municipio__departamento__nombre_departamento,data.sector__aldea__municipio__nombre_municipio,data.sector__nombre_sector),
            extranjero: data.es_extranjero_pasaporte ? true : false   
        };
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


    //#endregion






        /**
     * Obtiene y actualiza los municipios del control
     * @param {string} idDepto - ID del departamento seleccionado.
     */
    async function TraerMunicipios(idDepto) {
        let idMunicPrimero = null;
        try {
            const data = await fetchData(API_URLS.municiposXdepto, {
                departamento_id: idDepto,
            });

            if (Array.isArray(data) && data.length > 0) {
                municipio.innerHTML = ""; // Limpiar las opciones anteriores

                data.forEach((item, index) => {
                    const newOption = document.createElement("option");
                    newOption.value = item.id;
                    newOption.textContent = item.nombre_municipio;
                    if (index === 0) {
                        newOption.selected = true; // Seleccionar el primero automáticamente
                        idMunicPrimero = item.id;
                    }
                    municipio.appendChild(newOption);
                });
            } else {
                console.log("Ocurrió un problema al cargar los municipios.");
            }
        } catch (error) {
            console.error("Error al obtener los datos de la ubicación:", error);
        }

        return idMunicPrimero;
    }


    

    //#region Acompañanate

    /**
      * Evento para cambiar el departamento y cargar municipios correspondientes
      * carga de  el municipio y ubicacion persistentes si error al guardad
      */
    departamento.addEventListener("change", async function () {
        const departamentoId = departamento.value;
        if (departamentoId) {
            municipio.value = "";
            const idMunicPrimero = await TraerMunicipios(departamentoId);
            municipio.value = idMunicPrimero;
    
            // Disparar el evento 'change'
            municipio.dispatchEvent(new Event("change", { bubbles: true }));
        } else {
            municipio.value = ""; // Limpiar si no hay departamento seleccionado
        }
    });

    /*Autocomplte que  muestra los sectores segun el minicipio seleccionado*/
    const idSectorSelect = new TomSelect("#id_sector", {
        valueField: "id",
        labelField: "text",
        searchField: "text",
        load: function (query, callback) {
            const municipioId = document.querySelector("#id_municipio").value;
    
            if (!municipioId) {
                callback([]); // No cargar nada si no hay municipio seleccionado
                return;
            }
    
            fetch(`${API_URLS.obtenerSectores}?q=${query}&municipio_id=${municipioId}`)
                .then(response => response.json())
                .then(data => {
                    idSectorSelect.clearOptions(); 
                    callback(data.results);
                })
                .catch(() => callback([]));
        },
        placeholder: "SECTOR",
    });
    
    // Al cambiar de municipio, limpiar opciones y forzar nueva búsqueda
    document.querySelector("#id_municipio").addEventListener("change", function () {
        idSectorSelect.clearOptions();
        idSectorSelect.clear(); 
        idSectorSelect.load(""); 
    });


    /**
     * Obtiene y actualiza los datos del acompañante (busca en 4 lugares) en el formulario.
     * @param {string} numero - Identificador del acompañante (DNI) sin guiones.
     */
    async function obtenerDatosAcompaniante(numero) {
        try {
            let URL = API_URLS.busquedaAcompaniante;  // URL de la API para buscar los datos del acompañante
            let parametros = {};
            parametros["DNI"] = numero.replace(/-/g, "");  // Eliminar los guiones del DNI

            // Llamada a la API para obtener los datos del acompañante
            const data = await fetchData(URL, parametros);

            if (data && "mensaje" in data) {
                limpiarCamposAcompaniante();  // Limpiar campos si hay mensaje de error o vacío
                toastr.info(data.mensaje, "Información");
            } else if (data) {
                llenarCamposAcompaniante(data);  // Si los datos son válidos, llenar los campos
            } else {
                limpiarCamposAcompaniante();  // Limpiar campos si no se encuentran datos
                toastr.info("No se encontraron datos para el acompañante.");
            }
        } catch (error) {
            limpiarCamposAcompaniante();  // Limpiar los campos si ocurre un error
            toastr.warning("Error al obtener los datos del acompañante.");
        }
    }

    /**
     * Llena los campos del formulario con los datos del acompañante obtenidos de la API.
     * @param {Object} acompaniante - Objeto que contiene los datos del acompañante.
     */
    async function llenarCamposAcompaniante(acompaniante) {
        // Asignar valores a los campos del formulario
        idAcompaniante.value = acompaniante.id || "";
        dniAcompaniante.value = acompaniante.dni ? acompaniante.dni.toString() : "";
        telefono.value = acompaniante.telefono || "";
        acompanianteNombre1.value = acompaniante.primer_nombre || "";
        acompanianteNombre2.value = acompaniante.segundo_nombre || "";
        acompanianteApellido1.value = acompaniante.primer_apellido || "";
        acompanianteApellido2.value = acompaniante.segundo_apellido || "";

        // Si existe el departamento_id, obtener los municipios correspondientes
        if (acompaniante.departamento_id) {
            departamento.value = acompaniante.departamento_id;
            await TraerMunicipios(acompaniante.departamento_id);

            // Si existe el municipio_id, asignar valor al campo municipio y disparar evento 'change'
            if (acompaniante.municipio_id) {
                municipio.value = acompaniante.municipio_id;
                municipio.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }

        // Si existe sector_id, agregar la opción al select y seleccionar el valor correspondiente
        if (acompaniante.sector_id) {
            if (idSectorSelect) {
                // Crear la nueva opción para el sector
                const nuevaOpcion = { id: acompaniante.sector_id, text: acompaniante.sector_nombre };
                idSectorSelect.addOption(nuevaOpcion);

                // Seleccionar la opción en el TomSelect
                idSectorSelect.addItem(acompaniante.sector_id);
            } else {
                console.error("Error: idMunicipioSelect no está definido");
            }
        }
    }

    /**
     * Limpia todos los campos del formulario relacionados con el acompañante y restablece valores predeterminados.
     */
    async function limpiarCamposAcompaniante() {
        // Limpiar campos del formulario
        idAcompaniante.value = "";
        telefono.value = "";
        acompanianteNombre1.value = "";
        acompanianteNombre2.value = "";
        acompanianteApellido1.value = "";
        acompanianteApellido2.value = "";
        departamento.value = 10;  // Restablecer departamento a 10 (valor predeterminado)

        // Si existe el select de municipio, limpiar las opciones y la selección
        if (idSectorSelect) {
            idSectorSelect.clearOptions();  // Limpiar opciones
            idSectorSelect.clear();  // Limpiar selección
        }

        // Llamar a la función TraerMunicipios con el valor de departamento 10
        await TraerMunicipios(10);

        // Disparar evento 'change' para el municipio (para actualizar el valor)
        municipio.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Configuración de la máscara de entrada para el campo DNI
    Inputmask({
        regex: regexIdentidad,  // Expresión regular para la validación del formato del DNI
        placeholder: formatoIdentidad,  // Placeholder para el campo DNI

        // Acción cuando se completa el campo DNI (se realiza la búsqueda)
        oncomplete: async function () {
            try {
                await obtenerDatosAcompaniante(this.value);  // Llamar a obtenerDatosAcompaniante
            } catch (error) {
                console.error("Error en la llamada a obtenerDatosPacienteExpedienteIdentidad:", error);
            }
        },

        // Acción cuando el campo DNI es limpiado
        oncleared: function () {
            limpiarCamposAcompaniante();  // Limpiar los campos del formulario
        }
    }).mask(dniAcompaniante);  // Aplicar la máscara al campo de DNI

    
    dniAcompaniante.addEventListener("dblclick", async function(){
        let data = await mostrasBusquedaPersonaAvanzada();
        if(data){
            const acompaniante = mapearAcompaniante(data);
            llenarCamposAcompaniante(acompaniante);
        };
    })

    /**
 * Mapea los datos del backend para que coincidan con los campos usados en la función llenarCamposAcompaniante.
 * @param {Object} data - Objeto recibido del backend.
 * @returns {Object} Objeto mapeado con los nombres de propiedades adecuados.
 */
function mapearAcompaniante(data) {
    return {
        id: data.codigo || "",
        dni: data.dni ? data.dni.toString() : "",
        telefono: data.telefono || "",
        primer_nombre: data.primer_nombre || "",
        segundo_nombre: data.segundo_nombre || "",
        primer_apellido: data.primer_apellido || "",
        segundo_apellido: data.segundo_apellido || "",
        departamento_id: data["sector__aldea__municipio__departamento__id"] || "",
        departamento_nombre: data["sector__aldea__municipio__departamento__nombre_departamento"] || "",
        municipio_id: data["sector__aldea__municipio__id"] || "",
        municipio_nombre: data["sector__aldea__municipio__nombre_municipio"] || "",
        sector_id: data["sector__id"] || "",
        sector_nombre: data["sector__nombre_sector"] || ""
    };
    }



    /* Listener para eagregar una nuebo sector */
    
    agregarSector.addEventListener("click", async function(){
        const departamento_id = departamento.value;
        const id_municipio = municipio.value;

        if (departamento_id && id_municipio){

            const data = await AgregarSectorModal(id_municipio);
            //agregarlo al tomslect
            // Si existe sector_id, agregar la opción al select y seleccionar el valor correspondiente
            if (data.sector_id && data.nombre_sector) {
                if (idSectorSelect) {
                    // Crear la nueva opción para el sector
                    const nuevaOpcion = { id: data.sector_id, text: data.nombre_sector };
                    idSectorSelect.addOption(nuevaOpcion);

                    // Seleccionar la opción en el TomSelect
                    idSectorSelect.addItem(data.sector_id);
                } else {
                    console.error("Error: idMunicipioSelect no está definido");
                }
            }
        }
        else{
            toastr.info(`Porfavor defina un departamento y municipio`);
        }

    })



    //#endregion



    // Controlar el envío del formulario y evaluar la respuesta para abrir el PDF
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const botonGuardar = document.getElementById("formularioIngreso-botonGuardar");
        
        // Verificación básica de paciente seleccionado
        if (!idPaciente.value) {
            toastr.error("No se ha seleccionado un paciente válido. Por favor, indique un paciente para registrar el ingreso.");
            dniPaciente.select();
            return;
        }
    
         // Guardamos el contenido original para restaurarlo luego
        const textoOriginal = botonGuardar.innerHTML;

        // Subfunción para restaurar el botón
        function habilitarBoton() {
            botonGuardar.disabled = false;
            botonGuardar.innerHTML = textoOriginal;
        }

        // Desactivamos el botón y mostramos el spinner
        botonGuardar.disabled = true;
        botonGuardar.innerHTML = `
            <span class="spinner" style="
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid #ccc;
                border-top: 2px solid #333;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
                margin-right: 6px;
                vertical-align: middle;
            "></span> Guardando...
        `;


        const formData = new FormData(form);
        const csrfToken = window.CSRF_TOKEN;
    
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
            // Errores de validación del backend
            if (data.errors) {
                Object.entries(data.errors).forEach(([campo, mensaje]) => {
                    toastr.error(mensaje, `Error de digitación`);
                });
            } else {
                toastr.error("Ocurrió un error de validación.");
            }

            habilitarBoton(); // restauramos botón
            return;
            }

            if (data.success) {

                if (MD != 2){
                    toastr.success("Ingreso registrado correctamente");
                    let nuevaVentana = null
                    nuevaVentana = window.open(data.pdf_url, "_blank");
                    if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                        toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                    } else {
                        setTimeout(() => {
                            window.location.href = data.redirect_url;
                        }, 1000);
                    }
                }else{
                    toastr.success("Ingreso actualizado correctamente");
                    setTimeout(() => {
                        habilitarBoton();    
                    }, 1000);
                }
                return; // no es ncesario habilitar el botoin
            } else {
                // error no relacionado con validación
                toastr.error(data.error || "Algo salió mal.");
                habilitarBoton();
            }   
        } catch (error){
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al registrar el paciente.");
            habilitarBoton(); // error de red, restauramos botón
        }
    });

     //evitamos el formualrio guarde al precionar enter, peticion de los uusaurios
    form.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
        }
    });


    // manjo si es modo edicion
    if (MD === 2) {
        if (dicContexto.acompaniante) {
            llenarCamposAcompaniante(dicContexto.acompaniante);
        }
        
        // Si el formulario ya está finalizado, desactiva todo
        if (lectura) {
            document.querySelectorAll('input, textarea, select').forEach(field => {
                field.setAttribute('disabled', 'true');
            });
        
            camaSelect.disable();
            idSectorSelect.disable();
            salaSelect.disable();
            agregarSector.disabled = true;

            document.querySelector("#formularioIngreso-botonGuardar").disabled = true;
            document.querySelector("#formularioIngreso-botonInactivar").disabled = true;
        
            toastr.info("Formulario en modo solo lectura");
        } else {
            // Solo agrega el listener si el formulario NO está finalizado
            const botonInactivar = document.getElementById("formularioIngreso-botonInactivar");
            if (botonInactivar) {
                botonInactivar.addEventListener("click", async function() {
                    if (idIngreso) {
                        const titulo = `Desactivar ingreso`;
                        const mensaje = `¿ Realmente desea desactivar el ingreso, es un proceso irreversible ?`;
                        
                        const resultado = await confirmarAccion(titulo, mensaje);
                        
                        if (resultado) {
                            // Desactiva el botón aquí para evitar múltiples clics
                            botonInactivar.disabled = true;

                            try {
                                const inactivacionExitosa = await inactivarIngreso(idIngreso);

                                if (inactivacionExitosa) {
                                    setTimeout(() => {
                                        if (window.history.length > 1) {
                                            history.back();
                                        } else {
                                            window.location.href = API_URLS.listarIngresos;
                                        }
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
        
        // El resto del código que no depende de `finalizado`
        const botonImprimir = document.getElementById("formularioIngreso-botonImprimir");
        
        if (extranjero){
            quitarMascaraIdentidad();
        } else {
            aplicarMascaraIdentidad();
        }

        if (botonImprimir) {
            botonImprimir.addEventListener("click", function () {
                if (idIngreso) {
                    imprimirHojaHospitalizacion(idIngreso);
                }
            });
        }

    } else {
        aplicarMascaraIdentidad();
    }


});