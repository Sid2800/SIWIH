document.addEventListener('DOMContentLoaded', function () {
    // Registro y edicion comparten el mismo editor. Solo cambia el input que
    // recibira el WebP y el formulario que finalmente lo envia.
    const formularioEquipo = document.getElementById('formulario_equipo');
    const fotoEquipo = (
        document.getElementById('foto_general_dispositivo')
        || document.getElementById('imagen_archivo_dispositivo')
    );
    const fotoCamara = (
        document.getElementById('foto_general_camara')
        || document.getElementById('imagen_camara_dispositivo')
    );
    const selectorFoto = (
        document.getElementById('foto_general_selector')
        || document.getElementById('imagen_selector_dispositivo')
    );
    const seleccionarFoto = (
        document.getElementById('seleccionar_foto_general')
        || document.getElementById('seleccionar_imagen_dispositivo')
    );
    const capturarFoto = (
        document.getElementById('capturar_foto_general')
        || document.getElementById('capturar_imagen_dispositivo')
    );
    const previewFoto = (
        document.getElementById('foto_general_preview')
        || document.getElementById('imagen_preview_dispositivo')
    );
    const contenidoFoto = (
        document.getElementById('foto_general_contenido')
        || document.getElementById('imagen_contenido_dispositivo')
    );
    const tipoImagen = document.getElementById('tipo_imagen_dispositivo');
    const guardarImagen = document.getElementById('guardar_imagen_dispositivo');
    let previewUrl = null;

    function mostrarErrorFoto(mensaje) {
        if (window.toastr) {
            toastr.error(mensaje);
        } else {
            window.alert(mensaje);
        }
    }

    function actualizarPreview(archivo) {
        if (previewUrl) {
            AdjuntarImagenHelper.quitarUrlPreview(previewUrl);
        }

        previewUrl = AdjuntarImagenHelper.crearUrlPreview(archivo);
        previewFoto.src = previewUrl;
        previewFoto.hidden = false;
        contenidoFoto.hidden = true;
        if (guardarImagen) {
            guardarImagen.disabled = false;
        }
    }

    function obtenerEtiquetaFoto() {
        if (!tipoImagen || tipoImagen.selectedIndex < 0) {
            return 'general';
        }
        return tipoImagen.options[tipoImagen.selectedIndex].text.toLowerCase();
    }

    async function prepararFoto(inputOrigen) {
        const archivoOriginal = inputOrigen.files[0];
        inputOrigen.value = '';

        if (!archivoOriginal) {
            return;
        }

        const validacion = AdjuntarImagenHelper.validarArchivo(archivoOriginal);
        if (!validacion.valido) {
            mostrarErrorFoto(validacion.error);
            return;
        }

        const archivoWebp = await ImageEditor.open(
            archivoOriginal,
            {
                titulo: `Foto ${obtenerEtiquetaFoto()} del equipo`,
                subtitulo: 'Ajuste el encuadre antes de continuar'
            }
        );

        if (!archivoWebp) {
            return;
        }

        const transferencia = new DataTransfer();
        transferencia.items.add(archivoWebp);
        fotoEquipo.files = transferencia.files;
        actualizarPreview(archivoWebp);
    }

    if (
        fotoEquipo
        && fotoCamara
        && selectorFoto
        && seleccionarFoto
        && capturarFoto
    ) {
        seleccionarFoto.addEventListener('click', function () {
            fotoEquipo.click();
        });
        capturarFoto.addEventListener('click', function () {
            fotoCamara.click();
        });
        selectorFoto.addEventListener('click', function () {
            fotoEquipo.click();
        });
        selectorFoto.addEventListener('keydown', function (evento) {
            if (evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                fotoEquipo.click();
            }
        });
        fotoEquipo.addEventListener('change', function () {
            prepararFoto(fotoEquipo);
        });
        fotoCamara.addEventListener('change', function () {
            prepararFoto(fotoCamara);
        });
        window.addEventListener('beforeunload', function () {
            if (previewUrl) {
                AdjuntarImagenHelper.quitarUrlPreview(previewUrl);
            }
        });
    }

    // Las miniaturas existentes abren el visor compartido de SIWIH Images.
    const botonesGaleria = Array.from(
        document.querySelectorAll('.equipos-imagenes__abrir')
    );
    if (botonesGaleria.length && typeof ImageViewer !== 'undefined') {
        const urlsGaleria = botonesGaleria.map(function (boton) {
            return boton.dataset.imagenUrl;
        });
        const etiquetasGaleria = botonesGaleria.map(function (boton) {
            return boton.dataset.imagenEtiqueta;
        });
        const contenedorGaleria = document.querySelector('[data-titulo-galeria]');
        const tituloGaleria = contenedorGaleria
            ? contenedorGaleria.dataset.tituloGaleria
            : 'Fotografías del equipo';

        botonesGaleria.forEach(function (boton, indice) {
            boton.addEventListener('click', function () {
                ImageViewer.open(
                    urlsGaleria,
                    indice,
                    tituloGaleria,
                    etiquetasGaleria
                );
            });
        });
    }

    document.querySelectorAll('img[data-imagen-completa]').forEach(function (imagen) {
        imagen.addEventListener('error', function () {
            const completa = imagen.dataset.imagenCompleta;
            if (completa && imagen.src !== completa) {
                imagen.src = completa;
            }
        }, { once: true });
    });

    // La garantia se calcula en pantalla igual que la calculara el servidor,
    // para que el usuario vea el vencimiento antes de guardar. El calculo de
    // verdad lo hace el modelo: esto es solo un anticipo.
    const inicioGarantia = document.getElementById('inicio_garantia_dispositivo');
    const mesesGarantia = document.getElementById('garantia_meses_dispositivo');
    const finGarantia = document.getElementById('garantia_dispositivo');
    const ayudaGarantia = document.getElementById('ayuda_garantia_dispositivo');

    function sumarMeses(fechaTexto, meses) {
        // El plazo se cuenta en meses de calendario, no en dias: dos anios
        // vencen el mismo dia del mes. El ultimo dia cubierto es la vispera
        // de cumplirse el plazo.
        const partes = fechaTexto.split('-').map(Number);
        const inicio = new Date(partes[0], partes[1] - 1, partes[2]);
        const fin = new Date(inicio.getFullYear(), inicio.getMonth() + meses, inicio.getDate());

        // Un 31 de enero mas un mes no existe: el navegador lo desborda al mes
        // siguiente, asi que se retrocede al ultimo dia del mes esperado.
        const mesEsperado = (inicio.getMonth() + meses) % 12;
        if (fin.getMonth() !== mesEsperado) {
            fin.setDate(0);
        }

        fin.setDate(fin.getDate() - 1);

        const mes = String(fin.getMonth() + 1).padStart(2, '0');
        const dia = String(fin.getDate()).padStart(2, '0');
        return `${fin.getFullYear()}-${mes}-${dia}`;
    }

    function actualizarGarantia() {
        if (!inicioGarantia || !mesesGarantia || !finGarantia) {
            return;
        }

        const meses = parseInt(mesesGarantia.value, 10);
        const calculada = inicioGarantia.value && !Number.isNaN(meses);

        // Con duracion elegida el vencimiento no se teclea: se muestra ya
        // resuelto y de solo lectura, para que nadie lo contradiga a mano.
        finGarantia.readOnly = calculada;

        if (calculada) {
            finGarantia.value = sumarMeses(inicioGarantia.value, meses);
        }

        if (!ayudaGarantia) {
            return;
        }

        if (calculada) {
            ayudaGarantia.textContent = 'Calculado desde el inicio y la duración.';
            ayudaGarantia.hidden = false;
        } else if (inicioGarantia.value) {
            ayudaGarantia.textContent = 'Elija una duración o escriba la fecha del contrato.';
            ayudaGarantia.hidden = false;
        } else {
            ayudaGarantia.hidden = true;
        }
    }

    if (inicioGarantia && mesesGarantia && finGarantia) {
        inicioGarantia.addEventListener('change', actualizarGarantia);
        mesesGarantia.addEventListener('change', actualizarGarantia);
        actualizarGarantia();
    }

    // Select2 consulta empleados por AJAX para no cargar toda la tabla en el HTML.
    const responsableSelect = $('#responsable_dispositivo');
    const urlEmpleados = formularioEquipo
        ? formularioEquipo.dataset.urlEmpleados
        : '';

    if (responsableSelect.length && responsableSelect.select2 && urlEmpleados) {
        responsableSelect.select2({
            width: '100%',
            placeholder: 'Buscar por DNI o nombre',
            minimumInputLength: 1,
            ajax: {
                url: urlEmpleados,
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    return {
                        q: params.term || ''
                    };
                },
                processResults: function (data) {
                    return data;
                },
                cache: true
            },
            language: {
                inputTooShort: function () {
                    return 'Escriba el DNI o nombre del empleado';
                },
                noResults: function () {
                    return 'No se encontraron empleados';
                },
                searching: function () {
                    return 'Buscando...';
                }
            }
        });
    }

    // Al elegir al responsable se consulta su ficha en RRHH: se muestra si es
    // personal clinico y en que unidad esta, y se sugiere la ubicacion. Es una
    // sugerencia: la unidad dice donde trabaja la persona, y el aparato puede
    // estar en un punto de atencion mas concreto, asi que solo se rellena
    // cuando el campo esta vacio y nunca pisa lo que el usuario ya eligio.
    const ubicacionSelect = document.getElementById('ubicacion_dispositivo');
    const datosResponsable = document.getElementById('datos_responsable_dispositivo');

    function describirEmpleado(datos) {
        if (!datosResponsable) {
            return;
        }

        const partes = [datos.tipo_personal];

        if (datos.unidad) {
            partes.push(datos.unidad);
        }

        datosResponsable.textContent = partes.join(' · ');
        datosResponsable.hidden = false;
    }

    async function consultarDatosEmpleado(empleadoId) {
        const url = datosResponsable
            ? datosResponsable.dataset.urlDatos
            : '';

        if (!url || !empleadoId) {
            return;
        }

        try {
            const respuesta = await fetch(
                `${url}?empleado_id=${encodeURIComponent(empleadoId)}`,
                { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
            );

            if (!respuesta.ok) {
                return;
            }

            const datos = await respuesta.json();
            describirEmpleado(datos);

            if (ubicacionSelect && !ubicacionSelect.value && datos.ubicacion_sugerida) {
                ubicacionSelect.value = String(datos.ubicacion_sugerida);
            }
        } catch (error) {
            // Que falle la sugerencia no debe estorbar el registro: la
            // ubicacion se elige a mano, que es el flujo normal de todos modos.
            if (datosResponsable) {
                datosResponsable.hidden = true;
            }
        }
    }

    if (responsableSelect.length) {
        responsableSelect.on('change', function () {
            consultarDatosEmpleado(responsableSelect.val());
        });

        if (responsableSelect.val()) {
            consultarDatosEmpleado(responsableSelect.val());
        }
    }

    // Tipo, marca y modelo son tres Select2 en cascada: cada uno solo ofrece
    // lo que existe para lo ya elegido. Los catalogos se cargan por AJAX y no
    // aceptan valores libres; las opciones nacen en el catalogo.
    const tipoSelect = $('#tipo_dispositivo');
    const marcaSelect = $('#marca_dispositivo');
    const modeloSelect = $('#modelo_dispositivo');

    function configurarSelectRemoto(elemento, opciones) {
        return elemento.select2({
            width: '100%',
            allowClear: true,
            placeholder: opciones.placeholder,
            ajax: {
                url: opciones.url,
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    return $.extend(
                        { q: params.term || '', page: params.page || 1 },
                        opciones.extra ? opciones.extra() : {}
                    );
                },
                processResults: function (data) {
                    return data;
                },
                cache: true
            },
            language: {
                noResults: function () {
                    return opciones.sinResultados;
                },
                searching: function () {
                    return 'Buscando...';
                }
            }
        });
    }

    function valorElegido(elemento) {
        const valor = elemento.val();
        return valor ? String(valor) : '';
    }

    function tipoElegido() {
        return valorElegido(tipoSelect);
    }

    function marcaElegida() {
        return valorElegido(marcaSelect);
    }

    // Cada eslabon se habilita cuando el anterior tiene valor. Deshabilitar en
    // vez de esconder deja ver que el campo existe y por que todavia no se
    // puede usar; el placeholder lo explica.
    function refrescarCascada() {
        const hayTipo = tipoElegido() !== '';
        const hayMarca = marcaElegida() !== '';

        if (marcaSelect.length) {
            marcaSelect.prop('disabled', !hayTipo);
        }

        if (modeloSelect.length) {
            modeloSelect.prop('disabled', !(hayTipo && hayMarca));
        }
    }

    if (tipoSelect.length && tipoSelect.select2) {
        configurarSelectRemoto(tipoSelect, {
            url: tipoSelect.data('url-tipos'),
            placeholder: 'Buscar o elegir tipo de equipo',
            sinResultados: 'No se encontraron tipos de equipo'
        });
    }

    if (marcaSelect.length && marcaSelect.select2) {
        configurarSelectRemoto(marcaSelect, {
            url: marcaSelect.data('url-marcas'),
            placeholder: 'Elija primero el tipo de equipo',
            sinResultados: 'Este tipo no tiene marcas registradas',
            extra: function () {
                return { tipo_id: tipoElegido() };
            }
        });
    }

    if (modeloSelect.length && modeloSelect.select2) {
        configurarSelectRemoto(modeloSelect, {
            url: modeloSelect.data('url-modelos'),
            placeholder: 'Elija primero la marca',
            sinResultados: 'Esta marca no tiene modelos de este tipo',
            extra: function () {
                return { tipo_id: tipoElegido(), marca_id: marcaElegida() };
            }
        });
    }

    // Al cambiar de tipo caen marca y modelo: los que estaban elegidos
    // pertenecian al tipo anterior y ya no son opciones validas.
    tipoSelect.on('change', function () {
        marcaSelect.val(null).trigger('change.select2');
        modeloSelect.val(null).trigger('change.select2');
        refrescarCascada();
        mostrarDatosTipo(tipoElegido());
    });

    marcaSelect.on('change', function () {
        modeloSelect.val(null).trigger('change.select2');
        refrescarCascada();
    });

    // Categoria y tecnologia no se capturan: las trae el tipo. Se muestran
    // para que quien registra note de inmediato si eligio el tipo equivocado,
    // antes de llenar el resto de la ficha.
    const datosTipo = document.getElementById('datos_tipo_dispositivo');

    async function mostrarDatosTipo(tipoId) {
        const url = datosTipo ? datosTipo.dataset.urlDatos : '';

        if (!url || !tipoId) {
            if (datosTipo) {
                datosTipo.hidden = true;
            }
            return;
        }

        try {
            const respuesta = await fetch(
                `${url}?tipo_id=${encodeURIComponent(tipoId)}`,
                { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
            );

            if (!respuesta.ok) {
                datosTipo.hidden = true;
                return;
            }

            const datos = await respuesta.json();
            const categorias = [datos.categoria].concat(datos.secundarias || []);
            const partes = [categorias.join(' + '), datos.tecnologia];

            // Un tipo sin marcas deja la cascada sin nada que ofrecer. Vale
            // mas avisarlo aqui que dejar al usuario abriendo un desplegable
            // vacio sin saber por que.
            if (!datos.total_marcas) {
                partes.push('sin marcas registradas en el catálogo');
                datosTipo.classList.add('equipos-registro__ayuda--aviso');
            } else {
                datosTipo.classList.remove('equipos-registro__ayuda--aviso');
            }

            datosTipo.textContent = partes.join(' · ');
            datosTipo.hidden = false;
        } catch (error) {
            datosTipo.hidden = true;
        }
    }

    refrescarCascada();

    if (tipoElegido()) {
        mostrarDatosTipo(tipoElegido());
    }

    // La procedencia se busca contra el servidor igual que las anteriores. El
    // catalogo puede llegar a cientos de entradas y un desplegable corriente
    // obligaria a recorrerlas a mano. El endpoint tambien busca por RTN,
    // porque es lo que trae la factura que el tecnico tiene delante.
    const procedenciaSelect = $('#procedencia_dispositivo');

    if (procedenciaSelect.length && procedenciaSelect.select2) {
        configurarSelectRemoto(procedenciaSelect, {
            url: procedenciaSelect.data('url-procedencias'),
            placeholder: 'Buscar por nombre o RTN',
            sinResultados: 'No se encontraron procedencias'
        });
    }

    // Select2 mide el ancho al arrancar. Los controles dentro de un details
    // cerrado se reajustan cuando este se despliega.
    const bloquesOpcionales = document.querySelectorAll(
        '.equipos-registro__opcionales'
    );

    bloquesOpcionales.forEach(function (bloqueOpcionales) {
        bloqueOpcionales.addEventListener('toggle', function () {
            if (this.open) {
                $('#marca_dispositivo, #modelo_dispositivo, #procedencia_dispositivo')
                    .trigger('change.select2');
            }
        });
    });

    // Abre el bloque de procedencia antes de que el navegador intente enfocar
    // un control required que estuviera oculto dentro de details.
    const bloqueProcedencia = document.getElementById('procedencia_equipo');

    if (formularioEquipo && bloqueProcedencia) {
        formularioEquipo.addEventListener('invalid', function (evento) {
            if (bloqueProcedencia.contains(evento.target)) {
                bloqueProcedencia.open = true;
            }
        }, true);
    }
});
