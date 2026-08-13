document.addEventListener('DOMContentLoaded', function () {
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

    // La constancia no forma parte de las seis fotografias del equipo.
    const enlaceFicha = document.getElementById('abrir_ficha_firmada');

    if (enlaceFicha && typeof ImageViewer !== 'undefined') {
        enlaceFicha.addEventListener('click', function (evento) {
            evento.preventDefault();
            ImageViewer.open(
                enlaceFicha.dataset.imagenUrl,
                0,
                'Ficha firmada',
                [enlaceFicha.dataset.imagenEtiqueta]
            );
        });
    }

    // Si una miniatura no existe, se intenta mostrar el archivo completo.
    document.querySelectorAll('img[data-imagen-completa]').forEach(function (imagen) {
        imagen.addEventListener('error', function () {
            const completa = imagen.dataset.imagenCompleta;
            if (completa && imagen.src !== completa) {
                imagen.src = completa;
            }
        }, { once: true });
    });
});
