const ImageViewer = (() => {

    let panzoomInstance = null;
    let overlay = null;
    let images = [];
    let currentIndex = 0;
    let viewerTitle = "";
    let viewerSubtitles = [];


    function createOverlay() {

        overlay = document.createElement("div");
        overlay.className = "visor-overlay";

        overlay.innerHTML = `
            <div class="visor-overlay-stage">


                <div class="visor-overlay-info">
                    <div class="visor-overlay-title"></div>
                    <div class="visor-overlay-subtitle"></div>

                </div>

                <div class="visor-overlay-contador"></div>

                <button class="visor-overlay-close-top">
                    <i class="bi bi-x-lg"></i>
                </button>

                

                <button class="visor-overlay-nav visor-overlay-prev">
                    <i class="bi bi-caret-left-square"></i>
                </button>
                <div class="f-panzoom" id="visor-overlay-contendor-img"></div>
                <button class="visor-overlay-nav visor-overlay-next">
                    <i class="bi bi-caret-right-square"></i>
                </button>
            </div>



            
            <div class="visor-overlay-toolbar">
                <button data-action="zoomIn" title="Zoom +">
                    <i class="bi bi-zoom-in"></i>
                </button>

                <button data-action="zoomOut" title="Zoom -">
                    <i class="bi bi-zoom-out"></i>
                </button>

                <button data-action="rotateCW" title="Rotar derecha">
                    <i class="bi bi-arrow-clockwise"></i>
                </button>

                <button data-action="rotateCCW" title="Rotar izquierda">
                    <i class="bi bi-arrow-counterclockwise"></i>
                </button>

                <button data-action="flipX" title="Espejo horizontal">
                    <i class="bi bi-symmetry-vertical"></i>
                </button>

                <button data-action="reset" title="Restablecer">
                    <i class="bi bi-arrow-repeat"></i>
                </button>

                <button data-action="close" title="Cerrar">
                    <i class="bi bi-x-lg"></i>
                </button>

            </div>

            
        `;

        document.body.appendChild(overlay);


        overlay.querySelectorAll("[data-action]").forEach(btn => {
            btn.addEventListener("click", () => {
                const action = btn.dataset.action;

                if (action === "close") {
                    close();
                } else if (panzoomInstance) {
                    panzoomInstance.execute(action);
                }
            });
        });


        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && overlay?.classList.contains("activo")) {
                e.stopPropagation();
                e.preventDefault();
                close();
            }

            if (e.key === "ArrowRight") next();
            if (e.key === "ArrowLeft") prev();

        }, true); 

        overlay.querySelector(".visor-overlay-prev").addEventListener("click", prev);
        overlay.querySelector(".visor-overlay-next").addEventListener("click", next);
        overlay.querySelector(".visor-overlay-close-top").addEventListener("click", close);
    }

    function open(data, index = 0,  title = "", subtitles = []) {
        if (!overlay) createOverlay();

        if (Array.isArray(data)) {
            images = data;
        } else {
            images = [data];
        }

        currentIndex = index;
        viewerTitle = title;
        viewerSubtitles = subtitles;

        render();
    }

    function render() {
        const container = overlay.querySelector("#visor-overlay-contendor-img");

        const titleEl = overlay.querySelector(".visor-overlay-title");
        const subtitleEl = overlay.querySelector(".visor-overlay-subtitle");
        const prevBtn = overlay.querySelector(".visor-overlay-prev");
        const nextBtn = overlay.querySelector(".visor-overlay-next");
        const contador = overlay.querySelector(".visor-overlay-contador");


        titleEl.textContent = viewerTitle;
        subtitleEl.textContent = viewerSubtitles[currentIndex] || "";


        if (images.length <= 1) {
            prevBtn.style.display = "none";
            nextBtn.style.display = "none";
            contador.textContent = "1 / 1";
        } else {
            prevBtn.style.display = "block";
            nextBtn.style.display = "block";
            contador.textContent = `${currentIndex + 1} / ${images.length}`;
            
        }

        overlay.classList.remove("activo");
        void overlay.offsetWidth;
        overlay.classList.add("activo");

        container.innerHTML = "";

        const nuevaImg = document.createElement("img");
        nuevaImg.id = "visor-overlay-img";
        nuevaImg.className = "f-panzoom__content";

        container.appendChild(nuevaImg);


        if (panzoomInstance) {
            panzoomInstance.destroy();
            panzoomInstance = null;
        }


        nuevaImg.src = images[currentIndex];


        nuevaImg.onload = () => {

            panzoomInstance = Panzoom(container, {
                contain: "inside",
                click: "toggleCover"
            }).init();

        };

    }

    function next() {
        if (currentIndex < images.length - 1) {
            currentIndex++;
        } else {
            currentIndex = 0;
        }
        render();
    }


    function prev() {
        if (currentIndex > 0) {
            currentIndex--;
        } else {
            currentIndex = images.length - 1;
        }
        render();
    }



    function close() {
        overlay.classList.remove("activo");
    }

    return { open, close };

})();
