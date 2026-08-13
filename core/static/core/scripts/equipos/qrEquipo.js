document.addEventListener('DOMContentLoaded', function () {
    const botonImprimir = document.getElementById('imprimir_qr_equipo');

    if (botonImprimir) {
        botonImprimir.addEventListener('click', function () {
            window.print();
        });
    }
});
