// Espera a que el DOM esté completamente cargado antes de ejecutar el código
document.addEventListener("DOMContentLoaded", () => {

//#region MenuPrincipal

      const logo = document.getElementById("logo");
      const aside = document.querySelector(".barra-navegacion");
      const spans = aside.querySelectorAll("span");
      const palanca = document.getElementById("switch");
      const bolita = document.getElementById("bolita");
      const menu = document.querySelector(".ocultar-mostrar-barra-navegacion");
      const main = document.querySelector("main");

      const botonCerrarSesion = document.getElementById("bp-cerrar-usuario__boton");

      // Inicializa el estado guardado al cargar la página
      initBarraNavegacion(aside, spans, main);
      initModoOscuro();

      // Listener para el menú de ocultar/mostrar la barra de navegación
      menu.addEventListener("click", () => {
         toggleBarraNavegacion(aside, menu);
      });

      // Listener para el logo que minimiza/maximiza la barra de navegación
      logo.addEventListener("click", () => {
         toggleMinimizarBarra(aside, main, spans);
      });

      // Listener para la palanca que cambia el modo oscuro
      palanca.addEventListener("click", () => {
         toggleModoOscuro(bolita);
      });


   // Función para inicializar la barra de navegación
   function initBarraNavegacion(aside, spans, main) {
      if (localStorage.getItem("barraNavegacion") === "mini") {
         aside.classList.add("barra-navegacion-mini");
         spans.forEach(span => {
            span.classList.add("oculto");
         });
         main.classList.add("min-main");
         botonCerrarSesion.classList.add("bp-cerrar-usuario__boton-oculto"); // ocultar boton cerrar cesion
      }
      aside.classList.add("barra-navegacion-mostrar2");
   }

   // Función para inicializar el modo oscuro
   function initModoOscuro() {
      const modo = localStorage.getItem("modo");
      if (modo === "oscuro") {
         document.body.classList.add("darkmode");
         document.getElementById("bolita").classList.add("bp-modo-oscuro-switch__bolita-encendido");
      }
   }

   // Función para alternar la barra de navegación
   function toggleBarraNavegacion(aside, menu) {
      aside.classList.toggle("barra-navegacion-mostrar");
      // Cambia la visibilidad de los elementos de menú
      if (aside.classList.contains("barra-navegacion-mostrar")) {
         menu.children[0].style.display = "none"; // Oculta
         menu.children[1].style.display = "block"; // Muestra
      } else {
         menu.children[0].style.display = "block"; // Muestra
         menu.children[1].style.display = "none"; // Oculta
      }
   }

   // Función para alternar la minimización de la barra
   function toggleMinimizarBarra(aside, main, spans) {
      aside.classList.toggle("barra-navegacion-mini");
      main.classList.toggle("min-main");
      botonCerrarSesion.classList.toggle ("bp-cerrar-usuario__boton-oculto"); // ocultar boton cerrar cesion
      spans.forEach(span => {
         span.classList.toggle("oculto");
      });

      // Guardar el estado en localStorage
      if (aside.classList.contains("barra-navegacion-mini")) {
         localStorage.setItem("barraNavegacion", "mini");
      } else {
         localStorage.setItem("barraNavegacion", "normal");
      }
   }

   // Función para alternar el modo oscuro
   function toggleModoOscuro(bolita) {
      const body = document.body;
      body.classList.toggle("darkmode");
      bolita.classList.toggle("bp-modo-oscuro-switch__bolita-encendido");

      // Guardar el estado del modo en localStorage
      if (body.classList.contains("darkmode")) {
         localStorage.setItem("modo", "oscuro");
      } else {
         localStorage.setItem("modo", "claro");
      }
   }

   //#region Cerrar Sesión
   const btnCerrarSesion = document.getElementById('cerrar-sesion-btn');

   if (btnCerrarSesion) {
      btnCerrarSesion.addEventListener('click', async () => {
         const confirmado = await confirmarAccion(
            '¿Estás seguro?',
            'Estás a punto de cerrar sesión.'
         );

         if (confirmado) {
            document.getElementById('bp-cerrar-usuario__boton').submit();
         }
      });
   }
   
   //#endregion

//#region 





//#region Notificaciones   

      toastr.options = {
      "closeButton": true, // Mostrar botón para cerrar
      "debug": false,
      "newestOnTop": true,
      "progressBar": true, // Barra de progreso
      "positionClass": "toast-bottom-right", // Ubicación
      "preventDuplicates": true,
      "onclick": null,
      "showDuration": "5000", // Duración de la aparición
      "hideDuration": "1000", // Duración del desvanecimiento
      "timeOut": "5000", // Tiempo hasta que la notificación desaparece
      "extendedTimeOut": "1000", // Tiempo adicional de espera
      "showEasing": "swing",
      "hideEasing": "linear",
      "showMethod": "fadeIn", // Método de aparición
      "hideMethod": "fadeOut" // Método de desvanecimiento
      };

      // Selecciona todos los elementos de mensaje
      document.querySelectorAll('.toast-message').forEach(function(el) {
         var message = el.value;
         var type = el.getAttribute('data-type');

         // Muestra el mensaje en Toastr según su tipo
         if (type === "success") {
            toastr.success(message);
         } else if (type === "error") {
            toastr.error(message);
         } else if (type === "warning") {
            toastr.warning(message);
         } else {
            toastr.info(message);
         }
      });

//#region 







//#region modal Cambio de Zonza

   const zonaBase = document.getElementById("bp-base-zona");


   zonaBase.addEventListener("click", async function (){
      let data = await CambiarModal(); 
      if(data && zonaBase){
         zonaBase.textContent = data.nombre_zona;
         zona = data.zona; // variable global

      }
   });



   async function CambiarModal(){
      let resultado;
      const modal =await Swal.fire({
         title: "Cambiar Zona Activa",
         html: `
                  <div>
                     <form method="post" class="">
                     <fieldset class="modalCambiarZona">
                     <legend>Seleccione la nueva zona</legend>
                           <select id="modal-id-zona" name="zona" class="formularioCampo-select">
                           </select>
                     </fieldset>
                     </form>
                  </div>
               `,
         showCancelButton: true,
         showCloseButton: true,
         confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
         cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
         customClass: {
            popup: 'contenedor-modal-sector',
            title: 'contener-modal-titulo',
            content: 'contener-modal-contenido',
            confirmButton: 'contener-modal-boton-confirmar',
            cancelButton: 'contener-modal-boton-cancelar',
         },
         didOpen: async () => {
            // Añadir clases personalizadas a los botones del modal
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) {
               actionsContainer.classList.add('contener-modal-contenedor-botones-min');
            }
         
            // Añadir clases personalizadas al contenedor HTML del modal
            const htmlContainer = document.querySelector('.swal2-html-container');
            if (htmlContainer) {
               htmlContainer.classList.add('contener-modal-contenedor-html');
            }
         
            // Obtener el select de zonas dentro del modal
            const zonaSelect = document.querySelector('#modal-id-zona');
         
            // Limpiar el select
            if (zonaSelect) {
               zonaSelect.innerHTML = '';
            }
         
            // Cargar zonas desde el backend
            try {
               const data = await fetchData(urls["listarZona"]);
         
               if (Array.isArray(data) && data.length > 0) {
                  data.forEach((item, index) => {
                     const option = new Option(
                        item.nombre_zona,
                        item.codigo,
                        index === 0, 
                        index === 0
                     );
                     zonaSelect.appendChild(option);
                  });
               } else {
                  console.warn("No se encontraron zonas.");
               }
            } catch (error) {
               console.error("Error al cargar zonas:", error);
            }


         }
      });

      if (modal.isConfirmed) {
         const zona = document.querySelector('#modal-id-zona').value; // ← CORREGIDO
      
         try {
            const response = await fetch(urls["cambiarZona"], {
               method: "POST",
               headers: {
                  "Content-Type": "application/json"
               },
               body: JSON.stringify({
                  zona: zona
               })
            });
      
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
      
            const data = await response.json();
      
            if (data.zona) {
               resultado = data;
               Swal.close(); // Cerrar el modal solo si todo va bien
            } else {
               toastr.error("Existe un problema al cambiar la zona");
            }
      
         } catch (error) {
            toastr.error("Error al cambiar la zona: " + error.message);
         }
      }
      
      return resultado;

   }



//#endregion




});



