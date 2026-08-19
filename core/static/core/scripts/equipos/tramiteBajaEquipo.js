document.addEventListener('DOMContentLoaded', function () {
    // La foto del equipo se amplia en el visor compartido antes de confirmar.
    const fotoEquipo = document.getElementById('ampliar_foto_equipo');

    if (fotoEquipo && typeof ImageViewer !== 'undefined') {
        function ampliarFotoEquipo() {
            ImageViewer.open(
                fotoEquipo.dataset.imagenUrl,
                0,
                'Foto del equipo',
                [fotoEquipo.alt]
            );
        }

        fotoEquipo.addEventListener('click', ampliarFotoEquipo);
        fotoEquipo.addEventListener('keydown', function (evento) {
            if (evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                ampliarFotoEquipo();
            }
        });
    }

    // El editor compartido entrega el WebP que acepta SIWIH Images.
    const fichaFirmada = document.getElementById('ficha_firmada_dispositivo');
    const fichaCamara = document.getElementById('ficha_firmada_camara');
    const selectorFicha = document.getElementById('ficha_firmada_selector');
    const seleccionarFicha = document.getElementById('seleccionar_ficha_firmada');
    const capturarFicha = document.getElementById('capturar_ficha_firmada');
    const previewFicha = document.getElementById('ficha_firmada_preview');
    const contenidoFicha = document.getElementById('ficha_firmada_contenido');
    const formularioBaja = document.querySelector('.equipos-baja__formulario');
    const botonGenerar = document.getElementById('generar_ficha_pdf');
    const botonConfirmar = document.getElementById('confirmar_baja_dispositivo');
    const campoMotivo = document.getElementById('motivo_baja_dispositivo');
    const codigoEquipo = formularioBaja
        ? formularioBaja.dataset.codigoEquipo
        : '';
    let previewUrl = null;

    function mostrarError(mensaje) {
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
        previewFicha.src = previewUrl;
        previewFicha.hidden = false;
        contenidoFicha.hidden = true;
    }

    async function prepararFicha(inputOrigen) {
        const archivoOriginal = inputOrigen.files[0];
        inputOrigen.value = '';

        if (!archivoOriginal) {
            return;
        }

        const validacion = AdjuntarImagenHelper.validarArchivo(archivoOriginal);
        if (!validacion.valido) {
            mostrarError(validacion.error);
            return;
        }

        const archivoWebp = await ImageEditor.open(
            archivoOriginal,
            {
                titulo: 'Ficha firmada de baja',
                subtitulo: 'Ajuste el encuadre para que firmas y texto sean legibles'
            }
        );

        if (!archivoWebp) {
            return;
        }

        const transferencia = new DataTransfer();
        transferencia.items.add(archivoWebp);
        fichaFirmada.files = transferencia.files;
        actualizarPreview(archivoWebp);
    }

    if (
        fichaFirmada
        && fichaCamara
        && selectorFicha
        && seleccionarFicha
        && capturarFicha
    ) {
        seleccionarFicha.addEventListener('click', function () {
            fichaFirmada.click();
        });
        capturarFicha.addEventListener('click', function () {
            fichaCamara.click();
        });
        selectorFicha.addEventListener('click', function () {
            fichaFirmada.click();
        });
        selectorFicha.addEventListener('keydown', function (evento) {
            if (evento.key === 'Enter' || evento.key === ' ') {
                evento.preventDefault();
                fichaFirmada.click();
            }
        });
        fichaFirmada.addEventListener('change', function () {
            prepararFicha(fichaFirmada);
        });
        fichaCamara.addEventListener('change', function () {
            prepararFicha(fichaCamara);
        });
        window.addEventListener('beforeunload', function () {
            if (previewUrl) {
                AdjuntarImagenHelper.quitarUrlPreview(previewUrl);
            }
        });
    }

    function datosFichaFaltantes() {
        const faltantes = [];

        if (campoMotivo && !campoMotivo.value.trim()) {
            faltantes.push({ campo: campoMotivo, etiqueta: 'el motivo de baja' });
        }

        return faltantes;
    }

    function enfocarCampo(campo) {
        campo.focus();
    }

    if (botonGenerar) {
        botonGenerar.addEventListener('click', function (evento) {
            const faltantes = datosFichaFaltantes();

            if (!faltantes.length) {
                return;
            }

            evento.preventDefault();
            mostrarError(
                'Complete '
                + faltantes.map(function (dato) { return dato.etiqueta; }).join(', ')
                + ' antes de generar la ficha.'
            );
            enfocarCampo(faltantes[0].campo);
        });
    }

    // La baja es irreversible, por lo que se confirma nombrando el equipo.
    if (formularioBaja && botonConfirmar) {
        let bajaConfirmada = false;

        formularioBaja.addEventListener('submit', async function (evento) {
            if (evento.submitter !== botonConfirmar || bajaConfirmada) {
                return;
            }

            evento.preventDefault();

            if (fichaFirmada && !fichaFirmada.files.length) {
                mostrarError(
                    'Adjunte la constancia firmada antes de confirmar la baja.'
                );
                if (selectorFicha) {
                    selectorFicha.focus();
                }
                return;
            }

            const aceptado = await confirmarAccion({
                titulo: 'Confirmar baja definitiva',
                mensajes: [
                    'El equipo <strong>' + codigoEquipo + '</strong> quedará dado de '
                    + 'baja de forma permanente: no podrá editarse ni volver a '
                    + 'asignarse. Esta acción no se puede deshacer.'
                ],
                icono: 'warning',
                botonAfirmativo: 'Sí, dar de baja',
                botonNegativo: 'Cancelar'
            });

            if (!aceptado) {
                return;
            }

            bajaConfirmada = true;
            formularioBaja.requestSubmit(botonConfirmar);
            botonConfirmar.disabled = true;
        });
    }
});
