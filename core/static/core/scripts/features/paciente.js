document.addEventListener('DOMContentLoaded', function() {

    // Configuración de URLs y API
    const API_URLS = {
        municiposXdepto: urls["municipioXdepto"],
        obtenerSectores:urls["sectorAutocomplete"],
        obtenerExpediente: urls["expedienteLibre"],
        obtenerPadre: urls["obtenerPadre"],
        detallesDomicilio: urls["detallesDomicilio"],
        busquedaCenso: urls["busquedaCenso"],
        editarPaciente: urls["editarPaciente"],
        obtenerPacienteCenso: urls["obtenerPacienteCenso"],
        
    };

    // Selectores globales de jQuery para evitar búsquedas repetidas en el DOM
    const $departamento = $("#id_departamento");
    const $municipio = $("#id_municipio");
    const $nombre1 = $("#id_primer_nombre");
    const $sector = $("#id_sector");
    const $nombre2 = $("#id_segundo_nombre");

    const $apellido1 = $("#id_primer_apellido");
    const $apellido2 = $("#id_segundo_apellido");

    const $fechaNac = $("#id_fecha_nacimiento");
    const $edad = $("#edad");
    const $telefono = $("#id_telefono");
    const $observacion = $("#id_observaciones");

    const $sexo = $("#id_sexo");
    const $nacionalidad = $("#id_nacionalidad");
    const $dni = $("#id_dni");
    // obejtos de manejo del expediente 
    const $expedienteNumero = $("#expediente-numero");
    const $estado = $("#id_estado");
    // contenedor detalle de registroa
    const $contenedorRegistro = $(".detallesRegistro");
    // objetos padres
    const $dnimadre = $("#madre_dni");
    const $dnipadre = $("#padre_dni");
    
    // Variables para los campos de la madre
    const $madreId = $("#id_madre");
    const $madreIdDomicilio = $("#id_domicilio_madre");
    const $madreNombre1 = $("#madre_nombre1");
    const $madreNombre2 = $("#madre_nombre2");
    const $madreApellido1 = $("#madre_apellido1");
    const $madreApellido2 = $("#madre_apellido2");

    // Variables para los campos del padre
    const $padreId = $("#id_padre");
    const $padreIdDomicilio = $("#id_domicilio_padre");
    const $padreNombre1 = $("#padre_nombre1");
    const $padreNombre2 = $("#padre_nombre2");
    const $padreApellido1 = $("#padre_apellido1");
    const $padreApellido2 = $("#padre_apellido2");


    // form
    const form = document.getElementById("form-paciente");

    // tipo de paciente
    const $tipo = $("#id_tipo")

    //boton agregar sector 
    const agregarSector = document.getElementById("agregar_ubicacion");
    //defuncion 
    const cadaverBtn = document.getElementById("btn-cadaver");
    const checkDefuncion = document.getElementById('switchDefuncion');

    // agregar atencion
    const agregar_atencionBtn = document.getElementById("frmPaciente-boton-agregar_atencion");

    // Mascaras 


    // Mascara de nombre y apellidos
    Inputmask({ regex: regexNombreApellido }).mask($nombre1);
    Inputmask({ regex: regexNombreApellido }).mask($nombre2);
    Inputmask({ regex: regexNombreApellido }).mask($apellido1);
    Inputmask({ regex: regexNombreApellido }).mask($apellido2);

    // Aplicar Inputmask a los campos del padre
    Inputmask({ regex: regexNombreApellido }).mask($padreNombre1);
    Inputmask({ regex: regexNombreApellido }).mask($padreNombre2);
    Inputmask({ regex: regexNombreApellido }).mask($padreApellido1);
    Inputmask({ regex: regexNombreApellido }).mask($padreApellido2);

    // Aplicar Inputmask a los campos de la madre
    Inputmask({ regex: regexNombreApellido }).mask($madreNombre1);
    Inputmask({ regex: regexNombreApellido }).mask($madreNombre2);
    Inputmask({ regex: regexNombreApellido }).mask($madreApellido1);
    Inputmask({ regex: regexNombreApellido }).mask($madreApellido2);

    //telefono
    Inputmask({
        regex: regexTelefono, 
        placeholder: formatoTelefono, 
    }).mask($telefono);


//#region  TrabajoInicialUbicaciones

    /**
   * Obtiene y actualiza los municipios del control
   * @param {string} idDepto - ID del departamento seleccionado.
   */
    async function TraerMunicipios(idDepto) {
        let idMUniPrimero;
        try {
            const data = await fetchData(API_URLS.municiposXdepto, {
                departamento_id: idDepto,
            });
    
            if (Array.isArray(data) && data.length > 0) {
                $municipio.empty(); // Limpiar las opciones anteriores
                data.forEach((item, index) => {
                    const newOption = new Option(
                        item.nombre_municipio,
                        item.id,
                        index === 0, // Establece el primero como seleccionado
                        index === 0 // Selecciona la primera opción de manera automática
                    );
                    $municipio.append(newOption);
                });
                idMUniPrimero = data[0].id; // Asigna el primer municipio
            } else {
                console.log("Ocurrió un problema al cargar los municipios.");
            }
        } catch (error) {
            console.error("Error al obtener los datos de la ubicación:", error);
        }
    
        return idMUniPrimero;
    }

    /**
      * Evento para cambiar el departamento y cargar municipios correspondientes
      * carga de  el municipio y ubicacion persistentes si error al guardad
      */
    $departamento.change(async function () {
        const departamentoId = $departamento.val();
        if (departamentoId) {
            $municipio.val(null).trigger("change");
            const idMUniPrimero = await TraerMunicipios(departamentoId);
            $municipio.val(idMUniPrimero).trigger("change");
        } else {
            $municipio.empty(); // Limpiar si no hay departamento seleccionado
        }
    });

    /**
     * Maneja el cambio de municipio, limpiando el campo de ubicación.
     */
    $municipio.change(function () {
        $sector.val(null).trigger("change");
    });


    /**
      * Configura el selector "ubicación" con Select2 para buscar ubicaciones por municipio.
      * @requires Select2
      */
    $sector.select2({
    ajax: {
        url: API_URLS.obtenerSectores, // Cambia la URL si es necesario
        dataType: "json",
        delay: 250,
        data: function (params) {
        return {
            municipio_id: $municipio.val(), // ID del departamento
            q: params.term, // La consulta de búsqueda
        };
        },
        processResults: function (data) {
        return {
            results: data.results,
        };
        },
        cache: true,
    },
    minimumInputLength: 2, // Mínimo de caracteres para iniciar la búsqueda
    placeholder: "Buscar ubicacion",
    allowClear: true,
    language: {
        errorLoading: () => "Los resultados no se pueden cargar.",
        inputTooShort: ({ minimum }) => `Ingresa al menos ${minimum} caracteres.`,
        searching: () => "Buscando...",
        noResults: () => "No se encontraron resultados.",
    },
    });

    /**
      * Obtiene y actualiza los datos de municipio y ubicación en el formulario.
      * @param {string} idDepto 
      * @param {string} idMunicipio
      * @param {string} idUbicacion
      */
    async function establecerUbicaciones(idDepto, idMunicipio, idUbicacion, nombreUbicacion) {
        try {
            $departamento.val(idDepto);
            await TraerMunicipios(idDepto);
            $municipio.val(idMunicipio).trigger("change");
            const newOption = new Option(nombreUbicacion, idUbicacion, true, true);
            $sector.append(newOption).trigger("change");
            
        } catch (error) {
            console.error("Error al obtener los datos de la ubicación:", error);
        }
    }


    //#endregion


//#region Traer Datos del Censo

    /**
     * Obtiene y actualiza los datos del paciente en el formulario.
     * @param {string} identidad - Identificador del paciente (DNI) sin guiones.
     */
    async function obtenerDatosPaciente(identidad) 
    {

        try {
            const data = await fetchData(API_URLS.obtenerPacienteCenso, {
            parametro: identidad.replace(/-/g, ""),
            });
            if (data.data.length > 0) {
                const paciente = data.data[0];
                
                await limpiarCamposPaciente();
                await actualizarCamposPaciente(paciente);
                await establecerUbicaciones(
                    paciente.ID_DEPARTAMENTO,
                    paciente.ID_MUNICIPIO,
                    paciente.ID_LUGAR_POBLADO,
                    paciente.NOMBRE_UBICACION
                );
                if (paciente.PACIENTE) {
                    toastr.info(`Identidad ligada a otro paciente: ${paciente.PACIENTE}`);
                }                
            } else {
                if (idTipo != 5){ //  dni no fue encontrado en el censo y el tipo anterior del pacientes es deconocido
                    limpiarCamposPaciente();
                } 
                toastr.info("No se encontraron datos para el paciente.");
            }
        } catch (error) {
            toastr.warning("Error al obtener los datos del paciente:", error);
        }
    }


    /**
      * Actualiza la máscara del campo de identidad según la nacionalidad y el tipo de identificación.
      * Obtiene el formato y máscara de identidad desde el servidor si el tipo es Identificación Nacional ('I'),
      * y aplica un formato genérico para Pasaporte ('P').
      */
    async function actualizarMascara() {
    var nacionalidadId = $nacionalidad.val();
    var tipo = $tipo.val();
    if (tipo == 1 && nacionalidadId == 1 ) {
        try {
        
            Inputmask({
            regex: regexIdentidad, // Expresión regular para validar la entrada
            placeholder: formatoIdentidad, // Formato visual para la entrada
            oncomplete: async function () {
                var identidad = $dni.val();
                if (nacionalidadId == 1) {
                    try {
                        await obtenerDatosPaciente(identidad); // Llama a obtenerDatosPaciente
                    } catch (error) {
                        console.error("Error al obtener datos del paciente:", error);
                    }
                }
            },
            }).mask($dni);
            
        } catch (error) {
            // Manejo de errores en la solicitud
            console.error("Error al obtener formato de identidad:", error);
        }
    } else {
        // Si el tipo es Pasaporte o nacionalidad extrajera
        Inputmask({
            mask: "", // Máscara vacía
            placeholder: "Pasaporte", // Texto de marcador para pasaporte
        }).mask($dni);
        
    }
    }


    /**
      * Llena o limpia los campos del formulario según los datos del paciente.
      * @param {object} paciente - Objeto con datos del paciente; si está vacío, se limpian los campos.
      */
    async function actualizarCamposPaciente(paciente) {
        $nombre1.val(paciente?.NOMBRE1 || "");
        $nombre2.val(paciente?.NOMBRE2 || "");
        $apellido1.val(paciente?.APELLIDO1 || "");
        $apellido2.val(paciente?.APELLIDO2 || "");

        $fechaNac.val(paciente?.FECHA_NACIMIENTO || "");
        $sexo.val(paciente?.SEXO || "");
        $edad.val(paciente.EDAD);
    }


    /**
      * Limpia los campos del formulario relacionados con los datos del paciente.
      */
    async function limpiarCamposPaciente() {
        $nombre1.val(""); // Limpia el campo de nombre
        $nombre1.attr("placeholder", "PRIMER NOMBRE");
        $nombre2.val(""); 
        $nombre2.attr("placeholder", "SEGUNDO NOMBRE");
        $apellido1.val(""); // Limpia el campo de apellido
        $apellido1.attr("placeholder", "PRIMER APELLIDO");
        $apellido2.val(""); // Limpia el campo de apellido
        $apellido2.attr("placeholder", "SEGUNDO APELLIDO");
        $fechaNac.val(""); // Limpia el campo de fecha de nacimiento
        $edad.val(""); //
        $sexo.val("M"); // Limpia el campo de género
        //$telefono.val(""); // no es requerido limpiarlo en ningun caso 
        $observacion.val("");
        $departamento.val(10); // Limpia el campo de departamento y desencadena un cambio
        await TraerMunicipios(10);
        $municipio.val(145);      
        $sector.val(null).trigger("change");   
    }

//#endregion


//#region Trabajo con el expediente

    /**
     * Función que maneja la búsqueda o actualización del expediente
     */
    async function  buscaNumeroExpediente(){

        if (!$expedienteNumero.val()) {
                // buscamos un expediente
            try {
                const response = await fetch(API_URLS.obtenerExpediente);
                if (!response.ok)
                    throw new Error(`Error en la red: ${response.statusText}`);
        
                const data = await response.json();
                if (data && data.expediente_numero) {
                    $expedienteNumero.val(data.expediente_numero);
                } else {
                    console.log("No se encontró expediente");
                }
                } catch (error) {
                console.error("Error al obtener los datos:", error);
                }
        }   
    }


    /*
    manejera el campo expedeinte segun el estado del paciente
    */
    $estado.change( function() {
        const estado = $estado.val();
        if (estado == "I"){
            $expedienteNumero.val("");
        } else if (dicContexto.infoExpediente){
            $expedienteNumero.val(dicContexto.infoExpediente.numero);
        } else 
        {
            buscaNumeroExpediente();
        }

    })

    
//#endregion


//#region Padres
    
    /**
     * Función que se ejecuta cuando el campo de DNI es completado correctamente.
     * Busca la información del padre/madre en la base de datos y llena los campos correspondientes.
     */
    async function handleDniComplete($idFields ,$dniField, $nombre1, $nombre2, $apellido1, $apellido2, $domicilio, placeholder, rol) {
        // Obtener el valor del DNI, eliminando guiones y espacios en blanco
        const identidad = $dniField.val().replace(/-/g, "").trim();
        
        // Validar si el DNI está vacío
        if (!identidad) {
            toastr.warning(`El DNI del ${rol} está vacío.`);
            return;
        }

        try {
            // Determinar el rol (P para padre, M para madre)
            let rolP = rol === "padre" ? "P" : "M";

            // Llamar a la API para obtener los datos de la persona con ese DNI
            const data = await fetchData(API_URLS.obtenerPadre, { dni: identidad, rol: rolP });
            
            // Si no se encuentran datos, mostrar un mensaje y salir
            if (!data || data.error) {
                toastr.info(data?.error || `No se encontraron datos para el ${rol}.`);

                if ((+$tipo.val() === 3 || +$tipo.val() === 4) && rolP === "M") {
                    limpiarNombresPacienteRN_HIJO();
                }
                if (rolP === "P")
                {
                    limpiarPadre($padreId, $dnipadre, $padreNombre1, $padreNombre2, $padreApellido1, $padreApellido2, $padreIdDomicilio);  
                }
                else{
                    limpiarPadre($madreId, $dnimadre, $madreNombre1, $madreNombre2, $madreApellido1, $madreApellido2, $madreIdDomicilio);
                }
                return;
            }


            // Si la API devuelve información válida (ID o DNI encontrado)
            if (data.id || data.dni) {
                // Llenar los campos de nombre y apellido con los datos obtenidos
                $idFields.val(data.id || "");
                $nombre1.val(data.nombre1 || "").attr("placeholder", placeholder);
                $nombre2.val(data.nombre2 || ""); 
                $apellido1.val(data.apellido1 || ""); 
                $apellido2.val(data.apellido2 || "");

                // Obtener el sexo de la persona
                let sexo = data.sexo || ""; 

                // Validar que el sexo coincida con el rol esperado
                if (sexo && ((sexo === "H" && rol !== "padre") || (sexo === "M" && rol !== "madre"))) {
                    toastr.info(`El sexo del ${rol} (${sexo}) no coincide con el rol esperado.`);
                }

                // Si el tipo de registro es RN o hijo, usar la información de la madre
                if (($tipo.val() == 3 || $tipo.val() == 4) && rolP === "M") {  

                    llenar_rn_hijo(
                        data.nombre1 || "",
                        data.nombre2 || "",
                        data.apellido1 || "",
                        data.apellido2 || "",
                        data.domicilio || ""
                    );
                }

                // Si hay domicilio en la data, llenarlo en el campo correspondiente
                if (data.domicilio) {
                    $domicilio.val(data.domicilio);
                }

                // Si la persona tiene hijos registrados, mostrarlos en una alerta modal
                if (data.hijos?.length > 0) {
                    mostrarHijosEnSwal(data);
                }
            } 

        } catch (error) {
            // Capturar errores en la solicitud y mostrarlos
            toastr.info(`Error al obtener los datos ${rol}: ${error.message}`);
        }
        
    }

    /**
     * Función que activa el listener para validar y completar el DNI con Inputmask.
     */
    async function activarListenerPadres($id,$dniField, $nombre1, $nombre2, $apellido1, $apellido2, $domicilio, placeholder, rol) {
        Inputmask({
            regex: regexIdentidad, // Aplicar la máscara con la expresión regular del DNI
            placeholder: formatoIdentidad, // Definir el formato de identidad como marcador de posición
            oncleared: function(){
                limpiarPadre($id, $dniField, $nombre1, $nombre2, $apellido1, $apellido2, $domicilio)

                if (rol === "madre" && [3, 4].includes(parseInt($tipo.val()))) {
                    limpiarNombresPacienteRN_HIJO();
                }
            },
            oncomplete: async function () {
                // Llamar a la función de manejo cuando el usuario complete el DNI
                await handleDniComplete($id, $dniField, $nombre1, $nombre2, $apellido1, $apellido2, $domicilio, placeholder, rol);
            }
        }).mask($dniField);
    }


    function limpiarNombresPacienteRN_HIJO() {
        const valorTipo = parseInt($tipo.val());

        if (isNaN(valorTipo)) {
            return; 
        }

        let prefijo = valorTipo === 3 ? "RN " : valorTipo === 4 ? "HIJO DE " : "";

        $nombre1.val(prefijo);
        $nombre1.attr("placeholder", "PRIMER NOMBRE");

        $nombre2.val("");
        $nombre2.attr("placeholder", "SEGUNDO NOMBRE");

        $apellido1.val("");
        $apellido1.attr("placeholder", "PRIMER APELLIDO");

        $apellido2.val("");
        $apellido2.attr("placeholder", "SEGUNDO APELLIDO");
    }
        


    function mostrarHijosEnSwal(data) {
        let contenidoHTML = '';
    
        if (data.hijos?.length > 0) {
            contenidoHTML += `
                <div style="overflow-x:auto;">
                    <table id="tablaHijos" class="modal-tabla-normal display nowrap" style="width:100%">
                        <thead>
                            <tr>
                                <th>DNI</th>
                                <th>Enlace</th>
                                <th>Nombre</th>
                                <th>Apellido</th>
                                <th>Fecha Nacimiento</th>
                                <th>Tipo de Identificación</th>
                            </tr>
                        </thead>
                        <tbody>`;
            
            data.hijos.forEach(hijo => {

                let nombreSlug = slugify(hijo.nombre + "-" + hijo.apellido);
                let urlEdit = API_URLS.editarPaciente.replace('0',hijo.id).replace('slug',nombreSlug);
                contenidoHTML += `
                    <tr>
                        <td>${hijo.dni || 'N/A'}</td>
                        <td>
                            <button type="button" class="formularioBotones-boton" onclick="window.location.href='${urlEdit}';">
                                <i class="bi bi-pencil"></i>
                            </button>
                        </td>
                        <td>${hijo.nombre}</td>
                        <td>${hijo.apellido}</td>
                        <td>${formatearFechaISO(hijo.fecha_nacimiento)}</td>
                        <td>${hijo.tipo}</td>
                        
                    </tr>`;
            });
    
            contenidoHTML += `
                        </tbody>
                    </table>
                </div>`;
        } else {
            contenidoHTML = `<p class="text-center">No se encontraron hijos</p>`;
        }
    
        Swal.fire({
            title: `Hijos de ${data.nombre1} ${data.apellido1}`,
            html: contenidoHTML,
            confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Cerrar',
            customClass: {
                icon: 'contenedor-modal-icon',
                popup: 'contener-modal-busqueda',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
            },
            didOpen: () => {
                // Esperar a que la tabla esté en el DOM
                setTimeout(() => {
                    $('#tablaHijos').DataTable({
                        responsive: true,
                        autoWidth: false,
                        paging: false, 
                        searching: false,
                        info: false,
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
                    });
                }, 100); // Espera breve para asegurar que se renderice antes de inicializar
            }
        });
    }
    
    // Inicializar funciones // input Mask y escichar el complete mask
    activarListenerPadres($madreId, $dnimadre, $madreNombre1, $madreNombre2, $madreApellido1, $madreApellido2, $madreIdDomicilio, "Nombre completo madre", "madre");

    activarListenerPadres($padreId, $dnipadre, $padreNombre1, $padreNombre2, $padreApellido1, $padreApellido2, $padreIdDomicilio,"Nombre completo padre", "padre");



    function limpiarPadre($id, $dniField, $nombre1, $nombre2, $apellido1, $apellido2, $domicilio) {
        $id.val("");
        //$dniField.val("");
        $domicilio.val("");
        $nombre1.val("").attr("placeholder", "PRIMER NOMBRE");
        $nombre2.val("").attr("placeholder", "SEGUNDO NOMBRE");
        $apellido1.val("").attr("placeholder", "PRIMER APELLIDO");
        $apellido2.val("").attr("placeholder", "SEGUNDO APELLIDO");
    }


    async function llenar_rn_hijo(nombre1, nombre2, apellido1, apellido2, domicilio){
        const tipoId = $tipo.val();
        let prefijo = tipoId == 3 ? "RN " : tipoId == 4 ? "HIJO DE " : "";
        $nombre1.val(prefijo+nombre1);
        $nombre2.val(nombre2 || "");
        $apellido1.val(apellido1 || "");
        $apellido2.val(apellido2 || "");
        try {
            const data = await fetchData(API_URLS.detallesDomicilio,{ id_sector: domicilio })
            if (!data) {
                toastr.info(`No se encontraron datos.`);
                return;
            }
            else
            {   
                establecerUbicaciones(
                    data.id_departamento,
                    data.id_municipio,
                    domicilio,
                    data.nombre_domicilio
                );
            }

        } catch (error) {
            toastr.warning(`No se encontro domicilio: ${error.message}`);
        }
    }

    function apagar_encender_replicaMadre(prefijo="",encender = 0){
        if (encender === 1){
            //activar el listener de campos madre 
            $madreNombre1.blur(function(){
                if ($madreNombre1.val()){
                    $nombre1.val(prefijo + $madreNombre1.val());
                }
            });
    
            $madreNombre2.blur(function() {
                if ($madreNombre2.val()) {
                    $nombre2.val($madreNombre2.val()); 
                }
            });
    
            $madreApellido1.blur(function() {
                if ($madreApellido1.val()) {
                    $apellido1.val($madreApellido1.val()); 
                }
            });
    
            $madreApellido2.blur(function() {
                if ($madreApellido2.val()) {
                    $apellido2.val($madreApellido2.val()); 
                }
            });
    
    
    
        }else {
            $madreNombre1.off('blur');
            $madreNombre2.off('blur');
            $madreApellido1.off('blur');
            $madreApellido2.off('blur');
        }
    }
    
//#endregion


//#region  Paciente Desconocido

// interceptamos el envio del form para llenar los datos de desconocido
form.addEventListener("submit",async function (event) {
    event.preventDefault(); // Siempre evitamos la recarga
    

    if (MD == 2){// solo si esta editando 
        const estado = document.querySelector("#id_estado");
        const estadoVal = estado.value;
        // Accede a dicContexto.infoExpediente y MD como variables globales (ya deben estar definidas)
        if (estadoVal === "I" && dicContexto.infoExpediente) {
            Swal.fire({
                title: '¿Estás seguro?',
                text: `Estás a punto de liberar el número de expediente: ${dicContexto.infoExpediente.numero}`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
                cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
                customClass: {
                    icon: 'contenedor-modal-icon',
                    popup: 'contenedor-modal',
                    title: 'contener-modal-titulo',
                    confirmButton: 'contener-modal-boton-confirmar',
                    cancelButton: 'contener-modal-boton-cancelar',
                },
                didOpen: () => {
                    const actionsContainer = document.querySelector('.swal2-actions');
                    if (actionsContainer) {
                        actionsContainer.classList.add('contener-modal-contenedor-botones-min');
                    }

                    const htmlContainer = document.querySelector('.swal2-html-container');
                    if (htmlContainer) {
                        htmlContainer.classList.add('contener-modal-contenedor-html');
                    }
                }
            }).then(async (result) => {
                if (result.isConfirmed) {
                    await enviarFormulario(); // Reenvía el formulario si el usuario confirma
                }
            });

            return; // Detiene ejecución si se lanzó SweetAlert
        }    
    }
    
    

    
    await enviarFormulario(); 
    
});


async function enviarFormulario() {
    const tipo = document.querySelector("#id_tipo");
    const tipoVal = tipo.value;
    const botonGuardar = document.getElementById("formularioPaciente-botonGuardar");

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

    // Si el tipo es "desconocido" (5)
    if (tipoVal === "5") {
        llenarDesconocido(); // llenar campos por defecto
    }



    const formData = new FormData(form);
    const csrfToken = window.CSRF_TOKEN;

    // verificamos y confirmamos que el paciente aagregar coincide con algun paciente externo
    const dniExterno = $dni.val()
    if (dniExterno) {
    const externo = await buscarPacienteExterno($dni.val());
        if (externo) {

            const titulo = `<i class="bi bi-person-vcard"></i> Paciente Externo Encontrado`;

            const mensaje = `
                El DNI <b>${externo.dni}</b> pertenece a 
                <b>${externo.primer_nombre} ${externo.primer_apellido} ${externo.segundo_apellido}</b>,<br> 
                registrado como <b>paciente externo</b>.<br><br>
                ¿Coincide con los datos que está registrando?
            `;

            const resultadoModal = await confirmarAccion(titulo, mensaje, "SI", "NO");
            if (resultadoModal){
                formData.append("idExterno", externo.id)
            }
        }
    }
    

    // verificamos si existen pacientes con campos similares
    const duplicado = await buscarPacienteSimilar(
        idPaciente,
        formData.get("primer_nombre"), 
        formData.get("primer_apellido") ,
        formData.get("fecha_nacimiento") , 
        formData.get("sexo")
    )

    if (duplicado && Array.isArray(duplicado) && duplicado.length > 0) {
        const confirmo = await mostrarDuplicadosEnSwal(duplicado);
        
        if (!confirmo) { 
            toastr.info("No se guardó el paciente.");
            habilitarBoton();
            return; // NO guarda
        }
    }



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
            if (data.messages) {
                Object.entries(data.messages).forEach(([campo, mensaje]) => {
                    toastr.info(mensaje);
                });
            }

            if (MD == 1){
                if (data.redirect_url) {
                    setTimeout(() => {
                        window.location.href = data.redirect_url;
                    }, 2000);
                    return; // no restauramos el botón porque redirige
                }
            }else{

                habilitarBoton();
            }


        
        } else {
            toastr.error(data.error || "Algo salió mal.");
            habilitarBoton(); // error lógico, restauramos botón
        }

    } catch (error) {
        console.error("Error:", error);
        toastr.error("Hubo un error inesperado al registrar el paciente.");
        habilitarBoton(); // error de red, restauramos botón
    }
}


// Función para llenar los datos de "desconocido"
function llenarDesconocido() {

    if (!$nombre1.val()) {
        $nombre1.val("DESCONOCIDO");
    }

    if (!$apellido1.val()) {
        $apellido1.val("APELLIDO DESCONOCIDO");
    }

    if (!$fechaNac.val()) {
        $fechaNac.val("1900-01-01");
    }

    if (!$sector.val()) {
        const newOption = new Option("DESCONOCIDO", 40342, true, true);
        $sector.append(newOption).trigger("change");
    }
}

//#endregion


//#region  BUsqueda Avanzada
$dni.on("dblclick", () =>{
    const nacionalidad = $nacionalidad.val();
    const tipo = $tipo.val();
    if (tipo == 1 && nacionalidad == 1){//  si es nacionalidad hondureña y si es identidad
        const inputId = $dni.attr("id");
        //busqueda avanzada 
        mostrarBusquedaAvanzada($dni, inputId);
    }
});


$dnimadre.on("dblclick", () =>{
    const inputId = $dnimadre.attr("id");
    mostrarBusquedaAvanzada($dnimadre, inputId);
    
});

$dnipadre.on("dblclick", () =>{

    const inputId = $dnipadre.attr("id");
    mostrarBusquedaAvanzada($dnipadre, inputId);

});


//buscada avanzada de pacientes
function mostrarBusquedaAvanzada(inputField,inputId) {
    Swal.fire({
    title: "Buscar Persona - Censo Electoral 2025",
    html: `
            <div style="overflow-x:auto;">
            <table id="modalTable" class="display" style="width:100%">
                <thead>
                    <tr>
                        <th>Identidad</th>
                        <th>Nombre</th>
                        <th>Apellido</th>
                        <th>Sexo</th>
                        <th>Fecha Nac</th>
                        <th>Domicilio</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
            </div>
        `,
    showCancelButton: true,
    showCloseButton: true,
    confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
    cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
    customClass: {
        popup: 'contener-modal-busqueda',
        title: 'contener-modal-titulo',
        content: 'contener-modal-contenido',
        confirmButton: 'contener-modal-boton-confirmar',
        cancelButton: 'contener-modal-boton-cancelar'
    },
    didOpen: () => {
    //clases perzonalizadas para no afectar la libreria
        const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) {
                actionsContainer.classList.add('contener-modal-contenedor-botones');
            }


    // Inicializar DataTable dentro del modal
        const tableModal = $("#modalTable").DataTable({
            responsive: true,
            processing: true,
            serverSide: true,
            ajax: {
            url: API_URLS.busquedaCenso,
            type: "GET",
            data: function (d) {

                d.search_sexo = $("#column-selector").val();
                d.search_nombre1 = $("#primerNombre").val();
                d.search_nombre2 = $("#segundoNombre").val();
                d.search_apellido1 = $("#primerApellido").val();
                d.search_apellido2 = $("#segundoApellido").val();
            },
            dataSrc: function (json) {
                // Verifica si el servidor envió un mensaje de error en un elento del JSon
                if (json.Myerror) {
                    toastr.warning(json.Myerror, "Aviso");
                    return [];
                }
                return json.data; // Si no hay error, retorna los datos
            },
            },
            dom: '<"DatatablesuperiorModal" <"controlesBusqueda"> >t<"inferior"lip><"clear">',

            columns: [
                { data: "NUMERO_IDENTIDAD", responsivePriority: 1, width: "20px" },
                { 
                    data: null, 
                    responsivePriority: 2,
                    render: function (data) {
                        let primer_nombre = data.PRIMER_NOMBRE || "";
                        let segundo_nombre = data.SEGUNDO_NOMBRE || "";
                        return `${primer_nombre} ${segundo_nombre}`;
                    }
                },
            { 
                data: null, 
                responsivePriority: 2,
                render: function (data) {
                    let primer_apellido = data.PRIMER_APELLIDO || "";
                    let segundo_apellido = data.SEGUNDO_APELLIDO || "";
                    return `${primer_apellido} ${segundo_apellido}`;
                }
            },
            { data: "SEXO", width: "8px" },
            {
                data: "FECHA_NACIMIENTO",
                width: "8px",
                render: function (data) {
                    if (data) {
                    let parts = data.split("/");
                    return `${parts[2]}/${parts[1]}/${parts[0]}`;
                    }
                    return data;
                },
            },
            {
                data: null,
                ordenable: false,
                render: function (data) {
                    let municipio = data.MUNI || "";
                    let departamento = data.DEPTO || "";
                    let ubicacion = data.LUGAR || "";
                    return `${departamento}, ${municipio}, ${ubicacion}`;
                },
            },
            ],
            pageLength: 8,
            lengthChange: false,
            language: {
            lengthMenu: "Mostrar _MENU_ por página",
            zeroRecords: "No se encontraron resultados",
            info: "_START_ a _END_ de _TOTAL_ registros",
            infoEmpty: "0 a 0 de 0 pacientes",
            infoFiltered: "(filtrado de _MAX_)",
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
        });

        // Agregar campos de búsqueda
        $(
            '<input type="text" id="primerNombre" class="formularioCampo-text" placeholder="Primer Nombre">'
        ).appendTo($(".controlesBusqueda"));
        $(
            '<input type="text" id="segundoNombre" class="formularioCampo-text" placeholder="Segundo Nombre">'
        ).appendTo($(".controlesBusqueda"));
        $(
            '<input type="text" id="primerApellido" class="formularioCampo-text" placeholder="Primer Apellido">'
        ).appendTo($(".controlesBusqueda"));
        $(
            '<input type="text" id="segundoApellido" class="formularioCampo-text" placeholder="Segundo Apellido">'
        ).appendTo($(".controlesBusqueda"));
        $(
            '<select id="column-selector" class="formularioCampo-select"><option value="1">Hombre</option><option value="2">Mujer</option></select>'
        ).appendTo($(".controlesBusqueda"));

        // Crear botón de búsqueda
        $(
            '<a id="buscarBtn" class="formularioBotones-boton"><i class="bi bi-search"></i><span>Buscar</span></a>'
        )
            .appendTo($(".controlesBusqueda"))
            .on("click", function () {
            tableModal.ajax.reload(); // Recargar la tabla con los parámetros de búsqueda
            });

        if (inputId == "madre_dni"){
            $("#column-selector").val(2);
            $("#column-selector").on("mousedown", function (e) {
                e.preventDefault();
            });
        } else if (inputId === "padre_dni"){
            $("#column-selector").val(1);
            $("#column-selector").on("mousedown", function (e) {
                e.preventDefault(); 
            });
        } 

        
        // Evento para el doble clic en una fila
        $("#modalTable tbody").on("dblclick", "tr", function () {
            const table = $("#modalTable").DataTable();
            const selectedData = table.row(this).data();
            procesarDatosSeleccionados(inputField,selectedData, inputId);
            Swal.close();
        });

        // Manejo de selección de fila en el DataTable
        $("#modalTable tbody").on("click", "tr", function () {
            const table = $("#modalTable").DataTable();
            $(this).toggleClass("selected");
            table.$("tr.selected").not(this).removeClass("selected");
        });
    },
    }).then((result) => {
    if (result.isConfirmed) {
        const table = $("#modalTable").DataTable();
        const selectedData = table.row(".selected").data(); // Obtén la fila seleccionada
        procesarDatosSeleccionados(inputField,selectedData, inputId);
    }
    });
}

//esta funcion hace una peticion segun los datos sleccionados para padre o para paciente, hace una segunda peticion
function procesarDatosSeleccionados(inputField,selectedData, inputId) {
    if (selectedData && selectedData.NUMERO_IDENTIDAD) {
            const selectedDni = selectedData.NUMERO_IDENTIDAD;
            if (inputId === "id_dni") {
                inputField.val(selectedDni);
                obtenerDatosPaciente(selectedDni);
            } else if (inputId === "madre_dni") {

                $dnimadre.val(selectedDni); 
                handleDniComplete($madreId, $dnimadre, $madreNombre1, $madreNombre2, $madreApellido1, $madreApellido2, $madreIdDomicilio, "Nombre completo madre", "madre");
                
            } else if (inputId === "padre_dni") {
                inputField.val(selectedDni);
                handleDniComplete($padreId, $dnipadre, $padreNombre1, $padreNombre2, $padreApellido1, $padreApellido2, $padreIdDomicilio,"Nombre completo padre", "padre");

            }  
            
    } else {
            toastr.warning("No seleccionaste ninguna fila", "Aviso");
    }
    }

//#endregion



//#region modal agregar Sector

agregarSector.addEventListener("click",() =>{
    const id_departamento = $departamento.val();
    const id_municipio = $municipio.val();
    if(id_departamento && id_municipio){
        AgregarSectorModal(id_municipio);
    }
    else{
        toastr.info(`Porfavor defina un departamento y municipio`);
    }
})

//#endregion



//Inicializacion

    //evitamos el formualrio guarde al precionar enter, peticion de los uusaurios
    form.addEventListener('keydown', function(event) {
        const target = event.target;
        // Bloquear Enter solo si no es textarea
        if (event.key === 'Enter' && target.tagName !== 'TEXTAREA') {
            event.preventDefault();
        }
    });

    // vamos validar en que modo esta el formulario
    if(MD==2){  //Editar 

        var nacionalidadId = $nacionalidad.val();
        var tipo = $tipo.val();

        // mostramos los campos detalle de registro
        if ($contenedorRegistro.hasClass('detallesRegistro__ocultar')) {
            $contenedorRegistro.removeClass('detallesRegistro__ocultar');
        }

        //cargamos expediente
        if (dicContexto.infoExpediente) {  
            $expedienteNumero.val(dicContexto.infoExpediente.numero  ?? "");
        }

        // aplicamos la mascara 
        if (tipo == 1 && nacionalidadId == 1 ){
            actualizarMascara();
        }

        // aplicamos el bloqueo
        manejarCambioTipoDocumento(tipo);
        $edad.val(calcularEdadComoTexto($fechaNac.val()));

        // Ubicacion 
        establecerUbicaciones(
            dicContexto.infoUbicacion.id_departamento,
            dicContexto.infoUbicacion.id_municipio,
            dicContexto.infoUbicacion.id_domicilio,
            dicContexto.infoUbicacion.nombre_domicilio

        );

        // madre
        if (dicContexto.infoMadre){
            $madreId.val(dicContexto.infoMadre.id ?? "");
            $dnimadre.val(dicContexto.infoMadre.dni ?? "");
            $madreNombre1.val(dicContexto.infoMadre.primer_nombre ?? "");
            $madreNombre2.val(dicContexto.infoMadre.segundo_nombre ?? "");
            $madreApellido1.val(dicContexto.infoMadre.primer_apellido ?? "");
            $madreApellido2.val(dicContexto.infoMadre.segundo_apellido ?? "");
        }

        //padre
        if(dicContexto.infoPadre){
            $padreId.val(dicContexto.infoPadre.id ?? "")
            $dnipadre.val(dicContexto.infoPadre.dni ?? "");
            $padreNombre1.val(dicContexto.infoPadre.primer_nombre ?? "");
            $padreNombre2.val(dicContexto.infoPadre.segundo_nombre ?? "");
            $padreApellido1.val(dicContexto.infoPadre.primer_apellido ?? "");
            $padreApellido2.val(dicContexto.infoPadre.segundo_apellido ?? "");
        }

        // modo lectura si aplica 
        if (dicContexto.soloLectura){
            modo_solo_lectura()
        }
        
        //mostramos is es defuncion
        if (dicContexto.defuncion){
            checkDefuncion.checked = dicContexto.defuncion;
            cadaverBtn.style.display = "flex";
        }
        
        //listener de agregar atencion
        agregar_atencionBtn.addEventListener('click', async function(event){
            await mostrarAgregarAtencion();
        });



    }else if(MD==1){
        
        // Llama a actualizarMascara al cargar el formulario para establecer la máscara inicial
        actualizarMascara();
        buscaNumeroExpediente();
        // tipo de identificacion   
        $tipo.val(1).trigger("change");  
        manejarCambioTipoDocumento(1);
    }

    // modo solo lectura 
    function modo_solo_lectura(){
        document.querySelectorAll('input, textarea').forEach(field => {
        field.setAttribute('readonly', 'true');
        });
        // Bloquea selects
        document.querySelectorAll('select').forEach(field => {
        field.setAttribute('disabled', 'true');
        });
        //bloqueamos que no muestre el modal de busqueda, el dni
        $dni.css("pointer-events", "none");
        $dnimadre.css("pointer-events", "none");
        $dnipadre.css("pointer-events", "none");
        // bloqque el boton de expedeitne
        $("#ckExpediente").css("pointer-events", "none");
        
        // el boton de guardadi
        $("#formularioPaciente-botonGuardar").prop('disabled', true);

        $("#agregar_ubicacion").prop('disabled', true);
        //document.getElementById('agregar_ubicacion').enable = false; // deshabilita el boton de agregar ubicacion
        
        // falta bloquear los checks  ck-formulario
        document.querySelectorAll('.ck-formulario').forEach(label => {
            label.style.pointerEvents = 'none';
            label.style.opacity = '0.6';
        });


        toastr.warning("Formulario en modo solo lectura");
    }


    //manejo de tipos de paciente
    $nacionalidad.change(function (){
        actualizarMascara();
    })

    // Cuando la página termine de cargarse, enfocar el campo de 'dni'
    if ($dni) $dni.focus();


    function desbloquear_controles(){
            $nacionalidad.prop("readonly", false).prop("tabIndex", 0);
            $dni.prop("readonly", false).prop("tabIndex", 0);        
            $nombre1.prop("readonly", false).prop("tabIndex", 0);
            $nombre2.prop("readonly", false).prop("tabIndex", 0);
            $apellido1.prop("readonly", false).prop("tabIndex", 0);
            $apellido2.prop("readonly", false).prop("tabIndex", 0);
    }

    function definir_limites_fecha(tipo = "NORMAL") {
        let hoy = new Date().toISOString().split("T")[0];  
        let fechaMin;

        if (tipo === "NORMAL") {
            fechaMin = "1900-01-01";
        } 
        else if (tipo === "RN") {
            let hace45Dias = new Date();
            hace45Dias.setDate(hace45Dias.getDate() - 28);
            fechaMin = hace45Dias.toISOString().split("T")[0];
        } 
        else if (tipo === "HIJO") {
            let hace18Anios = new Date();
            hace18Anios.setFullYear(hace18Anios.getFullYear() - 18); 
            fechaMin = hace18Anios.toISOString().split("T")[0];

            let hoy2 = new Date();
            hoy2.setDate(hoy2.getDate() - 28);
            hoy = hoy2.toISOString().split("T")[0]; 
        }

        // Aplicar los límites de fecha en el input
        $fechaNac.attr("min", fechaMin);
        $fechaNac.attr("max", hoy);

        // Retornar los valores para usarlos en validaciones
        return { fechaMin, fechaMax: hoy };
    }

    //FUNCIONALIDAD SEGUN TIPO PACIENTE A REGISTRAR
    $tipo.change(function () {    
        const tipoId = $tipo.val();
        actualizarMascara();
        $dni.val("");
        if (MD==1 || tipoId == 4 || tipoId == 3){ // si esta agregaddo o si es rn y hijo borra de lo contrario no
            limpiarCamposPaciente();
            }
        manejarCambioTipoDocumento(tipoId);

    });

    function manejarCambioTipoDocumento(tipoId) {
        // Validamos la selección                                                                                                                                                                                                                                                                                                                                                                                                               
        
        $nombre1.attr("required", true);
        $apellido1.attr("required", true);
        $fechaNac.attr("required", true);
        $sector.attr("required", true);

        if (MD==1){
            $("#id_estado_civil").val(2).change() 
            $("#id_ocupacion").val(4).change() 
            }

        if (tipoId != 1) { // Si no es identidad
            Inputmask.remove($dni[0]);
            $dni.removeAttr("required");
        }

        if (tipoId == 1) { // DNI
            //limpiarCamposPaciente();
            $dni.attr("required", true);
            desbloquear_controles();
            apagar_encender_replicaMadre();
            actualizarListenerFecha("NORMAL");
            
        }

        // Pasaporte
        if (tipoId == 2) {
            desbloquear_controles();
            actualizarListenerFecha("NORMAL");
        }

        // Función para desconocidos
        if (tipoId == 5) {
            $dni.val("").trigger("change");
            //limpiarCamposPaciente();
            actualizarMascara();
            desbloquear_controles();
            actualizarListenerFecha("NORMAL");

            $nombre1.removeAttr("required");
            $apellido1.removeAttr("required");
            $fechaNac.removeAttr("required");
            $sector.removeAttr("required");

        }

        // Funcionalidad para recién nacido o hijo de madre desconocida
        if (tipoId == 3 || tipoId == 4) {
            $dni.val("");


            if (MD==1){
                $("#id_estado_civil").val(6).change() // no aplica por defecto
                $("#id_ocupacion").val(6).change() // no aplica por defecto
                }


            // Escribir su prefijo
            
            let prefijo = tipoId == 3 ? "RN " : "HIJO DE ";
            if (MD==1){ // solo si se esta regagbndo
            $nombre1.val(prefijo);
            }

            // Bloquear campos automáticamente
            [$dni, $nombre1, $nombre2, $apellido1, $apellido2].forEach(campo => {
                campo.prop("readonly", true).prop("tabIndex", -1);
            });

            actualizarListenerFecha(tipoId == 3 ? "RN" : "HIJO");

            // Llamar los controles de escucha de la madre
            apagar_encender_replicaMadre(prefijo, 1);

            // mostrar el campo de orden gemelar
            ordenGemelarVisible();
        }else{
            ordenGemelarOculto();
        }

    }

    //funcion que muestra el orden gemelar ademas establece una mascara numerico 
    function ordenGemelarVisible(){
        const grupoOrdenGemelar = document.querySelector("#grupo-orden-gemelar");
        grupoOrdenGemelar.style.display = "flex";

        Inputmask({
            alias: "numeric",
            rightAlign: false,
            allowMinus: false,
            allowDecimal: false,
            min: 0,
            max: 9
        }).mask("#id_orden_gemelar")

    }
    
    function ordenGemelarOculto() {
        const grupoOrdenGemelar = document.querySelector("#grupo-orden-gemelar");
        grupoOrdenGemelar.style.display = "none"; // ← debe ser en minúsculas
        document.querySelector("#id_orden_gemelar").value = ""; // ← mejor usar cadena vacía
    }

    // Función para actualizar el evento change con los nuevos límites
    function actualizarListenerFecha(tipo = "NORMAL") {
        const { fechaMin, fechaMax } = definir_limites_fecha(tipo);

        // Remover el evento anterior si existe
        $fechaNac.off("change");

        // Agregar el nuevo evento con los límites actualizados
        $fechaNac.change(function () {
            const fecha = $fechaNac.val();
            if (!fecha) return;

            const fechaSeleccionada = new Date(fecha);
            const min = new Date(fechaMin);
            const max = new Date(fechaMax);

            const formatoFecha = (fecha) => {
                let dia = fecha.getDate().toString().padStart(2, '0');
                let mes = (fecha.getMonth() + 1).toString().padStart(2, '0'); // Se suma 1 porque los meses van de 0 a 11
                let anio = fecha.getFullYear();
            };

            if (fechaSeleccionada < min || fechaSeleccionada > max) {
                toastr.warning(`La fecha escrita no está dentro del rango permitido: ${formatoFecha(min)} - ${formatoFecha(max)}`);
                return;
            }
            const edadTexto = calcularEdadComoTexto(fecha);
            $edad.val(edadTexto);
        });
    }

    // manejo de las defuncion

    if (MD==2){
        checkDefuncion.addEventListener("click",  async function(e){
            e.preventDefault(); 
            let resultado = await mostrarModalDefuncion();

            if (resultado?.guardo === true) {
                toastr.info(`Defunción procesada correctamente`, "Cambios realizados");
                cadaverBtn.style.display = "flex";
                
                $estado.val("P");
                checkDefuncion.checked = true;
            } else if (resultado?.guardo === false) {
                toastr.alert(`No se procesó correctamente la defunción`, 'No se guardaron cambios');
            }
        });

        if (cadaverBtn){
                cadaverBtn.addEventListener('click', async function(event){
                event.preventDefault();
                
                const paciente = {
                    id: idPaciente,
                    dni: $dni.val(),
                    nombre: concatenarLimpio($nombre1.val(), $nombre2.val(), $apellido1.val(), $apellido2.val())
                };

                let resultado = await entregaEntregaCadaver(paciente)
                if (resultado?.guardo === true) {
                    toastr.info(`Entrega procesada correctamente`, "Cambios realizados")
                    setTimeout(() => {
                        const nuevaVentana = window.open(resultado.pdf_url, "_blank");
                            if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                                toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                            }
                    }, 1000);

                } else if (resultado?.guardo === false) {
                    toastr.alert(`No se procesó correctamente la entrega`, 'No se guardaron cambios');
                }
            });
        }
    }

    async function mostrarModalDefuncion() {
        // Asegurarnos de que los datos estén completos antes de continuar
        if (!idPaciente || !dicContexto.infoExpediente.numero) {
            toastr.error('Los datos del paciente no están completos.', 'Error');
            return;  // No procesamos si los datos son inválidos
        }

        const paciente = {
            id: idPaciente,
            dni: $dni.val(),
            nombre: concatenarLimpio($nombre1.val(), $nombre2.val(), $apellido1.val(), $apellido2.val()),
            numero: dicContexto.infoExpediente.numero
        };
        // Hacemos la llamada al backend
        let resultado = await AgregarDefuncionModal(paciente,dicContexto.soloLectura);
        return resultado
    }

    async function mostrarAgregarAtencion() {
        // Asegurarnos de que los datos estén completos antes de continuar
        if (!idPaciente || !dicContexto.infoExpediente.numero) {
            toastr.error('Los datos del paciente no están completos.', 'Error');
            return;  // No procesamos si los datos son inválidos
        }

        const paciente = {
            id: idPaciente,
            dni: $dni.val(),
            nombre: concatenarLimpio($nombre1.val(), $nombre2.val(), $apellido1.val(), $apellido2.val()),
            numero: dicContexto.infoExpediente.numero
        };

        // Hacemos la llamada al backend
        // trasmnutar zona por setvicio para ficlicita digidtacion
        let servicio = 0;

        if(zona){ // variable globak definida 
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

    async function mostrarDuplicadosEnSwal(duplicados) {
        let contenidoHTML = '';

        if (duplicados.length > 0) {
            contenidoHTML += `
                <div style="overflow-x:auto;">
                    <table id="tablaDuplicados" class="modal-tabla-normal display nowrap" style="width:100%">
                        <thead>
                            <tr>
                                <th>DNI</th>
                                <th>Editar</th>
                                <th>Primer Nombre</th>
                                <th>Segundo Nombre</th>
                                <th>Primer Apellido</th>
                                <th>Segundo Apellido</th>
                                <th>Fecha Nacimiento</th>
                                <th>Sexo</th>
                            </tr>
                        </thead>
                        <tbody>`;
            
            duplicados.forEach(p => {
                const nombreSlug = slugify(`${p.primer_nombre}-${p.primer_apellido}`);
                const urlEdit = API_URLS.editarPaciente.replace('0', p.id).replace('slug', nombreSlug);

                contenidoHTML += `
                    <tr>
                        <td>${p.dni || 'N/A'}</td>
                        <td>
                            <button type="button" class="formularioBotones-boton" onclick="window.location.href='${urlEdit}'">
                                <i class="bi bi-pencil"></i>
                            </button>
                        </td>
                        <td>${p.primer_nombre || ''}</td>
                        <td>${p.segundo_nombre || ''}</td>
                        <td>${p.primer_apellido || ''}</td>
                        <td>${p.segundo_apellido || ''}</td>
                        <td>${formatearFechaYYYYMMDD_a_DDMMYYYY(p.fecha_nacimiento)}</td>
                        <td>${p.sexo}</td>
                    </tr>`;
            });

            contenidoHTML += `
                        </tbody>
                    </table>
                </div>`;
        } else {
            contenidoHTML = `<p class="text-center">No se encontraron duplicados</p>`;
        }

        const resultado = await Swal.fire({
            title: '<i class="bi bi-people-fill"></i> Posibles pacientes duplicados',
            html: contenidoHTML,
            showCancelButton: true,
            confirmButtonText: '<i class="bi bi-check-circle-fill"></i>Continuar',
            cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
            customClass: {
                popup: 'contener-modal-busqueda',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'
            },
            didOpen: () => {
                const actionsContainer = document.querySelector('.swal2-actions');
                if (actionsContainer) {
                    actionsContainer.classList.add('contener-modal-contenedor-botones');
                }

                // Esperar a que la tabla esté en el DOM
                setTimeout(() => {
                    $('#tablaDuplicados').DataTable({
                        responsive: true,
                        serverSide:false,
                        autoWidth: true,
                        paging: false,
                        searching: false,
                        ordering: true,
                        info: false,
                        language: {
                            zeroRecords: "No se encontraron resultados",
                            emptyTable: "No hay datos para mostrar",
                        }
                    });
                }, 120);
            }
        });

        return resultado.isConfirmed;
    }

});




