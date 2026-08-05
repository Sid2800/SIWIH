const TipoAtencionLoader = (function () {

    async function cargar(selectId) {
    
        const select = document.getElementById(selectId);
        if (!select) return;
        try {
            // construir URL correctamente
            const data = await fetchData(API_URLS.listarTiposAtencion);

            // limpiar select
            if (select.virtualSelect) {
                select.virtualSelect.destroy();
            }


            if (Array.isArray(data) && data.length > 0) {

            const opciones = data.map(item => ({
                value: item.id,
                label: item.nombre_tipo_atencion,
                customData: item.prioridad_texto,
                description: item.prioridad_texto
            }));

            VirtualSelect.init({
                        ele: `#${selectId}`,
                        options: opciones,
                        hasOptionDescription: true,
                        searchPlaceholderText: 'Buscar...',
                        search: true,
                        placeholder: 'Seleccione',
                        additionalClasses: 'custom-wrapper',
                        additionalDropboxClasses: 'custom-dropbox',
                        
                    }); 

            return //select.virtualSelect;



            } else {
                console.warn("No hay tipos de atencion disponibles.");
                return null;
            }

        } catch (error) {
            console.error("Error cargando tipos de atencion:", error);
            toastr.error("No se pudieron cargar los tipos de atencion");
            return null;
        }
    }

    return {
        cargar
    };

})();