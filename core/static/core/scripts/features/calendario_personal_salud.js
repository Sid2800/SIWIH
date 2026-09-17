"use strict";

document.addEventListener("DOMContentLoaded", () => {

   const estado = {
      idPersonal: idPersonal,
      calendario: null,
      fecha: new Date(2026,11,2),
      fechaSeleccionada: null,
      personalSalud: null,
      entries: [],
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
      AUSENCIA: "AUSENCIA"
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

   }



   function inicializarCalendario() {

      estado.calendario = TimeGrid.create("#calendario", {
         startHour: 7,
         endHour: 13,
         resolution: 5,
         interval: 60,

         locale: "es",

         view: "workweek",

         title: "TITULO DE PRUEBA ",
         
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
         estado.calendario.actualizar();

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
         estado.calendario.cambiarEntries(
            estado.entries
         );

         estado.calendario.actualizar();

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
         estado.rangoDatos = rango;

         if (Array.isArray(data.workingDays) && data.workingDays.length > 0) {
            estado.calendario.cambiarDiasLaborales(data.workingDays);
         }

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

      const mostrarLibres = controles.cupoLibre.checked;
      const mostrarProgramadas = controles.cupoProgramada.checked;
      const mostrarReprogramadas = controles.cupoReprogramada.checked;
      const mostrarAusencias = controles.cupoAusencia.checked;

      const entriesFiltradas = estado.entries.filter(
         entry => {

            const tipoMovimiento =
               entry.data.tipo_movimiento;

            return (
               (
                  tipoMovimiento === TIPOS_MOVIMIENTO.LIBRE &&
                  mostrarLibres
               ) ||
               (
                  tipoMovimiento === TIPOS_MOVIMIENTO.ASIGNACION &&
                  mostrarProgramadas
               ) ||
               (
                  tipoMovimiento === TIPOS_MOVIMIENTO.REPROGRAMACION &&
                  mostrarReprogramadas
               ) ||
               (
                  tipoMovimiento === TIPOS_MOVIMIENTO.AUSENCIA &&
                  mostrarAusencias
               )
            );

         }
      );

      estado.calendario.cambiarEntries(
         entriesFiltradas
      );

      estado.calendario.actualizar();

   }
//#endregion


   

});