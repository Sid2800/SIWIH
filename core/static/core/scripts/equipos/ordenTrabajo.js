/* La hoja de trabajo: equipos y actividades sin recargar la pagina.
 *
 * Esta pantalla se llena de pie junto al aparato, escribiendo una linea tras
 * otra. Una recarga por linea perderia lo escrito arriba y haria el trabajo
 * mas lento que el papel, que es contra lo que esto compite. De ahi que todo
 * vaya por fetch.
 *
 * Las sugerencias de actividad vienen de lo que ya se escribio antes en
 * equipos de este tipo. No hay lista precargada: el catalogo nace vacio y se
 * llena con el uso, asi que la primera orden de un tipo se escribe completa y
 * de ahi en adelante se va eligiendo.
 */

(function () {
    'use strict';

    const pagina = document.querySelector('[data-orden]');

    if (!pagina) {
        return;
    }

    const aviso = pagina.querySelector('[data-aviso]');
    const lineas = pagina.querySelector('[data-lineas]');
    const filas = pagina.querySelector('[data-filas-equipos]');
    const contadorEquipos = pagina.querySelector('[data-contador-equipos]');
    const contadorActividades = pagina.querySelector('[data-contador-actividades]');

    const URL_AGREGAR_EQUIPO = pagina.dataset.urlAgregarEquipo;
    const URL_QUITAR_EQUIPO = pagina.dataset.urlQuitarEquipo;
    const URL_AGREGAR_ACTIVIDAD = pagina.dataset.urlAgregarActividad;
    const URL_QUITAR_ACTIVIDAD = pagina.dataset.urlQuitarActividad;
    const URL_SUGERENCIAS = pagina.dataset.urlSugerencias;
    const TIPO = pagina.dataset.tipo;

    // Tiempo que se espera antes de pedir sugerencias. Pedirlas en cada tecla
    // manda una peticion por letra y la lista parpadea mientras se escribe.
    const ESPERA_SUGERENCIAS = 220;

    function rutaDe(plantilla, identificador) {
        return plantilla.replace('/0/', '/' + identificador + '/');
    }

    function token() {
        const campo = pagina.querySelector('[name=csrfmiddlewaretoken]');
        return campo ? campo.value : '';
    }

    function avisar(texto, esError) {
        if (!aviso) {
            return;
        }

        aviso.textContent = texto;
        aviso.classList.toggle('equipos-orden__aviso--error', Boolean(esError));
    }

    function mensajeDeErrores(datos) {
        if (datos.error) {
            return datos.error;
        }

        if (datos.errores) {
            // Los errores llegan por campo. Se juntan en una sola frase
            // porque esta pantalla no tiene sitio para pintarlos junto a cada
            // campo sin desarmar la fila de agregar.
            return Object.keys(datos.errores)
                .map(function (campo) {
                    return [].concat(datos.errores[campo]).join(' ');
                })
                .join(' ');
        }

        return 'No se pudo completar la acción.';
    }

    async function enviar(url, cuerpo, comoFormulario) {
        const cabeceras = {
            'X-CSRFToken': token(),
            'X-Requested-With': 'XMLHttpRequest'
        };

        if (!comoFormulario) {
            cabeceras['Content-Type'] = 'application/json';
        }

        const respuesta = await fetch(url, {
            method: 'POST',
            headers: cabeceras,
            body: comoFormulario ? cuerpo : JSON.stringify(cuerpo || {})
        });

        let datos = {};

        try {
            datos = await respuesta.json();
        } catch (error) {
            throw new Error('El servidor respondió algo que no se entiende.');
        }

        if (!respuesta.ok) {
            throw new Error(mensajeDeErrores(datos));
        }

        return datos;
    }

    function ajustarContador(elemento, delta) {
        if (!elemento) {
            return;
        }

        const actual = parseInt(elemento.textContent, 10) || 0;
        elemento.textContent = Math.max(0, actual + delta);
    }

    // -----------------------------------------------------------------------
    // Equipos de la hoja
    // -----------------------------------------------------------------------

    const formularioEquipo = pagina.querySelector('[data-form-equipo]');

    if (formularioEquipo) {
        formularioEquipo.addEventListener('submit', async function (evento) {
            evento.preventDefault();

            const boton = formularioEquipo.querySelector('button[type=submit]');
            boton.disabled = true;

            try {
                const datos = await enviar(
                    URL_AGREGAR_EQUIPO,
                    new FormData(formularioEquipo),
                    true
                );

                dibujarFilaEquipo(datos.fila);
                formularioEquipo.reset();
                ajustarContador(contadorEquipos, 1);
                avisar(datos.fila.codigo + ' agregado a la hoja.');

                // El equipo que se acaba de agregar ya no debe ofrecerse: la
                // unicidad lo rechazaria con un error que no explica nada.
                const opcion = formularioEquipo.querySelector(
                    'option[value="' + datos.fila.id_dispositivo + '"]'
                );

                if (opcion) {
                    opcion.remove();
                }
            } catch (error) {
                avisar(error.message, true);
            } finally {
                boton.disabled = false;
            }
        });
    }

    function dibujarFilaEquipo(fila) {
        if (!filas) {
            return;
        }

        const vacio = filas.querySelector('[data-sin-equipos]');

        if (vacio) {
            vacio.remove();
        }

        const tr = document.createElement('tr');
        tr.dataset.fila = fila.id;

        const celdas = [
            fila.codigo,
            fila.ambiente || '—',
            fila.hora_inicio || '—',
            fila.hora_final || '—',
            fila.minutos === null ? '—' : fila.minutos
        ];

        celdas.forEach(function (texto) {
            const td = document.createElement('td');
            td.textContent = texto;
            tr.appendChild(td);
        });

        const acciones = document.createElement('td');
        const quitar = document.createElement('button');
        quitar.type = 'button';
        quitar.className = 'equipos-orden__quitar';
        quitar.dataset.quitaEquipo = fila.id;
        quitar.textContent = '×';
        quitar.setAttribute('aria-label', 'Quitar este equipo de la orden');
        acciones.appendChild(quitar);
        tr.appendChild(acciones);

        filas.appendChild(tr);
    }

    // -----------------------------------------------------------------------
    // Actividades: lo que se hizo
    // -----------------------------------------------------------------------

    const formularioActividad = pagina.querySelector('[data-form-actividad]');
    const campoNombre = formularioActividad
        ? formularioActividad.querySelector('input[name=nombre]')
        : null;
    const campoDetalle = formularioActividad
        ? formularioActividad.querySelector('input[name=detalle]')
        : null;
    const listaSugerencias = pagina.querySelector('[data-sugerencias]');

    if (formularioActividad) {
        formularioActividad.addEventListener('submit', async function (evento) {
            evento.preventDefault();
            await agregarActividad();
        });
    }

    async function agregarActividad() {
        if (!campoNombre || !campoNombre.value.trim()) {
            avisar('Escriba qué se hizo.', true);
            return;
        }

        const boton = formularioActividad.querySelector('button[type=submit]');
        boton.disabled = true;
        cerrarSugerencias();

        try {
            const datos = await enviar(URL_AGREGAR_ACTIVIDAD, {
                nombre: campoNombre.value,
                detalle: campoDetalle ? campoDetalle.value : ''
            });

            dibujarLinea(datos.linea);
            campoNombre.value = '';

            if (campoDetalle) {
                campoDetalle.value = '';
            }

            campoNombre.focus();
            ajustarContador(contadorActividades, 1);

            avisar(
                datos.linea.nueva_en_catalogo
                    ? 'Agregada. Es nueva: a partir de ahora se le va a sugerir.'
                    : 'Agregada.'
            );
        } catch (error) {
            avisar(error.message, true);
        } finally {
            boton.disabled = false;
        }
    }

    function dibujarLinea(linea) {
        if (!lineas) {
            return;
        }

        const vacio = lineas.querySelector('[data-sin-lineas]');

        if (vacio) {
            vacio.remove();
        }

        const li = document.createElement('li');
        li.dataset.linea = linea.id;

        const texto = document.createElement('span');
        texto.className = 'equipos-orden__linea-texto';
        texto.textContent = linea.texto;
        li.appendChild(texto);

        const quitar = document.createElement('button');
        quitar.type = 'button';
        quitar.className = 'equipos-orden__quitar';
        quitar.dataset.quitaActividad = linea.id;
        quitar.textContent = '×';
        quitar.setAttribute('aria-label', 'Quitar esta línea');
        li.appendChild(quitar);

        lineas.appendChild(li);
    }

    // -----------------------------------------------------------------------
    // Sugerencias
    // -----------------------------------------------------------------------

    let temporizador = null;
    let ultimaConsulta = '';

    if (campoNombre) {
        campoNombre.addEventListener('input', function () {
            window.clearTimeout(temporizador);
            temporizador = window.setTimeout(buscarSugerencias, ESPERA_SUGERENCIAS);
        });

        campoNombre.addEventListener('keydown', function (evento) {
            if (evento.key === 'Escape') {
                cerrarSugerencias();
            }
        });

        // Un clic fuera cierra la lista. Sin esto se queda abierta tapando el
        // boton de agregar.
        document.addEventListener('click', function (evento) {
            if (!evento.target.closest('.equipos-orden__campo--actividad')) {
                cerrarSugerencias();
            }
        });
    }

    async function buscarSugerencias() {
        if (!campoNombre || !listaSugerencias) {
            return;
        }

        const texto = campoNombre.value.trim();

        if (texto.length < 3) {
            cerrarSugerencias();
            return;
        }

        if (texto === ultimaConsulta) {
            return;
        }

        ultimaConsulta = texto;

        const url = URL_SUGERENCIAS +
            '?q=' + encodeURIComponent(texto) +
            '&tipo=' + encodeURIComponent(TIPO);

        try {
            const respuesta = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (!respuesta.ok) {
                cerrarSugerencias();
                return;
            }

            const datos = await respuesta.json();
            dibujarSugerencias(datos.sugerencias || []);
        } catch (error) {
            // Que falle el autocompletado no debe impedir escribir la linea a
            // mano, que es lo que de verdad hace falta.
            cerrarSugerencias();
        }
    }

    function dibujarSugerencias(sugerencias) {
        if (!listaSugerencias) {
            return;
        }

        listaSugerencias.textContent = '';

        if (!sugerencias.length) {
            cerrarSugerencias();
            return;
        }

        sugerencias.forEach(function (sugerencia) {
            const li = document.createElement('li');
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.dataset.sugerencia = sugerencia.nombre;
            boton.textContent = sugerencia.nombre;

            if (sugerencia.veces > 1) {
                const veces = document.createElement('small');
                veces.textContent = ' ' + sugerencia.veces + '×';
                boton.appendChild(veces);
            }

            li.appendChild(boton);
            listaSugerencias.appendChild(li);
        });

        listaSugerencias.hidden = false;
    }

    function cerrarSugerencias() {
        if (listaSugerencias) {
            listaSugerencias.hidden = true;
            listaSugerencias.textContent = '';
        }
    }

    // -----------------------------------------------------------------------
    // Clics: elegir sugerencia, elegir habitual, quitar
    // -----------------------------------------------------------------------

    pagina.addEventListener('click', async function (evento) {
        const sugerencia = evento.target.closest('[data-sugerencia]');

        if (sugerencia) {
            campoNombre.value = sugerencia.dataset.sugerencia;
            cerrarSugerencias();
            campoNombre.focus();
            return;
        }

        const habitual = evento.target.closest('[data-habitual]');

        if (habitual) {
            // Se escribe en el campo, no se agrega sola. Agregarla de un clic
            // es como se acaba firmando una tarea que no se hizo.
            campoNombre.value = habitual.dataset.habitual;
            campoNombre.focus();
            avisar('Escrita en el campo. Revísela y agréguela.');
            return;
        }

        const quitaEquipo = evento.target.closest('[data-quita-equipo]');

        if (quitaEquipo) {
            quitaEquipo.disabled = true;

            try {
                await enviar(
                    rutaDe(URL_QUITAR_EQUIPO, quitaEquipo.dataset.quitaEquipo),
                    {}
                );

                const fila = quitaEquipo.closest('[data-fila]');

                if (fila) {
                    fila.remove();
                }

                ajustarContador(contadorEquipos, -1);
                avisar('Equipo quitado de la hoja.');
            } catch (error) {
                quitaEquipo.disabled = false;
                avisar(error.message, true);
            }

            return;
        }

        const quitaActividad = evento.target.closest('[data-quita-actividad]');

        if (quitaActividad) {
            quitaActividad.disabled = true;

            try {
                await enviar(
                    rutaDe(
                        URL_QUITAR_ACTIVIDAD,
                        quitaActividad.dataset.quitaActividad
                    ),
                    {}
                );

                const linea = quitaActividad.closest('[data-linea]');

                if (linea) {
                    linea.remove();
                }

                ajustarContador(contadorActividades, -1);
                avisar('Línea quitada.');
            } catch (error) {
                quitaActividad.disabled = false;
                avisar(error.message, true);
            }
        }
    });
}());
