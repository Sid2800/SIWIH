

const TimeGrid = ( function () {

   "use strict";

    //#region Constantes

   const DEFAULT_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

   // FROMAS DE VISUALIZACION
   const VIEWS = Object.freeze([
      "day",
      "week",
      "workweek",
      "month"
   ]);


   const DEFAULT_OPTIONS = {

      // Title
      title: null,

      // Vista
      view: "day",

      // Fecha inicial
      date: new Date(),

      // Idioma
      locale: "es",

      // Zona horaria
      timezone: DEFAULT_TIMEZONE,

      // Horario laboral
      startHour: 7,
      endHour: 17,

      // Resolución interna
      resolution: 5,

      // Intervalo visible
      interval: 30,

      // Días laborales
      workingDays: [1, 2, 3, 4, 5],

      // Entradas
      entries: [],

      // Navigation
      navigation: true,

      // Modo de vision
      views: true,

   };


   const Validadores = {

      numero(nombre, valor) {
         if (typeof valor !== "number") {
               throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser un número.`
               );
         }
      },

      entero(nombre, valor) {
         if (!Number.isInteger(valor)) {
               throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser un número entero.`
               );
         }

      },

      cadena(nombre, valor) {
         if (typeof valor !== "string") {
               throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser una cadena.`
               );
         }

      },

      booleano(nombre, valor) {
         if (typeof valor !== "boolean") {
            throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser un valor booleano.`
            );
         }
      },

      array(nombre, valor) {
         if (!Array.isArray(valor)) {
               throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser un arreglo.`
               );
         }

      },

      fecha(nombre, valor) {
         if (!(valor instanceof Date)) {
               throw new TypeError(
                  `TimeGrid: '${nombre}' debe ser una instancia de Date.`
               );
         }

         if (isNaN(valor.getTime())) {
               throw new RangeError(
                  `TimeGrid: '${nombre}' no es una fecha válida.`
               );
         }

      },

      rango(nombre, valor, minimo, maximo) {
         if (valor < minimo || valor > maximo) {
               throw new RangeError(
                  `TimeGrid: '${nombre}' debe estar entre ${minimo} y ${maximo}.`
               );
         }

      },

      multiplo(nombre, valor, multiplo) {
         if (valor % multiplo !== 0) {
               throw new RangeError(
                  `TimeGrid: '${nombre}' debe ser un múltiplo de ${multiplo}.`
               );
         }
      },

      locale(nombre, valor) {
         this.cadena(nombre, valor);
         if (
               Intl.DateTimeFormat
                  .supportedLocalesOf([valor])
                  .length === 0
         ) {
               throw new RangeError(
                  `TimeGrid: '${valor}' no es un locale válido.`
               );
         }
      },

      timezone(nombre, valor) {
         this.cadena(nombre, valor);
         try {

               Intl.DateTimeFormat(undefined, {
                  timeZone: valor
               });
         } catch {

               throw new RangeError(
                  `TimeGrid: '${valor}' no es una zona horaria válida.`
               );
         }
      }

   };
    //#endregion


    //#region Estado

   let estado = {};

   let opciones = {};

   let controles = {};

    //#endregion


     //#region Inicialización

   function create(container, config = {}) {



      validarConfiguracion(config);

      opciones = {
         ...DEFAULT_OPTIONS,
         ...normalizarOpciones(config)
      };


      controles = {
         container: resolverContenedor(container)
      };

      estado = {
         date: opciones.date ?? new Date(),
         view: opciones.view,
         entries: []
      };

      render();
      inicializarListeners();

   
      return api;
   }

   //#endregion



   //#region  VALIDACION DE  ARGUMETOS


   function normalizarOpciones(config) {

      const opcionesValidas = {};

      for (const key in config) {

         if (key in DEFAULT_OPTIONS) {
               opcionesValidas[key] = config[key];
         }
         else {
            throw new Error(
               `TimeGrid: la opción '${key}' no existe. ` +
               `Las opciones válidas son: ${Object.keys(DEFAULT_OPTIONS).join(", ")}.`
            );
         }
      }
      return opcionesValidas;

   }



   function validarConfiguracion(opciones) {

      // title
      if ("title" in opciones) {
         Validadores.cadena("title", opciones.title);
      }

      // View
      if ("view" in opciones && !VIEWS.includes(opciones.view)) {
         throw new TypeError(
               `TimeGrid: 'view' debe ser uno de los siguientes valores: ${VIEWS.join(", ")}.`
         );
      }

      // Fecha
      if ("date" in opciones) {
         Validadores.fecha("date", opciones.date);
      }

      // Locale
      if ("locale" in opciones) {
         Validadores.locale("locale", opciones.locale);
      }

      // Timezone
      if ("timezone" in opciones) {
         Validadores.timezone("timezone", opciones.timezone);
      }

      // Ambas llaves deben existir
      if ("startHour" in opciones && !("endHour" in opciones)) {
         throw new Error(
               "TimeGrid: si define 'startHour', también debe definir 'endHour'."
         );
      }

      if ("endHour" in opciones && !("startHour" in opciones)) {
         throw new Error(
               "TimeGrid: si define 'endHour', también debe definir 'startHour'."
         );
      }

      // Hora de inicio
      if ("startHour" in opciones) {
         Validadores.numero("startHour", opciones.startHour);
         Validadores.entero("startHour", opciones.startHour);
         Validadores.rango("startHour", opciones.startHour, 0, 23);
      }

      // Hora de fin
      if ("endHour" in opciones) {
         Validadores.numero("endHour", opciones.endHour);
         Validadores.entero("endHour", opciones.endHour);
         Validadores.rango("endHour", opciones.endHour, 0, 23);
      }

      // La hora final debe ser superior a la inicial
      if (
         "startHour" in opciones &&
         "endHour" in opciones &&
         opciones.startHour >= opciones.endHour
      ) {
         throw new RangeError(
               "TimeGrid: 'startHour' debe ser menor que 'endHour'."
         );
      }

      // Resolution
      if ("resolution" in opciones) {
         Validadores.numero("resolution", opciones.resolution);
         Validadores.entero("resolution", opciones.resolution);
         Validadores.rango("resolution", opciones.resolution, 5, 60);
         Validadores.multiplo("resolution", opciones.resolution, 5);
      }

      // Interval
      if ("interval" in opciones) {
         Validadores.numero("interval", opciones.interval);
         Validadores.entero("interval", opciones.interval);
         Validadores.rango("interval", opciones.interval, 30, 180);
         Validadores.multiplo("interval", opciones.interval, 30);
      }

      // El intervalo debe coincidir con una línea de la cuadrícula
      if (
         "resolution" in opciones &&
         "interval" in opciones &&
         opciones.interval % opciones.resolution !== 0
      ) {
         throw new RangeError(
               "TimeGrid: 'interval' debe ser múltiplo de 'resolution'."
         );
      }

      // Días laborales
      if ("workingDays" in opciones) {
         Validadores.array("workingDays", opciones.workingDays);
         if (opciones.workingDays.length === 0) {
               throw new RangeError(
                  "TimeGrid: 'workingDays' debe contener al menos un día."
               );
         }

         const dias = new Set();

         for (const dia of opciones.workingDays) {

               Validadores.numero("workingDays", dia);
               Validadores.entero("workingDays", dia);
               Validadores.rango("workingDays", dia, 1, 7);

               if (dias.has(dia)) {
                  throw new RangeError(
                     `TimeGrid: el día '${dia}' está repetido en 'workingDays'.`
                  );
               }

               dias.add(dia);
         }
      }

      // navigation
      if ("navigation" in opciones) {
         Validadores.booleano("navigation", opciones.navigation);
      }

      if ("views" in opciones) {
         Validadores.booleano("views", opciones.navigation);
      }

   }
   //#endregion


   //#region Listeners 

   function inicializarListeners() {

      function inicializarListenersHeader() {

         Object.values(controles.views).forEach(input => {

               input.addEventListener("change", function () {

                  console.log(this.value);
                  estado.view = this.value;
                  cambiarVista()

               });

         });

      }

      if (opciones.views) {
         inicializarListenersHeader();
      }

   }


   //#region 



    //#region Render


   function cambiarVista(){
      render();
      inicializarListeners();
   }



   function render() {


      controles.container.innerHTML = `
         <div class="tg-container">

            <div class="tg-header"></div>

            <div class="tg-body">
               <div class="tg-grid">
               </div>
               
            </div>

         </div>
      `;

      renderHeader();
      
      renderGrid();

   }


   function renderHeader() {

      function renderTitle() {
         const rango = obtenerRangoMostrado();
         return `
               <div class="tg-title">

                  ${
                     opciones.title
                           ? `
                              <div class="tg-title-title">
                                 ${opciones.title}
                              </div>
                           `
                           : ""
                  }
                  <div class="tg-title-range">
                     ${rango}
                  </div>
               </div>
         `;
      }

      function renderNavigation() {
         return `
            <div class="tg-navigation">

               <button
                  type="button"
                  class="tg-button tg-button-navigation tg-button-previous"
                  aria-label="Anterior">
                  ${renderIcon("previous")}
               </button>

               <button
                  type="button"
                  class="tg-button tg-button-navigation tg-button-today">
                  <span>Hoy</span>

               </button>

               <button
                  type="button"
                  class="tg-button tg-button-navigation tg-button-next"
                  aria-label="Siguiente">
                  ${renderIcon("next")}
               </button>

            </div>
         `;
      }

      function renderViews() {

         return `
            <div class="tg-views">

               <label class="tg-view-option">

                  <input
                     type="radio"
                     name="tg-view"
                     value="day"
                     class="tg-view-input">

                  <div class="tg-view-content">
                     ${renderIcon("day")}
                     <span>Día</span>
                  </div>

               </label>

               <label class="tg-view-option">

                  <input
                     type="radio"
                     name="tg-view"
                     value="week"
                     class="tg-view-input">

                  <div class="tg-view-content">
                     ${renderIcon("week")}
                     <span>Semana</span>
                  </div>

               </label>

               <label class="tg-view-option">

                  <input
                     type="radio"
                     name="tg-view"
                     value="workweek"
                     class="tg-view-input">

                  <div class="tg-view-content">
                     ${renderIcon("workweek")}
                     <span>Laboral</span>
                  </div>

               </label>

               <label class="tg-view-option">

                  <input
                     type="radio"
                     name="tg-view"
                     value="month"
                     class="tg-view-input">

                  <div class="tg-view-content">
                     ${renderIcon("month")}
                     <span>Mes</span>
                  </div>

               </label>

            </div>
         `;

      }

      const header = controles.container.querySelector(".tg-header");

      header.innerHTML = `
         <div class="tg-header-content">
               <div class="tg-header-left">
                  ${renderTitle()}
               </div>

               <div class="tg-header-center">
                  ${opciones.navigation ? renderNavigation() : ""}
               </div>

               <div class="tg-header-right">
                  ${opciones.views ? renderViews() : ""}
               </div>
         </div>
      `;


      // AGREGAR  LA REFERNECIAS DE KLOS ONCORTLE RECIEN AGREGADOS SI APLICA
      if (opciones.views) {

         controles.views = {};
         header.querySelectorAll(".tg-view-input").forEach(input => {
            controles.views[input.value] = input;
         });

         controles.views[estado.view].checked = true;
      }

   }


   function renderGrid() {

      const grid = controles.container.querySelector(".tg-grid");

      function obtenerConfiguracionGrid() {

         const totalFilas =
            ((opciones.endHour - opciones.startHour) * 60) /
            opciones.resolution;

         const filasPorIntervalo =
            opciones.interval / opciones.resolution;

         return {
            totalFilas,
            filasPorIntervalo,
            spanFilas: filasPorIntervalo
         };

      }

      function obtenerGridStyle(totalColumnas) {

         return `
            --tg-interval-rows: ${configuracion.filasPorIntervalo};

            display: grid;
            grid-template-columns:
               var(--tg-time-width)
               repeat(${totalColumnas}, 1fr);

            grid-template-rows:
               var(--tg-header-height)
               repeat(${configuracion.totalFilas}, var(--tg-row-height));
         `;

      }

      function obtenerHoras() {

         const horas = [];

         for (
            let minutos = opciones.startHour * 60, fila = 2;
            minutos < opciones.endHour * 60;
            minutos += opciones.interval, fila += configuracion.spanFilas
         ) {

            const hora = Math.floor(minutos / 60);
            const minuto = minutos % 60;

            horas.push({
               hora,
               minuto,
               descripcion: `${String(hora).padStart(2, "0")}:${String(minuto).padStart(2, "0")}`,
               gridRowStart: fila,
               gridRowEnd: fila + configuracion.spanFilas
            });

         }

         return horas;

      }

      function renderHoras(horas) {

         return horas.map(hora => `
            <div
               class="tg-week-time"
               style="
                  grid-column: 1;
                  grid-row: ${hora.gridRowStart} / ${hora.gridRowEnd};
               ">
               ${hora.descripcion}
            </div>
         `).join("");

      }

      const configuracion = obtenerConfiguracionGrid();
      const horas = obtenerHoras();

      function renderWeekGrid() {

         const dias = obtenerDiasSemana();

         return `
            <div
               class="tg-week tg-week-grid"
               style="${obtenerGridStyle(dias.length)}">

               <div class="tg-week-time-header"></div>

               ${dias.map(dia => `
                  <div class="tg-week-day-header">
                     <span class="tg-week-day-header-number">
                        ${dia.numero}
                     </span>
                     <span>
                        ${dia.nombre}
                     </span>
                  </div>
               `).join("")}

               ${renderHoras(horas)}

            </div>
         `;

      }

      function renderDayGrid() {

         const dia = obtenerDiaSeleccionado();

         return `
            <div
               class="tg-week tg-day-grid"
               style="${obtenerGridStyle(1)}">

               <div class="tg-week-time-header"></div>

               <div class="tg-week-day-header">
                  <span class="tg-week-day-header-number">
                     ${dia.numero}
                  </span>

                  <span>
                     ${dia.nombre} · ${dia.mes}
                  </span>
               </div>

               ${renderHoras(horas)}

            </div>
         `;

      }

      function renderWorkWeekGrid() {

         const dias = obtenerDiasSemana(true);

         return `
            <div
               class="tg-week tg-workweek-grid"
               style="${obtenerGridStyle(dias.length)}">

               <div class="tg-week-time-header"></div>

               ${dias.map(dia => `
                  <div class="tg-week-day-header">
                     <span class="tg-week-day-header-number">
                        ${dia.numero}
                     </span>
                     <span>
                        ${dia.nombre}
                     </span>
                  </div>
               `).join("")}

               ${renderHoras(horas)}

            </div>
         `;
      }

      function renderMonthGrid() {
         return `Month`;
      }

      switch (estado.view) {

         case "day":
            grid.innerHTML = renderDayGrid();
            break;

         case "week":
            grid.innerHTML = renderWeekGrid();
            break;

         case "workweek":
            grid.innerHTML = renderWorkWeekGrid();
            break;

         case "month":
            grid.innerHTML = renderMonthGrid();
            break;

      }

   }

   //#endregion

   //#region Utilidades


   function formatearMes(fecha) {

      const texto = fecha.toLocaleDateString(opciones.locale, {
         month: "long",
         year: "numeric",
         timeZone: opciones.timezone
      });
      return texto.charAt(0).toUpperCase() + texto.slice(1);
   }


   function formatearRangoSemana(fecha, dias) {

      const inicio = obtenerInicioSemana(fecha);
      const fin = new Date(inicio);

      fin.setDate(fin.getDate() + dias);

      const mismoMes = inicio.getMonth() === fin.getMonth();

      if (mismoMes) {

         const mes = fin.toLocaleDateString(opciones.locale, {
               month: "long",
               timeZone: opciones.timezone
         });

         return `${inicio.getDate()} - ${fin.getDate()} - ${mes} - ${fin.getFullYear()}`;

      }

      const inicioTexto = inicio.toLocaleDateString(opciones.locale, {
         day: "numeric",
         month: "long",
         timeZone: opciones.timezone
      });

      const finTexto = fin.toLocaleDateString(opciones.locale, {
         day: "numeric",
         month: "long",
         year: "numeric",
         timeZone: opciones.timezone
      });

      return `${inicioTexto} - ${finTexto}`;

   }


   function obtenerInicioSemana(fecha) {
      const inicio = new Date(fecha);
      const dia = inicio.getDay(); // 0=Domingo, 1=Lunes...
      const diferencia = dia === 0 ? -6 : 1 - dia;
      inicio.setDate(inicio.getDate() + diferencia);
      return inicio;

   }


   function formatearDia(fecha) {
      const texto = fecha.toLocaleDateString(opciones.locale, {
         weekday: "long",
         day: "numeric",
         month: "long",
         year: "numeric",
         timeZone: opciones.timezone
      });

      return texto.charAt(0).toUpperCase() + texto.slice(1);

   }


   function obtenerRangoMostrado() {

      switch (estado.view) {

         case "day":
               return formatearDia(estado.date);
         case "week":
               return formatearRangoSemana(estado.date, 6);
         case "workweek":
               return formatearRangoSemana(estado.date, 4);
         case "month":
               return formatearMes(estado.date);
      }
   }


   function resolverContenedor(container) {

      if (typeof container === "string") {
         container = document.querySelector(container);
      }

      if (!(container instanceof HTMLElement)) {
         throw new Error("TimeGrid: contenedor no válido.");
      }

      return container;
   }

   // obtener valores de grid


   function obtenerDiasSemana(soloLaborables = false) {
      const dias = [];

      const fecha = new Date(estado.date);

      const diaSemana = fecha.getDay();

      const diferencia = diaSemana === 0 ? -6 : 1 - diaSemana;

      fecha.setDate(fecha.getDate() + diferencia);

      const formatoLargo = new Intl.DateTimeFormat(opciones.locale, {
         weekday: "long"
      });

      const formatoCorto = new Intl.DateTimeFormat(opciones.locale, {
         weekday: "short"
      });

      for(let i = 0; i < 7; i++){

         const dia = new Date(fecha);

         dias.push({
            diaSemana: dia.getDay() === 0 ? 7 : dia.getDay(),
            nombre: capitalizar(formatoLargo.format(dia)),
            nombreCorto: capitalizar(formatoCorto.format(dia)),
            numero: dia.getDate(),
            fecha: dia,
            mes: dia.getMonth() + 1,
            anio: dia.getFullYear(),
            esHoy: esMismaFecha(dia, new Date()),
            esSeleccionado: esMismaFecha(dia, estado.date),
            esMismoMes: dia.getMonth() === estado.date.getMonth()
         });

         fecha.setDate(fecha.getDate() + 1);
         
      }

      if (soloLaborables) {
         return dias.filter(dia =>
               opciones.workingDays.includes(dia.diaSemana)
            );
         }


      return dias

   }


   function obtenerDiaSeleccionado() {

      const fecha = new Date(estado.date);

      return {
         nombre: capitalizar(
               new Intl.DateTimeFormat(opciones.locale, {
                  weekday: "long"
               }).format(fecha)
         ),

         nombreCorto: capitalizar(
               new Intl.DateTimeFormat(opciones.locale, {
                  weekday: "short"
               }).format(fecha)
         ),

         numero: fecha.getDate(),

         mes: capitalizar(
               new Intl.DateTimeFormat(opciones.locale, {
                  month: "long"
               }).format(fecha)
         ),

         fecha,

         esHoy: esMismaFecha(fecha, new Date())
      };

   }

   function obtenerFilas() {

      const totalHoras = opciones.endHour - opciones.startHour;

      return {
         total: (totalHoras * 60) / opciones.resolution
      };

   }


   function esMismaFecha(fecha1, fecha2){

      return (
         fecha1.getFullYear() === fecha2.getFullYear() &&
         fecha1.getMonth() === fecha2.getMonth() &&
         fecha1.getDate() === fecha2.getDate()
      );

   }


   function capitalizar(texto){

      return texto.charAt(0).toUpperCase() + texto.slice(1);

   }

    //#endregion

   const api = {

      render,

      destroy() {
         estado.container.innerHTML = "";
      }

   };

   return {

      create

   };


})();