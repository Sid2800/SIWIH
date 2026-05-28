document.addEventListener('DOMContentLoaded', function () {

    //#region  Listener Generales
    const contenedorTarjetasDias = document.querySelector(".contenedor-dias-semana");

    contenedorTarjetasDias.addEventListener('click', async function (e) {
        const tarjeta = e.target.closest(".configurar-periodo-dia-tarjeta");

        if (!tarjeta) {
            return;
        }

        const diaSemana = tarjeta.dataset.diaSemana 
        const idDiaLaboral = tarjeta.dataset.idDiaLaboral || null;
        ManejarDiaLaboral.open(
            {diaNumero:diaSemana, diaID:idDiaLaboral, contexto:contextoAgenda }
        )
    })
    //#endregion



})