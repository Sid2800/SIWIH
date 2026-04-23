async function cargarSalas(select) {
   if (!select) return;

   try {
      const data = await fetchData(urls["listarSala"]);

      select.innerHTML = '';

      const placeholder = new Option("SELECCIONE UNA SALA", "");
      select.appendChild(placeholder);

      if (Array.isArray(data) && data.length > 0) {
         data.forEach(item => {
            const option = new Option(
               concatenarLimpio(item.nombre_sala, ' | ', item.servicio__nombre_corto),
               item.id
            );
            select.appendChild(option);
         });
      } else {
         console.warn("No se encontraron salas.");
      }

      } catch (error) {
         console.error("Error al cargar salas:", error);
         toastr.error("No se pudieron cargar las salas");
      }
}

const UnidadClinicaLoader = (function () {

   async function cargar(select, uso = "general") {
      if (!select) return;

      try {
         // construir URL correctamente


         const data = await fetchData(API_URLS.listarDependencias, { uso: uso });

         // limpiar select
         select.innerHTML = '';

         // placeholder
         select.appendChild(new Option("SELECCIONE UBICACIÓN", ""));

         if (Array.isArray(data) && data.length > 0) {

            data.forEach(item => {
               const texto =   `${item.nombre}  (${item.tipo})` ;
               const option = new Option(
                  texto,            // texto visible
                  item.clave        // valor: "S-1", "E-2", "A-3"
               );

               // opcional: metadata útil
               option.dataset.tipo = item.tipo;
               option.dataset.origen = item.origen;

               select.appendChild(option);
            });

         } else {
            console.warn("No hay dependencias disponibles.");
         }

      } catch (error) {
         console.error("Error cargando dependencias:", error);
         toastr.error("No se pudieron cargar las dependencias");
      }
   }

   return {
      cargar
   };

})();