
const PacientesLaborParto = (() => {



   // #region 1. CONFIGURACIÓN E INICIALIZACIÓN

      const controles = {};
         controles.paciente = {};
         controles.indicador ={};
         controles.tabs ={};
         controles.alta ={};
         controles.detalle ={};


      const estado = {
         pagina: 1,
         porPagina: 10,
         total: 0,
         totalPaginas: 0,
         totalFiltrado: 0,
         episodios: [],
         seleccionado: null,
         nuevoEstado: null,
         detalleEpisodio: null,
         filtrosEstado: [1, 2, 3, 4, 5],
         busqueda: "",
         orden: "fecha_ingreso",
         direccion: "desc",
      };


      const estilosLaborParto = {

         alta: {
            "color": "rgb(190, 95, 64)",
            "fondo": "rgba(190, 95, 64, 0.07)",
            "borderColor": "rgba(190, 95, 64, 0.50)",
            icono: "quirofano",
         },

      };


      const iconosMovimiento = {
         1: "sync_alt",
         2: "logout",
         3: "login",
      };


      async function inicializar() {
         inicializarControles();

         inicializarListeners();

         await obtenerEpisodiosLP();
         renderizarTabla();

         if (!estado.detalleEpisodio) {
            mostrarDetalleVacio();
            return;
         }

         mostrarDetalleEpisodio();

      }


      function inicializarControles() {

         controles.contenedor = document.querySelector(".labor-parto");
         controles.contador = document.getElementById("contadorEpisodios");
         controles.tablaBody = document.getElementById("tablaEpisodios");
         controles.rango = document.getElementById("rangoPaginacion");
         controles.totalPaginacion = document.getElementById("totalPaginacion");
         controles.paginaAnterior = document.getElementById("paginaAnterior");
         controles.paginaActual = document.getElementById("paginaActual");
         controles.paginaSiguiente = document.getElementById("paginaSiguiente");
         controles.buscarPaciente = document.getElementById("buscarPaciente");
         controles.contenedorFiltros = document.querySelector(".labor-parto__filtros-lista");
         controles.selectorEstados = document.getElementById("selectorEstados");
         controles.filtrosEstado = document.querySelectorAll(".labor-parto__filtro-check");
         controles.botonActualizarEstado = document.getElementById("btnActualizarEstado");
         controles.botonAgregarEpisodio= document.getElementById("botonAgregarEpisodio");

         controles.detallePacienteVacio = document.getElementById("detallePacienteVacio");
         controles.detalleEpisodio = document.getElementById("detalleEpisodio");
         // Paciente
         controles.paciente.nombre = document.getElementById("detalleNombrePaciente");
         controles.paciente.expediente = document.getElementById("detalleExpediente");
         controles.paciente.edad = document.getElementById("detalleEdad");
         controles.paciente.dni = document.getElementById("detalleDni");
         // Indicador de estado
         controles.indicador.contenedor = document.querySelector(".labor-parto__seccion.actual");
         controles.indicador.icono = document.querySelector(".labor-parto__estado-actual-icono");
         controles.indicador.texto = document.getElementById("detalleEstadoActual");
         controles.indicador.desde = document.getElementById("detalleEstadoDesde");
         controles.indicador.bebe = document.getElementById("indicadorBebe");
         // Información del episodio
         controles.detalle.fechaIngreso = document.getElementById("detalleFechaIngreso");
         controles.detalle.tiempoLabor = document.getElementById("detalleTiempoLabor");
         controles.detalle.unidadOrigen = document.getElementById("detalleUnidadOrigen");
         controles.detalle.unidadSalida = document.getElementById("detalleUnidadSalida");
         // tabs
         controles.tabs.movimientos= document.getElementById("detalleMovimientos"),
         controles.tabs.bebes= document.getElementById("detalleBebes"),
         //controles dentro de los tabs
         controles.tabs.botones = document.querySelectorAll(".labor-parto__tabs button");
         controles.tabs.tablaMovimientos = document.getElementById("tablaMovimientos");
         controles.tabs.tablaBebes = document.getElementById("tablaBebes");
         controles.tabs.botonRegistrarBebe =document.getElementById("registrarBebeLaborParto");

         // Alta del episodio
         controles.alta.botonSalidaTemporal = document.getElementById("botonSalidaTemporal");
         controles.alta.iconoSalidaTemporal = controles.alta.botonSalidaTemporal.querySelector("i");
         controles.alta.textoSalidaTemporal = controles.alta.botonSalidaTemporal.querySelector(".texto-boton");


         controles.alta.boton = document.getElementById("botonDarAlta");
         controles.alta.indicador = document.getElementById("indicadorAlta");
         controles.alta.indicadorSalidaTemporal = document.getElementById("indicadorSalidaTemporal");




         inicializarFiltrosEstado();
         inicializarSelectorEstados();


         const alta = estilosLaborParto.alta;


         controles.contenedor.style.setProperty(
            "--color-alta",
            alta.color
         );

         controles.contenedor.style.setProperty(
            "--fondo-alta",
            alta.fondo
         );

         controles.contenedor.style.setProperty(
            "--border-color-alta",
            alta.borderColor
         );

      }


      function inicializarListeners() {

         controles.tablaBody.addEventListener("click", async (event) => {

            const fila = event.target.closest(".labor-parto__fila");
            if (!fila) {
                  return;
            }

            // Limpiar selección anterior
            const filaSeleccionada = controles.tablaBody.querySelector(
                  ".labor-parto__fila--seleccionada"
            );

            if (filaSeleccionada) {
                  filaSeleccionada.classList.remove(
                     "labor-parto__fila--seleccionada"
                  );
            }

            // Toggle selección
            if (!fila.classList.contains("labor-parto__fila--seleccionada")) {
                  fila.classList.add(
                     "labor-parto__fila--seleccionada"
                  );


                  const episodioId = fila.dataset.episodioId;

                  if (estado.seleccionado === episodioId) {
                     return;
                  }

                  estado.seleccionado = episodioId;

                  estado.detalleEpisodio = null;
                  mostrarDetalleVacio();

                  await obtenerDetalleEpisodio();
            } else {
                  estado.seleccionado = null;
            }
         });

         //  tabs boton 
         controles.tabs.botones.forEach(boton => {

            boton.addEventListener("click", () => {
               activarTab(boton.dataset.tab);
            });

         });


         let timeoutBusqueda;

         controles.buscarPaciente.addEventListener("input", () => {
            clearTimeout(timeoutBusqueda);
            estado.busqueda = controles.buscarPaciente.value.trim();

            estado.pagina = 1;

            if (
               estado.busqueda.length > 0 &&
               estado.busqueda.length < 2
            ) {
               return;
            }

            timeoutBusqueda = setTimeout(() => {

               obtenerEpisodiosLP().then(() => {
                  renderizarTabla();
               });

            }, 900);

         });


         controles.contenedorFiltros.addEventListener("change", (event) => {

            const checkbox = event.target.closest(
               ".labor-parto__filtro-check"
            );

            if (!checkbox) {
               return;
            }

            const filtro = checkbox.closest(
               ".labor-parto__filtro"
            );

            filtro.classList.toggle(
               "labor-parto__filtro--activo",
               checkbox.checked
            );

            estado.filtrosEstado = Array.from(
               controles.filtrosEstado
            )
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) =>
               Number(
                  checkbox.closest(
                     ".labor-parto__filtro"
                  ).dataset.estado
               )
            );

            estado.pagina = 1;

            obtenerEpisodiosLP().then(() => {
               renderizarTabla();
            });
         });


         controles.paginaAnterior.addEventListener("click", () => {

            if (estado.pagina <= 1) {
               return;
            }

            estado.pagina--;

            obtenerEpisodiosLP().then(() => {
               renderizarTabla();
            });

         });


         controles.paginaSiguiente.addEventListener("click", () => {

            if (estado.pagina >= estado.totalPaginas) {
               return;
            }

            estado.pagina++;

            obtenerEpisodiosLP().then(() => {
               renderizarTabla();
            });

         });


         controles.selectorEstados.addEventListener("change", () => {
            actualizarBotonEstado();
         });



         controles.tabs.tablaMovimientos.addEventListener("dblclick", async (event) => {

            const fila = event.target.closest("tr[data-movimiento-id]");

            if (!fila) {
               return;
            }
            const movimientoId = fila.dataset.movimientoId;

            const resultado = await ManejarDetalleMovimientoLaborParto.open({
                  movimiento_id: movimientoId,
                  episodio: estado.detalleEpisodio
            })

            if (resultado) {
               await obtenerDetalleEpisodio();
            }

         });

         controles.tabs.tablaBebes.addEventListener("dblclick", async (event) =>{

            const fila = event.target.closest("tr[data-bebe-id]");
            if (!fila) return;
            const bebeId = fila.dataset.bebeId
            manejarBebe(bebeId)

         })

         controles.tabs.botonRegistrarBebe.addEventListener("click", () => manejarBebe());


         controles.botonAgregarEpisodio.addEventListener(
            "click",
            agregarEpisodio
         );

         controles.botonActualizarEstado.addEventListener(
            "click",
            cambiarEstado
         )

         controles.alta.boton.addEventListener(
            "click",
            darAlta
         )

         controles.alta.botonSalidaTemporal.addEventListener(
            "click",
            manejarSalidaTemporal
         )
      }

   //#endregion



   // #region 2. FILTROS Y CONTROLES VISUALES

      function inicializarFiltrosEstado() {
         const filtros = document.querySelectorAll(
            ".labor-parto__filtro"
         );

         filtros.forEach((filtro) => {

            const estado = estadosLaborParto.find(
                  (item) =>
                     item.value == filtro.dataset.estado
            );

            if (!estado) return;

            const icono = filtro.querySelector(
                  ".labor-parto__filtro-icono"
            );

            icono.innerHTML = IconosLaborParto.obtener(
                  estado.icono
            );

            filtro.style.setProperty(
                  "--color-estado",
                  estado.color
            );

            filtro.style.setProperty(
                  "--fondo-estado",
                  estado.fondo
            );

            filtro.style.setProperty(
                  "--border-color-estado",
                  estado.borderColor
            );
         });


         // FILTRO ESPECIAL: ALTAS
         const filtroAltas = filtros[4];

         if (filtroAltas) {

            const icono = filtroAltas.querySelector(
               ".labor-parto__filtro-icono"
            );

            icono.innerHTML = IconosLaborParto.obtener(
               "quirofano"
            );

            const alta = estilosLaborParto.alta;

            filtroAltas.style.setProperty(
               "--color-estado",
               alta.color
            );

            filtroAltas.style.setProperty(
               "--fondo-estado",
               alta.fondo
            );

            filtroAltas.style.setProperty(
               "--border-color-estado",
               alta.borderColor
            );
         }
      }


      function inicializarSelectorEstados() {
         estadosLaborParto.forEach((estado) => {

            const opcion = controles.selectorEstados.querySelector(
               `[data-estado="${estado.value}"]`
            );

            if (!opcion) {
               return;
            }

            opcion.style.setProperty(
               "--estado-color",
               estado.color
            );

            opcion.style.setProperty(
               "--estado-fondo",
               estado.fondo
            );

            opcion.style.setProperty(
               "--estado-border",
               estado.borderColor
            );

         });

      }


      function activarTab(nombreTab) {

         const contenidos = {
            movimientos: controles.tabs.movimientos,
            bebes: controles.tabs.bebes,
         };

         Object.values(contenidos).forEach(contenido => {
            contenido.classList.add("oculto");
         });

         controles.tabs.botones.forEach(boton => {
            boton.classList.remove("activo");
         });

         contenidos[nombreTab].classList.remove("oculto");

         const botonActivo = [...controles.tabs.botones].find(
            boton => boton.dataset.tab === nombreTab
         );

         if (botonActivo) {
            botonActivo.classList.add("activo");
         }

      }


      function actualizarPresentacionBotonEstado() {

         const episodio = estado.detalleEpisodio;

         const icono = controles.botonActualizarEstado.querySelector(
            ".material-symbols-outlined"
         );

         const texto = controles.botonActualizarEstado.querySelector(
            ".texto-boton"
         );

         const esRetorno = episodio?.salida_temporal === true;

         icono.textContent = esRetorno ? "assignment_return" : "save";

         texto.textContent = esRetorno
            ? "Registrar retorno"
            : "Actualizar estado";
      }


      function actualizarBotonEstado() {

         const episodio = estado.detalleEpisodio;
   

         if (!episodio || episodio.alta) {
            controles.botonActualizarEstado.disabled = true;
            return;
         }

         const esRetorno = episodio.salida_temporal; 


         const opcionSeleccionada =
            controles.selectorEstados.querySelector(
               'input[name="nuevoEstado"]:checked'
            );

         if (!opcionSeleccionada) {
            controles.botonActualizarEstado.disabled = true;
            return;
         }

         const estadoSeleccionado = Number(opcionSeleccionada.value);

         estado.nuevoEstado = estadoSeleccionado;

         if (esRetorno) {
            controles.botonActualizarEstado.disabled = false;
         } else {
            controles.botonActualizarEstado.disabled =
               estadoSeleccionado === episodio.estado_actual;
         }
      }


      function actualizarIndicadorAltaSalidaTemporal() {
         const episodio = estado.detalleEpisodio;

         const botonAlta = controles.alta.boton;
         const indicadorAlta = controles.alta.indicador;
         const botonSalidaTemporal = controles.alta.botonSalidaTemporal;
         const indicadorSalidaTemporal = controles.alta.indicadorSalidaTemporal;

         // Alta definitiva
         if (episodio.alta) {
            botonAlta.classList.add("oculto");
            indicadorAlta.classList.remove("oculto");

            botonSalidaTemporal.classList.add("oculto");
            indicadorSalidaTemporal.classList.add("oculto");

            return;
         }

         // Sin alta definitiva
         botonAlta.classList.remove("oculto");
         indicadorAlta.classList.add("oculto");

         // Salida temporal
         if (episodio.salida_temporal) {
            botonSalidaTemporal.classList.add("oculto");
            indicadorSalidaTemporal.classList.remove("oculto");
         } else {
            botonSalidaTemporal.classList.remove("oculto");
            indicadorSalidaTemporal.classList.add("oculto");
         }
      }


      function ocultarIndicadorAlta() {
         controles.alta.boton.classList.add("oculto");
         controles.alta.indicador.classList.add("oculto");
      }


      function ocultarIndicadorSalidaTemporal() {
         controles.alta.botonSalidaTemporal.classList.add("oculto");
         controles.alta.indicadorSalidaTemporal.classList.add("oculto");
      }


   //#endregion



   // #region 3. CONSULTAS Y TABLA DE EPISODIOS

      async function obtenerEpisodiosLP() {

         try {
            const data = await fetchData(
               API_URLS.listarEpisodiosAPI,
               {
                  pagina: estado.pagina,
                  por_pagina: estado.porPagina,
                  busqueda: estado.busqueda,
                  orden: estado.orden,
                  direccion: estado.direccion,
                  filtros_estado: estado.filtrosEstado
               }
            );
            if (data) {
               estado.episodios = data.episodios;
               estado.total = data.total;
               estado.totalPaginas = data.total_paginas;
               estado.totalFiltrado = data.total_filtrado;
               validarSeleccionActual();
            }

         } catch (error) {

            toastr.error(
               error.message,
               "Error al obtener los episodios"
            );

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
               return;
            }

            estado.detalleEpisodio = data;
            actualizarVistaDetalle();

         } catch (error) {
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
            actualizarRangoPaginacion();
            actualizarPaginacion();
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
                     data-episodio-id="${item.id}"
               >

                     <td class="labor-parto__columna-estado">
                        <div
                           class="labor-parto__estado-contenedor"
                           style="${estiloEstado}"
                           title="${item.estado_actual_texto}"
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
                                    ${nombrePaciente}
                                 </strong>

                                 <small>
                                    DNI- ${item.paciente__dni} - EXP- ${item.paciente__expediente_numero}
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
         actualizarRangoPaginacion();
         actualizarPaginacion();
      }


      function actualizarTotales() {
         const total = estado.total || 0;
         const totalFiltrado = estado.totalFiltrado || 0;
         controles.contador.textContent = total;
         controles.totalPaginacion.textContent = totalFiltrado;
      }


      function actualizarRangoPaginacion() {
         const totalFiltrado = estado.totalFiltrado || 0;

         if (totalFiltrado === 0) {
            controles.rango.textContent = "0";
            return;
         }

         const inicio = ((estado.pagina - 1) * estado.porPagina) + 1;
         const fin = Math.min(
            estado.pagina * estado.porPagina,
            totalFiltrado
         );

         controles.rango.textContent = `${inicio}-${fin}`;
      }


      function actualizarPaginacion() {

         const pagina = estado.pagina;
         const totalPaginas = estado.totalPaginas;

         controles.paginaActual.textContent =
            `Página ${pagina} de ${totalPaginas || 1}`;

         controles.paginaAnterior.disabled =
            pagina <= 1;

         controles.paginaSiguiente.disabled =
            pagina >= totalPaginas;
      }


   //#endregion

   

   // #region 4. DETALLE, MOVIMIENTOS Y BEBÉS


      function mostrarDetalleEpisodio() {
         controles.detallePacienteVacio.classList.add("oculto");
         controles.detalleEpisodio.classList.remove("oculto");
      }


      function mostrarDetalleVacio() {
         ocultarIndicadorAlta();
         ocultarIndicadorSalidaTemporal();
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
         actualizarPresentacionBotonEstado();
         actualizarBotonEstado();
         actualizarIndicadorAltaSalidaTemporal();
      }


      function actualizarDetalleEpisodio() {

         estado.nuevoEstado = null;

         const episodio = estado.detalleEpisodio;

         if (!episodio) {
            return;
         }

         controles.tabs.botonRegistrarBebe.style.display = episodio.alta ? "none" : "";

         const paciente = episodio.paciente;


         const nombre = concatenarLimpio(
            paciente.primer_nombre,
            paciente.segundo_nombre,
            paciente.primer_apellido,
            paciente.segundo_apellido
         );

         controles.paciente.nombre.textContent = nombre;

         controles.paciente.expediente.textContent =
         paciente.expediente_numero ?? "-";

         controles.paciente.edad.textContent =
            paciente.edad ?? "-";


         controles.paciente.dni.textContent = paciente.dni ?? "-"

         // Información del episodio
         controles.detalle.fechaIngreso.textContent =
            episodio.fecha_ingreso
               ? `${formatearFechaLocal(episodio.fecha_ingreso)} - ${formatearHoraLocal(episodio.fecha_ingreso)}`
               : "-";

         controles.detalle.unidadOrigen.textContent =episodio.unidad_entrada ?? "-";
         controles.detalle.unidadSalida.textContent =episodio.unidad_salida ?? "-";
         controles.detalle.tiempoLabor.textContent = episodio.tiempo_labor_parto ?? "-";

         const estadoInfo = episodio.estado_actual_info;

         if (estadoInfo) {
            
            controles.indicador.icono.innerHTML =
               IconosLaborParto.obtener(estadoInfo.icono);

            controles.indicador.icono.style.color = estadoInfo.color;
            controles.indicador.icono.style.backgroundColor = estadoInfo.fondo;
            controles.indicador.icono.style.border =`1px solid ${estadoInfo.borderColor}`;

            controles.indicador.texto.textContent = estadoInfo.texto;
            controles.indicador.texto.style.color = estadoInfo.color;

            controles.indicador.contenedor.style.backgroundColor =
               estadoInfo.fondo;


            if (episodio.alta) {
               controles.indicador.desde.textContent =
                  `Salida: ${formatearFechaLocal(episodio.fecha_alta)} - ${formatearHoraLocal(episodio.fecha_alta)}` ;
            } else {
               controles.indicador.desde.textContent =
                  `Hace ${episodio.duracion_estado}`;
            }
         }

         const bebe = episodio.bebes?.[0];

         if (bebe) {
            controles.indicador.bebe.style.display = "block";

            controles.indicador.bebe.style.color =
               bebe.sexo === "H"
                  ? "#4A80B8"
                  : "#C06A91";
         } else {
            controles.indicador.bebe.style.display = "none";
         }

         actualizarEstadoSeleccionado(episodio);
         renderizarMovimientos();
         renderizarBebes();

      }


      function actualizarEstadoSeleccionado(episodio) {

         const opciones = controles.selectorEstados.querySelectorAll(
            'input[name="nuevoEstado"]'
         );


         opciones.forEach(input => {
            input.checked = episodio.salida_temporal
               ? false
               : Number(input.value) === episodio.estado_actual;

            input.disabled = episodio.alta === true;
         });

         // Siempre comienza desactivado
         controles.botonActualizarEstado.disabled = true;
      }


      async function actualizarVistaEpisodio() {
         await obtenerEpisodiosLP();
         renderizarTabla();
         await obtenerDetalleEpisodio();
      }


      function obtenerDetalleMovimiento(movimiento) {

         if (movimiento.tipo === 1) {
            if (movimiento.estado_anterior_texto === null) {
               return `RETORNO → ${movimiento.estado_nuevo_texto}`;
            }

            return `${movimiento.estado_anterior_texto} → ${movimiento.estado_nuevo_texto}`;
         }

         if (movimiento.tipo === 2) {
            if (movimiento.es_salida_temporal) {
               return "SALIDA TEMPORAL — QUIRÓFANO";
            }

            if (movimiento.es_alta) {
               return `ALTA — ${movimiento.unidad_destino?.nombre ?? "-"}`;
            }

            return movimiento.unidad_destino?.nombre ?? "-";
         }

         if (movimiento.tipo === 3) {
            return movimiento.estado_nuevo_texto ?? "-";
         }
         return "-";
      }


      function renderizarMovimientos() {
         const movimientos = estado.detalleEpisodio?.movimientos ?? [];

         if (movimientos.length === 0) {
            controles.tabs.tablaMovimientos.innerHTML = `
               <tr>
                  <td colspan="4" class="labor-parto__vacio">
                     No hay movimientos registrados.
                  </td>
               </tr>
            `;
            return;
         }

         const filas = movimientos
            .filter((movimiento) => movimiento.id != null)
            .map((movimiento) => {
            const detalle = obtenerDetalleMovimiento(movimiento);

            const iconoMovimiento =
               iconosMovimiento[movimiento.tipo] ?? "help";

            return `
               <tr data-movimiento-id="${movimiento.id}">

                  <td class="labor-parto__columna-movimiento">
                     <span
                        class="material-symbols-outlined labor-parto__movimiento-icono"
                        title="${movimiento.tipo_texto}"
                     >
                        ${iconoMovimiento}
                     </span>
                  </td>

                  <td>
                     ${detalle}
                  </td>

                  <td>
                     ${formatearFechaLocal(movimiento.fecha_movimiento)}
                     ${formatearHoraLocal(movimiento.fecha_movimiento)}
                  </td>

                  <td>
                     ${movimiento.usuario ?? "-"}
                  </td>

               </tr>
            `;
         });

         controles.tabs.tablaMovimientos.innerHTML = filas.join("");
      }


      function renderizarBebes() {
      
         const bebes = estado.detalleEpisodio?.bebes ?? [];

         if (bebes.length === 0) {
            controles.tabs.tablaBebes.innerHTML = `
               <tr>
                  <td colspan="3" class="labor-parto__vacio">
                     No hay bebés registrados.
                  </td>
               </tr>
            `;

            return;
         }

         const filas = bebes.map((bebe) => {

            const iconoSexo = bebe.sexo === "H"
               ? "male"
               : bebe.sexo === "M"
                  ? "female"
                  : "help";

            return `
               <tr data-bebe-id="${bebe.id}">

                  <td class="labor-parto__columna-icono">
                     <div class="labor-parto__celda-icono">
                        <span class="material-symbols-outlined">
                           child_care
                        </span>
                        Bebé ${bebe.orden}
                     </div>
                  </td>

                  <td class="labor-parto__columna-icono">
                     <div class="labor-parto__celda-icono">
                        <span class="material-symbols-outlined">
                           ${iconoSexo}
                        </span>
                        ${bebe.sexo_texto ?? "-"}
                     </div>
                  </td>

                  <td>
                     ${
                        bebe.fecha_nacimiento
                           ? `${formatearFechaLocal(bebe.fecha_nacimiento)} ${formatearHoraLocal(bebe.fecha_nacimiento)}`
                           : "-"
                     }
                  </td>

               </tr>
            `;
         });

         controles.tabs.tablaBebes.innerHTML = filas.join("");
      }


      async function manejarBebe(bebeId = null) {

         if (!estado.detalleEpisodio) {
            return;
         }

         const config = {
            episodio: estado.detalleEpisodio,
         };


         if (bebeId !== null) {
            config.bebeId = bebeId;
         }

         const resultado = await ManejarBebeLaborParto.open(config);

         if (resultado?.guardado) {
            await actualizarVistaEpisodio();
         }
      }





   //#endregion



   // #region 5. OPERACIONES DEL EPISODIO

      async function agregarEpisodio() {

         const resultado = await ManejarEpisodioLaborParto.open({
            estadoInicial: estadosLaborParto[0],
            unidadesEntrada: unidadesEntradaLaborParto
         });


         if (resultado) {
            toastr.success(
               "Episodio de Labor y Parto registrado correctamente.",
               "Proceso realizado",
               { timeOut: 1500 }
            );

            await actualizarVistaEpisodio();
         }
      }


      async function cambiarEstado() {

         if (!estado.detalleEpisodio){
            return
         }

         if (!estado.nuevoEstado) {
            return;
         }


         const resultado = await ManejarMovimientoLaborParto.open({
               episodio:estado.detalleEpisodio,
               nuevoEstado:estado.nuevoEstado
         })


         if (resultado?.guardado) {
            toastr.success(
               "Movimiento de Labor y Parto registrado correctamente.",
               "Proceso realizado",
               { timeOut: 1500 }
            );

            await actualizarVistaEpisodio();
         }

      }


      async function darAlta() {

         if (!estado.detalleEpisodio) {
            return;
         }

         const resultado = await ManejarAltaLaborParto.open({
            episodio: estado.detalleEpisodio,
            unidadesSalida: unidadesSalidaLaborParto
         });

         if (resultado?.guardado) {
            await actualizarVistaEpisodio();
         }
      }

   //#endregion


   async function manejarSalidaTemporal() {
      const confirmado = await confirmarAccion({
         titulo: "Salida temporal a Quirófano",
         mensajes: [
            "El paciente será registrado como salida temporal hacia Quirófano.",
            "Su estado clínico actual se conservará hasta que se registre el retorno."
         ],
         icono: "warning",
         botonAfirmativo: "Continuar"
      });

      if (!confirmado) return;

      try {
         const response = await fetch(
            API_URLS.registrarSalidaTemporalLaborParto,
            {
               method: "POST",
               headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": window.CSRF_TOKEN,
               },
               body: JSON.stringify({
                  episodio_id: estado.detalleEpisodio.id,
               }),
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

            return;
         }

         if (response.status === 403) {
            toastr.warning(
               data.error ||
               "No tienes permisos para registrar la salida temporal."
            );

            return;
         }

         if (!response.ok) {
            throw new Error(
               data.error || "No se pudo registrar la salida temporal."
            );
         }

         // Actualizar los datos del episodio en pantalla.
         toastr.success(
            "La salida temporal se registró correctamente.",
            "Operación completada"
         );

         await actualizarVistaEpisodio();

      } catch (error) {
         console.error(
            "Error al registrar la salida temporal de Labor y Parto:",
            error
         );

         toastr.error(
            "No se pudo registrar la salida temporal. Inténtalo nuevamente.",
            "Error inesperado"
         );
      }
   }


   return {
      inicializar,
   };

})();


document.addEventListener('DOMContentLoaded', function () {
   PacientesLaborParto.inicializar();
})