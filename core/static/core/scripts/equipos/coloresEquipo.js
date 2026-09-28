// Colores del equipo: se agregan de uno en uno y el orden importa. El primero
// es el principal, el color con el que se reconoce el aparato, y los demas lo
// acompanan. La lista visible es solo la cara del campo oculto "colores", que
// es lo que viaja al servidor como "7,3,12".
document.addEventListener('DOMContentLoaded', function () {
    const contenedor = document.getElementById('colores_equipo');

    if (!contenedor) {
        return;
    }

    const campoOculto = document.getElementById('colores_dispositivo');
    const selector = document.getElementById('selector_color_dispositivo');
    const botonAgregar = document.getElementById('agregar_color_dispositivo');
    const lista = document.getElementById('lista_colores_dispositivo');
    const avisoVacio = document.getElementById('sin_colores_dispositivo');

    if (!campoOculto || !selector || !botonAgregar || !lista) {
        return;
    }

    // El selector se convierte en un Select2 para poder escribir el color en
    // vez de recorrer la lista entera: el catalogo pasa de la docena y buscar
    // "gris" es mas rapido que desplegarla y leerla. Si Select2 no estuviera
    // cargado, el <select> nativo sigue funcionando igual.
    const selectorJq = window.jQuery ? window.jQuery(selector) : null;

    if (selectorJq && selectorJq.select2) {
        selectorJq.select2({
            width: '100%',
            placeholder: 'Escriba o elija un color',
            allowClear: true,
            language: {
                noResults: function () {
                    return 'No se encontraron colores';
                }
            }
        });
    }

    function limpiarSelector() {
        selector.value = '';

        if (selectorJq && selectorJq.select2) {
            selectorJq.trigger('change.select2');
        }
    }

    function idsActuales() {
        return Array.from(lista.children).map(function (item) {
            return item.dataset.colorId;
        });
    }

    function sincronizar() {
        const ids = idsActuales();

        campoOculto.value = ids.join(',');

        if (avisoVacio) {
            avisoVacio.hidden = ids.length > 0;
        }

        // La numeracion y la etiqueta de principal se recalculan enteras: al
        // quitar el primero, el segundo pasa a serlo.
        Array.from(lista.children).forEach(function (item, indice) {
            item.querySelector('.equipos-colores__orden').textContent = indice + 1;

            const etiqueta = item.querySelector('.equipos-colores__etiqueta');

            if (indice === 0 && !etiqueta) {
                const nueva = document.createElement('span');
                nueva.className = 'equipos-colores__etiqueta';
                nueva.textContent = 'Principal';
                item.querySelector('.equipos-colores__nombre').after(nueva);
            } else if (indice !== 0 && etiqueta) {
                etiqueta.remove();
            }
        });

        // Un color ya agregado no debe poder elegirse otra vez. Select2 no
        // respeta el atributo hidden, asi que se deshabilita la opcion: eso
        // si la saca de su desplegable y tambien del select nativo.
        Array.from(selector.options).forEach(function (opcion) {
            const usada = opcion.value !== '' && ids.includes(opcion.value);
            opcion.hidden = usada;
            opcion.disabled = usada;
        });
    }

    function crearItem(id, nombre) {
        const item = document.createElement('li');
        item.className = 'equipos-colores__item';
        item.dataset.colorId = id;

        const orden = document.createElement('span');
        orden.className = 'equipos-colores__orden';

        const texto = document.createElement('span');
        texto.className = 'equipos-colores__nombre';
        texto.textContent = nombre;

        const quitar = document.createElement('button');
        quitar.className = 'equipos-colores__quitar';
        quitar.type = 'button';
        quitar.setAttribute('aria-label', `Quitar ${nombre}`);
        quitar.innerHTML = '<i class="bi bi-x-lg"></i>';

        item.append(orden, texto, quitar);
        return item;
    }

    botonAgregar.addEventListener('click', function () {
        const id = selector.value;

        if (!id || idsActuales().includes(id)) {
            return;
        }

        const nombre = selector.options[selector.selectedIndex].textContent.trim();
        lista.append(crearItem(id, nombre));
        limpiarSelector();
        sincronizar();
    });

    // Delegado: los items se crean y se borran, asi que el escuchador vive en
    // la lista y no en cada boton.
    lista.addEventListener('click', function (evento) {
        const quitar = evento.target.closest('.equipos-colores__quitar');

        if (!quitar) {
            return;
        }

        quitar.closest('.equipos-colores__item').remove();
        sincronizar();
    });

    // Enter dentro del selector agrega en vez de enviar el formulario: al
    // capturar varios colores seguidos es el gesto natural, y un envio a
    // medias obligaria a rehacer la pantalla entera.
    selector.addEventListener('keydown', function (evento) {
        if (evento.key === 'Enter') {
            evento.preventDefault();
            botonAgregar.click();
        }
    });

    sincronizar();
});
