document.addEventListener('DOMContentLoaded', function () {


    //#region  Listener Generales
    const contenedorTarjetasDias = document.querySelector(".contenedor-dias-semana");

    contenedorTarjetasDias.addEventListener("click", async function (e) {
        const tarjeta = e.target.closest(".configurar-periodo-dia-tarjeta");

        if (!tarjeta) return;

        const diaSemana = tarjeta.dataset.diaSemana;
        const idDiaLaboral = tarjeta.dataset.idDiaLaboral || null;

        /* Día quirúrgico → quitar */
        if (tarjeta.classList.contains("quirugico")) {
            await quitarDiaQuirurgico(idDiaLaboral);
            return;
        }

        /* Definir día quirúrgico */
        if (e.target.closest(".definir-quirurgico")) {
            await configurarDiaQuirurgico(
                contextoAgenda.periodoId,
                diaSemana
            );
            return;
        }

        /* Eliminar día laboral */
        if (e.target.closest(".eliminar")) {
            await llamarEliminarDiaLaboral(idDiaLaboral);
            return;
        }

        /* Definir / editar día laboral */
        const modal = await ManejarDiaLaboral.open({
            titulo: idDiaLaboral
                ? "Editar configuracion"
                : "Definir configuracion",
            diaNumero: diaSemana,
            diaID: idDiaLaboral,
            contexto: contextoAgenda
        });

        if (!modal) return;

        const resultado = modal.resultado;

        if (resultado) {
            await informarCambios({
                titulo: idDiaLaboral
                    ? "Cambios aplicados a la agenda"
                    : "Configuración creada correctamente",
                mensajes: construirMensajesCambios(resultado),
                icono: "info"
            });
        }
    });
    //#endregion




    async function configurarDiaQuirurgico(periodoId, diaNumero) {

        const confirmado = await confirmarAccion({
            titulo: "Configurar día quirúrgico",
            mensajes: [
                "El día seleccionado será configurado como día quirúrgico. " +
                "No se podrán registrar cupos de atención para este día.",
                "¿Desea continuar?"
            ],
            icono: "warning",
            botonAfirmativo: "Sí",
            botonNegativo: "Cancelar"
        });

        if (!confirmado) return false;

        const guardo = await DiaQuirurgicoHelpers.definirDiaQuirugico({
            periodoId,
            diaNumero
        });

        if (!guardo) return false;

        toastr.success(
            "Día quirúrgico configurado correctamente.",
            "Proceso realizado",
            {
                timeOut: 1000,
                onHidden: () => window.location.reload()
            }
        );

        return true;
    }



    async function quitarDiaQuirurgico(diaLaboralId) {

        const confirmado = await confirmarAccion({
            titulo: "Quitar día quirúrgico",
            mensajes: [
                "El día seleccionado dejará de estar configurado como día quirúrgico.",
                "¿Desea continuar?"
            ],
            icono: "warning",
            botonAfirmativo: "Sí, quitar",
            botonNegativo: "Cancelar"
        });

        if (!confirmado) return false;

        const quito = await DiaQuirurgicoHelpers.quitarDiaQuirugico({
            diaLaboralId
        });

        if (!quito) return false;

        toastr.success(
            "Día quirúrgico quitado correctamente.",
            "Proceso realizado",
            {
                timeOut: 1000,
                onHidden: () => window.location.reload()
            }
        );

        return true;
    }



    async function llamarEliminarDiaLaboral(diaLaboralId) {
        const confirmado = await confirmarAccion({
            titulo: "Eliminar día laboral",
            mensajes: [
                "El día laboral seleccionado y su configuración de cupos serán desactivados.",
                "Las <strong>citas asociadas podrían quedar sin cupo </strong> asignado y requerir reprogramación.",
                "<strong>¿Desea continuar?</strong>"
            ],
            icono: "warning",
            botonAfirmativo: "Eliminar",
            botonNegativo: "Cancelar"
        });

        if (!confirmado) return false;

        const eliminado = await AgendaMedicaHelper.eliminarDiaLaboral(diaLaboralId);


        if (eliminado?.success && eliminado?.resultado) {

            await informarCambios({
                titulo: "Día laboral eliminado",
                mensajes: construirMensajesCambios(eliminado.resultado),
                icono: "info"
            });
            window.location.reload();

        }


        return;
    }




})