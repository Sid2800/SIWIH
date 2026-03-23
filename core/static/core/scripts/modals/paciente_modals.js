const ModalPacienteProcesos = (function () {
    
    let PROCESOS_ESTADO = {
            cadaver: null,
            obito: null,
        };

    async function open(config = {}) {
        return await Swal.fire({
            title: `<i class="bi bi-gear"></i> Otros procesos`,
            html: `
                <div class="tituloFormulario-subrallado"></div>
                <div class="modal-contendor-data">
                    <div class="modal-contendor-data-encabezado" id="modalOtrosProcesosHeader"></div>
                    <div class="modal-procesos-tabla">
                        <table class="tabla-procesos">
                            <thead>
                                <tr>
                                    <th>PROCESO</th>
                                    <th>ESTADO</th>
                                    <th>ACCIÓN</th>
                                </tr>
                            </thead>
                            <tbody id="procesosBody"></tbody>
                        </table>
                    </div>
                </div>
                
            `,
            showCloseButton: true,
            showConfirmButton: false,
            customClass: {
                popup: "contenedor-modal",
                title: 'contener-modal-titulo',
                htmlContainer: 'html-modal-galeria',
                actions: 'contener-modal-contenedor-botones-min',
                confirmButton: 'contener-modal-boton-confirmar',
            },
            didOpen: () => inicializar(config)
        });
    }

    async function inicializar(config){
        //renderProcesos(config.procesos);
        PROCESOS_ESTADO = {
            cadaver: null,
            entrega: null,
            traslado: null
        }


        await obtenerInfo(config.procesos);
        console.log(PROCESOS_ESTADO);
        renderDatos(config.datos);
        renderDatos(config.obito);

        renderProcesos(config.procesos);

    }

    async function obtenerInfo(procesos = []) {


        for (let i = 0; i < procesos.length; i++) {

            const p = procesos[i];
            if (p.identificador === 'cadaver') {
                try {
                    const data = await fetchData(API_URLS.obtenerDefuncion, {
                        id: p.idPaciente
                    });
                    if (data && !data.mensaje) {
                        PROCESOS_ESTADO.cadaver = data;
                    } else {
                        ""
                    }
                } catch (error) {
                    console.error(error);
                }
            }

            if (p.identificador === 'obito') {
                try {
                    const data = await fetchData(API_URLS.obtenerDefuncion, {
                        id: p.idPaciente
                    });
                    if (data && !data.mensaje) {
                        PROCESOS_ESTADO.obito = data;
                    } else {
                        ""
                    }
                } catch (error) {
                    console.error(error);
                }
            }
        }

    }




    function renderDatos(datos = {}) {

        const header = document.getElementById("modalOtrosProcesosHeader");

        if (!header || !datos) return;

        Object.entries(datos).forEach(([label, value]) => {

            const fila = document.createElement("div");
            fila.className = "modal-dato";

            fila.innerHTML = `
                <span class="modal-dato-label">${label}</span>
                <span class="modal-dato-valor">${value}</span>
            `;

            header.appendChild(fila);
        });
    }

    function renderProcesos(procesos = []){
        console.log(procesos);
        const body = document.getElementById("procesosBody");
        if (!body) return;

        body.innerHTML = "";

        procesos.forEach(p => {
            const fila = document.createElement("tr");

            fila.innerHTML = `
                <td>${p.nombre}</td>
                <td>${p.estado ? "✔ Registrado" : "❌ No registrado"}</td>
                <td>
                    <button class="btn-accion" data-tipo="${p.tipo}">
                        ${p.estado ? "Ver" : "Registrar"}
                    </button>
                </td>
            `;

            body.appendChild(fila);
        });

        bindEventos();
    }





    function bindEventos(){
        document.querySelectorAll(".btn-accion").forEach(btn => {
            btn.addEventListener("click", function(){
                const tipo = this.dataset.tipo;

                if (tipo === "obito"){
                    ModalObito.open();
                } else if (tipo === "entrega"){
                    ModalEntrega.open();
                }
            });
        });
    }

    return { open };

})();