// Catalogo de equipos: buscadores de las listas y doble clic para renombrar.
//
// Hay dos clases de buscador, y la diferencia es cuanto puede crecer la lista:
//
//   - Tipos de equipo puede llegar a varios miles, asi que su busqueda va
//     contra la base y la lista viene paginada. El formulario se envia cuando
//     el usuario deja de teclear, no en cada letra: escribir "computadora" es
//     una consulta y no once. Sin JavaScript sigue funcionando con Enter.
//
//   - Marcas de un tipo y modelos de una marca son listas cortas por
//     naturaleza -pocas decenas- y ya vienen enteras en la pagina, asi que se
//     filtran aqui mismo, al instante y sin molestar al servidor.
document.addEventListener('DOMContentLoaded', function () {

    // ---------- Busqueda contra la base, diferida ----------
    // 400ms: lo bastante para no disparar a media palabra y lo bastante poco
    // para que la lista llegue antes de que el usuario mire la pantalla.
    const ESPERA_BUSQUEDA = 400;

    document.querySelectorAll('[data-busqueda-diferida]').forEach(function (formulario) {
        const campo = formulario.querySelector('input[type="search"]');

        if (!campo) {
            return;
        }

        let temporizador = null;

        campo.addEventListener('input', function () {
            window.clearTimeout(temporizador);
            temporizador = window.setTimeout(function () {
                formulario.submit();
            }, ESPERA_BUSQUEDA);
        });

        // Enter envia de inmediato, sin esperar el retardo.
        campo.addEventListener('keydown', function (evento) {
            if (evento.key === 'Enter') {
                window.clearTimeout(temporizador);
            }
        });
    });

    // ---------- Los filtros se envian al cambiar ----------
    // Un desplegable que hay que confirmar con un boton aparte se queda a
    // medias: se elige la categoria, no pasa nada, y el usuario cree que el
    // filtro no funciona.
    document.querySelectorAll('[data-envia-al-cambiar]').forEach(function (campo) {
        campo.addEventListener('change', function () {
            const formulario = campo.closest('form');

            if (formulario) {
                formulario.submit();
            }
        });
    });

    // ---------- Cuadros para dar de alta categoria y tecnologia ----------
    // El "+" de cada desplegable abre el suyo. Se hace con <dialog>, que ya
    // trae el cierre con Escape, el fondo bloqueado y el foco atrapado.
    document.querySelectorAll('[data-abre]').forEach(function (boton) {
        boton.addEventListener('click', function () {
            const dialogo = document.getElementById(boton.dataset.abre);

            if (!dialogo) {
                return;
            }

            dialogo.showModal();

            // El foco al primer campo: quien pulsa el "+" quiere escribir.
            const primero = dialogo.querySelector('input[type="text"]');

            if (primero) {
                primero.focus();
            }
        });
    });

    document.querySelectorAll('[data-cierra]').forEach(function (boton) {
        boton.addEventListener('click', function () {
            const dialogo = boton.closest('dialog');

            if (dialogo) {
                dialogo.close();
            }
        });
    });

    // Pulsar el fondo cierra, que es lo que espera cualquiera.
    document.querySelectorAll('.equipos-catalogo__dialogo').forEach(function (dialogo) {
        dialogo.addEventListener('click', function (evento) {
            const caja = dialogo.getBoundingClientRect();
            const dentro = (
                evento.clientX >= caja.left
                && evento.clientX <= caja.right
                && evento.clientY >= caja.top
                && evento.clientY <= caja.bottom
            );

            if (!dentro) {
                dialogo.close();
            }
        });
    });

    // ---------- Filtrado local de las listas cortas ----------
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
