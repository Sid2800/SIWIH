const RenderizarPacienteLaborParto = (function () {

   function renderizar(contenedor, paciente) {

      const nombre = concatenarLimpio(
         paciente.primer_nombre,
         paciente.segundo_nombre,
         paciente.primer_apellido,
         paciente.segundo_apellido
      );
      

      contenedor.insertAdjacentHTML("beforeend", `
         <div class="labor-parto__paciente-detalle">

               <div class="labor-parto__paciente-icono grande">
                  <span class="material-symbols-outlined">
                     pregnant_woman
                  </span>
               </div>

               <div class="labor-parto__paciente-datos">

                  <span class="modalLaborPartoPacienteNombre">
                     ${nombre}
                  </span>



                     <div class="labor-parto__dato">
                           <span class="labor-parto__dato-etiqueta">DNI:</span>
                           <strong>${paciente.dni}</strong>
                     </div>

                     <div class="labor-parto__dato">
                           <span class="labor-parto__dato-etiqueta">Expediente:</span>
                           <strong>${paciente.expediente_numero}</strong>
                     </div>

                     <div class="labor-parto__dato">
                           <span class="labor-parto__dato-etiqueta">Edad:</span>
                           <strong>${paciente.edad}</strong>
                     </div
               </div>
         </div>
      `);
   }

   return { renderizar };

})();



const ManejarEpisodioLaborParto = (function () {

    //#region Estado

   let estado = {
   };

   let controles = {};

    //#endregion


   function inicializarUnidadesEntrada() {

      const iconos = {
         "2": "emergency",
         "23": "breastfeeding",
      };


      const unidades = estado.unidadesEntrada;

      if (!unidades) {
         return;
      }

      controles.unidadesEntrada.innerHTML = "";

      Object.entries(unidades).forEach(([id, nombre]) => {

         const opcion = document.createElement("label");

         opcion.className = "labor-parto__opcion-unidad";
         opcion.dataset.unidad = id;

         opcion.innerHTML = `
            <input
               type="radio"
               name="unidadEntrada"
               value="${id}"
            >

            <span class="material-symbols-outlined">
               ${iconos[id] || "location_on"}
            </span>

            <span>
               ${nombre}
            </span>
         `;

         controles.unidadesEntrada.appendChild(opcion);
      });

      const primeraOpcion =
         controles.unidadesEntrada.querySelector(
            'input[name="unidadEntrada"]'
         );

      if (primeraOpcion) {
         primeraOpcion.checked = true;
      }
   }

   function inicializarEstadoInicial() {

      const estadoInicial = estado.estadoInicial;

      if (!estadoInicial) {
         return;
      }

      const contenedor = controles.estadoInicial;

      contenedor.style.setProperty(
         "--color-estado",
         estadoInicial.color
      );

      contenedor.style.setProperty(
         "--fondo-estado",
         estadoInicial.fondo
      );

      contenedor.style.setProperty(
         "--border-color-estado",
         estadoInicial.borderColor
      );

      controles.estadoInicialIcono.innerHTML = IconosLaborParto.obtener(estadoInicial.icono);
   }


    //#region Modal

   async function open(config = {}) {

      estado = {
         estadoInicial: null,
         unidadesEntrada: null,
         ...config
      };


      const modal = await Swal.fire({

         title: `<div class="icono-titulo-modal"><span class="material-symbols-outlined">pregnant_woman</span></div>${estado.modo === "editar" ? "Editar Episodio" : "Agregar Episodio"}`,

         html: `
               <div class="tituloFormulario-subrallado"></div>

               <form
                  method="post"
                  class="formulario"
                  id="formulario-modal-episodio-labor-parto"
               >

                  <!-- PACIENTE -->
                  <fieldset class="modalLaborPartoCampos">

                     <legend>Paciente</legend>

                     <div class="formularioCampoModal">

                           <label for="modal-labor-parto-paciente">
                              Paciente:
                           </label>

                           <div id="modal-labor-parto-paciente"></div>

                     </div>


                     <div class="formularioCampoModal">

                           <label for="modal-labor-parto-paciente-info">
                              Información:
                           </label>

                           <input
                              type="text"
                              id="modal-labor-parto-paciente-info"
                              class="formularioCampo-text"
                              readonly
                           >

                     </div>

                  </fieldset>


                  <!-- UNIDAD DE ENTRADA -->
                  <fieldset class="modalLaborPartoCampos">

                     <legend>Procedencia</legend>

                     <div
                        id="modal-labor-parto-unidades-entrada"
                        class="labor-parto__selector-unidades"
                     >

                     </div>

                  </fieldset>


                  <!-- ESTADO INICIAL -->
                  <fieldset class="modalLaborPartoCampos">

                     <legend>Estado inicial</legend>

                     <div class="labor-parto-estado-inicial">

                           <div
                              class="labor-parto-estado-icono"
                              id="modal-labor-parto-estado-icono"
                           ></div>

                           <div class="labor-parto-estado-contenido">

                              <strong>
                                 Trabajo de parto
                              </strong>

                              <span>
                                 Toda paciente recibida en Labor y Parto
                                 inicia en este estado.
                              </span>

                           </div>

                     </div>

                  </fieldset>


                  <!-- INGRESO -->
                  <fieldset class="modalLaborPartoCampos">

                     <legend>Ingreso</legend>

                     <div class="formularioCampoModal">

                           <label for="modal-labor-parto-fecha-ingreso">
                              Fecha y hora:
                           </label>

                           <input
                              type="text"
                              id="modal-labor-parto-fecha-ingreso"
                              class="formularioCampo-text"
                           >

                     </div>

                  </fieldset>


                  <!-- DETALLES DEL REGISTRO -->
                  <fieldset
                     class="modalLaborPartoCampos"
                     id="modal-labor-parto-detalles-registro"
                     style="display: none;"
                  >

                     <legend>Detalles del registro</legend>

                     <div class="formularioCampoModal">

                           <label>
                              Creado por:
                           </label>

                           <input
                              type="text"
                              id="modal-labor-parto-creado-por"
                              class="formularioCampo-text"
                              disabled
                           >

                     </div>

                     <div class="formularioCampoModal">

                           <label>
                              Fecha creado:
                           </label>

                           <input
                              type="text"
                              id="modal-labor-parto-fecha-creado"
                              class="formularioCampo-text"
                              disabled
                           >

                     </div>

                  </fieldset>

               </form>
         `,

            showCancelButton: true,
            showCloseButton: true,
            showLoaderOnConfirm: true,

            confirmButtonText:'<i class="bi bi-floppy-fill"></i> Guardar',
            cancelButtonText:'<i class="bi bi-x-circle-fill"></i> Cancelar',

            customClass: {
               popup: "contenedor-modal-episodio-labor-parto",
               title: "contener-modal-titulo",
               confirmButton: "contener-modal-boton-confirmar",
               cancelButton: "contener-modal-boton-cancelar",
            },

            didOpen: () => inicializar(),

            preConfirm: async () => {
               await procesarGuardado();
            },

      });

      return modal.isConfirmed
         ? modal.value
         : null;
   }


    //#endregion


    //#region Inicialización

   async function inicializar() {

      inicializarControles();
      await inicializarPaciente();
      inicializarUnidadesEntrada();
      inicializarEstadoInicial();
      
      inicializarFechaIngreso();
      if (estado.modo === "editar") {
         await cargarEpisodio();
         llenarFormulario();
      }

   }


   function inicializarControles() {

      controles = {

         formulario:document.getElementById("formulario-modal-episodio-labor-parto"),
         paciente:document.getElementById("modal-labor-parto-paciente"),
         pacienteInfo: document.getElementById("modal-labor-parto-paciente-info"),
         unidadesEntrada: document.getElementById("modal-labor-parto-unidades-entrada"),
         fechaIngreso: document.getElementById("modal-labor-parto-fecha-ingreso"),
         estadoInicial:document.querySelector(".labor-parto-estado-inicial"),
         estadoInicialIcono:document.getElementById("modal-labor-parto-estado-icono"),
         detallesRegistro: document.getElementById("modal-labor-parto-detalles-registro"),
         creadoPor: document.getElementById("modal-labor-parto-creado-por"),
         fechaCreado: document.getElementById("modal-labor-parto-fecha-creado"),
         

      };

   }


    //#endregion


    //#region Paciente

      async function inicializarPaciente() {

         controles.virtualPaciente = VirtualSelect.init({
            ele: "#modal-labor-parto-paciente",
            search: true,
            placeholder: "Buscar paciente...",
            searchPlaceholderText: "Buscar paciente...",
            hasOptionDescription: true,
            additionalClasses: 'custom-wrapper',
            additionalDropboxClasses: 'custom-dropbox',
            onServerSearch: buscarPacientes,
         });

         const slect = document.querySelector('#modal-labor-parto-paciente')
         slect._changeHandler  = function (){
               const options = slect.getSelectedOptions();
               if (!options) { 
                  controles.pacienteInfo.value = ""; 
                  return; 
               }
               controles.pacienteInfo.value = options.customData || "";
         }

         slect.addEventListener('change', slect._changeHandler);

      }


      async function buscarPacientes(searchValue,virtualSelect) {

         if (!searchValue || searchValue.length < 2) {
            virtualSelect.setServerOptions([]);
            return;
         }

         const data = await fetchData(API_URLS.busquedaPaciente,{valor_buscado:searchValue});

         const opciones = data.map(item => ({
            value: item.id,
            label: item.nombre_completo_interno,
            customData:item.info,
            description:item.info,
         }));

         virtualSelect.setServerOptions(opciones);

      }


    //#endregion


    //#region Fecha de ingreso

   function inicializarFechaIngreso() {

      controles.fpFechaIngreso = flatpickr(
         controles.fechaIngreso,
         {
               locale: "es",
               enableTime: true,
               time_24hr: true,
               dateFormat: "d/m/Y H:i",
               defaultDate: new Date(),
         }
      );

   }


    //#endregion



    //#endregion






    //#region Validaciones

   function validarCampos() {

      const paciente =
         document
               .getElementById("modal-labor-parto-paciente")
               .virtualSelect
               .getSelectedOptions();

      if (!paciente) {
         Swal.showValidationMessage(
               "Debe seleccionar una paciente"
         );

         return false;
      }

      const opcionSeleccionada =
         controles.unidadesEntrada.querySelector(
            'input[name="unidadEntrada"]:checked'
         );


      if (!opcionSeleccionada) {
         Swal.showValidationMessage(
            "Debe seleccionar la unidad de entrada"
         );

         return false;
      }


      const ahora = new Date();
         const fechaSeleccionada =
            controles.fpFechaIngreso.selectedDates[0];

         if (!fechaSeleccionada) {
            Swal.showValidationMessage(
               "Debe seleccionar la fecha y hora de ingreso"
            );

            return false;
         }

         if (fechaSeleccionada > ahora) {
            Swal.showValidationMessage(
               "La fecha no puede ser futura"
            );

            return false;
         }

      return {
         pacienteId: Number(paciente.value),
         unidadEntradaId: opcionSeleccionada.value,
         fechaIngreso: fechaSeleccionada,
      };

   }


    //#endregion


    //#region Persistencia

   async function procesarGuardado() {

      Swal.resetValidationMessage();

      const formData = validarCampos();

      if (!formData) {
         return false;
      }

      return await guardarEpisodio(formData);

   }


   async function guardarEpisodio(formData) {
      // POST crear episodio
      if (!formData) {
         return false;
      }

      try {
         const csrfToken = window.CSRF_TOKEN;
         
         const response = await fetch(API_URLS.guardarEpisodioLaborParto, {
               method: "POST",
               headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": csrfToken,
               },
               body: JSON.stringify({
                  pacienteId: formData.pacienteId,
                  unidadEntradaId: formData.unidadEntradaId,
                  fechaIngreso: formData.fechaIngreso,
               }),
         });

         const data = await response.json();


         // VALIDACIONES CONTROLADAS
         if (response.status === 400) {
               toastr.warning(data.error, "Error de Validacion");
               return false;
         }

         // ERRORES DE PERMISOS
         if (response.status === 403) {
               toastr.warning(
                  data.error || "No tienes permisos para realizar esta acción.",
                  "Acceso denegado"
               );
               return false;
         }

         // ERRORES REALES
         if (!response.ok) {
               throw new Error(
                  data.error || "No se pudo guardar el episodio de Labor y Parto."
               );
         }

         return data;

      } catch (error) {
         toastr.error(
               error.message || "Ocurrió un error inesperado.",
               "Error al guardar el episodio"
         );

         return false;
      }
   }


   async function editarEpisodio(formData) {

      // POST editar episodio

   }


    //#endregion


   return {
      open
   };

})();


const ManejarMovimientoLaborParto = (function () {

    //#region Estado
   let estado = {};

   let controles = {};

    //#endregion


    //#region Modal

   async function open(config = {}) {

      estado = {
         episodio: null,
         nuevoEstado: null,
         ...config
      };

      const modal = await Swal.fire({

         title: `<div class="icono-titulo-modal"><span class="material-symbols-outlined">sync_alt </span></div>Cambiar estado`,

         html: `
               <div class="tituloFormulario-subrallado"></div>

               <form
                  method="post"
                  class="formulario"
                  id="formulario-modal-movimiento-labor-parto"
               >

                  <fieldset class="modalLaborPartoCampos"  id="datosPacienteCambioEstado">
                     <legend>Datos de la paciente</legend>

                  </fieldset>

                     
                  <!-- ESTADO ACTUAL -->

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Estado actual</legend>

                     <div
                           id="modal-movimiento-estado-actual"
                           class="labor-parto-estado-inicial"
                     >
                           <div
                              class="labor-parto-estado-icono"
                              id="modal-movimiento-estado-actual-icono"
                           ></div>

                           <div class="labor-parto-estado-contenido">
                              <strong
                                 id="modal-movimiento-estado-actual-texto"
                              ></strong>

                              <span>
                                 Estado registrado actualmente para la paciente.
                              </span>
                           </div>
                     </div>

                  </fieldset>


                  <!-- NUEVO ESTADO -->

                  <fieldset class="modalLaborPartoCampos">
                  <legend>Nuevo estado</legend>

                  <div class="labor-parto__filtros modalLaborPartoSelectorEstados">
                     <div class="labor-parto__filtros-lista">

                           <!-- TRABAJO DE PARTO -->
                           <label
                              class="labor-parto__filtro"
                              data-estado="1"
                           >
                              <input
                                 type="radio"
                                 name="nuevoEstadoLaborParto"
                                 class="labor-parto__filtro-radio"
                                 value="1"
                              >

                              <span
                                 class="labor-parto__filtro-icono"
                                 data-icono="trabajo_parto"
                              ></span>

                              <span class="labor-parto__filtro-texto">
                                 Labor
                              </span>
                           </label>

                           <!-- EXPULSIVO -->
                           <label
                              class="labor-parto__filtro"
                              data-estado="2"
                           >
                              <input
                                 type="radio"
                                 name="nuevoEstadoLaborParto"
                                 class="labor-parto__filtro-radio"
                                 value="2"
                              >

                              <span
                                 class="labor-parto__filtro-icono"
                                 data-icono="expulsivo"
                              ></span>

                              <span class="labor-parto__filtro-texto">
                                 Expulsivo
                              </span>
                           </label>

                           <!-- PUERPERIO INMEDIATO -->
                           <label
                              class="labor-parto__filtro"
                              data-estado="3"
                           >
                              <input
                                 type="radio"
                                 name="nuevoEstadoLaborParto"
                                 class="labor-parto__filtro-radio"
                                 value="3"
                              >

                              <span
                                 class="labor-parto__filtro-icono"
                                 data-icono="puerperio_inmediato"
                              ></span>

                              <span class="labor-parto__filtro-texto">
                                 Puerperio
                              </span>
                           </label>

                           <!-- CUIDADOS INTERMEDIOS -->
                           <label
                              class="labor-parto__filtro"
                              data-estado="4"
                           >
                              <input
                                 type="radio"
                                 name="nuevoEstadoLaborParto"
                                 class="labor-parto__filtro-radio"
                                 value="4"
                              >

                              <span
                                 class="labor-parto__filtro-icono"
                                 data-icono="cuidados_intermedios"
                              ></span>

                              <span class="labor-parto__filtro-texto">
                                 Intermedios
                              </span>
                           </label>

                     </div>
                  </div>
               </fieldset>

                  <!-- OBSERVACION -->

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Observación (opcional)</legend>

                     <div class="formularioCampoModal">

                           <textarea
                              id="modal-movimiento-observacion"
                              class="formularioCampo-text"
                              maxlength="255"
                              rows="3"
                              resize="none"
                              placeholder="Ingrese una observación..."
                           ></textarea>

                     </div>
                  </fieldset>

               </form>
         `,

         showCancelButton: true,
         showCloseButton: true,
         showLoaderOnConfirm: true,

         confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
  

         cancelButtonText:
               '<i class="bi bi-x-circle-fill"></i> Cancelar',

         customClass: {
               popup: "contenedor-modal-episodio-labor-parto",
               title: "contener-modal-titulo",
               confirmButton: "contener-modal-boton-confirmar",
               cancelButton: "contener-modal-boton-cancelar",
         },

         didOpen: () => inicializar(),

         preConfirm: async () => {
               return await procesarGuardado();
         },

      });

      return modal.isConfirmed
         ? modal.value
         : null;
   }

    //#endregion


    //#region Inicialización

   function inicializar() {

      inicializarControles();
      inicializarSelectorEstados();
      inicializarPaciente();
      inicializarEstadoActual();
      
   }


   function inicializarControles() {
      controles = {
         formulario: document.getElementById("formulario-modal-movimiento-labor-parto"),
         datosPaciente: document.getElementById("datosPacienteCambioEstado"),

         estadoActual: document.getElementById( "modal-movimiento-estado-actual"),
         estadoActualIcono: document.getElementById("modal-movimiento-estado-actual-icono"),
         estadoActualTexto: document.getElementById("modal-movimiento-estado-actual-texto"),

         selectorEstados: document.querySelector("#formulario-modal-movimiento-labor-parto .modalLaborPartoSelectorEstados"),
         observacion: document.getElementById("modal-movimiento-observacion"),

      };

   }

    //#endregion

   function inicializarPaciente() {
      const episodio = estado.episodio;

      if (!episodio) {
         return;
      }

      const paciente = episodio.paciente;

      RenderizarPacienteLaborParto.renderizar(
         controles.datosPaciente,
         paciente
      );

   }



    //#region Estados

   function inicializarEstadoActual() {

      const episodio = estado.episodio;

      if (!episodio) {
         return;
      }

      const estadoActual = episodio.estado_actual_info

      if (!estadoActual) {
         return;
      }

      controles.estadoActual.style.setProperty(
         "--color-estado",
         estadoActual.color
      );

      controles.estadoActual.style.setProperty(
         "--fondo-estado",
         estadoActual.fondo
      );

      controles.estadoActual.style.setProperty(
         "--border-color-estado",
         estadoActual.borderColor
      );

      controles.estadoActualIcono.innerHTML =
         IconosLaborParto.obtener(estadoActual.icono);

      controles.estadoActualTexto.textContent =
         estadoActual.texto;

   }


   function inicializarSelectorEstados() {

      const opciones = controles.selectorEstados.querySelectorAll(
         ".labor-parto__filtro"
      );

      opciones.forEach((opcion) => {

         const estadoObj = estadosLaborParto.find(
               (item) => item.value == opcion.dataset.estado
         );


         if (!estadoObj) {
               return;
         }

         const icono = opcion.querySelector(
               ".labor-parto__filtro-icono"
         );

         icono.innerHTML = IconosLaborParto.obtener(
               estadoObj.icono
         );

         opcion.style.setProperty("--color-estado", estadoObj.color);
         opcion.style.setProperty("--fondo-estado", estadoObj.fondo);
         opcion.style.setProperty("--border-color-estado", estadoObj.borderColor);

         // Marcar el estado recibido como argumento
         const radio = opcion.querySelector(
            ".labor-parto__filtro-radio"
         );
         radio.checked = Number(opcion.dataset.estado) ===Number(estado.nuevoEstado);
         radio.disabled = Number(opcion.dataset.estado) ===Number(estado.episodio.estado_actual);

      });


   }


    //#endregion


    //#region Validaciones

   function validarCampos() {

      const observacion = controles.observacion.value.trim();

      const opcionSeleccionada =
            controles.selectorEstados.querySelector(
               'input[name="nuevoEstadoLaborParto"]:checked:not(:disabled)'
            );

      if (!opcionSeleccionada) {
            Swal.showValidationMessage(
               "Debe seleccionar un estado diferente al actual."
            );

            return false;
      }

      return {
            episodioId: estado.episodio.id,
            estadoNuevo: Number(opcionSeleccionada.value),
            observacion: observacion || null,
      };

   }

    //#endregion


    //#region Persistencia

   async function procesarGuardado() {

      Swal.resetValidationMessage();
      const formData = validarCampos();

      if (!formData) {
         return false;
      }


      return await guardarMovimiento(formData);

   }


   async function guardarMovimiento(formData) {

      if (!formData) {
         return false;
      }

      try {
         const csrfToken = window.CSRF_TOKEN;

         const response = await fetch(
            API_URLS.procesarMovimientoLaborParto,
            {
                  method: "POST",
                  headers: {
                     "Content-Type": "application/json",
                     "X-CSRFToken": csrfToken,
                  },
                  body: JSON.stringify({
                     episodioId: formData.episodioId,
                     estadoNuevo: formData.estadoNuevo,
                     observacion: formData.observacion,
                  }),
            }
         );

         const data = await response.json();

         // VALIDACIONES CONTROLADAS
         if (response.status === 400) {
            toastr.warning(data.error, "Error de validación");
            return false;
         }

         // ERRORES DE PERMISOS
         if (response.status === 403) {
            toastr.warning(
                  data.error || "No tienes permisos para realizar esta acción.",
                  "Acceso denegado"
            );
            return false;
         }

         // ERRORES REALES
         if (!response.ok) {
            throw new Error(
                  data.error || "No se pudo guardar el cambio de estado."
            );
         }

         return data;

      } catch (error) {
         console.error("Error al guardar el cambio de estado:", error);

         toastr.error(
            "No se pudo guardar el cambio de estado. Inténtalo nuevamente.",
            "Error inesperado"
         );

         return false;
      }
   }


    //#endregion


   return {
      open
   };

})();



const ManejarDetalleMovimientoLaborParto = (function () {

    //#region Estado

   let estado = {};
   estado.movimiento = null;
   estado.movimiento_id = null;
   estado.episodio = null;

   let controles = {};

    //#endregion


    //#region Modal
   async function open(config = {}) {
      estado = {
         movimiento_id: null,
         ...config
      };

      const modal = await Swal.fire({
         title: `<div class="icono-titulo-modal"><span class="material-symbols-outlined">sync_alt </span></div>Detalle  movimiento`,

         html: `
            <div class="tituloFormulario-subrallado"></div>

            <form id="formulario-modal-detalle-movimiento-labor-parto">

               <fieldset class="modalLaborPartoCampos"
                           id="datosPacienteDetalleMovimiento">
                     <legend>Datos de la paciente</legend>
               </fieldset>

               <fieldset class="modalLaborPartoCampos">
                     <legend>Contexto del episodio</legend>

                     <div class="contextoEpisodioLaborParto">

                        <div class="contextoEpisodioItem">
                           <i class="bi bi-calendar-event"></i>

                           <label>Fecha de ingreso</label>

                           <div class="contextoEpisodioValor">
                              <div id="modal-detalle-episodio-fecha-ingreso">
                                    13/03/2024 08:30
                              </div>

                              <div id="modal-detalle-episodio-tiempo-transcurrido"
                                    class="contextoEpisodioDetalle">
                                    Hace 2 horas 53 minutos
                              </div>
                           </div>
                        </div>

                        <div class="contextoEpisodioItem" id="modal-detalle-episodio-estado-actual-contenedor">
                           <div id="modal-detalle-episodio-estado-actual-icono"
                              class="contextoEpisodioIcono">
                           </div>

                           <label>Estado actual</label>

                           <div class="contextoEpisodioValor">
                              <div id="modal-detalle-episodio-estado-actual">
                                    ----
                              </div>

                              <div id="modal-detalle-episodio-detalle-estado-actual"
                                    class="contextoEpisodioDetalle">
                                    ----
                              </div>
                           </div>
                        </div>

                     </div>
               </fieldset>

               <fieldset class="modalLaborPartoCampos">
                  <legend>Cambio de estado</legend>

                  <div class="detalleCambioEstadoLaborParto">

                     <!-- ESTADO ANTERIOR -->
                     <div id="modal-detalle-movimiento-estado-anterior-contenedor"
                           class="detalleEstadoMovimiento">

                           <div class="detalleEstadoMovimientoTitulo">
                              Estado anterior
                           </div>

                           <div class="detalleEstadoMovimientoContenido">

                              <div id="modal-detalle-movimiento-estado-anterior-icono"
                                    class="detalleEstadoMovimientoIcono">
                              </div>

                              <div id="modal-detalle-movimiento-estado-anterior-texto"
                                    class="detalleEstadoMovimientoTexto">
                              </div>

                           </div>
                     </div>

                     <!-- ICONO CENTRAL DE TRANSICIÓN -->
                     <div id="modal-detalle-movimiento-transicion-icono"
                           class="detalleCambioEstadoIcono">
                           <i class="bi bi-arrow-right"></i>
                     </div>

                     <!-- ESTADO NUEVO -->
                     <div id="modal-detalle-movimiento-estado-nuevo-contenedor"
                           class="detalleEstadoMovimiento">

                           <div class="detalleEstadoMovimientoTitulo">
                              Estado nuevo
                           </div>

                           <div class="detalleEstadoMovimientoContenido">

                              <div id="modal-detalle-movimiento-estado-nuevo-icono"
                                    class="detalleEstadoMovimientoIcono">
                              </div>

                              <div id="modal-detalle-movimiento-estado-nuevo-texto"
                                    class="detalleEstadoMovimientoTexto">
                              </div>

                           </div>
                     </div>

                     </div>

                        <div class="informacionMovimientoLaborParto">

                        <div class="informacionMovimientoItem">
                              <i class="bi bi-arrow-left-right"></i>
                              <label>Tipo</label>

                              <div id="modal-detalle-movimiento-tipo">
                                 —
                              </div>
                        </div>

                        <div class="informacionMovimientoItem">
                              <i class="bi bi-calendar-event"></i>
                              <label>Fecha </label>

                              <div id="modal-detalle-movimiento-fecha">
                                 —
                              </div>
                        </div>

                        <div class="informacionMovimientoItem">
                              <i class="bi bi-person-badge"></i>
                              <label>Usuario </label>

                              <div id="modal-detalle-movimiento-usuario">
                                 —
                              </div>
                        </div>

                     </div>

                  
               </fieldset>

               <fieldset class="modalLaborPartoCampos">
                     <legend>Observación</legend>

                     <div class="formularioCampoModal">

                           <textarea id="modal-detalle-movimiento-observacion" class="formularioCampo-text" maxlength="255" rows="3" resize="none" placeholder="Ingrese una observación..."></textarea>

                     </div>
               </fieldset>

            </form>
         `,

         showCancelButton: true,
         showCloseButton: true,
         showLoaderOnConfirm: true,
         showDenyButton: true,

         confirmButtonText:
            '<i class="bi bi-floppy-fill"></i> Guardar',

         cancelButtonText:
            '<i class="bi bi-x-circle-fill"></i> Cancelar',

         denyButtonText:
            '<i class="bi bi-ban"></i> Desactivar',

         customClass: {
            popup: "contenedor-modal-episodio-labor-parto",
            title: "contener-modal-titulo",
            confirmButton: "contener-modal-boton-confirmar",
            cancelButton: "contener-modal-boton-cancelar",
            denyButton: "contener-modal-boton-cancelar",
         },

         focusConfirm: false,

            didOpen: async () => {
                  await inicializar();
            },

            preConfirm: async () => {
                  return await procesarGuardado();
            },

            preDeny: async () => {
                  return await procesarGuardado(false);
            }
      });

      if (modal.isConfirmed) {
         return modal.value;
      }

      if (modal.isDenied) {
         return modal.value;
      }

      return null;
   }
   //#endregion


    //#region Inicialización

   async function inicializar() {
      inicializarControles();
      await obtener_movimiento();
      inicializarPaciente();
      inicializarContextoEpisodio();
      inicializarMovimiento();
   }

   function inicializarControles() {
      controles = {
         formulario: document.getElementById("formulario-modal-detalle-movimiento-labor-parto"),
         datosPaciente: document.getElementById("datosPacienteDetalleMovimiento"),
         
         // CONTEXTO DEL EPISODIO
         fechaIngreso: document.getElementById("modal-detalle-episodio-fecha-ingreso"),
         tiempoTranscurrido: document.getElementById("modal-detalle-episodio-tiempo-transcurrido"),
         contenedorEstadoActual: document.getElementById("modal-detalle-episodio-estado-actual-contenedor"),
         estadoActual: document.getElementById("modal-detalle-episodio-estado-actual"),
         detalleEstadoActual: document.getElementById("modal-detalle-episodio-detalle-estado-actual"),
         iconoEstadoActual: document.getElementById("modal-detalle-episodio-estado-actual-icono"),


         // CAMBIO DE ESTADO
         contenedorEstadoAnterior: document.getElementById("modal-detalle-movimiento-estado-anterior-contenedor"),
         iconoEstadoAnterior: document.getElementById("modal-detalle-movimiento-estado-anterior-icono"),
         textoEstadoAnterior: document.getElementById("modal-detalle-movimiento-estado-anterior-texto"),

         iconoTransicion: document.getElementById("modal-detalle-movimiento-transicion-icono"),

         contenedorEstadoNuevo: document.getElementById("modal-detalle-movimiento-estado-nuevo-contenedor"),
         iconoEstadoNuevo: document.getElementById("modal-detalle-movimiento-estado-nuevo-icono"),
         textoEstadoNuevo: document.getElementById("modal-detalle-movimiento-estado-nuevo-texto"),

         // INFORMACIÓN DEL MOVIMIENTO
         tipoMovimiento: document.getElementById("modal-detalle-movimiento-tipo"),
         fechaMovimiento: document.getElementById("modal-detalle-movimiento-fecha"),
         usuarioResponsable: document.getElementById("modal-detalle-movimiento-usuario"),

         observacion: document.getElementById("modal-detalle-movimiento-observacion"),
      };
   }

    //#endregion


   async function obtener_movimiento() {

      if (!estado.movimiento_id) {
         return;
      }

      try {
         const data = await fetchData(
            API_URLS.obtenerMovimientoLaborParto,
            {
               id: estado.movimiento_id,
            }
         );

         if (!data) {
            return;
         }

         estado.movimiento = data.movimiento;

      } catch (error) {
         toastr.error(
            error.message,
            "Error al obtener el movimiento"
         );

      }
      
   
   }
    //#region Paciente

   function inicializarPaciente() {
      const episodio = estado.episodio;

      if (!episodio) {
         return;
      }

      const paciente = episodio.paciente;

      RenderizarPacienteLaborParto.renderizar(
         controles.datosPaciente,
         paciente
      );

   }


   function inicializarContextoEpisodio() {
      const episodio = estado.episodio;


      if (!episodio) {
         return;
      }

      controles.tiempoTranscurrido.textContent = episodio.tiempo_labor_parto ?? "-";
      controles.fechaIngreso.textContent =episodio.fecha_ingreso
                                          ? `${formatearFechaLocal(episodio.fecha_ingreso)} - ${formatearHoraLocal(episodio.fecha_ingreso)}`
                                          : "-";


      const estadoActual = episodio.estado_actual_info;



      if (estadoActual) {
         controles.estadoActual.textContent = episodio.alta
            ? `ALTA · ${estadoActual.texto}`
            : estadoActual.texto;

         controles.detalleEstadoActual.textContent =
            "Estado vigente del episodio.";

         controles.iconoEstadoActual.innerHTML =
            IconosLaborParto.obtener(estadoActual.icono);

         controles.contenedorEstadoActual.style.setProperty(
            "--color-estado",
            estadoActual.color
         );

         controles.contenedorEstadoActual.style.setProperty(
            "--fondo-estado",
            estadoActual.fondo
         );

         controles.contenedorEstadoActual.style.setProperty(
            "--border-color-estado",
            estadoActual.borderColor
         );
      }

   }  

   function inicializarMovimiento(){
      const movimiento = estado.movimiento;
      if (!movimiento) {
         return;
      }

      // ESTADO ANTERIOR
      const estadoAnterior = estadosLaborParto.find(estado => estado.value === movimiento.estado_anterior);
      controles.contenedorEstadoAnterior.style.setProperty("--color-estado", estadoAnterior.color);
      controles.contenedorEstadoAnterior.style.setProperty("--fondo-estado", estadoAnterior.fondo);
      controles.contenedorEstadoAnterior.style.setProperty("--border-color-estado", estadoAnterior.borderColor);
      controles.iconoEstadoAnterior.innerHTML =IconosLaborParto.obtener(estadoAnterior.icono);
      controles.textoEstadoAnterior.textContent = movimiento.estado_anterior_display;


      // ESTADO NUEVO

      let estadoNuevo = estadosLaborParto.find(estado => estado.value === movimiento.estado_nuevo);
      

      if (
         !estadoNuevo &&
         movimiento.estado_alta_info
      ) {
         estadoNuevo = movimiento.estado_alta_info;
      }


      controles.contenedorEstadoNuevo.style.setProperty("--color-estado", estadoNuevo.color);
      controles.contenedorEstadoNuevo.style.setProperty("--fondo-estado", estadoNuevo.fondo);
      controles.contenedorEstadoNuevo.style.setProperty("--border-color-estado",estadoNuevo.borderColor);
      controles.iconoEstadoNuevo.innerHTML = IconosLaborParto.obtener(estadoNuevo.icono);
      controles.textoEstadoNuevo.textContent = movimiento.estado_nuevo_display || estadoNuevo.texto;

      controles.tipoMovimiento.textContent = movimiento.tipo_display;
      controles.fechaMovimiento.textContent = movimiento.fecha_movimiento
                                          ? `${formatearFechaLocal(movimiento.fecha_movimiento)} - ${formatearHoraLocal(movimiento.fecha_movimiento)}`
                                          : "-";
                                          
      controles.usuarioResponsable.textContent = movimiento.usuario.nombre;
      controles.observacion.value = movimiento.observacion;
      
   }

    //#endregion



    //#region Validaciones

   function validarCampos() {
      const observacion = controles.observacion.value.trim();
      // Validar y obtener la observación modificada.
      return {
            observacion: observacion || null,
      };
   }

    //#endregion


    //#region Persistencia

   async function procesarGuardado(mantenerActivo = true) {
      Swal.resetValidationMessage();

      const formData = validarCampos();

      if (!formData) {
         return false;
      }

      formData.activo = mantenerActivo;

      return await guardarMovimiento(formData);
   }


   async function guardarMovimiento(formData) {
      if (!formData) {
         return false;
      }

      try {
         const csrfToken = window.CSRF_TOKEN;

         const response = await fetch(
               API_URLS.gestionarMovimientoLaborParto,
               {
                  method: "POST",
                  headers: {
                     "Content-Type": "application/json",
                     "X-CSRFToken": csrfToken,
                  },
                  body: JSON.stringify({
                     movimiento_id: estado.movimiento_id,
                     observacion: formData.observacion,
                     activo: formData.activo,
                  }),
               }
         );

         const data = await response.json();

         // VALIDACIONES CONTROLADAS
         if (response.status === 400) {
               toastr.warning(data.error, "Error de validación");
               return false;
         }

         // ERRORES DE PERMISOS
         if (response.status === 403) {
               toastr.warning(
                  data.error || "No tienes permisos para realizar esta acción.",
                  "Acceso denegado"
               );
               return false;
         }

         // ERRORES REALES
         if (!response.ok) {
               throw new Error(
                  data.error || "No se pudo gestionar el movimiento."
               );
         }

          // SIN CAMBIOS
         if (!data.guardado) {
            toastr.info(
                  "No se realizaron cambios en el movimiento.",
                  "Sin cambios"
            );
            return false;
         }

         toastr.success(
               formData.activo
                  ? "Observación actualizada correctamente."
                  : "Movimiento desactivado correctamente.",
               "Operación completada"
         );

         return data;

      } catch (error) {
         console.error("Error al gestionar el movimiento:", error);

         toastr.error(
               "No se pudo procesar la operación. Inténtalo nuevamente.",
               "Error inesperado"
         );

         return false;
      }
   }


    //#endregion


   return {
      open,
   };

})();



const ManejarAltaLaborParto = (function () {

    //#region Estado

   let estado = {};
   let controles = {};


   function inicializarUnidadesSalida() {

      const iconos = {
         "23": "breastfeeding",
         "31": "content_cut",
         "35": "outbound",
      };


      const unidades = estado.unidadesSalida;

      if (!unidades || !controles.unidadesSalida) {
         return;
      }

      controles.unidadesSalida.innerHTML = "";

      Object.entries(unidades).forEach(([id, nombre]) => {

         const opcion = document.createElement("label");

         opcion.className = "labor-parto__opcion-unidad";
         opcion.dataset.unidad = id;

         opcion.innerHTML = `
               <input
                  type="radio"
                  name="unidadSalida"
                  value="${id}"
                  required
               >

               <span class="material-symbols-outlined">
                  ${iconos[id] || "location_on"}
               </span>

               <span class="labor-parto__opcion-unidad-texto">
                  ${nombre}
               </span>
         `;

         controles.unidadesSalida.appendChild(opcion);
      });

      const primeraOpcion =
         controles.unidadesSalida.querySelector(
            'input[name="unidadSalida"]'
         );

      if (primeraOpcion) {
         primeraOpcion.checked = true;
      }
   }
    //#endregion


    //#region Modal

   async function open(config = {}) {

      estado = {
         episodio: null,
         unidadesSalida: null,
         ...config,
      };

      if (!estado.episodio?.id) {
         toastr.warning(
               "No se recibió un episodio válido.",
               "No se puede registrar el alta"
         );
         return null;
      }

      const modal = await Swal.fire({

         title: `<div class="icono-titulo-modal"><span class="material-symbols-outlined">logout</span></div>Dar de alta`,
         html: `
               <div class="tituloFormulario-subrallado"></div>

               <form id="formulario-modal-alta-labor-parto">

                  <fieldset
                     class="modalLaborPartoCampos"
                     id="datosPacienteAltaLaborParto">

                     <legend>Datos de la paciente</legend>

                  </fieldset>

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Unidad de salida</legend>

                     <div
                           id="modal-alta-unidades-salida"
                           class="unidadesSalidaLaborParto">

                     </div>

                  </fieldset>

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Información del alta</legend>

                     <div class="informacionAltaLaborParto">

                           <div class="informacionAltaItem">

                              <i class="bi bi-calendar-event"></i>

                              <div>
                                 <label>Fecha y hora del alta</label>

                                 <div
                                       id="modal-alta-fecha-hora"
                                       class="informacionAltaValor">
                                       Se registrará al confirmar
                                 </div>
                              </div>

                           </div>

                           <div class="informacionAltaItem">

                              <i class="bi bi-person-badge"></i>

                              <div>
                                 <label>Responsable del alta</label>

                                 <div
                                       id="modal-alta-responsable"
                                       class="informacionAltaValor">
                                       Usuario autenticado
                                 </div>
                              </div>

                           </div>

                     </div>

                  </fieldset>

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Observaciones (opcional)</legend>

                     <div class="formularioCampoModal">

                           <textarea
                              id="modal-alta-observacion"
                              class="formularioCampo-text"
                              maxlength="255"
                              rows="3"
                              placeholder="Ingrese una observación..."></textarea>

                     </div>

                  </fieldset>

               </form>
         `,

         showCancelButton: true,
         showCloseButton: true,
         showLoaderOnConfirm: true,

         confirmButtonText:
               '<i class="bi bi-floppy-fill"></i> Dar de alta',

         cancelButtonText:
               '<i class="bi bi-x-circle-fill"></i> Cancelar',

         customClass: {
               popup: "contenedor-modal-episodio-labor-parto",
               title: "contener-modal-titulo",
               confirmButton: "contener-modal-boton-confirmar",
               cancelButton: "contener-modal-boton-cancelar",
         },

         focusConfirm: false,

         didOpen: () => {
               inicializar();
         },

         preConfirm: async () => {
               return await procesarAlta();
         },

      });

      if (modal.isConfirmed) {
         return modal.value;
      }

      return null;
   }

    //#endregion


    //#region Inicialización

   function inicializar() {

      inicializarControles();
      inicializarPaciente();
      inicializarUnidadesSalida();
      inicializarInformacionAlta();
   }


   function inicializarControles() {

      controles = {

         formulario: document.getElementById("formulario-modal-alta-labor-parto"),
         datosPaciente: document.getElementById("datosPacienteAltaLaborParto"),
         unidadesSalida: document.getElementById("modal-alta-unidades-salida"),
         fechaHora: document.getElementById("modal-alta-fecha-hora"),
         responsable: document.getElementById("modal-alta-responsable"),
         observacion: document.getElementById("modal-alta-observacion"),
         selectorSexo: document.getElementById("modal-alta-selector-sexo"),

      };
   }


   function inicializarPaciente() {

      const episodio = estado.episodio;

      if (!episodio?.paciente) {
         return;
      }

      RenderizarPacienteLaborParto.renderizar(
         controles.datosPaciente,
         episodio.paciente
      );
   }

   function inicializarInformacionAlta() {
         const ahora = new Date();

         controles.fechaHora.textContent =
            `${formatearFechaLocal(ahora)} - ${formatearHoraLocal(ahora)}`;

         controles.responsable.textContent =
            usuarioAutenticado.nombre;
   }


   function validarCampos() {

      const unidadSeleccionada = controles.unidadesSalida.querySelector(
         'input[name="unidadSalida"]:checked'
      );

      if (!unidadSeleccionada) {
         Swal.showValidationMessage(
               "Selecciona una unidad de salida."
         );
         return false;
      }

      return {
         episodio_id: estado.episodio.id,
         unidad_salida: unidadSeleccionada.value,
         observacion: controles.observacion.value.trim() || null,
      };
   }



   async function procesarAlta() {

      Swal.resetValidationMessage();

      const formData = validarCampos();

      if (!formData) {
         return false;
      }

      return await guardarAlta(formData);
   }


   async function guardarAlta(formData) {

      try {
         const response = await fetch(
               API_URLS.registrarAltaLaborParto,
               {
                  method: "POST",

                  headers: {
                     "Content-Type": "application/json",
                     "X-CSRFToken": window.CSRF_TOKEN,
                  },

                  body: JSON.stringify(formData),
               }
         );

         const data = await response.json();
         if (response.status === 400) {

               const mensaje = Array.isArray(data.error)
                  ? data.error.join(" ")
                  : data.error;

               toastr.warning(
                  mensaje || "Error de validación."
               );

               return false;
         }

         if (response.status === 403) {

               toastr.warning(
                  data.error ||
                  "No tienes permisos para registrar el alta."
               );

               return false;
         }

         if (!response.ok) {

               throw new Error(
                  data.error || "No se pudo registrar el alta."
               );
         }

         toastr.success(
               "El alta se registró correctamente.",
               "Operación completada"
         );

         return data;

      } catch (error) {

         console.error(
               "Error al registrar el alta de Labor y Parto:",
               error
         );

         toastr.error(
               "No se pudo registrar el alta. Inténtalo nuevamente.",
               "Error inesperado"
         );

         return false;
      }
   }



   return {
      open,
   };

})();



const ManejarBebeLaborParto = (function () {

   //#region Estado

   let estado = {};

   let controles = {};

   //#endregion


   //#region Modal

   async function open(config = {}) {

      estado = {
         episodio: null,
         bebeId: null,
         bebe: null,
         ...config,
      };

      const esEdicion = Boolean(estado.bebeId);

      if (!estado.episodio?.id) {
         toastr.warning(
               "No se recibió un episodio válido.",
               "No se puede continuar"
         );
         return null;
      }


      const modal = await Swal.fire({

         title: `<div class="icono-titulo-modal"><span class="material-symbols-outlined">child_care</span></div>${esEdicion ? "Editar bebé" : "Registrar bebé"}`,

         html: `
               <div class="tituloFormulario-subrallado"></div>

               <form
                  method="post"
                  class="formulario"
                  id="formulario-modal-bebe-labor-parto"
               >

                  <!-- CONTEXTO DEL EPISODIO -->

                  <fieldset class="modalLaborPartoCampos" id="datosPacienteGestionBebe">

                     <legend>Datos de la madre</legend>

                  </fieldset>


                  <!-- DATOS DEL BEBÉ -->

                  <fieldset class="modalLaborPartoCampos">

                     <legend>Datos del bebé</legend>
                     <!-- SEXO DEL BEBÉ -->
               
                     <div
                        id="modal-bebe-selector-sexo"
                        class="labor-parto__selector-sexo"
                     >
                        <span class="labor-parto__etiqueta">Sexo</span>

                        <!-- HOMBRE -->
                        <label
                              class="labor-parto__opcion-sexo"
                              data-sexo="H"
                        >
                              <input
                                 type="radio"
                                 name="sexoBebeLaborParto"
                                 value="H"
                                 required
                              >

                              <span class="material-symbols-outlined">
                                 male
                              </span>

                              <span class="labor-parto__opcion-sexo-texto">
                                 Hombre
                              </span>
                        </label>

                        <!-- MUJER -->
                        <label
                              class="labor-parto__opcion-sexo"
                              data-sexo="M"
                        >
                              <input
                                 type="radio"
                                 name="sexoBebeLaborParto"
                                 value="M"
                                 required
                                 checked
                              >

                              <span class="material-symbols-outlined">
                                 female
                              </span>

                              <span class="labor-parto__opcion-sexo-texto">
                                 Mujer
                              </span>
                        </label>

                        <!-- NO IDENTIFICADO -->
                        <label
                              class="labor-parto__opcion-sexo"
                              data-sexo="N"
                        >
                              <input
                                 type="radio"
                                 name="sexoBebeLaborParto"
                                 value="N"
                                 required
                              >

                              <span class="material-symbols-outlined">
                                 transgender
                              </span>

                              <span class="labor-parto__opcion-sexo-texto">
                                 No identificado
                              </span>
                        </label>

                     </div>

                     <div class="labor-parto__bebe-grid"">
                        <div class="formularioCampoModal">
                           <label for="modal-bebe-orden">
                              Orden de nacimiento:
                           </label>

                           <input
                              type="text"
                              id="modal-bebe-orden"
                              class="formularioCampo-text"
                              readonly
                           >
                        </div>


                        <div class="formularioCampoModal">

                              <label for="modal-bebe-fecha-nacimiento">
                                 Fecha y hora de nacimiento:
                              </label>

                              <input
                                 type="text"
                                 id="modal-bebe-fecha-nacimiento"
                                 class="formularioCampo-text"
                                 placeholder="Seleccione fecha y hora"
                                 autocomplete="off"
                              >

                        </div>


                        <div class="formularioCampoModal observaciones">

                              <label for="modal-bebe-observacion">
                                 Observaciones:
                              </label>

                              <textarea
                                 id="modal-bebe-observacion"
                                 class="formularioCampo-text"
                                 rows="3"
                                 maxlength="255"
                                 placeholder="Observaciones opcionales"
                              ></textarea>

                        </div>
                     </div>
                     

                  </fieldset>

               </form>
         `,

         showCancelButton: true,
         showDenyButton: true,
         showCloseButton: true,

         confirmButtonText: `<i class="bi bi-floppy-fill"></i> ${esEdicion ? 'Guardar' : 'Registrar'}`,
         cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
         denyButtonText: '<i class="bi bi-ban"></i> Desactivar',

         focusConfirm: true,

         customClass: {
            popup: "contenedor-modal-episodio-labor-parto",
            title: "contener-modal-titulo",
            confirmButton: "contener-modal-boton-confirmar",
            cancelButton: "contener-modal-boton-cancelar",
            denyButton: "contener-modal-boton-cancelar oculto",
         },

         didOpen: async () => {
               inicializarControles();
               inicializarFechaNacimiento();
               inicializarPaciente();

               if (esEdicion) {
                  await obtenerBebe();
                  llenarFormulario();
                  Swal.getDenyButton()?.classList.remove("oculto");
               }
               inicializarOrden();
         },

         preConfirm: async () => {

               const datos = validarCampos();

               if (!datos) {
                  return false;
               }

               return await guardarBebe(datos);
         },

         preDeny: async () => {
            const datos = validarCampos();

            if (!datos) {
               return false;
            }

            datos.estado = false;

            return await guardarBebe(datos);
         },

      });

      if ((!modal.isConfirmed && !modal.isDenied) || !modal.value) {
         return null;
      }

      toastr.success(
         esEdicion
               ? "Los datos del bebé se actualizaron correctamente."
               : "El bebé se registró correctamente.",
         "Proceso realizado",
         { timeOut: 1500 }
      );

      return {
         guardado: true,
         modo: esEdicion ? "editar" : "crear",
         bebe: modal.value.bebe,
      };
   }

   //#endregion


   //#region Controles

   function inicializarControles() {

      controles = {
         formulario: document.getElementById(
               "formulario-modal-bebe-labor-parto"
         ),

         datosPaciente: document.getElementById(
               "datosPacienteGestionBebe"
         ),

         orden: document.getElementById(
               "modal-bebe-orden"
         ),

         selectorSexo: document.getElementById("modal-bebe-selector-sexo"),


         fechaNacimiento: document.getElementById(
               "modal-bebe-fecha-nacimiento"
         ),

         observacion: document.getElementById(
               "modal-bebe-observacion"
         ),

         flatpickr: null,
      };

   }

   //#endregion


   //#region Flatpickr

   function inicializarFechaNacimiento() {

      controles.flatpickr = flatpickr(
         controles.fechaNacimiento,
         {
               locale: "es",
               enableTime: true,
               time_24hr: true,
               dateFormat: "d/m/Y H:i",
               defaultDate: new Date(),
               allowInput: true,
         }
      );

   }

   //#endregion


   //#region Datos iniciales


   function inicializarOrden() {
      const esEdicion = Boolean(estado.bebeId);

      const orden = esEdicion
         ? estado.bebe.orden
         : obtenerSiguienteOrden();

      controles.orden.value = `# ${orden}`;
   }

   function obtenerSiguienteOrden() {

      const bebes = estado.episodio.bebes || [];

      if (!bebes.length) {
         return 1;
      }

      return Math.max(
         ...bebes.map(bebe => Number(bebe.orden) || 0)
      ) + 1;
   }


   
   function inicializarPaciente() {
      const episodio = estado.episodio;

      if (!episodio) {
         return;
      }

      const paciente = episodio.paciente;

      RenderizarPacienteLaborParto.renderizar(
         controles.datosPaciente,
         paciente
      );

   }



   function llenarFormulario() {

      const bebe = estado.bebe;

      controles.selectorSexo.querySelector(
         `input[name="sexoBebeLaborParto"][value="${bebe.sexo}"]`
      ).checked = true

      controles.observacion.value =
         bebe.observacion || "";

      if (bebe.fecha_nacimiento) {
         controles.flatpickr.setDate(
               bebe.fecha_nacimiento,
               false
         );
      }
   }

   //#endregion


   //#region Validación

   function validarCampos() {

      const sexoSeleccionado = controles.selectorSexo.querySelector(
         'input[name="sexoBebeLaborParto"]:checked'
      )?.value;

      if (!sexoSeleccionado) {
         Swal.showValidationMessage(
               "Selecciona una unidad de salida."
         );
         return false;
      }

      const fechaSeleccionada = controles.flatpickr.selectedDates[0];

      const ahora = new Date();

      if (fechaSeleccionada && fechaSeleccionada > ahora) {
         Swal.showValidationMessage(
            "La fecha de nacimiento no puede ser futura"
         );

         return false;
      }

            

      const observacion =
         controles.observacion.value.trim();

      return {
         episodioId: estado.episodio.id,
         bebeId: estado.bebeId,
         sexo: sexoSeleccionado,
         fechaNacimiento: fechaSeleccionada || null,
         observacion: observacion || null,
      };
   }

   //#endregion


   //#region Obtener bebé

   async function obtenerBebe() {

      if (!estado.bebeId) {
         return;
      }

      try {
         const data = await fetchData(
            API_URLS.obtenerBebeLaborParto,
            {
               id: estado.bebeId,
            }
         );

         if (!data) {
            return;
         }

         estado.bebe = data.bebe;

      } catch (error) {
         toastr.error(
            error.message,
            "Error al obtener el movimiento"
         );

      }
      
   }

   //#endregion


   //#region Guardar bebé

   function mostrarMensajeBebe(accion) {
      const mensajes = {
         creado: {
               tipo: "success",
               mensaje: "El bebé se registró correctamente.",
               titulo: "Proceso realizado",
         },
         actualizado: {
               tipo: "success",
               mensaje: "Los datos del bebé se actualizaron correctamente.",
               titulo: "Proceso realizado",
         },
         desactivado: {
               tipo: "success",
               mensaje: "Se desactivó el registro del bebé.",
               titulo: "Proceso realizado",
         },
         sin_cambios: {
               tipo: "info",
               mensaje: "No se realizaron cambios en los datos del bebé.",
               titulo: "Sin cambios",
         },
      };

      const configuracion = mensajes[accion];

      if (!configuracion) return;

      toastr[configuracion.tipo](
         configuracion.mensaje,
         configuracion.titulo,
         { timeOut: 1500 }
      );
   }





   async function guardarBebe(datos) {

      try {
         const response = await fetch(
               API_URLS.procesarBebeLaborParto,
               {
                  method: "POST",

                  headers: {
                     "Content-Type": "application/json",
                     "X-CSRFToken": window.CSRF_TOKEN,
                  },

                  body: JSON.stringify(datos),
               }
         );

         const data = await response.json();




         if (response.status === 400) {

               const mensaje = Array.isArray(data.error)
                  ? data.error.join(" ")
                  : data.error;

               toastr.warning(
                  mensaje || "Error de validación."
               );

               return false;
         }

         if (response.status === 403) {

               toastr.warning(
                  data.error ||
                  "No tienes permisos para registrar el bebe."
               );

               return false;
         }

         if (!response.ok) {

               throw new Error(
                  data.error || "No se pudo registrar el bebe."
               );
         }


         mostrarMensajeBebe(data.accion);
         return data;


      } catch (error) {

         console.error(
               "Error al registrar el bebe de Labor y Parto:",
               error
         );

         toastr.error(
               "No se pudo registrar el bebe. Inténtalo nuevamente.",
               "Error inesperado"
         );

         return false;
      }

      
   }

   //#endregion


   //#region CSRF

   function obtenerCookie(nombre) {

      const cookies = document.cookie
         .split(";")
         .map(cookie => cookie.trim());

      const cookie = cookies.find(
         valor => valor.startsWith(`${nombre}=`)
      );

      return cookie
         ? decodeURIComponent(
               cookie.substring(nombre.length + 1)
         )
         : null;
   }

   //#endregion


   return {
      open,
   };

})();