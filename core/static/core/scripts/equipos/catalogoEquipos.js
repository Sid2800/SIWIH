// Catalogo de equipos: buscador de cada lista y doble clic para renombrar.
//
// El filtrado se hace sobre las filas que ya estan en la pagina, sin volver a
// consultar al servidor. Para unas decenas de entradas es instantaneo, y al
// servidor le ahorra una consulta por cada letra que se teclea. El dia que un
// catalogo crezca a miles de filas habra que paginarlo y buscar contra la
// base; hasta entonces esto es lo barato y lo rapido.
document.addEventListener('DOMContentLoaded', function () {

    // ---------- Buscadores ----------
    document.querySelectorAll('[data-filtra]').forEach(function (campo) {
        const lista = document.getElementById(campo.dataset.filtra);

        if (!lista) {
            return;
        }

        const panel = campo.closest('.equipos-catalogo__panel');
        const sinCoincidencias = panel
            ? panel.querySelector('.equipos-catalogo__sin-coincidencias')
            : null;
        const filas = [...lista.querySelectorAll('.equipos-catalogo__item')];

        function normalizar(texto) {
            // Sin tildes y en minusculas: quien busca "electrico" tiene que
            // encontrar "ELECTRICO" y tambien "eléctrico".
            return texto
                .toLowerCase()
                .normalize('NFD')
                .replace(/[̀-ͯ]/g, '');
        }

        // El texto de cada fila se calcula una vez, no en cada pulsacion.
        const textos = filas.map(function (fila) {
            return normalizar(fila.textContent);
        });

        campo.addEventListener('input', function () {
            const busqueda = normalizar(campo.value.trim());
            let visibles = 0;

            filas.forEach(function (fila, indice) {
                const coincide = !busqueda || textos[indice].includes(busqueda);
                fila.hidden = !coincide;

                if (coincide) {
                    visibles += 1;
                }
            });

            if (sinCoincidencias) {
                sinCoincidencias.hidden = visibles > 0 || !busqueda;
            }
        });
    });

    // ---------- Un clic elige, doble clic renombra ----------
    // El enlace navega por si solo, asi que el primer clic se retiene un
    // momento: si llega un segundo, se cancela y se va a la edicion. 250ms es
    // lo que tarda un doble clic normal.
    const ESPERA_DOBLE_CLIC = 250;

    document.querySelectorAll('[data-url-editar]').forEach(function (enlace) {
        let temporizador = null;

        enlace.addEventListener('click', function (evento) {
            // Ctrl+clic o rueda del raton abren en otra pestana: eso se
            // respeta y no se retiene.
            if (evento.ctrlKey || evento.metaKey || evento.button !== 0) {
                return;
            }

            evento.preventDefault();

            if (temporizador) {
                return;
            }

            temporizador = window.setTimeout(function () {
                temporizador = null;
                window.location.href = enlace.getAttribute('href');
            }, ESPERA_DOBLE_CLIC);
        });

        enlace.addEventListener('dblclick', function (evento) {
            evento.preventDefault();
            window.clearTimeout(temporizador);
            temporizador = null;
            window.location.href = enlace.dataset.urlEditar;
        });
    });
});
