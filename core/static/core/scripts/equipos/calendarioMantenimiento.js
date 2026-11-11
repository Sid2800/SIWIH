/* Calendario de mantenimiento: mover y omitir visitas sin recargar.
 *
 * Mover una visita arrastra a las que vienen detras, asi que el servidor
 * devuelve las fechas de todas las afectadas y aqui se repintan. Si solo se
 * actualizara la movida, el calendario mentiria hasta la siguiente recarga: la
 * pantalla diria seis meses donde la base ya dice cinco y medio.
 */

(function () {
    'use strict';

    const pagina = document.querySelector('[data-calendario]');

    if (!pagina) {
        return;
    }

    const aviso = pagina.querySelector('[data-aviso]');

    // Las URL vienen con un 0 de relleno porque Django necesita un numero
    // para construir la ruta. Se sustituye por el identificador real.
    const PLANTILLA_MOVER = pagina.dataset.urlMover;
    const PLANTILLA_OMITIR = pagina.dataset.urlOmitir;

    function rutaDe(plantilla, identificador) {
        // Se sustituye el segmento /0/ completo y no el primer cero que
        // aparezca: una ruta puede llevar ceros en otras partes y cambiar el
        // equivocado da un 404 difícil de explicar.
        return plantilla.replace('/0/', '/' + identificador + '/');
    }

    function token() {
        const campo = document.querySelector('[name=csrfmiddlewaretoken]');

        if (campo) {
            return campo.value;
        }

        // El calendario no lleva formulario propio, asi que el token sale de
        // la cookie. Sin esto Django rechazaria cada peticion con un 403 que
        // en pantalla parece un fallo de permisos.
        const cookie = document.cookie
            .split(';')
            .map(function (trozo) { return trozo.trim(); })
            .find(function (trozo) { return trozo.startsWith('csrftoken='); });

        return cookie ? cookie.slice('csrftoken='.length) : '';
    }

    function avisar(texto, esError) {
        if (!aviso) {
            return;
        }

        aviso.textContent = texto;
        aviso.classList.toggle('equipos-orden__aviso--error', Boolean(esError));
    }

    async function pedir(url, cuerpo) {
        const respuesta = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(cuerpo || {})
        });

        let datos = {};

        try {
            datos = await respuesta.json();
        } catch (error) {
            // Una respuesta que no es JSON significa que algo devolvio HTML:
            // casi siempre la pantalla de acceso denegado o un error del
            // servidor. Decirlo es mejor que quedarse callado.
            throw new Error('El servidor respondió algo que no se entiende.');
        }

        if (!respuesta.ok) {
            throw new Error(datos.error || 'No se pudo completar la acción.');
        }

        return datos;
    }

    function fechaLegible(iso) {
        const partes = String(iso).split('-');

        if (partes.length !== 3) {
            return iso;
        }

        return partes[2] + '/' + partes[1] + '/' + partes[0];
    }

    function repintarSiguientes(siguientes) {
        (siguientes || []).forEach(function (visita) {
            const campo = pagina.querySelector('[data-mueve="' + visita.id + '"]');

            if (campo) {
                campo.value = visita.fecha;
            }
        });
    }

    pagina.addEventListener('change', async function (evento) {
        const campo = evento.target.closest('[data-mueve]');

        if (!campo) {
            return;
        }

        const identificador = campo.dataset.mueve;
        const anterior = campo.defaultValue;

        if (!campo.value) {
            campo.value = anterior;
            return;
        }

        campo.disabled = true;

        try {
            const datos = await pedir(
                rutaDe(PLANTILLA_MOVER, identificador),
                { fecha: campo.value }
            );

            campo.value = datos.fecha;
            campo.defaultValue = datos.fecha;
            repintarSiguientes(datos.siguientes);

            const cuantas = (datos.siguientes || []).length;

            avisar(
                'Visita movida al ' + fechaLegible(datos.fecha) +
                (cuantas > 1
                    ? '. Se corrieron también las ' + (cuantas - 1) + ' siguientes.'
                    : '.')
            );
        } catch (error) {
            // Se devuelve el campo a su valor anterior: dejarlo con la fecha
            // nueva haria creer que el cambio se guardo.
            campo.value = anterior;
            avisar(error.message, true);
        } finally {
            campo.disabled = false;
        }
    });

    pagina.addEventListener('click', async function (evento) {
        const boton = evento.target.closest('[data-omite]');

        if (!boton) {
            return;
        }

        const motivo = window.prompt(
            'Omitir esta visita. ¿Por qué no se hizo?'
        );

        if (motivo === null) {
            return;
        }

        if (!motivo.trim()) {
            avisar('Hace falta decir por qué se omite.', true);
            return;
        }

        boton.disabled = true;

        try {
            await pedir(
                rutaDe(PLANTILLA_OMITIR, boton.dataset.omite),
                { motivo: motivo }
            );

            const fila = boton.closest('[data-visita]');

            if (fila) {
                fila.classList.add('equipos-calendario__visita--omitida');
                const acciones = fila.querySelector(
                    '.equipos-calendario__visita-acciones'
                );

                if (acciones) {
                    acciones.textContent = 'Omitida: ' + motivo.trim();
                }
            }

            avisar('Visita omitida.');
        } catch (error) {
            avisar(error.message, true);
        } finally {
            boton.disabled = false;
        }
    });
}());
