const ImageEditor = (() => {

    let overlay = null;
    let cropper = null;
    let resolver = null;
    let modoActual = "medico";

    function createOverlay(){

        overlay = document.createElement("div");
        overlay.className = "editor-overlay";

        overlay.innerHTML = `
            <div class="editor-overlay-stage">

                <div class="editor-overlay-info">
                    <div class="editor-overlay-title"></div>
                    <div class="editor-overlay-subtitle"></div>
                </div>

                <button class="editor-overlay-close-top">
                    <i class="bi bi-x-lg"></i>
                </button>

                <img id="editor-overlay-img">

                <div class="editor-overlay-toolbar">

                    <button data-action="zoomIn" title="Zoom +">
                        <i class="bi bi-zoom-in"></i>
                    </button>

                    <button data-action="zoomOut" title="Zoom -">
                        <i class="bi bi-zoom-out"></i>
                    </button>

                    <button type="button" data-action="rotateLeft">
                        <i class="bi bi-arrow-counterclockwise"></i>
                    </button>

                    <button type="button" data-action="rotateRight">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>

                    <button type="button" data-action="reset">
                        <i class="bi bi-arrow-repeat"></i>
                    </button>

                    <button type="button" data-action="confirm">
                        <i class="bi bi-check-lg"></i>
                    </button>

                    <button type="button" data-action="cancel">
                        <i class="bi bi-x-lg"></i>
                    </button>

                </div>

            </div>
        `;
        document.body.appendChild(overlay);

        let toolbar = overlay.querySelector(".editor-overlay-toolbar")

        toolbar.addEventListener("click", (e) => {

            const btn = e.target.closest("[data-action]");
            if (!btn) return;

            const action = btn.dataset.action;

            if (action === "cancel") {
                cancel();
                return;
            }

            if (!cropper) return;

            switch(action){

                case "rotateRight":
                    cropper.rotate(90);
                    break;

                case "rotateLeft":
                    cropper.rotate(-90);
                    break;

                case "zoomIn":
                    cropper.zoom(0.1);
                    break;

                case "zoomOut":
                    cropper.zoom(-0.1);
                    break;

                case "reset":
                    cropper.reset();
                    break;

                case "confirm":
                    confirm();
                    break;
            }




        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && overlay?.classList.contains("activo")) {
                e.stopPropagation();
                e.preventDefault();
                cancel();
            }
        }, true); 

        overlay.querySelector(".editor-overlay-close-top").addEventListener("click", cancel);


    }

    function open(file, info={}, modo = "medico"){
        if(!overlay) createOverlay();
        modoActual = modo;

        return new Promise(resolve => {
            resolver = resolve;
            render(file,info);
        });

    }

    function render(file, info={}) {
        const img = document.getElementById("editor-overlay-img");
        const titleEl = overlay.querySelector(".editor-overlay-title");
        const subtitleEl = overlay.querySelector(".editor-overlay-subtitle");


        overlay.classList.remove("activo");
        void overlay.offsetWidth;
        overlay.classList.add("activo");
        img.src = URL.createObjectURL(file);

        if (cropper) cropper.destroy();

        titleEl.textContent = info.titulo || "";
        subtitleEl.textContent = info.subtitulo || "";

        
                
        cropper = new Cropper(img,{
            viewMode:1,
            responsive:true,
            autoCropArea: 0.9,
            aspectRatio: NaN,
            initialAspectRatio: 9/10
        });
    }

    function confirm(){

        let configCanvas;

        if (modoActual === "usuario") {
            configCanvas = {
                width: 300,
                height: 300,
                imageSmoothingEnabled: true,
                imageSmoothingQuality: "high"
            };
        } else {
            configCanvas = {
                maxWidth: 1200,
                maxHeight: 1200,
                imageSmoothingEnabled: true,
                imageSmoothingQuality: "high"
            };
        }

        const canvas = cropper.getCroppedCanvas(configCanvas);

        canvas.toBlob(blob => {

            const file = new File(
                [blob],
                "imagen_editada.webp",
                { type: "image/webp" }
            );

            resolver(file);
            close();
        }, "image/webp", modoActual === "usuario" ? 0.8 : 0.9);

    }

    function cancel(){
        resolver(null);
        close();

    }

    function close(){

        overlay.classList.remove("activo");
        const img = document.getElementById("editor-overlay-img");
        if (img?.src?.startsWith("blob:")) {
            URL.revokeObjectURL(img.src);
        }

        if (cropper) {
            cropper.destroy();
            cropper = null;
        }

    }

    return { open };

})();