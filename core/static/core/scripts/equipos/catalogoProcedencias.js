document.addEventListener('DOMContentLoaded', function () {
    // Formatea 33484816 como 3348-4816. Prefijos y extensiones se respetan.
    const campos = [
        document.getElementById('telefono_procedencia_catalogo'),
        document.getElementById('telefono_alterno_procedencia_catalogo'),
    ].filter(Boolean);

    campos.forEach(function (campo) {
        function formatear() {
            const digitos = campo.value.replace(/\D/g, '');

            if (digitos.length !== 8 || campo.value.trim().startsWith('+')) {
                return;
            }

            campo.value = digitos.slice(0, 4) + '-' + digitos.slice(4);
        }

        campo.addEventListener('input', formatear);
        campo.addEventListener('blur', formatear);
    });
});
