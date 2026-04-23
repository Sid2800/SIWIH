const ControlGaleria = (function () {

    function render(container, imagenes = [], titulo_album) {
        if (!container) return;

        container.innerHTML = "";


        if (!imagenes.length) {

            container.innerHTML = `
                <div class="galeria-vacia">
                    No hay imágenes disponibles
                </div>
            `;

            return;
        }
        
        const fragment = document.createDocumentFragment();

        imagenes.forEach((img, index) => {

            const wrapper = document.createElement("div");
            wrapper.innerHTML = crearTarjeta(img);
            const tarjeta = wrapper.firstElementChild;

            
            tarjeta.addEventListener("click", () => {
                const validImages = imagenes.filter(i => i.url_imagen);
                const urls = validImages.map(i => i.url_imagen);
                const subtitles = validImages.map(i => i.estudio__descripcion_estudio);
                if (!urls.length) {
                    console.warn("El estudio no tiene imágenes");
                    return;
                }
                const startIndex = validImages.findIndex(i => i.id === img.id);
                if (startIndex === -1) {
                    console.warn("El estudio no tiene imagen");
                    return;
                }

                ImageViewer.open(urls, startIndex, titulo_album, subtitles);
            
            });
            fragment.appendChild(tarjeta);

        });

        container.replaceChildren(fragment);

    }


    
    function crearTarjeta(img){
        let url = null;

        if (img.url_thumb) {
            url = img.url_thumb;
        }
        else if (img.url_imagen) {
            url = img.url_imagen;
        }
        else{
            url = window.APP_CONFIG.estudioDefaultImg
        }
        
        let impreso = img.impreso ? "IMPRESO":"NO IMPRESO"

        return `
            <div class="ui-gallery__card" data-id="${img.id}">

                <div class="ui-gallery__image">
                    <img src="${url}" 
                        alt="${img.estudio__descripcion_estudio}">
                </div>

                <div class="ui-gallery__info">
                    <div class="ui-gallery__title">
                        ${img.estudio__descripcion_estudio}
                    </div>
                    <div class="ui-gallery__subtitle">
                        ${impreso}
                    </div>
                </div>
            </div>
        `;
        }

    return {
        render
    };

})();