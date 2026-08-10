document.addEventListener('DOMContentLoaded', function () {


    console.table(contextoAgenda);
    //#region  Listener Generales
    const contenedorTarjetasDias = document.querySelector(".contenedor-dias-semana");

    contenedorTarjetasDias.addEventListener('click', async function (e) {
        const tarjeta = e.target.closest(".configurar-periodo-dia-tarjeta");

        if (!tarjeta) {
            return;
        }

        const diaSemana = tarjeta.dataset.diaSemana 
        const idDiaLaboral = tarjeta.dataset.idDiaLaboral || null;

        const modal = await ManejarDiaLaboral.open({
            titulo: idDiaLaboral ? "Editar configuracion" : "Definir configuracion",
            diaNumero:diaSemana, 
            diaID:idDiaLaboral, 
            contexto:contextoAgenda 
        })

        if (!modal) {
            return;
        }

        toastr.success(
            idDiaLaboral
                ? "Configuración del día actualizada correctamente."
                : "Configuración del día creada correctamente.",
            "Proceso realizado",
            {
                timeOut: 1500,
                onHidden: () => window.location.reload()
            }
        );
    })
    //#endregion



})