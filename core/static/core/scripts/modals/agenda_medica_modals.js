const ManejarPeriodoLaboral = (function (){

    async function open(config ={}) {
        return await Swal.fire({
            title: `<span class="material-symbols-outlined">work</span> Agregar Periodo Laboral`,
            html: `
                <div class="tituloFormulario-subrallado"></div>
                <form method="post" class="formulario" id="formulario-model-defuncion">
                    <fieldset class="modalPeriodoLaboralCampos">
                        <legend>Personal de Salud</legend>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-personal-salud">Nombre:</label>
                            <select id="modal-periodo-laboral-personal-salud" class="formularioCampo-select" name="personal_salud">
                            </select>
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-especialidad">Especialidad:</label>
                            <input type="text" id="modal-periodo-laboral-especialidad" class="formularioCampo-text" name="especialidad" readonly>
                            </select>
                        </div>
                        

                        <input type="hidden" id="modal-periodo-laboral-id" name="idPeriodoLaboral">
                    </fieldset>

                    <fieldset class="modalPeriodoLaboralCampos">
                        <legend>Periodo Laboral</legend>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-fecha-inicial">Fecha inicial</label>
                            <input type="date" id="modal-periodo-fecha-inicial" name="fecha_inicial"  class="formularioCampo-date" required>
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-fecha-final">Fecha final</label>
                            <input type="date" id="modal-periodo-fecha-final" name="fecha_final" class="formularioCampo-date">
                        </div>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-jornada">Jornada:</label>
                            <select id="modal-periodo-laboral-jornada" class="formularioCampo-select" name="jornada">
                            </select>
                        </div>

                    </fieldset>


                    <fieldset class="modalPeriodoLaboralCampos" id="modal-campos-defuncion-registros" style="display: none;">
                    <legend>Detalles del registro</legend>
                    <div class="formularioCampoModal">
                        <label for="Fregistro">Registrado</label>
                        <input type="text" id="modal-defuncion-detalles-registro" class="formularioCampo-text" disabled>
                    </div>
                    </fieldset>
                </form>
            `,
            showCancelButton: true,
            showCloseButton: true,
            confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
            cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
            customClass: {
                popup: 'contener-modal-defuncion',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'

            },
            didOpen: () => inicializar(config)
        });
    }

    async function inicializar(config){
        console.log(config);
        const titleElement = Swal.getTitle(); 
    }

    return { open };

})();