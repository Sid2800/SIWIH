const ModalGaleriaUsuario = (function () {


    let usuariosModal = null;
    async function open(config = {}) {

        const modal = await Swal.fire({

            title: `<i class="bi bi-images"></i> ${config.titulo}`,

            html: `
                

                <div class="modal-galeria-contendor-imagenes fieldset-falso usuario">
                    <span class="form-subtitulo-fieldset-falso">Usuarios Activos</span>

                    <div class="modal-galeria-usuario-body">
                        <div id="ui-gallery-usuario" class="ui-gallery-usuario"></div>
                    </div>

                    <input type="file" id="inputGaleria" accept="image/*" hidden>

                </div>
            `,

            showCloseButton: true,
            showConfirmButton: true,
            confirmButtonText: `<i class="bi bi-box-arrow-in-left"></i> VOLVER`,

            customClass: {
                popup: "contenedor-modal-galeria",
                title: 'contener-modal-titulo',
                actions: 'contener-modal-contenedor-botones-min',
                confirmButton: 'contener-modal-boton-confirmar',
            },

            didOpen: () => {
                inicializar(config.usuarios);



            }

        });

        return modal;
    }


    // ===== INICIALIZACION =====
    function inicializar(usuarios) {
        usuariosModal=usuarios;
        //obtenerData(config.parametros);
        renderGaleria();
        listenerDelegado();
    }


    // ===== GALERIA =====
    function renderGaleria() {
        let container = document.getElementById('ui-gallery-usuario');

        if (!usuariosModal.length) {
            container.innerHTML = `
                <div class="galeria-vacia">
                    No hay usuarios disponibles
                </div>
            `;
            return;
        }

        const fragment = document.createDocumentFragment();

        usuariosModal.forEach((usuario) => {
            const wrapper = document.createElement("div");
            wrapper.innerHTML = crearTarjeta(usuario);
            const tarjeta = wrapper.firstElementChild;
            fragment.appendChild(tarjeta);
        });
        
        container.replaceChildren(fragment);

    }

    function crearTarjeta(usuario){
        let url = null;

        if (usuario.url_thumb) {
            url = usuario.url_thumb;
        }
        else if (usuario.url_imagen) {
            url = usuario.url_imagen;
        }
        else{
            url = window.APP_CONFIG.usuarioDefaultImg
        }
        
        let nombre = usuario.nombre
            ? concatenarLimpio(usuario.nombre, usuario.apellido).slice(0, 17)
            : "NO DEFINIDO";


        return `
            <div class="ui-gallery__card galeria_usuario__tarjeta" data-id="${usuario.id}">

                <div class="ui-gallery__image usuario">
                    <img src="${url}" 
                        alt="${usuario.username}">
                </div>

                <div class="ui-gallery__info usuario">
                    <div class="ui-gallery__title usuario">
                        ${usuario.username}
                    </div>
                    <div class="ui-gallery__subtitle usuario">
                        ${nombre}
                    </div>
                </div>
            </div>
        `;
    }

    function listenerDelegado(){
        const usuariosGrid = document.getElementById('ui-gallery-usuario');
        const inputGaleria = document.getElementById("inputGaleria");

        inputGaleria.value = "";

        let usuarioActivo = null;
        usuariosGrid.addEventListener("click", (e) => {
            const tarjeta = e.target.closest('.galeria_usuario__tarjeta');
            if (!tarjeta) return;

            usuarioActivo = {
                id: tarjeta.dataset.id,
                img: tarjeta.querySelector("img")
            };

            inputGaleria.click();
        });


        inputGaleria.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file || !usuarioActivo) return;

            if (!AdjuntarImagenHelper.validarArchivo(file)){
                return;
            }

            

            const usuario = usuariosModal.find(u => u.id ===parseInt(usuarioActivo.id, 10));
            if (!usuario) {
                console.warn("Usuario no encontrado");
            }else{

                let info = {
                    "titulo": usuario.username,
                    "subtitulo": concatenarLimpio(usuario.nombre, usuario.apellido)
                }
                const archivoEditado = await ImageEditor.open(file,info);

                if (!archivoEditado) return;
                
                const oldSrc = usuarioActivo.img.src;
                const url = URL.createObjectURL(archivoEditado);
                usuarioActivo.img.src = url;
                
                if (oldSrc?.startsWith("blob:")) {
                    URL.revokeObjectURL(oldSrc);
                }

                const formData = new FormData();
                formData.append("usuario_id", usuario.id);
                formData.append("archivo", archivoEditado);

                try {
                    const response = await fetch(API_URLS.procesarImagenUsuario, {
                        method: "POST",
                        body: formData,
                        headers: {
                            "X-CSRFToken": window.CSRF_TOKEN
                        }
                    });
    
                    if (!response.ok) {
                        throw new Error("Error al subir imagen");
                    }

                    const data = await response.json();
                    if (data.guardo && data.url) {
                        usuarioActivo.img.src = data.url; 
                        const usuario = usuariosModal.find(u => u.id === parseInt(usuarioActivo.id, 10));
                        if (usuario) {
                            usuario.url_imagen = data.url;
                        }
                    }
                    else {
                        toastr.warning("NO se proceso la imagen");
                        
                    }
                    inputGaleria.value = "";

                } catch (error) {
                    console.error(error);
                }

                
            }
        }

    }



    // ===== RETURN =====
    return {
        open
    };

})();