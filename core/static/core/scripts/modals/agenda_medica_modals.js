

class DiaSemanaMap {

    static dias = new Map([
        [1, "LUNES"],
        [2, "MARTES"],
        [3, "MIÉRCOLES"],
        [4, "JUEVES"],
        [5, "VIERNES"],
        [6, "SÁBADO"],
        [7, "DOMINGO"]
    ]);

    static get(numeroDia) {
        return this.dias.get(Number(numeroDia)) || "";
    }

}


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
                iconoEstado.classList.add('icon-amarillo');
                break;

            case EstadoTemporalPeriodo.EN_EJECUCION:
                textoEstado.textContent = 'En Ejecucion';
                iconoEstado.classList.add('icon-verde');
                break;

            case EstadoTemporalPeriodo.FINALIZADO:
                textoEstado.textContent = 'Finalizado';
                iconoEstado.classList.add('icon-gris');
                break;

            default:
            iconoEstado.classList.add('icon-rojo');
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


//   dia laboral
const ManejarDiaLaboral = (function (){
    let estado = {
        titulo: "",
        diaID: null,
        diaNumero: null,
        contexto: null,
        diaRegistro: null,
    };

    let TiposAtencionregistros = [];


    async function open(config ={}) {
        estado = {
                titulo: "Definir configuracion",
                diaNumero: null,
                diaID: null,
                contexto: null,
                ...config
            };
        
        TiposAtencionregistros = [];

        const modal = await Swal.fire({
            title: `<i class="bi bi-calendar-date"></i> ${estado.titulo} - ${DiaSemanaMap.get(parseInt(estado.diaNumero))} `,
            html: `
                <div class="tituloFormulario-subrallado"></div>

                <div class="modal-contendor-data-encabezado" id="modalDiaLaboralHeader" style="margin-botom:10px">
                </div>

                <form method="post" class="formulario" id="formulario-modal-dia-laboral">
                    <fieldset class="modalDiaLaboralCampos">
                        <legend>Horario</legend>

                        <div class="formularioCampoModal">
                            <label for="modal-dia-laboral-horario-inicio">Inicio:</label>
                            <input type="text" id="modal-dia-laboral-horario-inicio" class="formularioCampo-text" name="horario_inicio">
                            
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-dia-laboral-horario-fin">Fin:</label>
                            <input type="text" id="modal-dia-laboral-horario-fin" class="formularioCampo-text" name="horario_inicio" >
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-dia-laboral-horario-cupos">Cupos:</label>
                            <input type="text" id="modal-dia-laboral-horario-cupos" class="formularioCampo-text" readonly>
                        </div>
                
                    </fieldset>
                            <fieldset class="modalDiaLaboralControlesCupos">
                                <legend>Registro</legend>
                                <div class="formularioCampoModal">
                                    <label for="modal-dia-laboral-tipo_atencion">Atencion:</label>
                                    <div id="modal-dia-laboral-tipo_atencion" class="" name="atencion"></div>
                                </div>

                                <div class="formularioCampoModal">
                                    <label for="modal-dia-laboral-cupos">Cupos:</label>
                                    <input type="number" id="modal-dia-laboral-cupos" class="formularioCampo-text" name="cupos" min="1" max="20" step="1" value="1">
                                </div>

                                <div class="formularioCampoModal">
                                    <label for="modal-dia-laboral-duracion_minutos">Duración :</label>
                                    <input type="number" id="modal-dia-laboral-duracion_minutos" class="formularioCampo-text" name="duracion_minutos" min="5" max="60" step="5" value="5">
                                </div>
                                
                                <div>
                                    <button type="button" class="agregar-editar-cupo-dia-boton" id="agregar-editar-cupo-boton"> 
                                        <i class="bi bi-check-circle-fill"></i>
                                        <span id="agregar-editar-cupo-boton-texto">APLICAR</span>
                                    </button>
                                </div>
                            </fieldset>
                        <fieldset class="modalDiaLaboralContenedorCupos">
                        <legend>Cupos</legend>

                        <div class="contenedor-tabla-estatica-procesos">
                            <i class="bi bi-exclamation-triangle-fill icon-amarillo indicador-tabla-estatica oculto"
                                title="La configuración supera la duración de la jornada laboral">
                            </i>
                            <table class="tabla-estatica-procesos">
                                <thead>
                                    <tr>
                                        <th>Tipo Atención</th>
                                        <th>Cupos</th>
                                        <th class="tabla-estatica-columna-responsive">Duración</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>

                                <tbody id="tabla-estatica-tipos-atencion-body">

                                </tbody>
                            </table>
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
                popup: 'contenedor-modal-dia-laboral',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'

            },
            didOpen: () => inicializar(),
            preConfirm: async () => {
                return await procesarGuardado();
            },
        });

        let indicador = ""
        if (modal.isConfirmed) {
            indicador = modal.value

        }

        return indicador
    }


    async function inicializar(){
        const headerModal = document.getElementById('modalDiaLaboralHeader');
        const cupos = document.getElementById('modal-dia-laboral-horario-cupos');

        
        flatpickr("#modal-dia-laboral-horario-inicio", {
            locale: "es",
            enableTime: true,
            noCalendar: true,
            time_24hr: true,
            dateFormat: "H:i",
            defaultDate: estado.contexto.jornada.horaInicio || "08:00" 
        });

        flatpickr("#modal-dia-laboral-horario-fin", {
            locale: "es",
            enableTime: true,
            noCalendar: true,
            time_24hr: true,
            dateFormat: "H:i",
            defaultDate: estado.contexto.jornada.horaFin || "08:00" 
            
        });


        cupos.value = "0";

        await TipoAtencionLoader.cargar('modal-dia-laboral-tipo_atencion');

        renderDatosContexto("modalDiaLaboralHeader", {
            "Personal Clínico": estado.contexto.personalClinicoNombre,
            "Periodo": estado.contexto.periodoTexto,
            "Día": DiaSemanaMap.get(estado.diaNumero)
        });;

        renderizarTabla();
        inicializarListeners();
    }


    function inicializarListeners(){
        const botonAgregarEditar = document.getElementById('agregar-editar-cupo-boton');
        const tablaBody = document.querySelector("#tabla-estatica-tipos-atencion-body");
        botonAgregarEditar.addEventListener(
                'click',
                agregarEditarTipoAtencion
            );

        tablaBody.addEventListener('dblclick', (e) => {
            const fila = e.target.closest('tr');
            const botonEliminar = e.target.closest('.botonTablaEliminar');
            if (botonEliminar) return;
            if(!fila) return;
            const id = Number(fila.dataset.id);
            if (id){
                editarTipoAtencion(id)
            }
        });

        tablaBody.addEventListener('click', (e) => {
            const fila = e.target.closest('tr');
            if(!fila) return;

            const id = Number(fila.dataset.id);

            const botonEditar = e.target.closest('.botonTablaEditar');
            const botonEliminar = e.target.closest('.botonTablaEliminar');

            if(botonEditar && id){
                editarTipoAtencion(id);
            }
            else if(botonEliminar){
                eliminarTipoAtencion(id);

            }

        });
    }   


    function editarTipoAtencion(id){
        const tipoAtencion = document.querySelector('#modal-dia-laboral-tipo_atencion')
        const cupos = document.getElementById('modal-dia-laboral-cupos')
        const duracion = document.getElementById('modal-dia-laboral-duracion_minutos')

        if (!id) { return;}
         // buscar por id si ya esta en los registros 
        const registro =
            TiposAtencionregistros.find(
                item => item.id === id
            );

        if (registro){
            // llenar el registro 
            console.table(registro);
            cupos.value = registro.cupos;
            duracion.value = registro.duracion;
            tipoAtencion.setValue(String(registro.id));
        } else {
            return;
        }
    } 


    function eliminarTipoAtencion(id){
        if(!id){ return; }

        TiposAtencionregistros =
            TiposAtencionregistros.filter(
                item => item.id !== id
            );

        renderizarTabla();

        limpiarControles();

        toastr.info(
            "Tipo de atención eliminado"
        );
    }


    function actualizarTotalCupos(){
        const total =
            TiposAtencionregistros.reduce( // funcion que se usa para acumular un valor dento de un array
                (acumulador, item) => acumulador + item.cupos,  // es la varuiabkle que pasa entre iterdcaione sy va cmabiand su valor 
                0                           // valor inical del acumulador
            ); 

        document.getElementById(
            'modal-dia-laboral-horario-cupos'
        ).value = total;
    }


    function renderizarTabla(){
        const tbody =
            document.getElementById(
                "tabla-estatica-tipos-atencion-body"
            );

        tbody.innerHTML = "";

        if(TiposAtencionregistros.length === 0){

            tbody.innerHTML = `
                <tr>
                    <td colspan="4"
                        class="tabla-estatica-tabla-vacia">
                        No hay tipos de atención registrados
                    </td>
                </tr>
            `;


            actualizarTotalCupos();
            actualizarIndicadorJornada();
            return;
        }

        
        TiposAtencionregistros.forEach(item => {
            tbody.innerHTML += `
                <tr data-id="${item.id}">
                    <td>${item.tipo}</td>
                    <td>${item.cupos}</td>

                    <td class="tabla-estatica-columna-responsive">
                        ${item.duracion} MIN
                    </td>

                    <td>
                        <div class="tabla-estatica-acciones-wrapper">
                            <button type="button"
                                    class="tabla-estatica-boton botonTablaEditar">
                                <i class="bi bi-pencil-square"></i>
                            </button>

                            <button type="button"
                                    class="tabla-estatica-boton botonTablaEliminar">
                                <i class="bi bi-trash-fill"></i>
                            </button>
                        </div>
                    </td>

                </tr>
            `;
        });

        actualizarTotalCupos();
        actualizarIndicadorJornada();
        
    }


    function agregarEditarTipoAtencion(){
        Swal.resetValidationMessage();

        const tipoAtencion = document.getElementById('modal-dia-laboral-tipo_atencion').virtualSelect
        const cupos = document.getElementById('modal-dia-laboral-cupos')
        const duracion = document.getElementById('modal-dia-laboral-duracion_minutos')
        const opciones = tipoAtencion.getSelectedOptions();

        if(TiposAtencionregistros.length >= 5){
            Swal.showValidationMessage(
                "El límite de tipos de atención es 5"
            );
            return;
        }


        if (!tipoAtencion || !opciones) { //|| !opciones?.length
            Swal.showValidationMessage(
                "Seleccione un tipo de atención para procesar"
            );
            return;
        }

        if (!cupos || Number(cupos.value) <= 0) {
            Swal.showValidationMessage(
                "Ingrese una cantidad de cupos válida"
            );
            return;
        }

        if (!duracion || Number(duracion.value) < 5) {
            Swal.showValidationMessage(
                "La duración debe ser mayor o igual a 5 minutos"
            );
            return;
        }

        const nuevo = {
            id: Number(opciones.value),
            tipo: opciones.label,
            cupos: Number(cupos.value),
            duracion: Number(duracion.value),
        }

        // buscar por id si ya esta en los registros 
        const index = TiposAtencionregistros.findIndex(
            item => item.id === nuevo.id
        );


        if (index >= 0){
            TiposAtencionregistros[index] = nuevo;
            toastr.info("Tipo de atención actualizado");
        } else {
            TiposAtencionregistros.push(nuevo);
        }

        renderizarTabla();
        limpiarControles();
    }


    function actualizarIndicadorJornada(){
        const indicador = document.querySelector('.indicador-tabla-estatica');
        if(!indicador){ return; }

        if(validarDuracionJornada()){
            indicador.classList.add('oculto');
        } else {
            indicador.classList.remove('oculto');
        }
    }


    function validarDuracionJornada(){
        const totalMinutos = TiposAtencionregistros.reduce(
                (totalActual, registro) => {
                    return ( totalActual + (registro.cupos * registro.duracion));
                },
                0
            );
        return (totalMinutos <= Number( estado.contexto.jornada.duracion )
        );
    }


    function limpiarControles(){
        const tipoAtencion = document.getElementById('modal-dia-laboral-tipo_atencion').virtualSelect
        const cupos = document.getElementById('modal-dia-laboral-cupos')
        const duracion = document.getElementById('modal-dia-laboral-duracion_minutos')

        tipoAtencion.reset();
        cupos.value = 1;
        duracion.value = 5;
    }


    function  validarCampos() {
        const horarioInicio = document.getElementById('modal-dia-laboral-horario-inicio')._flatpickr;
        const horarioFin = document.getElementById('modal-dia-laboral-horario-fin')._flatpickr;

        const horaInicio = horarioInicio.input.value;
        const horaFin = horarioFin.input.value;

        const inicioMinutos = convertirHoraMinutos(horaInicio);
        const finMinutos = convertirHoraMinutos(horaFin);

        // validar rango
        if(inicioMinutos >= finMinutos){
            Swal.showValidationMessage(
                "La hora de inicio debe ser menor que la hora final"
            );
            return false;
        }


        if(TiposAtencionregistros.length === 0){
            Swal.showValidationMessage(
                "Debe registrar al menos un tipo de atención"
            );
            return false;
        }


        

        return  {
                horaInicio,
                horaFin,
            };
    }

    async function procesarGuardado() {
        Swal.resetValidationMessage();
        
        const formData = validarCampos();
        if (!formData){
            return
        }

        console.log(formData);

        //ojo si hay registro es edicion
        if (estado && estado.diaRegistro){// indica que estamos editando 
            // validad impacto 
                const confirmado = await confirmarAccion({
                titulo: "jlsadkjalskdas",
                mensajes: [ "mensaje1","mensaje2","mensaje3"],
                icono: "warning"
            });
        }else {// estamos agregandio llamado a guardado
            guardarPeriodo(formData);
            return "guradao agregar"
        }

        
        
        if (!confirmado){
            return "cancelo"
        }else{
            return "aprobo cambios"
            // llmar a guardar
        }
    }



    async function guardarPeriodo(formData){
        if (!formData){
            return
        }


        try {
            const csrfToken = window.CSRF_TOKEN;
            if (!Array.isArray(TiposAtencionregistros) || TiposAtencionregistros.length === 0) {
                toastr.error("Debe agregar al menos un estudio antes de continuar.");
                return;
            }
            const configuraciones = TiposAtencionregistros.map(registro => ({
                id: registro.id,
                cupos: registro.cupos,
                duracion: registro.duracion,
                diaId: estado.diaID,
            }));

            const response = await fetch(API_URLS.guardarDiaPeriodoLaboral, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    horaInicio: formData.horaInicio, 
                    horaFin: formData.horaFin,
                    configuraciones: configuraciones,
                    diaNumero: estado.diaNumero,
                    periodoId: contextoAgenda.periodoId
                })
            });

            const data = await response.json(); 

            console.log(data);
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

        } catch (error) {
            toastr.error(error.message, "Error al guardar el dia laboral ");
        }
    }


    return {  open };

})();