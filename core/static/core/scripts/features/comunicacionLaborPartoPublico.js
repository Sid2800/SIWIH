

const PacientesLaborPartoPublico = (() => {


   // #region 1. CONFIGURACIÓN E INICIALIZACIÓN
      const controles = {};
         controles.paciente = {};
         controles.detalle = {};
         controles.estado = {};
         controles.lineaTiempo = {};
         controles.bebe = {};
         controles.fechaHora = {};
         controles.actualizacion = {};

      const MAX_EVENTOS_LINEA_TIEMPO = 5;
      const INTERVALO_ROTACION = 40; // SEGUNDOS
      const INTERVALO_LISTADO = INTERVALO_ROTACION * 3; // 120 segundo



      const estado = {
         // Información del listado.
         episodios: [],
         total: 0,
         totalPacientesAtencion: 0,
         totalSalidasRecientes: 0,

         // Selección y detalle del paciente.
         seleccionado: null,
         detalleEpisodio: null,

         // Control de rotación automática.
         temporizadorRotacion: null,
         procesandoRotacion: false,
         segundosAcumulados: 0,

      };

      

      async function cargarDatosIniciales() {

         const cargado = await obtenerEpisodiosLP();

         if (!cargado) {
            return false;
         }

         renderizarTabla();

         if (estado.episodios.length > 0) {
            await seleccionarEpisodio(String(estado.episodios[0].id));
         }

         return true;
      }


      async function inicializar() {

         inicializarControles();

         inicializarListeners();

         await cargarDatosIniciales();

         iniciarRotacionAutomatica();

         actualizarContadorVisual();

         actualizarFechaHora();
         setInterval(actualizarFechaHora, 1000);

      }


      function inicializarControles() {
         // Fecha y hora.
         controles.fechaHora.fecha = document.getElementById("fecha-actual");
         controles.fechaHora.hora = document.getElementById("hora-actual");

         // Tabla y contadores.
         controles.contador = document.getElementById("contadorEpisodios");
         controles.tablaBody = document.getElementById("tablaEpisodios");

         controles.totalPacientesAtencion = document.getElementById("totalPacientesAtencion");
         controles.totalSalidasRecientes = document.getElementById("totalSalidasRecientes");

         // Panel de detalle.
         controles.detallePacienteVacio = document.getElementById("detallePacienteVacio");
         controles.detalleEpisodio = document.getElementById("detalleEpisodio");

         // Información del paciente.
         controles.paciente.nombre = document.getElementById("detalleNombrePacientePublico");

         // Indicador de estado.
         controles.estado.icono = document.querySelector(".detalle-episodio__estado-actual-icono");
         controles.estado.texto = document.getElementById("detalleNombreEstado");
         controles.estado.descripcion = document.getElementById("detalleDescripcionEstado");
         controles.estado.salidaDefinitiva = document.getElementById("detalleSalidaDefinitiva");
         controles.estado.salidaTemporal = document.getElementById("detalleSalidaTemporal");

         // Información del episodio.
         controles.detalle.fechaIngreso = document.getElementById("detalleFechaIngreso");
         controles.detalle.tiempoLaborLabel = document.getElementById("detalleTiempoServicioLabel");
         controles.detalle.tiempoLabor = document.getElementById("detalleTiempoServicio");
         controles.detalle.unidadOrigen = document.getElementById("detalleUnidadProcedencia");

         // Línea de tiempo.
         controles.lineaTiempo.contenedor = document.getElementById("lineaTiempoEpisodio");

         // Información de los bebés.
         controles.bebe.informacionBebe = document.getElementById("detalleInformacionBebe");

         // Indicador de actualización.
         controles.actualizacion.contador = document.getElementById("contadorActualizacion");
         controles.actualizacion.barra = document.getElementById("barraActualizacion");
         controles.actualizacion.barraValor = document.getElementById("barraActualizacionValor");

         // Indicador de conexión.
         controles.conexion = document.querySelector(".encabezado-labor-parto__estado");
         controles.conexion.texto = document.querySelector(".encabezado-labor-parto__envivo");
         controles.conexion.descripcion = document.querySelector(".encabezado-labor-parto__descripcion");
      }


      function inicializarListeners() {

         controles.tablaBody.addEventListener("click", async (event) => {

            const fila = event.target.closest(".labor-parto__fila");
            if (!fila || estado.procesandoRotacion) return;

            const episodioId = fila.dataset.episodioId;

            estado.procesandoRotacion = true;

            try {
               await seleccionarEpisodio(episodioId);

               estado.segundosAcumulados = 0;
               actualizarContadorVisual();

            } finally {
               estado.procesandoRotacion = false;
            }

         });

      }


      function actualizarIndicadorConexion(conectado) {

         const indicador = controles.conexion;

         indicador.classList.toggle("icon-verde-tenue", conectado);
         indicador.classList.toggle("icon-verde", conectado);

         indicador.classList.toggle("icon-rojo-tenue", !conectado);
         indicador.classList.toggle("icon-rojo", !conectado);

         controles.conexion.texto.innerHTML = `
            <i class="bi bi-broadcast"></i>
            ${conectado ? "En vivo" : "Sin conexión"}
         `;

         controles.conexion.descripcion.innerHTML = conectado
         ? "Información actualizada<br>en tiempo real"
         : "No se puede actualizar<br>la información";
      }


      function actualizarFechaHora() {
         const ahora = new Date();

         const fecha = ahora.toLocaleDateString("es-HN", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric"
         });

         const hora = ahora.toLocaleTimeString("es-HN", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
         });

         controles.fechaHora.fecha.textContent = fecha;
         controles.fechaHora.hora.textContent = hora;
      }


      function iniciarRotacionAutomatica() {

         if (estado.temporizadorRotacion) {
            clearInterval(estado.temporizadorRotacion);
         }

         estado.temporizadorRotacion = setInterval(async () => {

            if (estado.procesandoRotacion) {
               return;
            }

            estado.procesandoRotacion = true;

            try {
               estado.segundosAcumulados++;
               actualizarContadorVisual();

               if (estado.segundosAcumulados % INTERVALO_ROTACION === 0) {
                  if (estado.segundosAcumulados >= INTERVALO_LISTADO) {
                     await obtenerEpisodiosLP();
                     renderizarTabla();
                     estado.segundosAcumulados = 0;
                  }

                  await seleccionarSiguienteEpisodio();
               }

            } finally {
               estado.procesandoRotacion = false;
            }

         }, 1000);
      }

   //#endregion




   // #region 2. CONSULTAS Y TABLA DE EPISODIOS

      async function obtenerEpisodiosLP() {

         try {
            const data = await fetchData(
               API_URLS.listarEpisodiosPublicoAPI
            );

            if (!data) return false;

            estado.episodios = data.episodios;
            estado.total = data.total || 0;
            estado.totalPacientesAtencion =
               (data.total_atencion + data.total_salidas_temporales) || 0;
            estado.totalSalidasRecientes = data.total_salidas_recientes || 0;

            validarSeleccionActual();
            
            actualizarIndicadorConexion(true);
            return true;

         } catch (error) {
            
            actualizarIndicadorConexion(false);
            toastr.error(
               error.message,
               "Error al obtener los episodios"
            );

            return false;
         }
      }


      async function obtenerDetalleEpisodio() {


         if (!estado.seleccionado){
            return;
         }
         try {
            const data = await fetchData(
               API_URLS.obtenerEpisodioLaborParto,
               {
                  id: estado.seleccionado,
               }
            );

            if (!data) {
               actualizarIndicadorConexion(false);
               return;
            }

            estado.detalleEpisodio = data;
            actualizarVistaDetalle();
            actualizarIndicadorConexion(true);


         } catch (error) {
            actualizarIndicadorConexion(false);
            toastr.error(
               error.message,
               "Error al obtener detalle del episodio"
            );

         }
      }


      function validarSeleccionActual() {

         if (!estado.seleccionado) {
            return;
         }

         const existe = estado.episodios.some(
            episodio => episodio.id === Number(estado.seleccionado)
         );

         if (!existe) {
            estado.seleccionado = null;
            estado.detalleEpisodio = null;

            mostrarDetalleVacio();
         }
      }



   //#endregion





   //#region 3. Renderizar / Visuales

      function renderizarTabla() {
         const tbody = controles.tablaBody;

         if (estado.episodios.length === 0) {
            tbody.innerHTML = `
               <tr>
                     <td colspan="3" class="labor-parto__vacio">
                        Página sin resultados: no hay episodios para mostrar.
                     </td>
               </tr>
            `;
            actualizarTotales();
            return;
         }

         const filas = estado.episodios.map((item) => {
            const nombrePaciente = concatenarLimpio(
               item.paciente__primer_nombre,
               item.paciente__segundo_nombre,
               item.paciente__primer_apellido,
               item.paciente__segundo_apellido
            );


            const estiloEstado = `
               color: ${item.estado_actual_color.color};
            `;

            const horaIngreso = formatearHoraLocal(
               item.fecha_ingreso
            );

            const fechaIngreso = formatearFechaLocal(
               item.fecha_ingreso
            );

            const iconoEstado = IconosLaborParto.obtener(
               item.estado_actual_color.icono
            );

            return `
               <tr
                     class="labor-parto__fila"
                     data-episodio-id="${escaparHTML(item.id)}"
               >

                     <td class="labor-parto__columna-estado">
                        <div
                           class="labor-parto__estado-contenedor"
                           style="${estiloEstado}"
                           title="${escaparHTML(item.estado_actual_texto)}"
                        >

                           <div class="labor-parto__estado-icono">
                                 ${iconoEstado}
                           </div>
                        </div>

                     </td>

                     <td>
                        <div class="labor-parto__paciente">

                           <div>
                                 <strong>
                                    ${escaparHTML(nombrePaciente)}
                                 </strong>

                                 <small>
                                    EXP-. ${escaparHTML(item.paciente__expediente_numero)}
                                 </small>
                           </div>

                        </div>
                     </td>

                     
                     <td>
                        <div class="labor-parto__fecha">

                           <strong>
                              <span class="material-symbols-outlined">
                                 schedule
                              </span>
                              ${horaIngreso}
                           </strong>

                           <small>
                              <span class="material-symbols-outlined">
                                 calendar_today
                              </span>
                              ${fechaIngreso}
                           </small>

                        </div>
                     </td>

               </tr>
            `;
         });

         tbody.innerHTML = filas.join("");

         actualizarTotales();
  
      }


      function actualizarTotales() {
         const total = estado.total || 0;
         const totalAtencion = estado.totalPacientesAtencion || 0;
         const totalSalidasRecientes = estado.totalSalidasRecientes || 0;

         controles.contador.textContent = total;
         controles.totalPacientesAtencion.textContent = totalAtencion;
         controles.totalSalidasRecientes.textContent = totalSalidasRecientes;
      }


      function mostrarDetalleEpisodio() {
         controles.detallePacienteVacio.classList.add("oculto");
         controles.detalleEpisodio.classList.remove("oculto");
      }


      function mostrarDetalleVacio() {
         controles.detallePacienteVacio.classList.remove("oculto");
         controles.detalleEpisodio.classList.add("oculto");
      }


      function actualizarVistaDetalle() {

         if (!estado.detalleEpisodio) {
            mostrarDetalleVacio();
            return;
         }

         mostrarDetalleEpisodio();
         actualizarDetalleEpisodio();

      }


      function actualizarDetalleEpisodio() {

         const episodio = estado.detalleEpisodio;

         if (!episodio) {
            return;
         }

         // Identificación del paciente.
         const paciente = episodio.paciente;

         const nombre = concatenarLimpio(
            paciente.primer_nombre,
            paciente.segundo_nombre,
            paciente.primer_apellido,
            paciente.segundo_apellido
         );

         controles.paciente.nombre.textContent = nombre;

         // Información general del episodio.
         controles.detalle.fechaIngreso.textContent =
            episodio.fecha_ingreso
               ? `${formatearFechaLocal(episodio.fecha_ingreso)} - ${formatearHoraLocal(episodio.fecha_ingreso)}`
               : "-";

         controles.detalle.unidadOrigen.textContent =
            episodio.unidad_entrada ?? "-";

         // Información del estado actual.
         const estadoInfo = episodio.estado_actual_info;

         if (estadoInfo) {

            const detalle = controles.detalleEpisodio;

            detalle.style.setProperty("--color-estado", estadoInfo.color);
            detalle.style.setProperty("--fondo-estado", estadoInfo.fondo);
            detalle.style.setProperty("--borde-estado", estadoInfo.borderColor);

            controles.estado.icono.innerHTML =
               IconosLaborParto.obtener(estadoInfo.icono);

            controles.estado.texto.textContent = estadoInfo.texto;
            controles.estado.descripcion.textContent = estadoInfo.descripcion;
         }

         // Información de salida.
         if (episodio.alta) {

            controles.detalle.tiempoLaborLabel.textContent = "Salida de Labor y Parto";

            controles.detalle.tiempoLabor.textContent =
               episodio.fecha_alta
                  ? `${formatearFechaLocal(episodio.fecha_alta)} - ${formatearHoraLocal(episodio.fecha_alta)}`
                  : "-";

            controles.estado.salidaDefinitiva.classList.remove("oculto");

         } else {

            controles.detalle.tiempoLaborLabel.textContent = "Tiempo en el servicio";
            controles.detalle.tiempoLabor.textContent = episodio.tiempo_labor_parto ?? "-";

            controles.estado.salidaDefinitiva.classList.add("oculto");
         }

         // Indicador de salida temporal.
         if (episodio.salida_temporal) {
            controles.estado.salidaTemporal.classList.remove("oculto");
         } else {
            controles.estado.salidaTemporal.classList.add("oculto");
         }

         // Información complementaria.
         renderizarLineaTiempo();
         renderizarInformacionBebes();

      }


      function renderizarLineaTiempo() {

         const episodio = estado.detalleEpisodio;
         if (!episodio) {
            return;
         }

         const movimientos = episodio.movimientos ?? [];
         const movimientosVisibles = movimientos.slice(
            0,
            MAX_EVENTOS_LINEA_TIEMPO
         ).reverse();

         const lineaTiempo = controles.lineaTiempo.contenedor;

         // Restaurar estructura de la línea de tiempo.
         lineaTiempo.innerHTML = `
            <div class="detalle-episodio__conexion"></div>
         `;

         // Construir acontecimientos registrados.
         for (const movimiento of movimientosVisibles) {
            const evento = crearEventoMovimiento(movimiento);
            lineaTiempo.appendChild(evento);
         }

         // Completar espacios disponibles.
         const espaciosDisponibles =
            MAX_EVENTOS_LINEA_TIEMPO - movimientosVisibles.length;

         for (let i = 0; i < espaciosDisponibles; i++) {
            lineaTiempo.appendChild(crearEventoFuturo());
         }
      }


      function crearEventoMovimiento(movimiento) {

         const { indicador } = movimiento;

         const evento = document.createElement("div");

         evento.style.setProperty("--color-estado", indicador.color);
         evento.style.setProperty("--fondo-estado", indicador.fondo);
         evento.style.setProperty("--borde-estado", indicador.borderColor);

         evento.className = "detalle-episodio-evolucion__evento";

         if (movimiento.es_movimiento_actual) {
            evento.classList.add("detalle-episodio__evento--actual");
         } else {
            evento.classList.add("detalle-episodio__evento--completado");
         }

         evento.dataset.tipo = movimiento.tipo;
         evento.dataset.estado = movimiento.estado_nuevo;
         evento.dataset.actual = String(movimiento.es_movimiento_actual);

         let fechaTexto = "";

         if (movimiento.es_alta) {
            fechaTexto = `Salida: ${formatearFechaLocal(movimiento.fecha_movimiento)} ${formatearHoraLocal(movimiento.fecha_movimiento)}`;
         } else {
            fechaTexto = movimiento.duracion;

            if (!fechaTexto) {
               fechaTexto = "";
            }
         }

         evento.innerHTML = `
            <div class="detalle-episodio__icono">
               ${IconosLaborParto.obtener(indicador?.icono)}
            </div>

            <div class="detalle-episodio-evolucion__informacion">
               <span>${escaparHTML(indicador?.texto ?? movimiento.tipo_texto)}</span>
               <p>${fechaTexto}</p>
            </div>

            ${movimiento.es_movimiento_actual ? `
               <span
                  class="detalle-episodio__verificacion material-symbols-outlined"
                  aria-label="Último acontecimiento"
               >check</span>
            ` : ""}
         `;

         return evento;
      }


      function crearEventoFuturo() {

         const evento = document.createElement("div");

         evento.className = `
            detalle-episodio-evolucion__evento
            detalle-episodio__evento--futuro
         `;

         evento.dataset.tipo = "estado";
         evento.dataset.estado = "";
         evento.dataset.actual = "false";

         evento.innerHTML = `
            <div class="detalle-episodio__icono">
               <span class="material-symbols-outlined" aria-hidden="true">
                  schedule
               </span>
            </div>
         `;

         return evento;
      }

      
      function renderizarInformacionBebes() {

         const episodio = estado.detalleEpisodio;

         if (!episodio) {
            return;
         }

         const contenedor = controles.bebe.informacionBebe;
         const bebes = episodio.bebes ?? [];

         // Encabezado general.
         const cantidadBebes = bebes.length;
         const textoCantidad = cantidadBebes === 1
            ? "1 nacimiento"
            : `${cantidadBebes} nacimientos`;

         // Sin bebés registrados.
         let contenido = "";

         if (cantidadBebes === 0) {

            contenido = `
               <div class="detalle-episodio__bebe-vacio">

                  <span class="material-symbols-outlined" aria-hidden="true">
                     schedule
                  </span>

                  <div>
                     <h4>Aún no se ha registrado el nacimiento</h4>
                     <p>
                        La información del bebé se mostrará cuando se registre el nacimiento.
                     </p>
                  </div>

               </div>
            `;

         } else {

            // Generar una tarjeta por cada bebé.
            contenido = bebes.map((bebe, indice) => {

               let colorBebe = "#8d969f";
               let sexoTexto = "N/D";

               if (bebe.sexo === "H") {
                  colorBebe = "#4A80B8";
                  sexoTexto = "Hombre";
               } else if (bebe.sexo === "M") {
                  colorBebe = "#C06A91";
                  sexoTexto = "Mujer";
               }

               const fechaNacimiento = bebe.fecha_nacimiento
                  ? `${formatearFechaLocal(bebe.fecha_nacimiento)} - ${formatearHoraLocal(bebe.fecha_nacimiento)}`
                  : "Fecha no disponible";

               return `
                  <article
                     class="detalle-episodio__bebe-tarjeta"
                     style="--color-bebe: ${colorBebe};"
                  >

                     <div class="detalle-episodio__bebe-icono">
                        ${IconosLaborParto.obtener("bebe")}
                     </div>

                     <div class="detalle-episodio__bebe-datos">

                        <h4>Bebé ${indice + 1}</h4>

                        <div class="detalle-episodio__bebe-detalle">

                           <span class="material-symbols-outlined" aria-hidden="true">
                              calendar_month
                           </span>

                           <p>${fechaNacimiento}</p>

                        </div>

                     </div>

                     <span class="detalle-episodio__bebe-sexo">
                        ${sexoTexto}
                     </span>

                  </article>
               `;

            }).join("");
         }

         // Construir el componente completo.
         contenedor.innerHTML = `
            <div class="detalle-episodio__bebe-encabezado">

               <div class="detalle-episodio__bebe-encabezado-icono">
                  <span class="material-symbols-outlined" aria-hidden="true">
                     child_care
                  </span>
               </div>

               <div class="detalle-episodio__bebe-encabezado-informacion">

                  <h4>Información del bebé(s)</h4>

                  <span class="detalle-episodio__bebe-cantidad">
                     ${textoCantidad}
                  </span>

               </div>

            </div>

            <div class="detalle-episodio__bebe-contenido">
               ${contenido}
            </div>
         `;
      }


      function obtenerSiguienteEpisodio() {

         
         const episodios = estado.episodios;

         
         if (!episodios.length) {
            return null;
         }


         if (estado.seleccionado === null) {
            return episodios[0];
         }

         const indiceActual = episodios.findIndex(
            episodio => String(episodio.id) === estado.seleccionado
         );

         if (indiceActual === -1) {
            return episodios[0];
         }

         const siguienteIndice = (indiceActual + 1) % episodios.length;

         return episodios[siguienteIndice];
      }


      async function seleccionarEpisodio(episodioId) {

         // Evitar procesar nuevamente el episodio seleccionado.
         if (estado.seleccionado === episodioId) {
            return;
         }

         // Buscar y limpiar la fila seleccionada anteriormente.
         const filaSeleccionada = controles.tablaBody.querySelector(
            ".labor-parto__fila--seleccionada"
         );

         if (filaSeleccionada) {
            filaSeleccionada.classList.remove(
               "labor-parto__fila--seleccionada"
            );
         }

         // Buscar la fila correspondiente al episodio.
         const fila = controles.tablaBody.querySelector(
            `[data-episodio-id="${episodioId}"]`
         );

         if (!fila) {
            return;
         }

         // Marcar la nueva fila como seleccionada.
         fila.classList.add("labor-parto__fila--seleccionada");

         // Actualizar el episodio seleccionado.
         estado.seleccionado = episodioId;

         // Limpiar el detalle anterior.
         estado.detalleEpisodio = null;
         mostrarDetalleVacio();

         // Cargar su detalle.
         await obtenerDetalleEpisodio();
      }

      
      async function seleccionarSiguienteEpisodio() {
   

         const siguiente = obtenerSiguienteEpisodio();

         if (!siguiente) {
            return;
         }


         await seleccionarEpisodio(String(siguiente.id));
      }



      function actualizarContadorVisual() {

         const restante = INTERVALO_ROTACION - (
            estado.segundosAcumulados % INTERVALO_ROTACION
         );

         const progreso = (
            (INTERVALO_ROTACION - restante) / INTERVALO_ROTACION
         ) * 100;

         controles.actualizacion.contador.textContent =
            `${restante} segundos`;

         controles.actualizacion.barraValor.style.width =
            `${progreso}%`;

         controles.actualizacion.barra.setAttribute(
            "aria-valuenow",
            progreso
         );
      }




   //#endregion






   return {
      inicializar,
   };

})();



document.addEventListener('DOMContentLoaded', function () {
   PacientesLaborPartoPublico.inicializar();
})