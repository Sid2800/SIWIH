

const TimeGrid = ( function () {

   "use strict";

//#region Constantes

   const DEFAULT_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

   const DESCRIPCION_MAXIMA = 100;
   const TITLE_MAXIMA = 15;

   const MONTH_ROWS_PER_WEEK = 6;

   // FROMAS DE VISUALIZACION
   const VIEWS = Object.freeze([
      "day",
      "week",
      "workweek",
      "month"
   ]);

   const ENTRY_ICONS = Object.freeze([
      "circle",
      "square",
      "diamond",
      "triangle",
      "star"
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
      onDateChange: null,

      // Modo de vision
      views: true,

      // Group color
      useGroupColor: false,

   };

   const DEFAULT_ENTRY_OPTIONS = {

      subtitle: null,
      description: null,
      agrupation: null,

      color: null,
      textColor: null,
      borderColor: null,
      iconColor: null,


      icon: null,
      className: null,

      editable: true,
      visible: true,
      disabled: false,
      selected: false,


      data: {}
   };


//#endregion


//#region Estado

   let estado = {};

   let opciones = {};

   let controles = {};

//#endregion


//#region Inicialización

   function create(container, config = {}) {

      opciones = {
         ...DEFAULT_OPTIONS,
         ...normalizarOpciones(config)
      };

      validarConfiguracion(opciones);


      controles = {
         container: resolverContenedor(container)
      };

      estado = {
         date: new Date(opciones.date ?? new Date()),
         view: opciones.view,
         entries: []
      };

      render();
      inicializarListeners();

   
      return api;
   }

//#endregion


//#region  Validaciones
   
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
      },


      color(nombre, valor) {

         if (valor === null) {
            return;
         }

         this.cadena(nombre, valor);

         const hexadecimal =
            /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

         const rgb =
            /^rgba?\(\s*(?:\d{1,3}\s*,\s*){2}\d{1,3}(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)$/;

         if (!hexadecimal.test(valor) && !rgb.test(valor)) {
            throw new TypeError(
               `TimeGrid: '${nombre}' debe ser un color hexadecimal, RGB o RGBA válido.`
            );
         }

      }

   };

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

   function normalizarFechaEntry(nombre, valor) {

      if (valor instanceof Date) {
         Validadores.fecha(nombre, valor);
         return new Date(valor);
      }

      if (typeof valor === "string") {

         const match = valor.match(
            /^\d{4}-\d{2}-\d{2}$/
         );

         if (match) {

            const [anio, mes, dia] = valor
               .split("-")
               .map(Number);

            const fecha = new Date(
               anio,
               mes - 1,
               dia
            );

            Validadores.fecha(nombre, fecha);

            return fecha;

         }

         const fecha = new Date(valor);

         if (isNaN(fecha.getTime())) {

            throw new RangeError(
               `TimeGrid: '${nombre}' no es una fecha válida.`
            );

         }

         return fecha;

      }

      throw new TypeError(
         `TimeGrid: '${nombre}' debe ser una instancia de Date o una cadena de fecha válida.`
      );
   }



   function normalizarFechaSinHora(nombre, valor, inicio = true) {

      Validadores.cadena(
         nombre,
         valor
      );

      const partes = valor.split("-");

      if (
         partes.length !== 3 ||
         partes.some(parte => !/^\d+$/.test(parte))
      ) {
         throw new TypeError(
            `TimeGrid: '${nombre}' debe usar el formato YYYY-MM-DD.`
         );
      }

      const [anio, mes, dia] = partes.map(Number);

      const fecha = new Date(
         anio,
         mes - 1,
         dia
      );

      Validadores.fecha(
         nombre,
         fecha
      );

      if (!inicio) {
         fecha.setDate(
            fecha.getDate() + 1
         );
      }

      return fecha;
   }


   function validarView(view) {
      if (!VIEWS.includes(view)) {
         throw new TypeError(
            `TimeGrid: 'view' debe ser uno de los siguientes valores: ${VIEWS.join(", ")}.`
         );
      }

   }


   function validarHoras(opciones) {

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

      if ("startHour" in opciones) {
         Validadores.numero("startHour", opciones.startHour);
         Validadores.entero("startHour", opciones.startHour);
         Validadores.rango("startHour", opciones.startHour, 0, 23);
      }

      if ("endHour" in opciones) {
         Validadores.numero("endHour", opciones.endHour);
         Validadores.entero("endHour", opciones.endHour);
         Validadores.rango("endHour", opciones.endHour, 0, 23);
      }

      if (
         "startHour" in opciones &&
         "endHour" in opciones &&
         opciones.startHour >= opciones.endHour
      ) {
         throw new RangeError(
            "TimeGrid: 'startHour' debe ser menor que 'endHour'."
         );
      }

   }


   function validarResolution(resolution) {
      Validadores.numero("resolution", resolution);
      Validadores.entero("resolution", resolution);
      Validadores.rango("resolution", resolution, 5, 15);
      Validadores.multiplo("resolution", resolution, 5);

   }


   function validarInterval(interval) {
      Validadores.numero("interval", interval);
      Validadores.entero("interval", interval);
      Validadores.rango("interval", interval, 30, 120);
      Validadores.multiplo("interval", interval, 5);

   }


   function validarRelacionIntervaloResolution(opciones) {
      if (
         "resolution" in opciones &&
         "interval" in opciones &&
         opciones.interval % opciones.resolution !== 0
      ) {
         throw new RangeError(
            "TimeGrid: 'interval' debe ser múltiplo de 'resolution'."
         );
      }

   }


   function validarWorkingDays(workingDays) {
      Validadores.array("workingDays", workingDays);

      if (workingDays.length === 0) {
         throw new RangeError(
            "TimeGrid: 'workingDays' debe contener al menos un día."
         );
      }

      const dias = new Set();
      for (const dia of workingDays) {

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


   function validarNavigation(navigation) {
      Validadores.booleano("navigation", navigation);

   }


   function validarViews(views) {
      Validadores.booleano("views", views);

   }

   function validarEntry(entry) {
      if (!entry || typeof entry !== "object") {
         throw new TypeError(
            "TimeGrid: 'entry' debe ser un objeto."
         );
      }


      // ID
      if (!("id" in entry)) {
         throw new Error(
            "TimeGrid: 'entry.id' es obligatorio."
         );
      }

      Validadores.numero("entry.id", entry.id);
      Validadores.entero("entry.id", entry.id);

      // TITLE
      if (!("title" in entry)) {
         throw new Error(
            "TimeGrid: 'entry.title' es obligatorio."
         );
      }

      Validadores.cadena("entry.title", entry.title);


      if (entry.title.length < 5) {
         throw new RangeError(
            "TimeGrid: 'entry.title' debe contener al menos 5 caracteres."
         );
      }

      // AGRUPACION
      if ("agrupation" in entry) {
         Validadores.cadena("entry.agrupation", entry.agrupation);
      }


      // START
      if (!("start" in entry)) {
         throw new Error(
            "TimeGrid: 'entry.start' es obligatorio."
         );
      }

      if (entry.start === null || entry.start === "") {
         throw new Error(
            "TimeGrid: 'entry.start' no puede estar vacío."
         );
      }

      const tieneHoraStart = tieneHora(entry.start);

      // END
      if (!("end" in entry)) {
         throw new Error(
            "TimeGrid: 'entry.end' es obligatorio."
         );
      }

      if (entry.end === null || entry.end === "") {
         throw new Error(
            "TimeGrid: 'entry.end' no puede estar vacío."
         );
      }

      const tieneHoraEnd = tieneHora(entry.end);


      // Ambos deben usar el mismo formato
      if (tieneHoraStart !== tieneHoraEnd) {
         throw new TypeError(
            "TimeGrid: 'entry.start' y 'entry.end' deben usar el mismo formato de fecha."
         );
      }


      // Determinar si la Entry trabaja con hora
      entry.tieneHora = tieneHoraStart;




      // Normalizar fechas
            
      if (entry.tieneHora) {

         entry.start = normalizarFechaEntry(
            "entry.start",
            entry.start
         );

         entry.end = normalizarFechaEntry(
            "entry.end",
            entry.end
         );

         entry.multidia =
            entry.start.toDateString() !== entry.end.toDateString();

      }
      else {

         const fechaInicio = normalizarFechaSinHora(
            "entry.start",
            entry.start
         );

         const fechaFin = normalizarFechaSinHora(
            "entry.end",
            entry.end
         );

         entry.multidia =
            fechaInicio.toDateString() !==
            fechaFin.toDateString();

         entry.start = fechaInicio;

         entry.end = normalizarFechaSinHora(
            "entry.end",
            entry.end,
            false
         );

      }

      // El final debe ser posterior al inicio
      if (entry.end <= entry.start) {
         throw new RangeError(
            "TimeGrid: 'entry.end' debe ser posterior a 'entry.start'."
         );
      }




      // DURACIÓN MÍNIMA

      const duracionMinutos =
         (entry.end - entry.start) / 60000;
      const duracionMinima = opciones.resolution * 2;

      if (duracionMinutos < duracionMinima) {
         throw new RangeError(
            `TimeGrid: 'entry' debe tener una duración mínima de ${duracionMinima} minutos.`
         );
      }

      const minutosInicio =
         (entry.start.getHours() * 60) +
         entry.start.getMinutes() -
         (opciones.startHour * 60);

      if (minutosInicio % opciones.resolution !== 0) {
         throw new RangeError(
            `TimeGrid: 'entry.start' debe ajustarse a la resolución de ${opciones.resolution} minutos.`
         );
      }

      const minutosFin =
         (entry.end.getHours() * 60) +
         entry.end.getMinutes() -
         (opciones.startHour * 60);

      if (minutosFin % opciones.resolution !== 0) {
         throw new RangeError(
            `TimeGrid: 'entry.end' ${entry.id} //// ${entry.start.getHours()} ${entry.end.getMinutes()} //// debe ajustarse a la resolución de ${opciones.resolution} minutos.`
         );
      }


      // validar el color

      if ("color" in entry) {
         Validadores.color("entry.color", entry.color);
      }

      if ("textColor" in entry) {
         Validadores.color("entry.textColor", entry.textColor);
      }

      if ("borderColor" in entry) {
         Validadores.color("entry.borderColor", entry.borderColor);
      }

      if ("iconColor" in entry) {
         Validadores.color("entry.iconColor", entry.iconColor);
      }

      if ("subtitle" in entry && entry.subtitle !== null) {
         Validadores.cadena("entry.subtitle", entry.subtitle);
      }

      // DESCRIPTION
      if ("description" in entry && entry.description !== null) {
         Validadores.cadena("entry.description", entry.description);
      }

      // ICON
      if ("icon" in entry && entry.icon !== null) {
         Validadores.cadena("entry.icon", entry.icon);

         if (!ENTRY_ICONS.includes(entry.icon)) {
            throw new RangeError(
               `TimeGrid: 'icon' debe ser uno de los siguientes valores: ${ENTRY_ICONS.join(", ")}.`
            );
         }
      }

   

      // CLASS NAME
      if ("className" in entry && entry.className !== null) {
         Validadores.cadena("entry.className", entry.className);
      }

      // EDITABLE
      if ("editable" in entry) {
         Validadores.booleano("entry.editable", entry.editable);
      }

      // VISIBLE
      if ("visible" in entry) {
         Validadores.booleano("entry.visible", entry.visible);
      }

      // DISABLED
      if ("disabled" in entry) {
         Validadores.booleano("entry.disabled", entry.disabled);
      }

      // SELECTED
      if ("selected" in entry) {
         Validadores.booleano("entry.selected", entry.selected);
      }

      // DATA
      if ("data" in entry) {
         if (
            entry.data === null ||
            typeof entry.data !== "object" ||
            Array.isArray(entry.data)
         ) {
            throw new TypeError(
               "TimeGrid: 'entry.data' debe ser un objeto."
            );
         }
      }


   }

   function validarTraslapes(entries) {

      for (let i = 0; i < entries.length; i++) {
         for (let j = i + 1; j < entries.length; j++) {
            const entryA = entries[i];
            const entryB = entries[j];

            console.table(entryB)

            if (
               entryA.start < entryB.end &&
               entryA.end > entryB.start
            ) {
               throw new RangeError(
                  `TimeGrid: las entries '${entryA.id} ${entryA.title}'y '${entryB.id} ${entryB.title}' se traslapan.`
               );
            }
         }
      }
   }

   function validarEntries(entries) {

      Validadores.array("entries", entries);
      for (const entry of entries) {
         validarEntry(entry);
      }

      validarTraslapes(entries);

   }


   function normalizarTooltipEntry(entry) {
      if (!entry.tieneHora) {

         const fin = new Date(entry.end);
         fin.setDate(fin.getDate() - 1);

         return [
            entry.title,
            entry.subtitle,
            `${formatearFecha(entry.start)} - ${formatearFecha(fin)}`
         ].filter(Boolean).join("\n");
      }

      return [
         entry.title,
         entry.subtitle,
         `${formatearFecha(entry.start)} ${formatearHora(entry.start)} - ${formatearFecha(entry.end)} ${formatearHora(entry.end)}`
      ].filter(Boolean).join("\n");
   }


   function normalizarEntries(entries) {

      const entriesRender = [];

      for (const entry of entries) {

         entry.subtitle =
            entry.subtitle ?? DEFAULT_ENTRY_OPTIONS.subtitle;

         entry.description =
            entry.description ?? DEFAULT_ENTRY_OPTIONS.description;

         entry.agrupation =
            entry.agrupation ?? DEFAULT_ENTRY_OPTIONS.agrupation;

         entry.color =
            entry.color ?? DEFAULT_ENTRY_OPTIONS.color;

         entry.textColor =
            entry.textColor ?? DEFAULT_ENTRY_OPTIONS.textColor;

         entry.borderColor =
            entry.borderColor ?? DEFAULT_ENTRY_OPTIONS.borderColor;

         entry.iconColor =
            entry.iconColor ?? DEFAULT_ENTRY_OPTIONS.iconColor;

         entry.icon =
            entry.icon ?? DEFAULT_ENTRY_OPTIONS.icon;

         entry.className =
            entry.className ?? DEFAULT_ENTRY_OPTIONS.className;

         entry.editable =
            entry.editable ?? DEFAULT_ENTRY_OPTIONS.editable;

         entry.visible =
            entry.visible ?? DEFAULT_ENTRY_OPTIONS.visible;

         entry.disabled =
            entry.disabled ?? DEFAULT_ENTRY_OPTIONS.disabled;

         entry.selected =
            entry.selected ?? DEFAULT_ENTRY_OPTIONS.selected;

         entry.data =
            entry.data ?? {};

         entry.tooltip = normalizarTooltipEntry(entry);

         if (!entry.multidia) {
            entriesRender.push(entry);
            continue;
         }

         entriesRender.push(
            ...crearSegmentosEntry(entry)
         );
      }

      return entriesRender;
   }


   function validarConfiguracion(opciones) {

      if ("title" in opciones) {
         Validadores.cadena("title", opciones.title);
      }

      if ("view" in opciones) {
         validarView(opciones.view);
      }

      if ("date" in opciones) {
         Validadores.fecha("date", opciones.date);
      }

      if ("locale" in opciones) {
         Validadores.locale("locale", opciones.locale);
      }

      if ("timezone" in opciones) {
         Validadores.timezone("timezone", opciones.timezone);
      }

      validarHoras(opciones);

      if ("resolution" in opciones) {
         validarResolution(opciones.resolution);
      }

      if ("interval" in opciones) {
         validarInterval(opciones.interval);
      }

      validarRelacionIntervaloResolution(opciones);

      if ("workingDays" in opciones) {
         validarWorkingDays(opciones.workingDays);
      }

      if ("navigation" in opciones) {
         validarNavigation(opciones.navigation);
      }

      if ("views" in opciones) {
         validarViews(opciones.views);
      }

      if ("entries" in opciones) {

         const entriesInternas = structuredClone(
            opciones.entries
         );

         validarEntries(entriesInternas);
         opciones.entries = entriesInternas;
         opciones.entriesRender = normalizarEntries(
            entriesInternas
         );
      }

   }


//#endregion


//#region Listeners 

   function inicializarListeners() {

      function inicializarListenersHeader() {
         Object.values(controles.views).forEach(input => {
               input.addEventListener("change", function () {
                  cambiarVista(this.value)
               });

         });

      }

      function inicializarListenersNavigation() {
         controles.container
            .querySelector(".tg-button-previous")
            .addEventListener("click", () => {
                  navegarFecha(-1);
            });

         controles.container
            .querySelector(".tg-button-today")
            .addEventListener("click", () => {
                  irHoy();
            });

         controles.container
            .querySelector(".tg-button-next")
            .addEventListener("click", () => {
                  navegarFecha(1);
            });

      }


      if (opciones.views) {
         inicializarListenersHeader();
      }

      inicializarListenersNavigation();

   }


//#endregion 


//#region Render

   // Render principal  
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
      renderEntries();
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
      const diasMes = obtenerDiasMes();
      const configuracion = obtenerConfiguracionGrid();
      const horas = obtenerHoras();
      const dia = obtenerDiaSeleccionado();
      const dias = obtenerDiasSemana();

      function obtenerConfiguracionGrid() {
         if (estado.view === "month") {

            const totalSemanas = Math.ceil(
                     diasMes.length / 7
               ) * MONTH_ROWS_PER_WEEK; 

            return {
                  totalFilas: totalSemanas,
                  filasPorIntervalo: MONTH_ROWS_PER_WEEK,
                  spanFilas: MONTH_ROWS_PER_WEEK
            };
         }

         const totalFilas =
            ((opciones.endHour - opciones.startHour + 1) * 60) /
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
         if (estado.view === "month") {
            return `
                  --tg-interval-rows: ${configuracion.filasPorIntervalo};

                  display: grid;
                  grid-template-columns:
                     repeat(${totalColumnas}, 1fr);

                  grid-template-rows:
                     var(--tg-header-height)
                     repeat(${configuracion.totalFilas}, var(--tg-month-row-height));
            `;
         }

   
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
            minutos < (opciones.endHour + 1)  * 60;
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


      function renderDayGrid() {
         const clases = [
                        "tg-week-day-header-number",
                        dia.esHoy ? "tg-day-number-today" : "",
                        dia.esSeleccionado ? "tg-day-number-selected" : ""
                     ].filter(Boolean).join(" ");


         return `
            <div
               class="tg-week tg-day-grid"
               style="${obtenerGridStyle(1)}">

               <div class="tg-week-time-header"></div>

               <div class="tg-week-day-header">
                  <span 
                     class="${clases}"
                     >
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


      function renderWeekGrid(soloLaborables = false) {
         const dias = obtenerDiasSemana(soloLaborables);

         return `
            <div
                  class="tg-week tg-week-grid"
                  style="${obtenerGridStyle(dias.length)}">

                  <div class="tg-week-time-header"></div>

                  ${dias.map(dia => {

                     const clases = [
                        "tg-week-day-header-number",
                        dia.esHoy ? "tg-day-number-today" : "",
                        dia.esSeleccionado ? "tg-day-number-selected" : ""

                     ].filter(Boolean).join(" ");
                     return `
                        <div class="tg-week-day-header">
                              <span class="${clases}">
                                 ${dia.numero}
                              </span>

                              <span>
                                 ${dia.nombre}
                              </span>
                        </div>
                     `;
                  }).join("")}
                  ${renderHoras(horas)}
            </div>
         `;
      }

      function renderMonthGrid() {

         return `
            <div
               class="tg-month tg-month-grid"
               style="${obtenerGridStyle(dias.length)}">
               ${dias.map(dia => `
                  <div class="tg-week-day-header">
                     <span>
                        ${dia.nombre.slice(0, 3)}
                     </span>
                  </div>
               `).join("")}
               ${diasMes.map((dia, indice) => {

                  const posicion = obtenerPosicionDiaMes(indice);

                  const clases = [
                     "tg-month-day-number",
                     !dia.esMesActual ? "tg-month-day-number-other" : "",
                     dia.esHoy ? "tg-month-day-number-today" : "",
                     dia.esSeleccionado ? "tg-day-number-selected" : ""
                  ].filter(Boolean).join(" ");

                  return `
                     <span
                        class="${clases}"
                        style="
                           grid-column: ${posicion.columna};
                           grid-row: ${posicion.filaInicio} / ${posicion.filaFin};
                        ">
                        ${dia.numero}
                     </span>
                  `;

               }).join("")}
            </div>
         `;
      }

      switch (estado.view) {
         case "day":
            grid.innerHTML = renderDayGrid();
            break;
         case "week":
            grid.innerHTML = renderWeekGrid();
            break;
         case "workweek":
            grid.innerHTML = renderWeekGrid(true);
            break;
         case "month":
            grid.innerHTML = renderMonthGrid();
            break;

      }

   }

   function renderEntries() {
      switch (estado.view) {

         case "day":
            renderEntriesDay();
            break;

         case "week":
            renderEntriesWeek();
            break;

         case "workweek":
            renderEntriesWeek();
            break;

         case "month":
            renderEntriesMonth();
            break;
      }
   }

   function renderEntryDay(entry) {
      const filaInicio = obtenerFilaEntry(entry.start, estado.date);
      const filaFin = obtenerFilaEntry(entry.end, estado.date, true);

      const filas = filaFin - filaInicio;

      const clases = obtenerClasesEntry(entry, filas);
      const estilos = obtenerEstilosEntry(
         entry,
         filaInicio,
         filaFin
      );

      const icono = renderIconoEntry(entry);
      const subtitle = renderSubtitleEntry(entry);


      const description = entry.description
         ? `
            <span class="tg-entry__description">
               ${limitarTexto(entry.description, DESCRIPCION_MAXIMA)}
            </span>
         `
         : "";

      return `
         <div
            class="${clases}"
            title="${entry.tooltip}"
            style="${estilos}">
            ${icono}

            <div class="tg-entry__content">
               <div class="tg-entry__header">
                  <span class="tg-entry__title">
                     ${entry.title}
                  </span>
                  ${subtitle}
               </div>
               ${description}
            </div>
         </div>
      `;
   }


   function renderEntryWeek(entry) {
      const filaInicio = obtenerFilaEntry(entry.start,entry.start);
      const filaFin = obtenerFilaEntry(entry.end, entry.end, true);

      const filas = filaFin - filaInicio;
      const columna = obtenerColumnaEntry(entry.start);


      const clases = obtenerClasesEntry(entry, filas);
      const estilos = obtenerEstilosEntry(
            entry,
            filaInicio,
            filaFin
         );

      const icono = renderIconoEntry(entry);
      const subtitle = renderSubtitleEntry(entry);
      return `
         <div
            class="${clases}"
            title="${entry.tooltip}"
            style="${estilos}">
            ${icono}
            <div class="tg-entry__content">
               <div class="tg-entry__header">
                  <span class="tg-entry__title">
                     ${limitarTexto(entry.title, TITLE_MAXIMA)}
                  </span>
                  ${subtitle}
               </div>
            
            </div>
         </div>
      `;
   }


   function renderEntryMonth(grupo) {

      const entries = grupo.entries;
      const total = entries.length;

      const agrupaciones = {};
      const entriesSinAgrupacion = [];

      for (const entry of entries) {

         if (!entry.agrupation) {
            entriesSinAgrupacion.push(entry);
            continue;
         }

         if (!agrupaciones[entry.agrupation]) {
            agrupaciones[entry.agrupation] = [];
         }

         agrupaciones[entry.agrupation].push(entry);
      }

      const indiceDia = grupo.indiceDia;
      const posicion = obtenerPosicionDiaMes(indiceDia);

      const agrupacionesArray = Object.entries(agrupaciones);

      let lineasVisibles = 3
      const lineasPintar = agrupacionesArray.length + entriesSinAgrupacion.length
      if (lineasPintar > 3) {
         lineasVisibles--;
      }
      const agrupacionesRestantes  = lineasPintar - lineasVisibles
      let lineasPintadas = 0;

     
   
      return `
         <div
            class="tg-month-entry"
            style="
               grid-column: ${posicion.columna};
               grid-row: ${posicion.filaInicio} / ${posicion.filaFin};
            ">

            <div class="tg-month-entry-total">
               ${renderIcon("count")}
               <span>${total}</span>
            </div>

            <div class="tg-month-entry-groups">

               ${
                  (() => {

                     let html = "";

                     for (const [nombre, cantidad] of agrupacionesArray) {

                        if (lineasPintadas >= lineasVisibles) {
                           break;
                        }

                        const tooltip = cantidad
                              .map(entry => entry.tooltip)
                              .join("\n");
                        
                        const color = cantidad[0].color;
                        const borderColor = cantidad[0].borderColor;

                        html += `
                           <div
                              class="tg-month-entry-group"
                              title="${tooltip}"
                              style="${
                                 opciones.useGroupColor
                                    ? `
                                       background-color: ${color};
                                       border-color: ${borderColor};
                                    `
                                    : ""
                              }">

                              <span class="tg-entry-group__icon">
                                 ${renderIcon("collection")}
                              </span>

                              <span class="tg-month-entry-group-title">
                                 ${nombre}
                              </span>

                              <span class="tg-month-entry-group-total">
                                 ${cantidad.length}
                              </span>

                           </div>
                        `;

                        lineasPintadas++;
                     }

                     for (const entry of entriesSinAgrupacion) {

                        if (lineasPintadas >= lineasVisibles) {
                           break;
                        }

                        html += renderEntryMonthFree(entry, entriesSinAgrupacion.length);
                        lineasPintadas++;
                     }

                     return html;

                  })()
               }

               ${
                  lineasPintar > lineasPintadas
                     ? `
                        <div class="tg-month-entry-more">
                           Ver más · ${lineasPintar - lineasPintadas}
                        </div>
                     `
                     : ""
               }

            </div>

         </div>
      `;
   }


   function renderEntriesDay() {
      const grid = controles.container.querySelector(".tg-day-grid");
      for (const entry of opciones.entriesRender) {

         if (!entry.visible) {
            continue;
         }

         if (!esEntryVisible(entry)) {
            continue;
         }

         grid.insertAdjacentHTML(
            "beforeend",
            renderEntryDay(entry)
         );
      }

   }

   function renderEntriesWeek() {
      const grid = controles.container.querySelector(".tg-week-grid");


      for (const entry of opciones.entriesRender ) {

         if (!entry.visible) {
            continue;
         }

         if (!esEntryVisible(entry)) {
            continue;
         }

         grid.insertAdjacentHTML(
            "beforeend",
            renderEntryWeek(entry)
         );
         
      }
   }

   function renderEntriesMonth() {

      const grid = controles.container.querySelector(".tg-month-grid");
      const diasMes = obtenerDiasMes();

      const entriesVisibles = opciones.entriesRender.filter(entry => {
         if (!entry.visible) {
            return false;
         }
         return esEntryVisible(entry);

      });

      const entriesPorDia = {};

      for (const entry of entriesVisibles) {

         const fecha = entry.start.toDateString();
         if (!entriesPorDia[fecha]) {
            const indiceDia = diasMes.findIndex(dia =>
               esMismaFecha(dia.fecha, entry.start)
            );

            entriesPorDia[fecha] = {
               indiceDia,
               entries: []
            };
         }

         entriesPorDia[fecha].entries.push(entry);
      }

      for (const entries of Object.values(entriesPorDia)) {

         grid.insertAdjacentHTML(
            "beforeend",
            renderEntryMonth(entries)
         );
      }
   }


   function renderSubtitleEntry(entry) {
      if (!entry.subtitle) {
         return "";
      }

      return `
         <span class="tg-entry__subtitle">
            ${entry.subtitle}
         </span>
      `;
   }

   function renderIconoEntry(entry) {
      if (!entry.icon) {
         return "";
      }

      return `
         <span
            class="tg-entry__icon"
            ${entry.iconColor !== null
               ? `style="color: ${entry.iconColor};"`
               : ""}>
            ${renderIcon(entry.icon)}
         </span>
      `;
   }

   function renderEntryMonthFree(entry, cantidad) {

      const icono = renderIconoEntry(entry);

      const filasSupuestas = cantidad === 1 ? 6 : 2;



      return `
         <div
            class="${obtenerClasesEntry(entry, filasSupuestas)}"
            style="
               ${entry.color !== null ? `background-color: ${entry.color};` : ""}
               ${entry.textColor !== null ? `color: ${entry.textColor};` : ""}
               ${entry.borderColor !== null ? `border-color: ${entry.borderColor};` : ""}
            "
            title="${entry.tooltip}">
            ${icono}

            <div class="tg-entry__content">
               <div class="tg-entry__header">
                  <span class="tg-entry__title">
                     ${entry.title}
                  </span>

                  
               </div>
            </div>
         </div>
      `;
   }

//#endregion


//#region Navagacion Y estado
   function cambiarVista(view) {
      validarView(view);
      estado.view = view;
      actualizar();
   }


   function actualizar() {
      render();
      inicializarListeners();
   }


   function irHoy() {
      cambiarFecha(new Date());
      actualizar();
   }


   function notificarCambioFecha() {

      if (typeof opciones.onDateChange === "function") {

         opciones.onDateChange(
            estado.date
         );

      }

   }

   // funciones publicas 

   function navegarFecha(direccion) {
      const fecha = new Date(estado.date);
      switch (estado.view) {

         case "day":
            fecha.setDate(
               fecha.getDate() + direccion
            );
            break;

         case "week":
         case "workweek":
            fecha.setDate(
               fecha.getDate() + (direccion * 7)
            );
            break;
         case "month":
            estado.date = sumarMeses(fecha, direccion);
            actualizar();
            return;
      }
      cambiarFecha(fecha);
      actualizar();
   }


   function cambiarFecha(fecha) {
      Validadores.fecha("fecha", fecha);
      estado.date = fecha;
      notificarCambioFecha();
   }

   function cambiarTitulo(titulo) {

      Validadores.cadena("title", titulo);
      opciones.title = titulo;
   }

   function cambiarDiasLaborales(workingDays) {

      validarWorkingDays(workingDays);
      opciones.workingDays = [...workingDays];

   }

   function cambiarEntries(entries) {
      Validadores.array(
         "entries",
         entries
      );

      const entriesInternas = structuredClone(
         entries
      );

      validarEntries(entriesInternas);
      opciones.entries = entriesInternas;
      opciones.entriesRender = normalizarEntries(
         entriesInternas
      );
         

   }

//#endregion


//#region Entries

   function obtenerFilaEntry(fecha, fechaReferencia, esFin = false) {
      const inicioVisible = new Date(fechaReferencia);
      inicioVisible.setHours(opciones.startHour, 0, 0, 0);

      const finVisible = new Date(fechaReferencia);
      finVisible.setHours(opciones.endHour + 1, 0, 0, 0);


      if (
         esFin &&
         fecha.getHours() === 0 &&
         fecha.getMinutes() === 0 &&
         fecha.getSeconds() === 0 &&
         fecha.getMilliseconds() === 0
      ) {
         return 2 + (
            ((opciones.endHour - opciones.startHour + 1) * 60) /
            opciones.resolution
         );
      }

      if (fecha < inicioVisible) {
         fecha = inicioVisible;
      }

      if (fecha > finVisible) {
         fecha = finVisible;
      }

      const minutos = (
         fecha.getHours() * 60 +
         fecha.getMinutes()
      );

      const inicio = opciones.startHour * 60;

      return 2 + (
         (minutos - inicio) / opciones.resolution
      );
   }


   function obtenerColumnaEntry(fecha) {
         const soloLaborables =
            estado.view === "workweek";

         const dias =
            obtenerDiasSemana(soloLaborables);

         const diaSemana =
            fecha.getDay() === 0
               ? 7
               : fecha.getDay();

         const indice =
            dias.findIndex(
               dia => dia.diaSemana === diaSemana
            );

         return indice + 2;
   }


   function obtenerEstilosEntry(entry, filaInicio, filaFin) {
      const columna =
         estado.view === "day"
            ? 2
            : obtenerColumnaEntry(entry.start);

      return `
         grid-column: ${columna};
         grid-row: ${filaInicio} / ${filaFin};
         ${entry.color !== null ? `background-color: ${entry.color};` : ""}
         ${entry.textColor !== null ? `color: ${entry.textColor};` : ""}
         ${entry.borderColor !== null ? `border-color: ${entry.borderColor};` : ""}
      `;
   }


   function obtenerClasesEntry(entry, filas) {
      const claseVista =
         estado.view === "day"
            ? "tg-entry-day"
            : "tg-entry-week";

      return [
         "tg-entry",
         claseVista,
         filas <= 2 ? "tg-entry--compact" : "",
         filas >= 6 ? "tg-entry--extended" : "",
         entry.selected ? "tg-entry--selected" : "",
         entry.disabled ? "tg-entry--disabled" : ""
      ].filter(Boolean).join(" ");

   }

   function obtenerPosicionDiaMes(indice) {

      const semana = Math.floor(indice / 7);
      const diaSemana = indice % 7;

      const columna = diaSemana + 1;
      const filaInicio = 2 + (semana * MONTH_ROWS_PER_WEEK);
      const filaFin = filaInicio + MONTH_ROWS_PER_WEEK;

      return {
         columna,
         filaInicio,
         filaFin
      };

   }


   function esEntryVisible(entry) {
      switch (estado.view) {

         case "day":
            return esEntryVisibleDay(entry);

         case "week":
            return esEntryVisibleWeek(entry);

         case "workweek":
            return esEntryVisibleWorkweek(entry);

         case "month":
            return esEntryVisibleMonth(entry);
      }

      return false
   }


   function esEntryVisibleDay(entry) {
      const inicioVisible = new Date(estado.date);
      inicioVisible.setHours(
         opciones.startHour,
         0,
         0,
         0
      );

      const finVisible = new Date(estado.date);
      finVisible.setHours(
         opciones.endHour + 1 ,
         0,
         0,
         0
      );

      return (
         entry.start < finVisible &&
         entry.end > inicioVisible
      );

   }

   function esEntryVisibleWeek(entry) {
      const inicioSemana = obtenerInicioSemana(estado.date);

      for (let i = 0; i < 7; i++) {

         const inicioVisible = new Date(inicioSemana);
         inicioVisible.setDate(
            inicioVisible.getDate() + i
         );
         inicioVisible.setHours(
            opciones.startHour,
            0,
            0,
            0
         );

         const finVisible = new Date(inicioSemana);
         finVisible.setDate(
            finVisible.getDate() + i
         );
         finVisible.setHours(
            opciones.endHour + 1 ,
            0,
            0,
            0
         );

         if (
            entry.start < finVisible &&
            entry.end > inicioVisible
         ) {
            return true;
         }
      }

      return false;
   }

   function esEntryVisibleWorkweek(entry) {
      const dias = obtenerDiasSemana(true);
      for (const dia of dias) {

         const inicioVisible = new Date(dia.fecha);
         inicioVisible.setHours(
            opciones.startHour,
            0,
            0,
            0
         );

         const finVisible = new Date(dia.fecha);
         finVisible.setHours(
            opciones.endHour + 1,
            0,
            0,
            0
         );

         if (
            entry.start < finVisible &&
            entry.end > inicioVisible
         ) {
            return true;
         }
      }
      return false;
   }

   function esEntryVisibleMonth(entry) {

      const diasMes = obtenerDiasMes();

      const inicioVisible = diasMes[0].fecha;
      const finVisible = new Date(diasMes[diasMes.length - 1].fecha);

      return (
         entry.start <= finVisible &&
         entry.end > inicioVisible
      );

   }

   function crearSegmentosEntry(entry) {

      const segmentos = [];

      let fechaActual = new Date(entry.start);

      while (fechaActual < entry.end) {

         const siguienteDia = new Date(fechaActual);

         siguienteDia.setDate(
            siguienteDia.getDate() + 1
         );

         siguienteDia.setHours(
            0, 0, 0, 0
         );

         const finSegmento =
            siguienteDia < entry.end
               ? siguienteDia
               : entry.end;

         segmentos.push({

            ...entry,

            start: new Date(fechaActual),

            end: new Date(finSegmento)

         });

         fechaActual = siguienteDia;

      }

      return segmentos;

   }

//#endregion 


//#region Utilidades de fechas
   function formatearHora(fecha) {
      return `${String(fecha.getHours()).padStart(2, "0")}:${String(fecha.getMinutes()).padStart(2, "0")}`;
   }


   function formatearFecha(fecha) {

      return new Intl.DateTimeFormat(
         opciones.locale,
         {
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
         }
      ).format(fecha);

   }


   function formatearMes(fecha) {

      const texto = fecha.toLocaleDateString(opciones.locale, {
         month: "long",
         year: "numeric",
         timeZone: opciones.timezone
      });
      return texto.charAt(0).toUpperCase() + texto.slice(1);
   }


   function formatearRangoWeek(fecha, dias) {
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


   function formatearDiasWorkweek() {
      const dias = obtenerDiasSemana(true);

      const numeros = dias.map(dia =>
         dia.numero
      );

      const mes = dias[0].fecha.toLocaleDateString(
         opciones.locale,
         {
            month: "long",
            timeZone: opciones.timezone
         }
      );

      const anio = dias[0].fecha.getFullYear();

      let diasTexto;
      if (numeros.length === 1) {
         diasTexto = `${numeros[0]}`;
      }
      else if (numeros.length === 2) {
         diasTexto = `${numeros[0]} y ${numeros[1]}`;
      }
      else {
         diasTexto =
            `${numeros.slice(0, -1).join(", ")} y ${numeros[numeros.length - 1]}`;
      }
      return `${diasTexto} de ${mes} de ${anio}`;
   }


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


   function obtenerDiasMes() {

         const fecha = new Date(
            estado.date.getFullYear(),
            estado.date.getMonth(),
            1
         );

         const inicio = obtenerInicioSemana(fecha);

         const ultimoDiaMes = new Date(
            estado.date.getFullYear(),
            estado.date.getMonth() + 1,
            0
         );

         const fin = obtenerInicioSemana(ultimoDiaMes);
         fin.setDate(fin.getDate() + 6);

         const dias = [];
         const actual = new Date(inicio);

         const formatoFecha = new Intl.DateTimeFormat(opciones.locale, {
            timeZone: opciones.timezone,
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric"
         });

         while (actual <= fin) {

            dias.push({
                  fecha: new Date(actual),
                  fechaTexto: formatoFecha.format(actual),
                  numero: actual.getDate(),
                  mes: actual.getMonth() + 1,
                  anio: actual.getFullYear(),
                  esMesActual:
                     actual.getMonth() === estado.date.getMonth() &&
                     actual.getFullYear() === estado.date.getFullYear(),
                  esHoy: esMismaFecha(actual, new Date()),
                  esSeleccionado: esMismaFecha(actual, estado.date),
                  
            });

            actual.setDate(actual.getDate() + 1);
         }

         return dias;
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

         esHoy: esMismaFecha(fecha, new Date()),
         esSeleccionado: esMismaFecha(fecha, estado.date),
      };

   }


   function esMismaFecha(fecha1, fecha2){

      return (
         fecha1.getFullYear() === fecha2.getFullYear() &&
         fecha1.getMonth() === fecha2.getMonth() &&
         fecha1.getDate() === fecha2.getDate()
      );

   }


   function obtenerRangoMostrado() {
      switch (estado.view) {

         case "day":
               return formatearDia(estado.date);
         case "week":
               return formatearRangoWeek(estado.date, 6);
         case "workweek":
               return formatearDiasWorkweek(estado.date, 4);
         case "month":
               return formatearMes(estado.date);
      }
   }


//#endregion


//#region Utilidades generales 

   

   function resolverContenedor(container) {

      if (typeof container === "string") {
         container = document.querySelector(container);
      }

      if (!(container instanceof HTMLElement)) {
         throw new Error("TimeGrid: contenedor no válido.");
      }

      return container;
   }

   function sumarMeses(fecha, cantidad) {

      const nuevaFecha = new Date(fecha);

      const dia = nuevaFecha.getDate();

      nuevaFecha.setDate(1);
      nuevaFecha.setMonth(nuevaFecha.getMonth() + cantidad);

      const ultimoDia = new Date(
         nuevaFecha.getFullYear(),
         nuevaFecha.getMonth() + 1,
         0
      ).getDate();

      nuevaFecha.setDate(Math.min(dia, ultimoDia));

      return nuevaFecha;
   }

   function limitarTexto(texto, maximo) {
      if (texto.length <= maximo) {
         return texto;
      }

      return texto.slice(0, maximo).trim() + "...";
   }

   function tieneHora(valor) {

      if (valor instanceof Date) {
         return true;
      }

      if (typeof valor !== "string") {
         return false;
      }

      return valor.includes("T");
   }

   function capitalizar(texto){
      return texto.charAt(0).toUpperCase() + texto.slice(1);
   }

//#endregion

   const api = {
      render,
      cambiarFecha,
      cambiarVista,
      cambiarTitulo,
      cambiarEntries,
      cambiarDiasLaborales,
      actualizar,
      destroy() {
         controles.container.innerHTML = "";
      }
   };

   return {
      create
   };


})();