const ModalGaleria = (function () {


    
    async function open(config = {}) {
        
        const modal = await Swal.fire({

            title: `<i class="bi bi-images"></i> Galería ${config.titulo || ""}`,

            html: `
                <div class="tituloFormulario-subrallado"></div>

                <div class="modal-galeria-contendor-data">
                    <div class="modal-galeria-contendor-data-encabezado" id="modalGaleriaHeader"></div>
                    <div class="modal-galeria-contendor-imagenes fieldset-falso">
                        <span class="form-subtitulo-fieldset-falso">Estudios Registrados</span>

                        <div id="ui-gallery" class="ui-gallery"></div>

                    </div>
                </div>
            `,

            showCloseButton: true,
            showConfirmButton: true,
            confirmButtonText: `<i class="bi bi-box-arrow-in-left"></i> VOLVER`,
            
            customClass: {
                popup: "contenedor-modal-galeria",
                title: 'contener-modal-titulo',
                htmlContainer: 'html-modal-galeria',
                actions: 'contener-modal-contenedor-botones-min',
                confirmButton: 'contener-modal-boton-confirmar',
            },

            didOpen: () => {
                inicializar(config);
            }

        });

        return modal;
    }

    // ===== INICIALIZAR CONTENIDO =====
    function inicializar(config) {

        renderDatos(config.datos);
        //obtenerEstudio()
        obtenerData(config.parametros);

    }

    // ===== RENDER DATOS =====
    function renderDatos(datos = {}) {

        const header = document.getElementById("modalGaleriaHeader");

        if (!header || !datos) return;

        Object.entries(datos).forEach(([label, value]) => {

            const fila = document.createElement("div");
            fila.className = "modalGaleriaDato";

            fila.innerHTML = `
                <span class="modalGaleriaLabel">${label}</span>
                <span class="modalGaleriaValor">${value}</span>
            `;

            header.appendChild(fila);
        });
    }

    // ===== RENDER IMAGENES =====
    function inicializarGaleria(data, titulo_album) {

        const contenedor = document.getElementById("ui-gallery");
        ControlGaleria.render(contenedor, data, titulo_album);
    }


    async function obtenerData(parametros){

        let titulo_album = parametros.tituloAlbum ? parametros.tituloAlbum : ""; 

        if (!parametros?.idEvaluacion || !parametros?.idPaciente) {
            toastr.error("No se pudo identificar la evaluación", "Galería");
            return;
        }

        try {
            const params = new URLSearchParams({
                id: parametros.idEvaluacion,
                id_paciente: parametros.idPaciente
            });

            const url = `${urls.obtenerImagenesEvaluacion}?${params}`;

            const resp = await fetch(url);

            if (!resp.ok) {
                let errorMsg = "Error consultando imágenes";

                try {
                    const errorData = await resp.json();
                    errorMsg = errorData.error || errorMsg;
                } catch {}

                throw new Error(errorMsg);
            }

            const data = await resp.json();

            
            if (!data.success) {
                toastr.error(data.error || "Error obteniendo imágenes", "Galería");
                return;
            }
            else if (data.media_server_offline){
                toastr.error("El servicio de imágenes no se encuentra disponible", "Galería");
                return;
            }
            inicializarGaleria(data.data,titulo_album);

        } catch (error) {
            toastr.error(error.message,"Galeria");
        }
    }



    // ===== API PUBLICA =====
    return {
        open
    };

})();