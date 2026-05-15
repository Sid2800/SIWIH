
const ManejarPeriodoLaboral = (function (){
    let modalTitulo = "";
    let modalPeriodoID = null;
    let periodoRegistro = null;

    const EstadoTemporalPeriodo = {
        FUTURO: 'FUTURO',
        EN_EJECUCION: 'EN_EJECUCION',
        FINALIZADO: 'FINALIZADO',
    };

    async function open(config ={}) {
        const {
            titulo = "Agregar Periodo Laboral",
            periodoID = null,
        } = config;

        modalTitulo = titulo;
        modalPeriodoID = periodoID;

        const modal = await Swal.fire({
            title: `<i class="bi bi-calendar-check"></i> ${titulo}`,

            html: `
                <div class="tituloFormulario-subrallado"></div>
                <form method="post" class="formulario" id="formulario-modal-periodo-laboral">
                    <fieldset class="modalPeriodoLaboralCampos">
                        <legend>Personal de Salud</legend>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-personal-salud">Nombre:</label>
                            <div id="modal-periodo-laboral-personal-salud" class="" name="personal_salud"></div>
                            </select>
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-especialidad">Especialidad:</label>
                            <input type="text" id="modal-periodo-laboral-especialidad" class="formularioCampo-text" name="especialidad" readonly>
                            </select>
                        </div>
                        

                        <input type="hidden" id="modal-periodo-laboral-id" name="idPeriodoLaboral">
                    </fieldset>

                    <fieldset class="modalPeriodoLaboralCampos">
                        <legend>Periodo Laboral</legend>

                        <div id="periodoLaboral__estado" class="formularioCampoModal periodo-estado-oculto" >
                            <label >Estado:</label>

                            <div class="formularioCampoModalPeriodoEstado">
                                <div class="estado-indicador">
                                    <i id="modalPeriodoEstadoIndicarIcono" class="bi bi-circle-fill icon-gris"></i>
                                    <span id="modalPeriodoEstadoIndicarTexto">#####</span>
                                </div>

                                <label class="ck-formulario" for="chk-periodo-estado">
                                    <input type="checkbox" id="chk-periodo-estado" class="ck-formulario__checkbox" hidden="">
                                    <div class="ck-formulario__base">
                                        <div class="ck-formulario__bolita"></div>
                                    </div>
                                    <span class="ck-formulario__label">Activo</span>
                                </label>
                            </div>
                        </div>

                        
                        <div class="formularioCampoModal">
                            <label for="modal-periodo-fecha-inicial">Rango:</label>

                            <div class="formularioCampoModalRangoFecha">
                                <input type="date" id="modal-periodo-fecha-inicial" name="fecha_inicial"  class="formularioCampo-date" required>
                                <label >al</label>
                                <input type="date" id="modal-periodo-fecha-final" name="fecha_final" class="formularioCampo-date">
                            </div>

                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-jornada">Jornada:</label>
                            <select id="modal-periodo-laboral-jornada" class="formularioCampo-select" name="jornada">
                            </select>
                        </div>
                    

                    </fieldset>


                    <fieldset class="modalPeriodoLaboralCampos" id="modal-campos-defuncion-registros" style="display: none;">
                    <legend>Detalles del registro</legend>
                    <div class="formularioCampoModal">
                        <label for="Fregistro">Actualizado</label>
                        <input type="text" id="modal-defuncion-detalles-registro" class="formularioCampo-text" disabled>
                    </div>
                    </fieldset>
                </form>
            `,
            showCancelButton: true,
            showCloseButton: true,
            showLoaderOnConfirm: true,
            confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
            cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
            customClass: {
                popup: 'contenedor-modal-periodo-laboral',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'

            },
            didOpen: () => inicializar(periodoID),
            preConfirm: async () => {
                return await procesarGuardado();
            },
        });

        if (modal.isConfirmed){

        }

        return modal
    }

    async function inicializar(periodoID){
        const personalSalud = document.getElementById("modal-periodo-laboral-personal-salud");
        const especialidad = document.getElementById("modal-periodo-laboral-especialidad");
        const fechaInicio = document.getElementById("modal-periodo-fecha-inicial");
        const fechaFinal = document.getElementById("modal-periodo-fecha-final");
        const detallesRegistro = document.getElementById("modal-defuncion-detalles-registro");
        const fieldsetRegistro = document.getElementById("modal-campos-defuncion-registros");

        const hoy = fechaManana(false)


        // Traer, el persona clinico
        //#region inizialiar general
            let data = await PersonalClinicoLoader.cargar();

            const opciones = data.map(item => ({
                value: item.id,
                label: item.nombre,
                customData: item.especialidad__nombre_especialidad,
                description: item.especialidad__nombre_especialidad
            }));

            if (personalSalud.virtualSelect) {
                personalSalud.virtualSelect.destroy();
            }

            // inicializar el vistual select 
            VirtualSelect.init({
                ele: '#modal-periodo-laboral-personal-salud',
                options: opciones,
                hasOptionDescription: true,
                searchPlaceholderText: 'Buscar...',
                search: true,
                placeholder: 'Seleccione',
                additionalClasses: 'custom-wrapper',
                additionalDropboxClasses: 'custom-dropbox',
            }); 

            // listnere de select 
            const slect = document.querySelector('#modal-periodo-laboral-personal-salud')
            slect._handler  = function (){
                const options = slect.getSelectedOptions();
                if (!options) { 
                    especialidad.value = ""; 
                    return; 
                }
                especialidad.value = options.customData || "";
            }
            slect.addEventListener('change', slect._handler)

            // jornada laboral 
            const jornada = document.getElementById("modal-periodo-laboral-jornada");
            await JornadaLoader.cargar(jornada);

            // definir las fechas iniciales max y demas 
            fechaInicio.value = hoy;
            fechaInicio.min = hoy;

            fechaFinal.min = hoy;
            fechaFinal.value = hoy;

            
        //#endregion

        //#region inicializar para la reapertura del form en caso de cancele el proceso
         /*   if(formData){
                slect.setValue(formData.personal);
                fechaInicio.value=formData.fechaInicio;
                fechaFinal.value=formData.fechaFinal;
                jornada.value = formData.jornada
                console.table(formData);
                if (formData.detallesRegistro){
                    mostrarLLenarCamposExlusivosEdicion(
                        {
                        "modificado_por": formData.detallesRegistro.modificado_por,
                        "fecha_modificado": formData.detallesRegistro.fecha_modificado,
                        "estadoRegistro": formData.estadoRegistro,
                        "estadoTemporal": formData.estadoTemporal, 
                        }
                    )
                        
                    fieldsetRegistro.style.display = 'block';
                }
                return
            }*/
        //#endregion
        
        // region para cargar el modo edicion del modal
        if (modalPeriodoID){
            periodoRegistro = await traerPeriodo();
            if (!periodoRegistro){
                return;
            }
            llenarPeriodo(periodoRegistro);

            return;
        }
        //#endregion


        

    }

    function manejarResultadoGuardado(resultado) {
        
        if (resultado.guardo === true) {
        
            toastr.success(
                "Periodo procesado correctamente"
            );
            return true;
        }

        if (resultado.guardo === false) {
            toastr.info(
                "Los datos consignados son idénticos a los registrados"
            );
            return false;
        }

        toastr.warning(
            "No se pudo determinar el resultado del proceso"
        );
        return false;

    }

    async function procesarGuardado() {
        Swal.resetValidationMessage();
        
        const formData = validarCampos();
        if (!formData){
            return
        }
        const resultadoImpacto = await validarImpactoPeriodo(formData);

        if (!resultadoImpacto){
            return false;
        }

        if (!resultadoImpacto.resultado){
            const guardado  = await guardarPeriodo(formData);
            return manejarResultadoGuardado(guardado);
        } 
        

        const confirmado = await confirmarAccion({
            titulo: resultadoImpacto.resultado.titulo,
            mensajes: resultadoImpacto.resultado.mensajes,
            icono: "warning"
        });
        
        if (!confirmado){
            return false;
        }else{

            formData.fechaModificadoImpacto = resultadoImpacto.resultado.fecha_modificado;
            formData.fecha_modificado = resultadoImpacto.resultado.fecha_modificado
            const guardado  = await guardarPeriodo(formData);
            return manejarResultadoGuardado(guardado);
            // llmar a guardar
        }
    }

    async function traerPeriodo() {

        if (!modalPeriodoID){
            return;
        }

        try {
            const response = await fetch(
                `${API_URLS.obtenerPeriodoLaboral}?id=${modalPeriodoID}`,
                {
                    method: "GET",
                    headers: {
                        "Content-Type": "application/json",
                    }
                }
            );

            const data = await response.json();
            if (!response.ok){
                throw new Error(data.error);
            }
            console.table(data);
            return data;
        } catch (error) {
            toastr.error(
                error.message,
                "Error al obtener el período"
            );
        }
    }

    function llenarPeriodo(periodo) {

        if (!periodo){
            return;
        }

        const slect = document.querySelector('#modal-periodo-laboral-personal-salud')
        const fechaInicio = document.getElementById("modal-periodo-fecha-inicial");
        const fechaFinal = document.getElementById("modal-periodo-fecha-final");
        const jornada = document.getElementById("modal-periodo-laboral-jornada");

  
        slect.setValue(periodo.id_personal_clinico);
        fechaInicio.value = periodo.fecha_inicio || "";
        fechaFinal.value = periodo.fecha_final || "";
        jornada.value = periodo.id_jornada;
        mostrarLLenarCamposExlusivosEdicion(
            {
            "modificado_por": periodo.modificado_por,
            "fecha_modificado": periodo.fecha_modificado,
            "estadoRegistro": periodo.estado,
            "estadoTemporal": periodo.ejecucion, 

            }
        )

        aplicarRestriccionesPeriodo(periodo.ejecucion);


    }

    function mostrarLLenarCamposExlusivosEdicion(objeto ={}){
        const {
            modificado_por = null,
            fecha_modificado = null,
            estadoRegistro = null,
            estadoTemporal = null,
        } = objeto;

        const detallesRegistro = document.getElementById("modal-defuncion-detalles-registro");
        const fieldsetRegistro = document.getElementById("modal-campos-defuncion-registros");
        const contenderControlesEstado = document.getElementById("periodoLaboral__estado");
        const textoEstado = document.getElementById('modalPeriodoEstadoIndicarTexto');
        const iconoEstado = document.getElementById('modalPeriodoEstadoIndicarIcono');
        const estadoRegistroObjeto = document.getElementById('chk-periodo-estado');

        detallesRegistro.value = (
            concatenarLimpio(
                modificado_por, ' | ',
                formatFecha(fecha_modificado)
            ) || ""
        );

        iconoEstado.classList.remove(
            'icon-verde',
            'icon-amarillo',
            'icon-rojo',
            'icon-gris'
        );

        estadoRegistroObjeto.checked = Boolean(estadoRegistro);

        switch (estadoTemporal) {
            case EstadoTemporalPeriodo.FUTURO:
                textoEstado.textContent = 'Futuro';
                iconoEstado.classList.add('icon-verde');
                break;

            case EstadoTemporalPeriodo.EN_EJECUCION:
                textoEstado.textContent = 'En Ejecucion';
                iconoEstado.classList.add('icon-amarillo');
                break;

            case EstadoTemporalPeriodo.FINALIZADO:
                textoEstado.textContent = 'Finalizado';
                iconoEstado.classList.add('icon-rojo');
                break;

            default:
            iconoEstado.classList.add('icon-gris');
        }

        fieldsetRegistro.style.display = 'block';
        contenderControlesEstado.classList.remove('periodo-estado-oculto');
    }

    function aplicarRestriccionesPeriodo(estadoTemporal){
        const slect = document.querySelector('#modal-periodo-laboral-personal-salud')
        const fechaInicio = document.getElementById("modal-periodo-fecha-inicial");
        const fechaFinal = document.getElementById("modal-periodo-fecha-final");
        const jornada = document.getElementById("modal-periodo-laboral-jornada");
        const estadoRegistroObjeto = document.getElementById('chk-periodo-estado');

        // compos generales no dependenientes
        fechaInicio.readOnly = false;
        fechaFinal.readOnly = false;
        estadoRegistroObjeto.disabled = false;

        // componentes generales
        slect.disable();
        jornada.disabled = true;


        switch (estadoTemporal) {
            case EstadoTemporalPeriodo.EN_EJECUCION:
                fechaInicio.readOnly = true;
                estadoRegistroObjeto.disabled = true;
                break;

            case EstadoTemporalPeriodo.FINALIZADO:
                fechaInicio.readOnly = true;
                fechaFinal.readOnly = true;
                estadoRegistroObjeto.disabled = true;
                break;
        }

    }


    function  validarCampos() {
        const personal = document.querySelector('#modal-periodo-laboral-personal-salud').value;
        const jornada = document.getElementById("modal-periodo-laboral-jornada").value;
        const fechaInicio = document.getElementById("modal-periodo-fecha-inicial").value;
        const fechaFinal = document.getElementById("modal-periodo-fecha-final").value;
        const estadoRegistro = document.getElementById("chk-periodo-estado").checked;
  

        if (!personal) {
            Swal.showValidationMessage("Debe seleccionar un medico");
            return false;
        }


        if (fechaFinal && fechaFinal < fechaInicio) {
            Swal.showValidationMessage("La fecha final no puede ser menor que la inicial");
            return false;
        }

        const detallesRegistro = periodoRegistro
                                ? {
                                    modificado_por: (
                                        periodoRegistro.modificado_por
                                    ),

                                    fecha_modificado: (
                                        periodoRegistro.fecha_modificado
                                    )
                                }
                                : null;
        
        const estadoTemporal = periodoRegistro
                                ? periodoRegistro.ejecucion : null;

        const fechaModificado = periodoRegistro
                                ? periodoRegistro.fecha_modificado
                                : null;

        return  {
                personal,
                jornada,
                fechaInicio,
                fechaFinal,
                estadoRegistro,
                detallesRegistro,
                estadoTemporal,
                fechaModificado,
                fechaModificadoImpacto: null
            };
    }

    async function validarImpactoPeriodo(formData){


        if (!formData){
            return
        }

        try {
                const csrfToken = window.CSRF_TOKEN;
                const response = await fetch(API_URLS.validarImpactoPeriodoLaboral, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    personalSalud: formData.personal, 
                    fechaInicio: formData.fechaInicio,
                    fechaFinal: formData.fechaFinal,
                    jornadaLaboral: formData.jornada,
                    idPeriodo: modalPeriodoID || null,
                    estado: modalPeriodoID ? formData.estadoRegistro : null
                })
                });
                
                const data = await response.json();

                // VALIDACIONES CONTROLADAS
                if (response.status === 400) {
                    toastr.warning(data.error, "Error de Validacion");
                    return false;
                }

                // ERRORES REALES
                if (response.status >= 500) {
                    throw new Error(
                        data.error ||
                        "No se pudo guardar el período"
                    );
                }

                return data;

            } catch (error) {
                toastr.error( error.message, "Error al validar  el periodo");
            }
    }

    async function guardarPeriodo(formData){
        if (!formData){
            return
        }
        try {
                const csrfToken = window.CSRF_TOKEN;
                const response = await fetch(API_URLS.guardarPeriodoLaboral, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    personalSalud: formData.personal, 
                    fechaInicio: formData.fechaInicio,
                    fechaFinal: formData.fechaFinal,
                    jornadaLaboral: formData.jornada,
                    fechaModificado: formData.fechaModificado ?? null,
                    estado: modalPeriodoID ? formData.estadoRegistro : null,
                    idPeriodo: modalPeriodoID || null,
                    fechaModificadoImpacto: formData.fechaModificadoImpacto ?? null,
                })
                });
                
                const data = await response.json();
        
                
                // VALIDACIONES CONTROLADAS
                if (response.status === 400) {
                    toastr.warning(data.error, "Error de Validacion");
                    return false;
                }

                // ERRORES REALES
                if (response.status >= 500) {
                    throw new Error(
                        data.error ||
                        "No se pudo guardar el período"
                    );
                }

                return data;

        } catch (error) {
            toastr.error(error.message, "Error al guardar el periodo");
        }
    }

    return { open };

})();