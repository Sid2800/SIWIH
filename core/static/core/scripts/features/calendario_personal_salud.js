"use strict";

document.addEventListener("DOMContentLoaded", () => {

   const estado = {
      idPersonal: idPersonal,
      calendario: null,
      fecha: new Date(2026,11,2),
      fechaSeleccionada: null,
      personalSalud: null,
      entries: [],
      filtros_tipos_atencion: [],
      seleccionTiposAtencion: new Map(), // PERMANENCIA EN LOS FILTROS DE TIPO DE ATENCION
      rangoDatos: {
         inicio: null,
         fin: null,
         mes: null,
         anio: null,
      }
   };

   const controles = {
      calendario: null,
      fechaSeleccionada: null,
   };

   const TIPOS_MOVIMIENTO = Object.freeze({
      LIBRE: "LIBRE",
      ASIGNACION: "ASIGNACION",
      REPROGRAMACION: "REPROGRAMACION",
      AUSENCIA: "AUSENCIA",
      DIA_QUIRURGICO: "DIA_QUIRURGICO"
   });



   inicializar();



   async function inicializar() {

      inicializarControles();
      inicializarCalendario();
      inicializarFecha();
      await inicializarPersonalSalud();
      inicializarEventos();

      establecerValoresIniciales();

      await cargarAgenda();

   }

   function inicializarControles() {

      controles.calendario = document.getElementById("calendario");
      controles.fechaSeleccionada = document.getElementById("fechaSeleccionada");
      controles.personalSalud = document.getElementById("seleccionarPersonalSalud");

      controles.cupoLibre = document.getElementById("chk-cupo-libre");
      controles.cupoProgramada = document.getElementById("chk-cupo-programada");
      controles.cupoReprogramada = document.getElementById("chk-cupo-reprogramada");
      controles.cupoAusencia = document.getElementById("chk-cupo-ausencia");
      controles.cupoQuirurgico = document.getElementById("chk-cupo-quirurgico");

      controles.filtrosTipoAtencion = document.getElementById("filtrosTipoAtencion");
   }



   function inicializarCalendario() {

      estado.calendario = TimeGrid.create("#calendario", {
         startHour: 7,
         endHour: 13,
         resolution: 5,
         interval: 60,

         locale: "es",

         view: "month",

         title: "TITULO DE CALENDARIO ",
         
         navigation: true,

         onDateChange: function(fecha) {

            estado.fecha = fecha;

            cargarAgenda();

         },


         views: true,

         date: estado.fecha,
         useGroupColor: true,

         entries: []

      });

   }

   function inicializarFecha() {

      estado.fechaSeleccionada = flatpickr(
         controles.fechaSeleccionada,
         {
            locale: "es",
            dateFormat: "Y-m-d",
            inline: true,
         }
      );

   }

   async function inicializarPersonalSalud(){
      try {
         let data = await PersonalClinicoLoader.cargar();

         const opciones = data.map(item => ({
               value: item.id,
               label: item.nombre,
               customData: item.especialidad__nombre_especialidad,
               description: item.especialidad__nombre_especialidad
         }));

         if (controles.personalSalud.virtualSelect) {
               controles.personalSalud.virtualSelect.destroy();
         }

         // inicializar el vistual select 
         VirtualSelect.init({
               ele: '#seleccionarPersonalSalud',
               options: opciones,
               hasOptionDescription: true,
               searchPlaceholderText: 'Buscar...',
               search: true,
               placeholder: 'Seleccione',
               additionalClasses: 'custom-wrapper',
               additionalDropboxClasses: 'custom-dropbox',
         }); 
      } catch (error) {

         console.error(
            "Error al cargar el personal de salud:",
            error
         );

      }

   }

   function renderizarFiltrosTipoAtencion() {

      const contenedor = controles.filtrosTipoAtencion;
      const opciones = estado.filtros_tipos_atencion;

      if (!contenedor) return;

      // VALORES MARCADOS EN LOS FILTROS DE TIPO DE ATENCION
      contenedor.querySelectorAll(
         ".agenda-filtro-tipo-atencion__checkbox"
      ).forEach(checkbox => {

         estado.seleccionTiposAtencion.set(
            String(checkbox.value),
            checkbox.checked
         );

      });

      contenedor.replaceChildren();
      if (!Array.isArray(opciones) || opciones.length === 0) {
         const mensaje = document.createElement("span");
         mensaje.className = "agenda-filtros-tipo-atencion__vacio";
         mensaje.textContent = "No hay tipos de atención disponibles para filtrar.";

         contenedor.appendChild(mensaje);
         return;
      }

      const fragmento = document.createDocumentFragment();

      opciones.forEach(opcion => {

         const id = `chk-tipo-atencion-${opcion.value}`;
         const tipoId = String(opcion.value);

         const label = document.createElement("label");
         label.className = "agenda-filtro-tipo-atencion";
         label.htmlFor = id;

         const checkbox = document.createElement("input");
         checkbox.type = "checkbox";
         checkbox.id = id;
         checkbox.className = "agenda-filtro-tipo-atencion__checkbox";
         checkbox.value = opcion.value;
         checkbox.checked = estado.seleccionTiposAtencion.has(tipoId)
            ? estado.seleccionTiposAtencion.get(tipoId)
            : true;

         const pill = document.createElement("span");
         pill.className = "agenda-filtro-tipo-atencion__pill";
         pill.textContent = opcion.text;

         pill.style.setProperty("--tipo-atencion-color", opcion.color);
         pill.style.setProperty("--tipo-atencion-border-color", opcion.borderColor);

         label.append(checkbox, pill);
         fragmento.appendChild(label);
      });

      contenedor.appendChild(fragmento);
   }


   function inicializarEventos() {
      // LISTENER PERSONAL DE SALUD
      const select = controles.personalSalud;

      select._changeHandler = function () {
         const options = select.getSelectedOptions();

         if (!options) {
            return;
         }

         estado.idPersonal = options.value;
         estado.nombrePersonal = options.label;

         estado.calendario.cambiarTitulo(
            estado.nombrePersonal
         );
         // Invalidar datos del profesional anterior
         estado.rangoDatos.mes = null;
         estado.rangoDatos.anio = null;

         cargarAgenda();

      };

      select.addEventListener(
         "change",
         select._changeHandler
      );


      // LISTENER FLATPICKR - SELECTOR DÍA
      estado.fechaSeleccionada.config.onChange.push(
         function(selectedDates) {

            if (!selectedDates.length) {
               return;
            }

            estado.fecha = selectedDates[0];
            estado.calendario.cambiarFecha(
               estado.fecha
            );

            cargarAgenda();
         }
      );

      // LISTENERS FILTROS
      controles.cupoLibre.addEventListener(
         "change",
         aplicarFiltros
      );

      controles.cupoProgramada.addEventListener(
         "change",
         aplicarFiltros
      );

      controles.cupoReprogramada.addEventListener(
         "change",
         aplicarFiltros
      );

      controles.cupoAusencia.addEventListener(
         "change",
         aplicarFiltros
      );

      controles.cupoQuirurgico.addEventListener(
         "change",
         aplicarFiltros
      );

      // LISTENER FILTROS POR TIPO DE ATENCIÓN
      controles.filtrosTipoAtencion.addEventListener(
         "change",
         function(event) {
            if (!event.target.matches(".agenda-filtro-tipo-atencion__checkbox")) {
                  return;
            }
            aplicarFiltros();

         }
      );


   }


   function establecerValoresIniciales() {

      // DEFINIR EL PERSONAL DE SALUD 
      if (estado.idPersonal) {
         const slect = document.querySelector('#seleccionarPersonalSalud')
         slect.setValue(
            estado.idPersonal
         );

      }

      //DEFINIR LA FECHA EN EL CALENDARIO SLECTOR 
      estado.fechaSeleccionada.setDate(
         estado.fecha
      );

   }


//#region  funcione auxiliares 

   function obtenerRangoDatos(fecha) {

      const mes = fecha.getMonth();
      const anio = fecha.getFullYear();

      const inicioMes = new Date(
         fecha.getFullYear(),
         fecha.getMonth(),
         1
      );

      const inicio = obtenerInicioSemana(inicioMes);

      const finMes = new Date(
         fecha.getFullYear(),
         fecha.getMonth() + 1,
         0
      );

      const fin = obtenerInicioSemana(finMes);

      fin.setDate(fin.getDate() + 6);

      return {
         inicio,
         fin,
         mes,
         anio,
      };

   }

   function obtenerInicioSemana(fecha) {

      const inicio = new Date(fecha);
      const dia = inicio.getDay();

      const diferencia = dia === 0
         ? 6
         : dia - 1;

      inicio.setDate(
         inicio.getDate() - diferencia
      );

      return inicio;
   }

   function requiereCargarAgenda(fecha) {

      if (
         estado.rangoDatos.mes === null ||
         estado.rangoDatos.anio === null
      ) {
         return true;
      }

      return (
         fecha.getMonth() !== estado.rangoDatos.mes ||
         fecha.getFullYear() !== estado.rangoDatos.anio
      );

   }

   async function cargarAgenda() {

      if (!requiereCargarAgenda(estado.fecha)) {
         return;
      }

      if (!estado.idPersonal){
         return;
      }

      try {

         const rango = obtenerRangoDatos(
            estado.fecha
         );

         const criterios = {
            medico: estado.idPersonal,
            fecha_inicio: getFechaLocalYYYYMMDD(
               rango.inicio
            ),
            fecha_fin: getFechaLocalYYYYMMDD(
               rango.fin
            ),
         };

         const data = await AgendaMedicaHelper.cargar(
            criterios
         );


         estado.entries = data.entries;
         estado.filtros_tipos_atencion = data.opciones_tipos_atencion;
         estado.rangoDatos = rango;

         if (Array.isArray(data.workingDays) && data.workingDays.length > 0) {
            estado.calendario.cambiarDiasLaborales(data.workingDays);
         }

         /// actualizar los filtros de tipo de atención en la interfaz
         renderizarFiltrosTipoAtencion();

         // Aplicar los filtros activos a las nuevas entries antes de mostrarlas.
         // Esta función actualiza las entries y renderiza el calendario.
         aplicarFiltros();



      } catch (error) {

         console.error(
            "Error al cargar la agenda médica:",
            error
         );

         toastr.error(
            "No se pudo cargar la agenda médica."
         );
      }

   }

   function aplicarFiltros() {

      // FILTROS POR ESTADO
      const mostrarLibres = controles.cupoLibre.checked;
      const mostrarProgramadas = controles.cupoProgramada.checked;
      const mostrarReprogramadas = controles.cupoReprogramada.checked;
      const mostrarAusencias = controles.cupoAusencia.checked;
      const mostrarQuirurgicos = controles.cupoQuirurgico.checked;


      // FILTROS POR TIPO DE ATENCIÓN
      const checkboxes = controles.filtrosTipoAtencion.querySelectorAll(
         ".agenda-filtro-tipo-atencion__checkbox"
      );

      const tiposAtencionSeleccionados = Array.from(checkboxes)
         .filter(checkbox => checkbox.checked)
         .map(checkbox => checkbox.value);


      // PRIMER FILTRO: ESTADO
      const entriesFiltradasEstado = estado.entries.filter(entry => {

         const tipoMovimiento = entry.data.tipo_movimiento;

         return (
               (tipoMovimiento === TIPOS_MOVIMIENTO.LIBRE && mostrarLibres) ||
               (tipoMovimiento === TIPOS_MOVIMIENTO.ASIGNACION && mostrarProgramadas) ||
               (tipoMovimiento === TIPOS_MOVIMIENTO.REPROGRAMACION && mostrarReprogramadas) ||
               (tipoMovimiento === TIPOS_MOVIMIENTO.AUSENCIA && mostrarAusencias) ||
               (tipoMovimiento === TIPOS_MOVIMIENTO.DIA_QUIRURGICO && mostrarQuirurgicos)
         );

      });


      // SEGUNDO FILTRO: TIPO DE ATENCIÓN
      const entriesFiltradas = entriesFiltradasEstado.filter(entry => {

         const tipoAtencionId = entry.data.tipo_atencion_id;

         // AUSENCIAS Y DÍAS QUIRÚRGICOS NO TIENEN TIPO DE ATENCIÓN
         if (tipoAtencionId === null) {
               return true;
         }

         // SI NO HAY FILTROS DISPONIBLES, CONSERVAR LOS CUPOS
         if (checkboxes.length === 0) {
               return true;
         }

         return tiposAtencionSeleccionados.includes(
               String(tipoAtencionId)
         );

      });


      // ACTUALIZAR CALENDARIO
      estado.calendario.cambiarEntries(entriesFiltradas);
      estado.calendario.actualizar();

   }
//#endregion


   

});