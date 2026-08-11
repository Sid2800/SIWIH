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

      async function cargar(select = null, uso = "general") {
         try {
               const data = await fetchData(
                  API_URLS.listarUnidadClinica,
                  { uso: uso }
               );

               if (!Array.isArray(data)) {
                  throw new Error("Respuesta inválida del servidor");
               }

               if (select) {
                  select.innerHTML = '';

                  data.forEach(item => {
                     const texto = `${item.nombre} (${item.tipo})`;

                     const option = new Option(
                           texto,
                           item.clave
                     );

                     option.dataset.tipo = item.tipo;
                     option.dataset.origen = item.origen;

                     select.appendChild(option);
                  });
               }

               return data;

         } catch (error) {
               console.error("Error cargando unidades clínicas:", error);
               toastr.error("No se pudieron cargar las unidades clínicas.");
               return [];
         }
      }

      return {
         cargar
      };

})();