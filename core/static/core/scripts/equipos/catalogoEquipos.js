// Catalogo de equipos: la pantalla se mueve sin recargarse.
//
// El catalogo es una cadena -un tipo declara sus marcas, y cada marca sus
// modelos- y recorrerla es el trabajo normal de esta pantalla. Recargando la
// pagina en cada paso se perdia el formulario de alta de arriba: quien llevaba
// escrito el nombre de un tipo nuevo y filtraba la lista para comprobar si ya
// existia volvia a encontrar el campo vacio.
//
// Asi que al elegir un tipo, al filtrar o al pasar de pagina solo se piden al
// servidor los trozos que cambian -las migas, la lista, el paso de marcas y el
// de modelos- y se ponen en el sitio de los que habia. El formulario de alta
// no se toca nunca.
//
// Todo sigue funcionando sin JavaScript: los filtros, la busqueda y los
// enlaces son un formulario GET y enlaces de verdad, asi que sin scripts la
// pagina se recarga como antes en lugar de quedarse quieta.
document.addEventListener('DOMContentLoaded', function () {

    // Trozos que el servidor sabe devolver por separado. Si alguno no viene
    // -el paso 3 no existe hasta que hay una marca elegida- se deja como
    // estaba en vez de dar error.
    const TROZOS = [
        'equipos_migas',
        'equipos_tipos_cuerpo',
        'equipos_paso_marcas',
        'equipos_paso_modelos',
    ];

    // Parametros que describen donde esta el usuario. Son los mismos que
    // viajan en la URL, de modo que el enlace se puede copiar y recargar.
    const PARAMETROS = ['tipo', 'marca', 'q', 'categoria', 'tecnologia', 'pagina'];

    const contenedor = document.querySelector('.equipos-catalogo');

    // ---------- Estado de la pantalla ----------
    function estadoDesdeUrl(busqueda) {
        const origen = new URLSearchParams(busqueda);
        const estado = {};

        PARAMETROS.forEach(function (nombre) {
            const valor = origen.get(nombre);

            if (valor) {
                estado[nombre] = valor;
            }
        });

        return estado;
    }

    let estado = estadoDesdeUrl(window.location.search);

    function urlDe(estado, parcial) {
        const parametros = new URLSearchParams();

        PARAMETROS.forEach(function (nombre) {
            if (estado[nombre]) {
                parametros.set(nombre, estado[nombre]);
            }
        });

        if (parcial) {
            parametros.set('parcial', '1');
        }

        const texto = parametros.toString();
        return window.location.pathname + (texto ? '?' + texto : '');
    }

    // ---------- Pedir y colocar los trozos ----------
    let peticionEnCurso = null;

    function cargar(nuevoEstado, empujarHistorial) {
        estado = nuevoEstado;

        if (contenedor) {
            contenedor.setAttribute('aria-busy', 'true');
        }

        // Si el usuario se adelanta -teclea y pulsa un tipo- la respuesta de
        // la peticion vieja podria llegar despues y pintar lo anterior. Se
        // guarda cual es la ultima y solo esa se dibuja.
        const miPeticion = {};
        peticionEnCurso = miPeticion;

        return window.fetch(urlDe(estado, true), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        })
            .then(function (respuesta) {
                if (!respuesta.ok) {
                    throw new Error('respuesta ' + respuesta.status);
                }

                return respuesta.text();
            })
            .then(function (html) {
                if (peticionEnCurso !== miPeticion) {
                    return;
                }

                colocar(html);

                if (empujarHistorial) {
                    window.history.pushState(estado, '', urlDe(estado, false));
                }
            })
            .catch(function () {
                // Si la peticion falla -la red, una sesion caducada- se
                // recarga de verdad: es mejor una pantalla que tarda que una
                // que se queda callada sin decir por que.
                window.location.href = urlDe(estado, false);
            })
            .finally(function () {
                if (peticionEnCurso === miPeticion && contenedor) {
                    contenedor.removeAttribute('aria-busy');
                }
            });
    }

    function colocar(html) {
        const recibido = new DOMParser().parseFromString(html, 'text/html');

        TROZOS.forEach(function (id) {
            const nuevo = recibido.getElementById(id);
            const actual = document.getElementById(id);

            if (nuevo && actual) {
                actual.replaceWith(nuevo);
            }
        });

        actualizarContador();
        prepararFiltrosLocales();
    }

    // El contador vive en la cabecera plegable, que no se cambia para no
    // cerrarla al vuelo, asi que su numero se copia del trozo que si llega.
    function actualizarContador() {
        const cuerpo = document.getElementById('equipos_tipos_cuerpo');
        const contador = document.querySelector(
            '#lista_tipos_panel .equipos-catalogo__contador'
        );

        if (cuerpo && contador && cuerpo.dataset.total) {
            contador.textContent = cuerpo.dataset.total;
        }
    }

    // El boton atras del navegador tiene que devolver al paso anterior, no
    // sacar al usuario de la pantalla.
    window.addEventListener('popstate', function (evento) {
        cargar(evento.state || estadoDesdeUrl(window.location.search), false);
    });

    // ---------- Un clic elige, doble clic renombra ----------
    // El primer clic se retiene un momento: si llega un segundo se cancela y
    // se abre la edicion. 250ms es lo que tarda un doble clic normal.
    const ESPERA_DOBLE_CLIC = 250;
    let temporizadorClic = null;

    function estadoDesdeEnlace(enlace) {
        const destino = new URL(enlace.getAttribute('href'), window.location.href);
        const pedido = estadoDesdeUrl(destino.search);
        // Lo que el enlace no diga se conserva: al elegir un tipo no se
        // pierde el filtro ni la busqueda que el usuario tenia puestos.
        const nuevo = Object.assign({}, estado, pedido);

        // Cambiar de tipo invalida la marca y vuelve a la primera pagina de
        // lo que se este mirando.
        if (pedido.tipo && pedido.tipo !== estado.tipo) {
            delete nuevo.marca;
        }

        if (!pedido.pagina) {
            delete nuevo.pagina;
        }

        return nuevo;
    }

    document.addEventListener('click', function (evento) {
        const enlace = evento.target.closest('[data-navega]');

        if (!enlace) {
            return;
        }

        // Ctrl+clic o rueda del raton abren en otra pestana: eso se respeta.
        if (evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.button !== 0) {
            return;
        }

        evento.preventDefault();

        if (!enlace.dataset.urlEditar) {
            cargar(estadoDesdeEnlace(enlace), true);
            return;
        }

        if (temporizadorClic) {
            return;
        }

        temporizadorClic = window.setTimeout(function () {
            temporizadorClic = null;
            cargar(estadoDesdeEnlace(enlace), true);
        }, ESPERA_DOBLE_CLIC);
    });

    document.addEventListener('dblclick', function (evento) {
        const enlace = evento.target.closest('[data-url-editar]');

        if (!enlace) {
            return;
        }

        evento.preventDefault();
        window.clearTimeout(temporizadorClic);
        temporizadorClic = null;
        // Renombrar si recarga: hay que llenar el formulario de arriba con el
        // tipo elegido, y eso lo dibuja el servidor.
        window.location.href = enlace.dataset.urlEditar;
    });

    // ---------- Busqueda y filtros de la lista de tipos ----------
    // 400ms: lo bastante para no disparar a media palabra y lo bastante poco
    // para que la lista llegue antes de que el usuario mire la pantalla.
    const ESPERA_BUSQUEDA = 400;

    document.querySelectorAll('[data-busqueda-diferida]').forEach(function (formulario) {
        const campo = formulario.querySelector('input[type="search"]');
        let temporizador = null;

        function pedir() {
            const nuevo = Object.assign({}, estado);

            // Cada vez que cambia lo que se busca se vuelve a la primera
            // pagina: la cuarta pagina de otro filtro no existe.
            delete nuevo.pagina;

            if (campo) {
                nuevo.q = campo.value.trim();

                if (!nuevo.q) {
                    delete nuevo.q;
                }
            }

            formulario.querySelectorAll('[data-envia-al-cambiar]').forEach(
                function (filtro) {
                    if (filtro.value) {
                        nuevo[filtro.name] = filtro.value;
                    } else {
                        delete nuevo[filtro.name];
                    }
                }
            );

            cargar(nuevo, true);
        }

        formulario.addEventListener('submit', function (evento) {
            evento.preventDefault();
            window.clearTimeout(temporizador);
            pedir();
        });

        if (campo) {
            campo.addEventListener('input', function () {
                window.clearTimeout(temporizador);
                temporizador = window.setTimeout(pedir, ESPERA_BUSQUEDA);
            });
        }

        // Un desplegable que hay que confirmar con un boton aparte se queda a
        // medias: se elige la categoria, no pasa nada, y el usuario cree que
        // el filtro no funciona.
        formulario.querySelectorAll('[data-envia-al-cambiar]').forEach(
            function (filtro) {
                filtro.addEventListener('change', function () {
                    window.clearTimeout(temporizador);
                    pedir();
                });
            }
        );
    });

    // ---------- Cuadros para dar de alta categoria y tecnologia ----------
    // El "+" de cada desplegable abre el suyo. Se hace con <dialog>, que ya
    // trae el cierre con Escape, el fondo bloqueado y el foco atrapado.
    document.addEventListener('click', function (evento) {
        const boton = evento.target.closest('[data-abre]');

        if (boton) {
            const dialogo = document.getElementById(boton.dataset.abre);

            if (dialogo) {
                dialogo.showModal();

                // El foco al primer campo: quien pulsa el "+" quiere escribir.
                const primero = dialogo.querySelector('input[type="text"]');

                if (primero) {
                    primero.focus();
                }
            }

            return;
        }

        const cierra = evento.target.closest('[data-cierra]');

        if (cierra) {
            const dialogo = cierra.closest('dialog');

            if (dialogo) {
                dialogo.close();
            }
        }
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
    // Marcas de un tipo y modelos de una marca son listas cortas por
    // naturaleza -pocas decenas- y ya vienen enteras, asi que se filtran aqui
    // mismo, al instante y sin molestar al servidor. La lista de tipos no: esa
    // puede llegar a miles y va paginada del servidor.
    function normalizar(texto) {
        // Sin tildes y en minusculas: quien busca "electrico" tiene que
        // encontrar "ELECTRICO" y tambien "eléctrico".
        return texto
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '');
    }

    function prepararFiltrosLocales() {
        document.querySelectorAll('[data-filtra]').forEach(function (campo) {
            if (campo.dataset.filtroListo) {
                return;
            }

            const lista = document.getElementById(campo.dataset.filtra);

            if (!lista) {
                return;
            }

            campo.dataset.filtroListo = '1';

            const panel = campo.closest('.equipos-catalogo__panel');
            const sinCoincidencias = panel
                ? panel.querySelector('.equipos-catalogo__sin-coincidencias')
                : null;
            const filas = [...lista.querySelectorAll('.equipos-catalogo__item')];
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
    }

    prepararFiltrosLocales();

    // ---------- Categorias del tipo, de una en una ----------
    // Una sola lista para todas: la primera es la principal -la que decide
    // que area da el mantenimiento- y las demas son secundarias. Antes eran
    // dos controles, un desplegable y una seccion aparte, para una sola
    // pregunta: a que familias pertenece este aparato.
    //
    // El desplegable se ordena segun la tecnologia elegida: las categorias
    // que ya se usan con ella suben arriba y el resto queda debajo. No se
    // esconde ninguna, porque la primera vez que una categoria se usa con una
    // tecnologia tiene que poder elegirse.
    (function categoriasDelTipo() {
        const bloque = document.getElementById('categorias_equipo');

        if (!bloque) {
            return;
        }

        const campoOculto = document.getElementById('categorias_tipo_catalogo');
        const selector = document.getElementById('selector_categoria_tipo');
        const boton = document.getElementById('agregar_categoria_tipo');
        const lista = document.getElementById('lista_categorias_tipo');
        const avisoVacio = document.getElementById('sin_categorias_tipo');
        const tecnologia = document.getElementById('tecnologia_tipo_catalogo');

        if (!campoOculto || !selector || !boton || !lista) {
            return;
        }

        function idsActuales() {
            return Array.from(lista.children).map(function (item) {
                return item.dataset.categoriaId;
            });
        }

        function sincronizar() {
            const ids = idsActuales();

            campoOculto.value = ids.join(',');

            if (avisoVacio) {
                avisoVacio.hidden = ids.length > 0;
            }

            // La numeracion y la etiqueta de principal se recalculan enteras:
            // al quitar la primera, la segunda pasa a serlo.
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

            // Una categoria ya agregada no debe poder elegirse otra vez.
            Array.from(selector.options).forEach(function (opcion) {
                const usada = opcion.value !== '' && ids.includes(opcion.value);
                opcion.hidden = usada;
                opcion.disabled = usada;
            });
        }

        function crearItem(id, nombre) {
            const item = document.createElement('li');
            item.className = 'equipos-colores__item';
            item.dataset.categoriaId = id;

            const orden = document.createElement('span');
            orden.className = 'equipos-colores__orden';

            const texto = document.createElement('span');
            texto.className = 'equipos-colores__nombre';
            texto.textContent = nombre;

            const quitar = document.createElement('button');
            quitar.className = 'equipos-colores__quitar';
            quitar.type = 'button';
            quitar.setAttribute('aria-label', 'Quitar ' + nombre);
            quitar.innerHTML = '<i class="bi bi-x-lg"></i>';

            item.append(orden, texto, quitar);
            return item;
        }

        // ----- El desplegable se ordena por la tecnologia elegida -----
        const opciones = Array.from(selector.options).filter(function (opcion) {
            return opcion.value !== '';
        });
        const vacia = selector.querySelector('option[value=""]');

        function grupo(etiqueta) {
            const nuevo = document.createElement('optgroup');
            nuevo.label = etiqueta;
            return nuevo;
        }

        function ordenarPorTecnologia() {
            const elegida = tecnologia ? tecnologia.value : '';

            // Se vacia el desplegable y se vuelve a montar: mover las
            // opciones conserva cual estaba seleccionada y evita reconstruir
            // los <option>, que llevan sus datos.
            Array.from(selector.querySelectorAll('optgroup')).forEach(function (viejo) {
                viejo.remove();
            });

            if (!elegida) {
                // Sin tecnologia no hay nada por lo que ordenar: la lista
                // plana y completa, como estaba.
                opciones.forEach(function (opcion) {
                    selector.append(opcion);
                });
                return;
            }

            const nombre = tecnologia.options[tecnologia.selectedIndex].textContent.trim();
            const usadas = grupo('Usadas con ' + nombre);
            const otras = grupo('Otras categorías');

            opciones.forEach(function (opcion) {
                const suyas = (opcion.dataset.tecnologias || '')
                    .split(',')
                    .filter(Boolean);

                (suyas.includes(elegida) ? usadas : otras).append(opcion);
            });

            // Un grupo vacio solo anade ruido: al principio, cuando ninguna
            // categoria se ha usado todavia con esa tecnologia, no aparece.
            if (usadas.children.length) {
                selector.append(usadas);
            }

            if (otras.children.length) {
                selector.append(otras);
            }

            if (vacia) {
                selector.prepend(vacia);
            }
        }

        boton.addEventListener('click', function () {
            const id = selector.value;

            if (!id || idsActuales().includes(id)) {
                return;
            }

            const nombre = selector.options[selector.selectedIndex].textContent.trim();
            lista.append(crearItem(id, nombre));
            selector.value = '';
            sincronizar();
        });

        // Delegado: los items se crean y se borran, asi que el escuchador
        // vive en la lista y no en cada boton.
        lista.addEventListener('click', function (evento) {
            const quitar = evento.target.closest('.equipos-colores__quitar');

            if (!quitar) {
                return;
            }

            quitar.closest('.equipos-colores__item').remove();
            sincronizar();
        });

        // Enter dentro del selector agrega en vez de enviar el formulario: al
        // capturar varias categorias seguidas es el gesto natural, y un envio
        // a medias obligaria a rehacer el formulario entero.
        selector.addEventListener('keydown', function (evento) {
            if (evento.key === 'Enter') {
                evento.preventDefault();
                boton.click();
            }
        });

        if (tecnologia) {
            tecnologia.addEventListener('change', ordenarPorTecnologia);
        }

        ordenarPorTecnologia();
        sincronizar();
    }());
});
