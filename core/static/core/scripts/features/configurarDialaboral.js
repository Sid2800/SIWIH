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
        const modal = await ManejarDiaLaboral.open(
            {diaNumero:diaSemana, diaID:idDiaLaboral, contexto:contextoAgenda }
        )

        console.table(modal);
    })
    //#endregion



})