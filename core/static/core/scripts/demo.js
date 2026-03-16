document.addEventListener('DOMContentLoaded', function () {
    // Registrar plugin de preview
    FilePond.registerPlugin(FilePondPluginImagePreview);

    // Crear FilePond
    FilePond.create(
        document.querySelector('.filepond'),
        {
            allowMultiple: false,
            instantUpload: false,   // importante
            allowRevert: false,
            imagePreviewHeight: 200,
            labelIdle: 'Toca para tomar o seleccionar una imagen'
        }
    );


})