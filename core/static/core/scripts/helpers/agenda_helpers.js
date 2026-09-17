"use strict";

const AgendaMedicaHelper = (function () {

   async function cargar(criterios) {

      try {
         const data = await fetchData(
            API_URLS.agendaMedicaAPI,
            criterios
         );

         if (!Array.isArray(data.entries)) {
            throw new Error(
               "Respuesta inválida del servidor"
            );
         }

         if (!Array.isArray(data.workingDays)) {
            throw new Error(
               "Respuesta inválida del servidor"
            );
         }

         return {
            entries: data.entries,
            workingDays: data.workingDays
         };

      } catch (error) {

         console.error(
            "Error al cargar la agenda médica:",
            error
         );

         throw error;
      }

   }

   async function eliminarDiaLaboral(diaLaboralId) {
      if (!diaLaboralId) return false;

      try {
         const response = await fetch(API_URLS.eliminarDiaLaboral, {
               method: "DELETE",
               headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": window.CSRF_TOKEN
               },
               body: JSON.stringify({
               diaID: diaLaboralId,
               })
         });

         const respuesta = await response.json();

         if (response.status === 400) {
               toastr.warning(respuesta.error, "Error de validación");
               return false;
         }

         if (response.status >= 500) {
               throw new Error(respuesta.error || "No se pudo eliminar el día laboral.");
         }

         return respuesta;

      } catch (error) {
         toastr.error(error.message, "Error al eliminar el día laboral");
         return false;
      }
   }



   return {
      cargar,
      eliminarDiaLaboral
   };

})();


const DiaQuirurgicoHelpers = (() => {

   async function definirDiaQuirugico(data) {
      if (!data) return false;

      try {
         const response = await fetch(API_URLS.definirDiaQuirugico, {
            method: "POST",
            headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": window.CSRF_TOKEN
            },
            body: JSON.stringify({
               periodoId: data.periodoId,
               diaNumero: data.diaNumero
            })
         });

         const respuesta = await response.json();

         if (response.status === 400) {
            toastr.warning(respuesta.error, "Error de validación");
            return false;
         }

         if (response.status >= 500) {
            throw new Error(respuesta.error || "No se pudo configurar el día quirúrgico.");
         }

         return true;

      } catch (error) {
         toastr.error(error.message, "Error al configurar el día quirúrgico");
         return false;
      }
   }


   async function quitarDiaQuirugico(data) {
      if (!data) return false;

      try {
         const response = await fetch(API_URLS.quitarDiaQuiurgico, {
            method: "DELETE",
            headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": window.CSRF_TOKEN
            },
            body: JSON.stringify({
               diaLaboralId: data.diaLaboralId,
            })
         });

         const respuesta = await response.json();

         if (response.status === 400) {
            toastr.warning(respuesta.error, "Error de validación");
            return false;
         }

         if (response.status >= 500) {
            throw new Error(respuesta.error || "No se pudo quitar el día quirúrgico.");
         }

         return true;

      } catch (error) {
         toastr.error(error.message, "Error al quitar el día quirúrgico");
         return false;
      }
   }

   return { 
      definirDiaQuirugico,
      quitarDiaQuirugico
   };

})();



const TipoAusenciaLoader = (function () {

      async function cargar(select = null) {
         try {
               const data = await fetchData(
                  API_URLS.listarTiposAusencia
               );

               if (!Array.isArray(data)) {
                  throw new Error("Respuesta inválida del servidor");
               }

               if (select) {
                  select.innerHTML = '';

                  data.forEach(item => {
                     const texto = `${item.texto}`;

                     const option = new Option(
                           texto,
                           item.value
                     );
                     select.appendChild(option);
                  });
               }

               return data;

         } catch (error) {
               console.error("Error cargando tipos de ausencias:", error);
               toastr.error("No se pudieron cargar los tipos de ausencias.");
               return [];
         }
      }

      return {
         cargar
      };

})();



function construirMensajesCambios(resultado, mensajeFinal = null) {
   const mensajes = [];

   const { cupos = {}, citas = {} } = resultado;

   const hayCambiosCupos =
      (cupos.agregados || 0) > 0 ||
      (cupos.editados || 0) > 0 ||
      (cupos.reordenados || 0) > 0 ||
      (cupos.eliminados || 0) > 0;

   if (hayCambiosCupos) {

      mensajes.push(`
         <strong class="mensaje-impacto-titulo">Cupos</strong>
      `);

      if ((cupos.agregados || 0) > 0) {
         mensajes.push(
               `Se agregaron <strong>${cupos.agregados}</strong> cupos a la agenda.`
         );
      }

      if ((cupos.editados || 0) > 0) {
         mensajes.push(
               `Se editaron <strong>${cupos.editados}</strong> cupos existentes.`
         );
      }

      if ((cupos.reordenados || 0) > 0) {
         mensajes.push(
               `Se reorganizaron <strong>${cupos.reordenados}</strong> cupos debido a los cambios en la configuración.`
         );
      }

      if ((cupos.eliminados || 0) > 0) {
         mensajes.push(
               `Se bloquearon <strong>${cupos.eliminados}</strong> cupos programados.`
         );
      }
   }

   const hayCambiosCitas =
      (citas.sin_cupo || 0) > 0 ||
      (citas.cambio_horario || 0) > 0;

   if (hayCambiosCitas) {

      mensajes.push(`
         <strong class="mensaje-impacto-titulo">Citas</strong>
      `);

      if ((citas.sin_cupo || 0) > 0) {
         mensajes.push(
               `<strong>${citas.sin_cupo}</strong> ${
                  citas.sin_cupo === 1 ? "cita quedó" : "citas quedaron"
               } sin cupo asignado y requieren reprogramación.`
         );
      }

      if ((citas.cambio_horario || 0) > 0) {
         mensajes.push(
               `<strong>${citas.cambio_horario}</strong> ${
                  citas.cambio_horario === 1 ? "cita modificó" : "citas modificaron"
               } su horario de atención.`
         );
      }
   }

   if (!mensajes.length) {
      mensajes.push(
         mensajeFinal ||
         "La operación fue realizada correctamente sin generar cambios en la agenda."
      );
   }

   return mensajes;
}