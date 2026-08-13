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
    const estadoFoto = (
        document.getElementById('foto_general_estado')
        || document.getElementById('imagen_estado_dispositivo')
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
        estadoFoto.textContent = 'Foto lista en formato WebP.';
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

        if (typeof DataTransfer === 'undefined') {
            mostrarErrorFoto('Este navegador no permite preparar la foto.');
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

    // Muestra solo el selector de area que corresponde al tipo elegido.
    const tipoArea = document.getElementById('tipo_area_dispositivo');
    const campoClinica = document.getElementById('campo_area_clinica');
    const campoNoClinica = document.getElementById('campo_area_no_clinica');
    const areaClinica = document.getElementById('area_clinica_dispositivo');
    const areaNoClinica = document.getElementById('area_no_clinica_dispositivo');

    function actualizarSelectorArea() {
        const mostrarClinica = tipoArea.value === 'clinica';
        const mostrarNoClinica = tipoArea.value === 'no_clinica';

        campoClinica.hidden = !mostrarClinica;
        campoNoClinica.hidden = !mostrarNoClinica;
        areaClinica.disabled = !mostrarClinica;
        areaNoClinica.disabled = !mostrarNoClinica;

        if (!mostrarClinica) {
            areaClinica.value = '';
        }
        if (!mostrarNoClinica) {
            areaNoClinica.value = '';
        }
    }

    tipoArea.addEventListener('change', actualizarSelectorArea);
    actualizarSelectorArea();

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

    // Marca y modelo son dos Select2 encadenados. Los catalogos se cargan por
    // AJAX y no aceptan valores libres: las opciones nacen en sus catalogos.
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

    function marcaElegida() {
        const valor = marcaSelect.val();
        return valor ? String(valor) : '';
    }

    function refrescarEstadoModelo() {
        if (!modeloSelect.length) {
            return;
        }
        const hayMarca = marcaElegida() !== '';
        modeloSelect.prop('disabled', !hayMarca);
    }

    if (marcaSelect.length && marcaSelect.select2) {
        configurarSelectRemoto(marcaSelect, {
            url: marcaSelect.data('url-marcas'),
            placeholder: 'Buscar o elegir marca',
            sinResultados: 'No se encontraron marcas'
        });
    }

    if (modeloSelect.length && modeloSelect.select2) {
        configurarSelectRemoto(modeloSelect, {
            url: modeloSelect.data('url-modelos'),
            placeholder: 'Seleccione primero una marca',
            sinResultados: 'Esta marca no tiene modelos activos',
            extra: function () {
                return { marca_id: marcaElegida() };
            }
        });

        refrescarEstadoModelo();

        marcaSelect.on('change', function () {
            modeloSelect.val(null).trigger('change.select2');
            refrescarEstadoModelo();
        });
    }

    // Tipo de equipo usa el mismo Select2 remoto y tampoco admite valores libres.
    const tipoSelect = $('#tipo_dispositivo');

    if (tipoSelect.length && tipoSelect.select2) {
        configurarSelectRemoto(tipoSelect, {
            url: tipoSelect.data('url-tipos'),
            placeholder: 'Buscar o elegir tipo de equipo',
            sinResultados: 'No se encontraron tipos de equipo'
        });
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
