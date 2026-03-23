const AdjuntarImagenHelper = ( function () {
    const TIPOS_PERMITIDOS  = ["image/jpeg", "image/png", "image/webp"];
    const MAXIMO_MB = 15;

    function MDaBytes(mb){
        return mb * 1024 * 1024
    }

    function validarArchivo(archivo, opciones = {}) {

        const {
            tiposPermitidos = TIPOS_PERMITIDOS,
            maxMB = MAXIMO_MB
        } = opciones;

        if (!tiposPermitidos.includes(archivo.type)) {
            return { valido: false, error: "Formato no permitido" };
        }

        if (archivo.size > MDaBytes(maxMB)) {
            return { valido: false, error: `Máximo ${maxMB}MB permitido` };
        }

        return { valido: true };
    }

    function crearUrlPreview(archivo) {
        return URL.createObjectURL(archivo);
    }

    function quitarUrlPreview(url) {
        URL.revokeObjectURL(url);
    }

    return {
        validarArchivo,
        crearUrlPreview,
        quitarUrlPreview
    };


})();