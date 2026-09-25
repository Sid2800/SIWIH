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

        // Un color ya agregado no debe poder elegirse otra vez.
        Array.from(selector.options).forEach(function (opcion) {
            opcion.hidden = opcion.value !== '' && ids.includes(opcion.value);
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
        selector.value = '';
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
