
const PersonalClinicoLoader = (function () {

    async function cargar(select = null) {
        try {
            const data = await fetchData(API_URLS.listarPersonalClinicoAPI);

            if (!Array.isArray(data)) {
                throw new Error("Respuesta invalida del servidor");
            }


            if (select) {
                select.innerHTML = '';

                data.forEach(item => {
                    const option = new Option(item.nombre, item.id);
                    option.dataset.especialidad =
                        item.especialidad__nombre_especialidad || "";
                    select.appendChild(option);
                });
            }

            return data;

        } catch (error) {
            console.error("Error cargando personal clinico:", error);
            toastr.error("No se lograron cargar el personal clinico");
            return [];
        }
    }

    return {
        cargar
    };

})();


const JornadaLoader = (function () {

    async function cargar(select = null) {
        try {
            const data = await fetchData(API_URLS.listarJornadaLaboralAPI);

            if (!Array.isArray(data)) {
                throw new Error("Respuesta invalida del servidor");
            }

            if (select) {
                select.innerHTML = '';

                data.forEach(item => {

                    const texto = `${item.nombre_jornada_laboral} | ${formatearHora(item.hora_inicio)} - ${formatearHora(item.hora_fin)}`;
                    const option = new Option(texto, item.id);
                    select.appendChild(option);
                });
            }

            return data;

        } catch (error) {
            console.error("Error cargando jornadas:", error);
            toastr.error("No se lograron cargar las jornadas");
            return [];
        }
    }

    return {
        cargar
    };

})();