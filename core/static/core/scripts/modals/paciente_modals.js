const ModalPacienteProcesos = (function () {
    
    let PROCESOS_UI = [];
    let idPaciente = 0
    let datos = {}

    async function open(config = {}) {
        return await Swal.fire({
            title: `<i class="bi bi-gear"></i>OTROS PROCESOS`,
            html: `
                <div class="tituloFormulario-subrallado"></div>
                <div class="modal-contendor-data">
                    <div class="modal-contendor-data-encabezado" id="modalOtrosProcesosHeader"></div>
                    <div class="modal-procesos-contendor">
                        <table class="modal-procesos-tabla">
                            <thead>
                                <tr>
                                    <th>PROCESO</th>
                                    <th>ESTADO</th>
                                    <th>ACCION</th>
                                </tr>
                            </thead>
                            <tbody id="procesosBody"></tbody>
                        </table>
                    </div>
                </div>
                
            `,
            showCloseButton: true,
            showConfirmButton: false,
            showCancelButton: true,
            cancelButtonText: '<i class="bi bi-arrow-left-circle"></i> Volver',


            customClass: {
                popup: "contenedor-modal-procesos",
                title: 'contener-modal-titulo',
                htmlContainer: 'html-modal-galeria',
                actions: 'contener-modal-contenedor-botones',
                cancelButton: 'contener-modal-boton-cancelar'
            },
            didOpen: () => inicializar(config)
        });
    }

    async function inicializar(config){
        //renderProcesos(config.procesos);
        

        PROCESOS_ESTADO = {
            cadaver: null,
            entrega: null,
            traslado: null
        }
        datos = {}
        idPaciente = 0
        
        idPaciente = config.idPaciente;
        datos = config.datos


        await obtenerInfo(config.procesos);
        renderDatos();
        renderProcesos(config.procesos);

    }

    async function obtenerInfo(procesos = []) {

        PROCESOS_UI = [];
        for (const p of procesos) {

            // CADAVER
            if (p.identificador === 'cadaver') {

                const data = await fetchData(API_URLS.obtenerDefuncion, {
                    id: idPaciente
                });

                if (data && !data.mensaje && data.fecha_entrega) {

                    PROCESOS_UI.push({
                        tipo: 'cadaver',
                        titulo: 'Entrega de cadáver',
                        data: data
                    });

                } else {
                    PROCESOS_UI.push({
                        tipo: 'cadaver',
                        titulo: 'Entrega de cadáver',
                        data: null
                    });
                }
            }

            //OBITOS
            if (p.identificador === 'obito') {

                const lista = await fetchData(API_URLS.listarObitosPaciente, {
                    id: idPaciente
                });

                const obitos = Array.isArray(lista) ? lista : (lista ? [lista] : []);

                if (obitos.length > 0) {

                    obitos.forEach((o, index) => {
                        PROCESOS_UI.push({
                            tipo: 'obito',
                            titulo: `Obito ${index + 1}`,
                            data: o
                        });
                    });

                } 
                    // SIEMPRE mostrar opción registrar
                if (obitos.length < 4) {
                    PROCESOS_UI.push({
                        tipo: 'obito',
                        titulo: `Obito ${obitos.length + 1}`,
                        data: null
                    });
                }               
                
            }
        }
    }




    function renderDatos() {
        renderDatosPaciente("modalOtrosProcesosHeader",datos);
    }

    function renderProcesos(){
        const body = document.getElementById("procesosBody");
        if (!body) return;

        body.innerHTML = "";

        PROCESOS_UI.forEach(p => {

            estadoTexto = `
                <span class="mp-estado is-error">
                    <i class="bi bi-exclamation-circle-fill"></i> Sin registro
                </span>
            `;

            let accionTexto = `
                <i class="bi bi-plus-circle-fill"></i> Registrar
            `;

            if (p.data) {
                const fecha = p.data.fecha_entrega || p.data.fecha || "";

                estadoTexto = `
                    <span class="mp-estado is-ok">
                        <i class="bi bi-check-circle-fill registrado"></i> ${fecha}
                    </span>
                `;

                accionTexto = `
                    <i class="bi bi-eye-fill"></i> Ver
                `;
            }

            const fila = document.createElement("tr");

            fila.innerHTML = `
                <td class="modal-procesos-nombre">${p.titulo}</td>
                <td class="modal-procesos-estado">${estadoTexto}</td>
                <td class="modal-procesos-accion">
                    <button class="modal-procesos-btn"
                            data-tipo="${p.tipo}"
                            data-id="${p.data ? p.data.id : ''}">
                        ${accionTexto}
                    </button>
                </td>
            `;

            body.appendChild(fila);
        });

        bindEventos();
    }
    

    function bindEventos(){

        const body = document.getElementById("procesosBody");
        if (!body) return;

        body.addEventListener("click",async function(e){

            const btn = e.target.closest(".modal-procesos-btn");

            if (!btn) return;

            const tipo = btn.dataset.tipo;
            const id = btn.dataset.id;

            if (tipo === "obito"){
                //ModalObito.open({ id });
                if (idPaciente && datos){
                    resultado = await registrarObito(id,idPaciente, datos);
                }

                if (resultado === null) {
                    return;
                }

                if (resultado?.guardo === true) {
                    toastr.info(`Obito procesado correctamente`, "Cambios realizados")
                    setTimeout(() => {
                            const nuevaVentana = window.open(resultado.pdf_url, "_blank");
                            if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                                toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                            }
                    }, 500);

                } else{
                    toastr.alert(`No se procesó correctamente la entrega`, 'No se guardaron cambios');
                }

                if (resultado === null) {
                    return;
                }

            } 
            else if (tipo === "cadaver"){
                //ModalEntrega.open({ id });
                resultado=false;
                if (idPaciente && datos){
                    resultado = await entregaEntregaCadaver(idPaciente, datos);
                }

                if (resultado === null) {
                    return;
                }


                if (resultado?.guardo === true) {
                    toastr.info(`Entrega procesada correctamente`, "Cambios realizados")
                    setTimeout(() => {
                        const nuevaVentana = window.open(resultado.pdf_url, "_blank");
                            if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                                toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                            }
                    }, 500);

                } else{
                    toastr.alert(`No se procesó correctamente la entrega`, 'No se guardaron cambios');
                }
            }

        });

    }

    return { open };

})();


/*Agrega una defunción y marca el paciente como difunto*/
async function entregaEntregaCadaver(idPaciente, datosPaciente) {
    let resultado = null;
    const modal = await Swal.fire({
        title: `<i class="bi bi-file-earmark-medical"></i> Entrega de Cadáver`,
        html: `
            <form method="post" class="formulario" id="formulario-modal-cadaver">
                <fieldset class="modalCadaverCampos">

                <fieldset class="modalCadaverDefuncionPacienteCampos">
                    <legend>Defuncion / Paciente:</b></legend>
                    <div class="formularioCampoModal">
                        <label>Paciente</label>
                        <input type="text" value="${datosPaciente.Paciente || ''}" disabled class="formularioCampo-text">
                    </div>

                    <div class="formularioCampoModal">
                        <label>DNI</label>
                        <input type="text" value="${datosPaciente.DNI || ''}" disabled class="formularioCampo-text">
                    </div>

                    <div id="contenedor-info-defuncion"></div>
                    <input type="hidden" id="modal-defuncion-id">
                </fieldset>

                
                <fieldset class="modalDefuncionResponsableCampos">
                <legend>Datos responsable</legend>

                    <div class="formularioCampoModal">
                        <label for="modal-cadaver-dni-responsable">Identidad</label>
                        <input type="text" id="modal-cadaver-dni-responsable" name="dni_responsable" class="formularioCampo-text" required>
                    </div>
                    
                    <div class="formularioCampoModal">
                        <label for="nombre_responsable">Nombre</label>
                        <input type="text" id="modal-cadaver-nombre-responsable" name="nombre_responsable" class="formularioCampo-text" placeholder="NOMBRE COMPLETO" required>
                    </div>

                    <div class="formularioCampoModal">
                        <label for="modal-cadaver-fecha-entrega">Fecha de entrega</label>
                        <input type="date" id="modal-cadaver-fecha-entrega" name="fecha_entrega" class="formularioCampo-text" required>
                    </div>

                </fieldset>
                </fieldset>
            </form>
        `,
        showCancelButton: true,
        showCloseButton: true,
        confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contener-modal-defuncion',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar'
        },
        preConfirm: () => {
            
            const dni = document.getElementById("modal-cadaver-dni-responsable").value;
            const nombre = document.getElementById("modal-cadaver-nombre-responsable").value;
            const fechaEntregaInput = document.getElementById("modal-cadaver-fecha-entrega");
            const idDefuncion = document.getElementById("modal-defuncion-id");


            if (!dni) {
                Swal.showValidationMessage('Debe indicar un DNI valido');
                return false;
            }

            if (!nombre) {
                Swal.showValidationMessage('Debe indicar el nombre del responsable ');
                return false;
            }

            if (!fechaEntregaInput.value) {
                Swal.showValidationMessage('Debe indicar la fecha de entrega');
                return false;
            }
        
            return {
                dni,
                nombre: nombre.toUpperCase(),
                fechaEntrega:fechaEntregaInput.value,
                idDefuncion: idDefuncion.value
                };
        },
        didOpen: async function () {
            const dni = document.getElementById("modal-cadaver-dni-responsable");
            const nombre = document.getElementById("modal-cadaver-nombre-responsable");
            const idDefuncion = document.getElementById("modal-defuncion-id");
            const fechaEntregaInput = document.getElementById("modal-cadaver-fecha-entrega");
            const titleElement = Swal.getTitle(); 

            Inputmask({
                regex: regexIdentidad,
                placeholder: formatoIdentidad,
                oncomplete: async function () {
                const resultado = await obtenerDatosPacienteCenso(dni.value);
                if (resultado){
                    nombre.value= concatenarLimpio(resultado.NOMBRE1,resultado.NOMBRE2,resultado.APELLIDO1,resultado.APELLIDO2);

                } else if (resultado === 0){
                    toastr.info("No se encontraron datos para el dni descrito.");
                } else {
                    toastr.warning("Error al obtener los datos de la persona");
                }
                }
            }).mask(dni);

            Inputmask({
                regex: regexNombreApellido,
                placeholder: 'NOMBRE COMPLETO'
            }).mask(nombre);


            // Verificar si el paciente ya tiene defunción
            
            try {
                let data = null;
                if (idPaciente){
                data = await fetchData(API_URLS.obtenerDefuncion, { id: idPaciente });
                }

                if (data && "mensaje" in data) {
                // NADA SIN DEFU NCION NO HAY ENTREGA 
                    toastr.warning("No se encontraron datos de la defuncion");
                    Swal.close();
                } else if (data) {
                llenar(data);
                }
            } catch (error) {
                console.error(error);
            }


            function renderDefuncionInfo(defuncion) {
                const contenedor = document.getElementById("contenedor-info-defuncion");
                if (fechaEntregaInput){
                fechaEntregaInput.min = defuncion.fecha_defuncion;
                }
                
                contenedor.innerHTML = `
                    <div class="formularioCampoModal">
                        <label>Fecha defunción</label>
                        <input type="date" value="${defuncion.fecha_defuncion || ''}" disabled class="formularioCampo-text">
                    </div>

                    <div class="formularioCampoModal">
                        <label>Tipo</label>
                        <input type="text" value="${defuncion.tipo_defuncion_display || ''}" disabled class="formularioCampo-text">
                    </div>
                `;
            }

            function llenar(defuncion) {
                idDefuncion.value = defuncion.id || "";
                // Mostrar info de defunción
                renderDefuncionInfo(defuncion);

                let fecha = defuncion.fecha_entrega 
                    ? defuncion.fecha_entrega.split("T")[0]
                    : fechaActualParaInput(false);

                fechaEntregaInput.value = fecha;
                if (defuncion.reponsable_nombre && defuncion.reponsable_dni) {
                titleElement.textContent = "Actualizar Entrega de Cadáver";
                dni.value = defuncion.reponsable_dni;
                nombre.value = defuncion.reponsable_nombre;
                }
            }
                    
            dni.select();
        }
    });

    if (modal.isConfirmed) {
        const formData = modal.value;

        try {
            const csrfToken = window.CSRF_TOKEN;
            Swal.showLoading();
            const response = await fetch(urls["procesarCadaver"], {
                method: "POST",
                headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                dniR: formData.dni,
                nombreR: formData.nombre,
                idPaciente: idPaciente,
                idDefuncion: formData.idDefuncion,
                fechaEntrega: formData.fechaEntrega
                })
            });

            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.error || `Error HTTP: ${response.status}`);
            }
            
            if (responseData.guardo) {
                resultado = responseData;
                Swal.close();
            } else {
                toastr.warning("No se guardaron cambios");
            }

        } catch (error) {
            toastr.error("Error al guardar la defunción: " + error.message);
        }
    }


    return resultado;
}


/*Agrega una defunción y marca el paciente como difunto*/
async function AgregarDefuncionModal(paciente, lectura) {
    let resultado = null;

    const modal = await Swal.fire({
        title: `<i class="bi bi-gear"></i>DEFINIR DEFUNCION`,
        html: `
            <div class="tituloFormulario-subrallado"></div>
            <div class="modal-contendor-data-encabezado" id="modalDefuncionHeader" style="margin-botom:10px"></div>

            <form method="post" class="formulario" id="formulario-model-defuncion">
                <fieldset class="modalDefuncionCampos">
                <legend>Defuncion</legend>

                <div class="formularioCampoModal">
                    <label for="modal-defuncion-fecha">Fecha</label>
                    <input type="date" id="modal-defuncion-fecha" name="fecha_defuncion" class="formularioCampo-date" required
                    )}>
                </div>

                <div class="formularioCampoModal">
                    <label for="modal-defuncion-tipo">Tipo</label>
                    <select id="modal-defuncion-tipo" class="formularioCampo-select" name="tipo">
                        <option value="1" selected>Intrahospitalaria</option>
                        <option value="2">Extrahospitalaria</option>
                    </select>
                </div>
                
                <div class="formularioCampoModal">
                    <label for="modal-defuncion-unidad-clinica">Unidad clinica</label>
                    <select id="modal-defuncion-unidad-clinica" class="formularioCampo-select" name="unidad-clinica">
                        <option value="" disabled selected>Seleccione una unidad clinica</option>
                    </select>
                </div>

                <div class="formularioCampoModal" id="modal-defuncion-motivo-campo">
                    <label for="motivo">Motivo</label>
                    <textarea id="modal-defuncion-motivo" class="formularioCampo-select" name="motivo" rows=2></textarea>
                </div>

                <input type="hidden" id="modal-defuncion-id" name="idDefuncion">
                </fieldset>

                <fieldset class="modalDefuncionCampos" id="modal-campos-defuncion-registros" style="display: none;">
                <legend>Detalles del registro</legend>
                <div class="formularioCampoModal">
                    <label for="Fregistro">Registrado</label>
                    <input type="text" id="modal-defuncion-detalles-registro" class="formularioCampo-text" disabled>
                </div>
                </fieldset>
            </form>
        `,
        showCancelButton: true,
        showCloseButton: true,
        confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
            popup: 'contener-modal-defuncion',
            title: 'contener-modal-titulo',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar'
        },
        preConfirm: () => {
            
            const unidad_clinica = document.getElementById("modal-defuncion-unidad-clinica").value;
            const fecha = document.getElementById("modal-defuncion-fecha").value;
            const tipo = document.getElementById("modal-defuncion-tipo").value
            const motivo = document.getElementById("modal-defuncion-motivo").value;
            const hoy = fechaActualParaInput(false);
            const idDefuncion = document.getElementById("modal-defuncion-id").value;

            if (!unidad_clinica && tipo!=="2") {
                Swal.showValidationMessage('Debe seleccionar una sala');
                return false;
            }

            if (!fecha) {
                Swal.showValidationMessage('Debe seleccionar una fecha');
                return false;
            }

            if (fecha > hoy) {
                Swal.showValidationMessage('La fecha no puede ser mayor que la fecha actual');
                return false;
            }

            return {
                tipo,
                fecha,
                unidad_clinica: unidad_clinica,
                tipo,
                motivo,
                idDefuncion
                };
        },
        didOpen: async function () {
            const confirmBtn = Swal.getConfirmButton();
            const titleElement = Swal.getTitle(); 
            const unidad_clinica = document.getElementById("modal-defuncion-unidad-clinica");
            const fecha = document.getElementById("modal-defuncion-fecha");
            const motivo = document.getElementById("modal-defuncion-motivo");
            const tipo = document.getElementById("modal-defuncion-tipo");
            const idDefuncion = document.getElementById("modal-defuncion-id");
            const detallesRegistro = document.getElementById("modal-defuncion-detalles-registro");
            const fieldsetRegistro = document.getElementById("modal-campos-defuncion-registros");

            //header paciente
            renderDatosPaciente("modalDefuncionHeader",{
                "Paciente": paciente.nombre,
                "DNI": paciente.dni,
                "Expediente": paciente.numero
            });

            // Cargar salas, area_atencion,  desde el backend
            await UnidadClinicaLoader.cargar(unidad_clinica,'defuncion');
            


            // Inicializar TomSelect
            const unidadSelect = new TomSelect("#modal-defuncion-unidad-clinica", {
                placeholder: 'Seleccione una unidad clinica',
                allowEmptyOption: true
            });

            // Verificar si el paciente ya tiene defunción
            
            try {
                let data = null;
                if (paciente){
                data = await fetchData(API_URLS.obtenerDefuncion, { id: paciente.id });
                }

                if (data && "mensaje" in data) {
                // No tiene defunción, establecer valores por defecto
                fecha.value = fechaActualParaInput(false);
                unidadSelect.clear(true);
                } else if (data) {
                llenarDefuncion(data);
                }
            } catch (error) {
                console.error(error);
            }

            function llenarDefuncion(defuncion) {
                titleElement.innerHTML = `<i class="bi bi-gear"></i> Actualizar defuncion`;
                motivo.value = defuncion.motivo || "";
                fecha.value = defuncion.fecha_defuncion || "";
                idDefuncion.value = defuncion.id || "";
                detallesRegistro.value = concatenarLimpio(defuncion.registrado, formatFecha(defuncion.fechaAdicion)) || "";
                fieldsetRegistro.style.display = 'block';
                tipo.value=defuncion.tipo_defuncion;
                if (String(defuncion.tipo_defuncion) === "2") {
                unidadSelect.disable();
                unidadSelect.clear();
                } else{
                if (unidadSelect){
                    unidadSelect.enable();
                    unidadSelect.clear(); // solo limpia

                    if (defuncion.unidad_codigo) {  
                        if (!unidadSelect.options[defuncion.unidad_codigo]) {
                            unidadSelect.addOption({
                            value: defuncion.unidad_codigo,  
                            text: defuncion.unidad_codigo
                            });
                        }

                        unidadSelect.addItem(defuncion.unidad_codigo, true);
                    }
                }
                }

            }

            // comporobar el modo de uso ose solo lectura
            if(lectura == true)
            {
                motivo.disabled = true;
                fecha.disabled = true;
                confirmBtn.style.pointerEvents = "none";
                unidadSelect.disable();
            }

            tipo.addEventListener("change", function() {
                if (this.value === "2") { // extrahospitalaria
                unidadSelect.disable();
                unidadSelect.clear();
                } else {
                unidadSelect.enable();
                }
            });



        }
    });

    if (modal.isConfirmed) {
            // Guardamos las referencias a los elementos
            const formData = modal.value;
    
            try {
                const csrfToken = window.CSRF_TOKEN;
                const response = await fetch(API_URLS.guardarDefuncion, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    unidad_clinica: formData.unidad_clinica, 
                    fecha: formData.fecha,
                    motivo: formData.motivo,
                    tipo: formData.tipo,
                    idDefuncion: formData.idDefuncion,
                    idPaciente: paciente.id
                })
                });
                
                const data = await response.json();
                if (!response.ok) throw new Error(`${data.error}`);
                
                if (data.guardo) {
                resultado = data;
                Swal.close();
                } 

            } catch (error) {
                toastr.error("Error al guardar la defuncion " + error.message);
            }
            
        
    }
    return resultado;
}


async function registrarObito(IdObito,idPaciente, datosMadre) {
    let resultado = null;
    const modal = await Swal.fire({

        title: `<i class="bi bi-gear"></i>AGREGAR OBITO`,
        html: `
            <div class="tituloFormulario-subrallado"></div>
            <div class="modal-contendor-data-encabezado" id="modalObitoHeader" style="margin-botom:10px"></div>

            <form method="post" class="formulario" id="formulario-model-obito">
            <fieldset class="modalObitoCampos">
                <legend>Obito</legend>

                <div class="formularioCampoModal">
                    <label for="modal-obito-fecha">Fecha de obito</label>
                    <input type="date" id="modal-obito-fecha" name="fecha" class="formularioCampo-date" required
                    )}>
                </div>

                <div class="formularioCampoModal">
                    <label for="modal-obito-tipo">Tipo</label>
                    <select id="modal-obito-tipo" class="formularioCampo-select" name="tipo">
                        <option value="1" selected>Intrahospitalaria</option>
                        <option value="2">Extrahospitalaria</option>
                    </select>
                </div>
                
                <div class="formularioCampoModal">
                    <label for="modal-obito-unidad-clinica">Unidad Clinica</label>
                    <select id="modal-obito-unidad-clinica" class="formularioCampo-select" name="unidad_clinica">
                        <option value="" disabled selected>Seleccione una unidad clinica</option>
                    </select>
                </div>


                <input type="hidden" id="modal-obito-id" name="idObito">
            </fieldset>

            <fieldset class="modalObitoCampos">
                <legend>Entrega Cadaver</legend>
                <div class="formularioCampoModal">
                    <label for="modal-cadaver-dni-responsable">Identidad</label>
                    <input type="text" id="modal-cadaver-dni-responsable" name="dni_responsable" class="formularioCampo-text" required>
                </div>
                
                <div class="formularioCampoModal">
                    <label for="modal-cadaver-nombre-responsable">Nombre</label>
                    <input type="text" id="modal-cadaver-nombre-responsable" name="nombre_responsable" class="formularioCampo-text" placeholder="NOMBRE COMPLETO" required>
                </div>
            </fieldset>
            

            <fieldset class="modalObitoCampos" id="modal-campos-obito-registro" style="display: none;">
                <legend>Detalles del registro</legend>
                <div class="formularioCampoModal">
                    <label for="Fregistro">Registrado</label>
                    <input type="text" id="modal-obito-detalles-registro" class="formularioCampo-text" disabled>
                </div>
            </fieldset>
            </form>
        `,

        showCancelButton: true,
        showCloseButton: true,
        confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
        cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
        customClass: {
                popup: 'contenedor-modal-obito',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'
            },
        preConfirm: () => {

            // validaciones
            const unidad_clinica = document.getElementById("modal-obito-unidad-clinica").value;
            const fecha = document.getElementById("modal-obito-fecha").value;
            const tipo = document.getElementById("modal-obito-tipo").value;
            const dniResponsable = document.getElementById("modal-cadaver-dni-responsable").value;
            const nombreResponsable = document.getElementById("modal-cadaver-nombre-responsable").value;
            const hoy = fechaActualParaInput(false);

            if (!unidad_clinica && tipo!=="2") {
                Swal.showValidationMessage('Debe seleccionar una dependencia');
                return false;
            }

            if (!fecha) {
                Swal.showValidationMessage('Debe seleccionar una fecha');
                return false;
            }

            if (fecha > hoy) {
                Swal.showValidationMessage('La fecha no puede ser mayor que la fecha actual');
                return false;
            }

            if (!dniResponsable) {
                Swal.showValidationMessage('Debe indicar un DNI valido');
                return false;
            }

            if (!nombreResponsable) {
                Swal.showValidationMessage('Debe indicar el nombre del responsable ');
                return false;
            }

            return {
                tipo,
                fecha,
                unidad_clinica: unidad_clinica,
                dniResponsable,
                nombreResponsable,
                idObito: document.getElementById("modal-obito-id").value || 0
            };
        },

        didOpen: async function () {
            const confirmBtn = Swal.getConfirmButton();
            const titleElement = Swal.getTitle(); 
            const unidad_clinica = document.getElementById("modal-obito-unidad-clinica");
            const fecha = document.getElementById("modal-obito-fecha");
            const tipo = document.getElementById("modal-obito-tipo");
            const idObito = document.getElementById("modal-obito-id");
            const detallesRegistro = document.getElementById("modal-obito-detalles-registro");
            const fieldsetRegistro = document.getElementById("modal-campos-obito-registro");
            const dniResponsable = document.getElementById("modal-cadaver-dni-responsable");
            const nombreResponsable = document.getElementById("modal-cadaver-nombre-responsable");

            renderDatosPaciente("modalObitoHeader",{
                "Nombre Madre: ": datosMadre.Paciente,
                "DNI Madre: ": datosMadre.DNI,
                "Expediente Madre: ": datosMadre.Expediente
            });

            // Cargar salas desde el backend
            await UnidadClinicaLoader.cargar(unidad_clinica);

            // Inicializar TomSelect
            const unidaClinicaSelect = new TomSelect("#modal-obito-unidad-clinica", {
                placeholder: 'Seleccione una unidad clinica',
                allowEmptyOption: true
            });


            Inputmask({
                regex: regexIdentidad,
                placeholder: formatoIdentidad,
                oncomplete: async function () {
                const resultado = await obtenerDatosPacienteCenso(this.value);
                if (resultado){
                    nombreResponsable.value= concatenarLimpio(resultado.NOMBRE1,resultado.NOMBRE2,resultado.APELLIDO1,resultado.APELLIDO2);

                } else if (resultado === 0){
                    toastr.info("No se encontraron datos para el dni descrito.");
                    nombreResponsable.value = "";
                } else {
                    toastr.warning("Error al obtener los datos de la persona");
                    
                }
                }
            }).mask(dniResponsable);

            Inputmask({
                regex: regexNombreApellido,
                placeholder: 'NOMBRE COMPLETO'
            }).mask(nombreResponsable);

            try {
                let data = null;
                if (IdObito){
                    data = await fetchData(API_URLS.obtenerObito, { id: IdObito });
                } else {
                    fecha.value = fechaActualParaInput(false);
                    unidaClinicaSelect.clear(true);
                }
                if (data && !("mensaje" in data)) {
                    llenarObito(data);
                }

            }catch (error) {
                console.error(error);
            }

            function llenarObito(obito) {
            // setear valores
                titleElement.innerHTML = `<i class="bi bi-gear"></i> Actualizar Obito`;
                fecha.value = obito.fecha_obito || "";
                idObito.value = obito.id || "";
                detallesRegistro.value = concatenarLimpio(obito.registrado, formatFecha(obito.fechaAdicion)) || "";
                fieldsetRegistro.style.display = 'block';
                tipo.value=obito.tipo_defuncion;
                if (String(obito.tipo_defuncion) === "2") {
                unidaClinicaSelect.disable();
                unidaClinicaSelect.clear();
                } else{
                    if (unidaClinicaSelect){
                        unidaClinicaSelect.enable();
                        unidaClinicaSelect.clear(); // solo limpia

                        if (obito.unidad_codigo) {  
                            if (!unidaClinicaSelect.options[obito.unidad_codigo]) {
                                    unidaClinicaSelect.addOption({
                                    value: obito.unidad_codigo,  
                                    text: obito.unidad_label
                                    });
                                }

                                unidaClinicaSelect.addItem(obito.unidad_codigo, true);
                        }
                        
                    }
                }
                if (obito.reponsable_nombre && obito.reponsable_dni) {
                    dniResponsable.value = obito.reponsable_dni;
                    nombreResponsable.value = obito.reponsable_nombre;
                }
            }

            tipo.addEventListener("change", function() {
                if (this.value === "2") { 
                unidaClinicaSelect.disable();
                unidaClinicaSelect.clear();
                } else {
                unidaClinicaSelect.enable();
                }
            });

        }

    });

    if (modal.isConfirmed) {
        const formData = modal.value;
        try {
            const csrfToken = window.CSRF_TOKEN;
            const response = await fetch(API_URLS.guardarObito, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    idPaciente: idPaciente,
                    idObito: formData.idObito,
                    tipo: formData.tipo,
                    unidadClinica: formData.unidad_clinica,
                    fecha: formData.fecha,
                    dniResponsable: formData.dniResponsable,
                    nombreResponsable: formData.nombreResponsable
                })
            });
            

            const data = await response.json();
            if (!response.ok) throw new Error(`${data.error}`);
            
            if (data.guardo) {
                resultado = data;
                Swal.close();
            } 

        } catch (error) {
            toastr.error("Error al guardar el obito " + error.message);
        }

    }

    return resultado;
}