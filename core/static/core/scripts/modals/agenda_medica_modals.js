const ManejarPeriodoLaboral = (function (){

    async function open(config ={}) {
        const {
            titulo = "Agregar Periodo Laboral",
            periodoID = null
        } = config;

        const modal = await Swal.fire({
            title: `<span class="material-symbols-outlined">work</span> ${titulo}`,
            html: `
                <div class="tituloFormulario-subrallado"></div>
                <form method="post" class="formulario" id="formulario-modal-periodo-laboral">
                    <fieldset class="modalPeriodoLaboralCampos">
                        <legend>Personal de Salud</legend>

                        <div class="formularioCampoModal">
                            <label for="modal-periodo-laboral-personal-salud">Nombre:</label>
                            <div id="modal-periodo-laboral-personal-salud" class="" name="personal_salud"></div>
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
                popup: 'contenedor-modal-periodo-laboral',
                title: 'contener-modal-titulo',
                confirmButton: 'contener-modal-boton-confirmar',
                cancelButton: 'contener-modal-boton-cancelar'

            },
            didOpen: () => inicializar(periodoID),
            preConfirm: () => {
                const personal = document.querySelector('#modal-periodo-laboral-personal-salud').value;
                const jornada = document.getElementById("modal-periodo-laboral-jornada").value;
                const fechaInicio = document.getElementById("modal-periodo-fecha-inicial").value;
                const fechaFinal = document.getElementById("modal-periodo-fecha-final").value;

                if (!personal) {
                    Swal.showValidationMessage("Debe seleccionar un medico");
                    return false;
                }


                if (fechaFinal && fechaFinal < fechaInicio) {
                    Swal.showValidationMessage("La fecha final no puede ser menor que la inicial");
                    return false;
                }

                return {
                    personal,
                    jornada,
                    fechaInicio,
                    fechaFinal
                };
                
            }

        });

        if (modal.isConfirmed){
            const formData = modal.value;
            await guardarPeriodo(formData);
        }

        return modal
    }

    async function inicializar(periodoID){
        const personalSalud = document.getElementById("modal-periodo-laboral-personal-salud");
        const especialidad = document.getElementById("modal-periodo-laboral-especialidad");
        
        
        // Traer, el persona clinico
        let data = await PersonalClinicoLoader.cargar();

        const opciones = data.map(item => ({
            value: item.id,
            label: item.nombre,
            customData: item.especialidad__nombre_especialidad,
            description: item.especialidad__nombre_especialidad
        }));

        if (personalSalud.virtualSelect) {
            personalSalud.virtualSelect.destroy();
        }

        // inicializar el vistual select 
        VirtualSelect.init({
            ele: '#modal-periodo-laboral-personal-salud',
            options: opciones,
            hasOptionDescription: true,
            searchPlaceholderText: 'Buscar...',
            search: true,
            placeholder: 'Seleccione',
            additionalClasses: 'custom-wrapper',
            additionalDropboxClasses: 'custom-dropbox',
        }); 

        // listnere de select 
        const slect = document.querySelector('#modal-periodo-laboral-personal-salud')
        slect._handler  = function (){
            const options = slect.getSelectedOptions();
            if (!options) { 
                especialidad.value = ""; 
                return; 
            }
            especialidad.value = options.customData || "";
        }
        slect.addEventListener('change', slect._handler)

        // definir las fechas iniciales max y demas 
        const fechaInicio = document.getElementById("modal-periodo-fecha-inicial");
        const fechaFinal = document.getElementById("modal-periodo-fecha-final");

        const hoy = fechaManana(false);

        fechaInicio.value = hoy;
        fechaInicio.min = hoy;

        fechaFinal.min = hoy;
        fechaFinal.value = hoy;

        // jornada laboral 
        const jornada = document.getElementById("modal-periodo-laboral-jornada");
        await JornadaLoader.cargar(jornada);


    }

    async function guardarPeriodo(formData){
        console.log("HOLa");
        console.log(formData);
        if (!formData){
            return
        }

        try {
                const csrfToken = window.CSRF_TOKEN;
                const response = await fetch(API_URLS.guardarDefuncion, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken 
                },
                body: JSON.stringify({
                    unidad_clinica: formData.unidad_clinica, 
                    fecha: formData.fecha,
                    motivo: formData.motivo,
                    tipo: formData.tipo,
                    idDefuncion: formData.idDefuncion,
                    idPaciente: paciente.id
                })
                });
                
                const data = await response.json();
                if (!response.ok) throw new Error(`${data.error}`);
                
                if (data.guardo) {
                resultado = data;
                Swal.close();
                } 

            } catch (error) {
                toastr.error("Error al guardar la defuncion " + error.message);
            }
    }

    return { open };

})();