document.addEventListener('DOMContentLoaded', function () {
    // Definición de las URLs de la API
    const API_URLS = {
        obtenerInteraccionFiltroAgrupacion: urls["obtenerInteraccionFiltroAgrupacion"],
        obtenerOpcionesFiltro: urls["obtenerOpcionesFiltro"],
        reporteGenerado: urls["reporteGenerado"],
        informesImagenologia: urls["informesImagenologia"],
        informesReferencia: urls["informesReferencia"],
        informesCatalogo: urls["informesCatalogo"],


    }

    // Referencias a los elementos del DOM
    const fechaInicio = document.getElementById('reporte-gen-fecha-inicial');
    const fechaFin = document.getElementById('reporte-gen-fecha-final');
    const agrupacion = document.getElementById('reporte-gen-agrupacion');
    const modelo = document.getElementById('reporte-gen-modelo');
    const interaccion = document.getElementById('reporte-gen-interacion');
    const filtro = document.getElementById('reporte-gen-filtro-campo');
    const valor = document.getElementById('reporte-gen-filtro-valor');
    const generarBtn = document.getElementById('reporte-gen-generar-boton');
    const detalleCk = document.getElementById('reporte-gen-interruptor-detalle');
    // infomre Rx
    const informeAnio = document.getElementById('informe-rx-informe-anio');
    const informeMes = document.getElementById('informe-rx-informe-mes');

    const informeRxInformeSelect = document.getElementById('informe-rx-informe');
    const informeRxGenerarBtn = document.getElementById('informe-rx-generar-boton');


    const informeReferenciaInformeSelect = document.getElementById('informe-referencia-informe');
    const informeReferenciaGenerarBtn = document.getElementById('informe-referencia-generar-boton');
// Catalogos
    const informeCatagoloGenerarBtn = document.getElementById('catalogo-generar-boton');
    const fechaInicioCatalogo = document.getElementById('catalogo-fecha-inicial');
    const fechaFinCatalogo = document.getElementById('catalogo-fecha-final');
    const informeCatalogoSelect = document.getElementById('catalogo-tipo');


// CHECK 

    const informeCriteriosPDF = document.getElementById('informe-export-pdf');
    const informeCriteriosEXCEL = document.getElementById('informe-export-xlsx');



    





    //#region Listeners de Eventos

    // Listener para el cambio del selector de 'modelo'.
    // Limpia y recarga las opciones de Agrupación, Interacción y Filtro.
    modelo.addEventListener('change', async function () {
        const valorModelo = modelo.value;

        // Destruye y limpia las instancias de TomSelect para recargar opciones.
        [agrupacion, interaccion, filtro].forEach(selectElement => {
            if (selectElement && selectElement.tomselect) {
                selectElement.tomselect.clearOptions();
                selectElement.tomselect.clear();
                selectElement.tomselect.destroy();
            }
        });

        await TraerInteraccionAgrupacionFiltro(valorModelo);


    });

    // Listener para el cambio del selector de 'filtro'.
    // Carga las opciones del selector 'valor' según el filtro y modelo seleccionados.
    filtro.addEventListener('change', async function () {
        const modeloV = modelo.value;
        const campoV = filtro.value;

        if (campoV) {
            if (valor && valor.tomselect) {
                valor.tomselect.clearOptions();
                valor.tomselect.clear();
                valor.tomselect.destroy();
            }
            await TraerValoresFiltro(modeloV, campoV);
        }
    });

    // Listener para el botón de 'generar'.
    // Valida los campos y envía los datos para generar el reporte.
    generarBtn.addEventListener('click', async function () { // ¡Ojo! Hacemos este listener async también.

        // Guardamos el contenido original del botón para restaurarlo después.
        const textoOriginal = generarBtn.innerHTML;

        // Subfunción para restaurar el botón a su estado original.
        function habilitarBoton() {
            generarBtn.disabled = false;
            generarBtn.innerHTML = textoOriginal;
        }

        // Desactivamos el botón y mostramos el spinner.
        generarBtn.disabled = true;
        generarBtn.innerHTML = `
            <span class="spinner" style="
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid #ccc;
                border-top: 2px solid #333;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
                margin-right: 6px;
                vertical-align: middle;
            "></span> Generando...
        `;

        try {
            if (verficarLleno()) { // Seguridad 1: Validación en el cliente.
                const objReporte = crearObjetoReporte();
                if (objReporte) {
                    // ¡Aquí está el cambio clave! Usamos 'await' para esperar que EnviarReporte termine.
                    await EnviarReporte(objReporte);
                }
            } else {
                toastr.warning("Por favor indique cada uno de los campos", "Digitacion");
            }
        } catch (error) {
            // En caso de un error inesperado en la lógica del botón
            console.error("Error en el proceso de generación del reporte:", error);
            toastr.error("Ocurrió un error inesperado al generar el reporte.");
        } finally {
            // 'finally' asegura que el botón siempre se habilite de nuevo,
            // ya sea que la operación termine bien o con error.
            habilitarBoton();
        }
    });
    

    //#endregion

    //#region Funciones de Carga y Llenado

    /**
     * Obtiene y actualiza los selectores de interacción, agrupación y filtro
     * basándose en el modelo seleccionado.
     * @param {string} modelo - El valor del modelo seleccionado.
     */
    async function TraerInteraccionAgrupacionFiltro(modelo) {
        try {
            const data = await fetchData(API_URLS.obtenerInteraccionFiltroAgrupacion, {
                modelo: modelo,
            });

            if (Object.keys(data).length > 0) {
                if (Object.keys(data.interaccion).length > 0) llenarInteraccion(data.interaccion);
                if (Object.keys(data.agrupacion).length > 0) llenarAgrupacion(data.agrupacion);
                if (Object.keys(data.filtro).length > 0) llenarFiltro(data.filtro);
            }
        } catch (error) {
            console.error("Error al obtener los datos del modelo", error);
        }
    }

    /**
     * Llena el selector de agrupaciones con las opciones recibidas.
     * @param {object} agrupaciones - Objeto con las opciones de agrupación (value: text).
     */
    function llenarAgrupacion(agrupaciones) {
        const opciones = Object.entries(agrupaciones).map(([value, text]) => ({
            value,
            text
        }));
        const tom = new TomSelect(agrupacion, {
            options: opciones,
            placeholder: "SELECCIONE UNA AGRUPACION"
        });
        if (opciones.length > 0) tom.setValue(opciones[0].value);
    }

    /**
     * Llena el selector de interacciones con las opciones recibidas.
     * @param {object} interacciones - Objeto con las opciones de interacción (value: text).
     */
    function llenarInteraccion(interacciones) {
        const opciones = Object.entries(interacciones).map(([value, text]) => ({
            value,
            text
        }));
        const tom = new TomSelect(interaccion, {
            options: opciones,
            placeholder: "SELECCIONE UNA INTERACCION"
        });
        if (opciones.length > 0) tom.setValue(opciones[0].value);
    }

    /**
     * Llena el selector de filtros con las opciones recibidas.
     * @param {object} filtros - Objeto con las opciones de filtro (value: text).
     */
    function llenarFiltro(filtros) {
        const opciones = Object.entries(filtros).map(([value, text]) => ({
            value,
            text
        }));
        const tom = new TomSelect(filtro, {
            options: opciones,
            placeholder: "SELECCIONE UN FILTRO"
        });
        if (opciones.length > 0) tom.setValue(opciones[opciones.length - 1].value);
    }

    /**
     * Obtiene y actualiza las opciones del selector de valor de filtro
     * basándose en el modelo y el campo de filtro seleccionados.
     * @param {string} modelo - Nombre del modelo.
     * @param {string} campo - Nombre del campo de filtro.
     */
    async function TraerValoresFiltro(modelo, campo) {
        try {
            const data = await fetchData(API_URLS.obtenerOpcionesFiltro, {
                modelo: modelo,
                campo: campo
            });
            if (Object.keys(data).length > 0 && Object.keys(data.valores).length > 0) {
                llenarValores(data.valores);
            }
        } catch (error) {
            console.error("Error al obtener los valores del filtro:", error);
        }
    }

    /**
     * Llena el selector de valores de filtro con las opciones recibidas.
     * @param {Array<Object>} campos - Array de objetos con 'id' y 'valor' para las opciones.
     */
    function llenarValores(campos) {
        const opciones = campos.map(({
            id,
            valor
        }) => ({
            value: id,
            text: valor
        }));
        const tom = new TomSelect(valor, {
            options: opciones,
            placeholder: "SELECCIONE UN VALOR"
        });
        if (opciones.length > 0) tom.setValue(opciones[0].value);
    }

    //#endregion

    //#region Lógica de Reporte

    /**
     * Verifica que todos los campos select dentro del formulario de reportes tengan un valor.
     * @returns {boolean} - True si todos los campos están llenos, false si hay alguno vacío.
     */
    function verficarLleno() {
        const fieldset = document.querySelector('.frmGeneradorReportesCampos');
        const selects = fieldset.querySelectorAll('select');
        for (let select of selects) {
            if (!select.value || select.value.trim() === '') {
                return false;
            }
        }
        return true;
    }

    /**
     * Crea un objeto con todos los datos necesarios para generar el reporte.
     * Formatea las fechas y obtiene los textos de las opciones de filtro.
     * @returns {object} - Objeto con los datos del reporte.
     */
    function crearObjetoReporte() {
        const fechaInicioValor = new Date(fechaInicio.value);
        const fechaFinValor = new Date(fechaFin.value);
        const fechaInicioStr = fechaInicioValor.toISOString().slice(0, 10);
        const fechaFinStr = fechaFinValor.toISOString().slice(0, 10);

        const campoFiltroTexto = filtro.options[filtro.selectedIndex].text;
        const campoValorTexto = valor.options[valor.selectedIndex].text;

        return {
            fechaInicio: fechaInicioStr,
            fechaFin: fechaFinStr,
            agrupacion: agrupacion.value,
            modelo: modelo.value,
            interaccion: interaccion.value,
            filtro: filtro.value,
            valor: valor.value,
            detalles: detalleCk.checked ? 1 : 0,
            campoFiltroTexto: campoFiltroTexto,
            campoValorTexto: campoValorTexto
        };
    }

    /**
     * Envía los datos del reporte al servidor y maneja la respuesta (PDF o JSON).
     * @param {object} reporteData - Datos del reporte a enviar.
     */
    async function EnviarReporte(reporteData) {
        const csrfToken = window.CSRF_TOKEN; // Seguridad 3: Uso de CSRF Token.

        try {
            const response = await fetch(API_URLS.reporteGenerado, {
                method: "POST",
                body: JSON.stringify({
                    fechaIni: reporteData.fechaInicio,
                    fechaFin: reporteData.fechaFin,
                    modelo: reporteData.modelo,
                    interaccion: reporteData.interaccion,
                    agrupacion: reporteData.agrupacion,
                    campoFiltro: reporteData.filtro,
                    valorFiltro: reporteData.valor,
                    detalles: reporteData.detalles,
                    campoFiltroTexto: reporteData.campoFiltroTexto,
                    campoValorTexto: reporteData.campoValorTexto
                }),
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
            });

            // Seguridad 2: Manejo de errores de API.
            if (!response.ok) {
                const data = await response.json();
                if (data.error) toastr.error(data.error, "Error");
                else if (data.errors) {
                    Object.entries(data.errors).forEach(([campo, mensaje]) => {
                        toastr.error(mensaje, `Error en: ${campo}`);
                    });
                } else toastr.error("Ocurrió un error inesperado.");
                return;
            }

            const contentType = response.headers.get("Content-Type");
            if (contentType === "application/pdf") {
                const blob = await response.blob();
                const pdfUrl = URL.createObjectURL(blob);
                const nuevaVentana = window.open(pdfUrl, "_blank");
                if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                    toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                }
                setTimeout(() => URL.revokeObjectURL(pdfUrl), 10000); // Limpiar URL temporal
            } else {
                const data = await response.json();
                if (data.success) toastr.success(data.message || "Proceso realizado correctamente");
                else toastr.error(data.error || "Ocurrió un error durante el proceso.");
            }
        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al generar el reporte");
        }
    }

    function limpiarNombreArchivo(nombre) {
        if (!nombre) return "archivo.xlsx";

        // quitar caracteres no válidos en Windows
        nombre = nombre.replace(/[\\/:*?"<>|]/g, "");

        // quitar el subrayado final antes de la extensión
        nombre = nombre.replace(/_+\.xlsx$/i, ".xlsx");

        // si trae .xlsx_.xlsx corregir
        nombre = nombre.replace(/(\.xlsx)+$/i, ".xlsx");

        // si termina con guion bajo  eliminar
        nombre = nombre.replace(/_+$/g, "");

        // si no tiene extensión  agregar una sola vez
        if (!nombre.toLowerCase().endsWith(".xlsx")) {
            nombre += ".xlsx";
        }

        return nombre;
    }

    //#endregion

    //#region  Informes 
    // Listener para el botón de 'generar'.
    // llama al ebvio de informe RX.
    if (informeRxGenerarBtn){
            informeRxGenerarBtn.addEventListener('click', async function () { // ¡Ojo! Hacemos este listener async también.

            if (informeCriteriosPDF) {
                if (informeCriteriosEXCEL && informeCriteriosEXCEL.checked) {
                    toastr.error("Función en desarrollo, lamentamos las molestias", "Ups");
                    return;
                }
            }


            // Guardamos el contenido original del botón para restaurarlo después.
            const textoOriginal = informeRxGenerarBtn.innerHTML;

            // Subfunción para restaurar el botón a su estado original.
            function habilitarBoton() {
                informeRxGenerarBtn.disabled = false;
                informeRxGenerarBtn.innerHTML = textoOriginal;
            }

            // Desactivamos el botón y mostramos el spinner.
            informeRxGenerarBtn.disabled = true;
            informeRxGenerarBtn.innerHTML = `
                <span class="spinner" style="
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    border: 2px solid #ccc;
                    border-top: 2px solid #333;
                    border-radius: 50%;
                    animation: spin 0.6s linear infinite;
                    margin-right: 6px;
                    vertical-align: middle;
                "></span> Generando...
            `;

            try {

                // Obtener valores directamente
                const informeObj = {
                    anio: informeAnio.value,
                    mes: informeMes.value,
                    informe: informeRxInformeSelect.value,
                };

                // Validar que todos tengan valor antes de continuar
                if (informeObj.anio && informeObj.mes && informeObj.informe) {
                    await EnviarInformeRx(informeObj);
                } else {
                    toastr.error("Indique los datos del informe", informeObj);
                }
                

            } catch (error) {
                // En caso de un error inesperado en la lógica del botón
                console.error("Error en el proceso de generación del informe:", error);
                toastr.error("Ocurrió un error inesperado al generar el informe.");
            } finally {
                // 'finally' asegura que el botón siempre se habilite de nuevo,
                // ya sea que la operación termine bien o con error.
                habilitarBoton();
            }
        });
    }

    


    // Listener para el botón de 'generar'.
    // llama al ebvio de informe Referencia.
    if (informeReferenciaGenerarBtn){
        informeReferenciaGenerarBtn.addEventListener('click', async function () { 
            let tipoDocumento = 0;
            if (informeCriteriosPDF) {
                if (informeCriteriosPDF.checked) {
                    tipoDocumento = 0;
                } else if (informeCriteriosEXCEL && informeCriteriosEXCEL.checked) {
                    tipoDocumento = 1;
                }
            }

            // Guardamos el contenido original del botón para restaurarlo después.
            const textoOriginal = informeReferenciaGenerarBtn.innerHTML;

            // Subfunción para restaurar el botón a su estado original.
            function habilitarBoton() {
                informeReferenciaGenerarBtn.disabled = false;
                informeReferenciaGenerarBtn.innerHTML = textoOriginal;
            }

            // Desactivamos el botón y mostramos el spinner.
            informeReferenciaGenerarBtn.disabled = true;
            informeReferenciaGenerarBtn.innerHTML = `
                <span class="spinner" style="
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    border: 2px solid #ccc;
                    border-top: 2px solid #333;
                    border-radius: 50%;
                    animation: spin 0.6s linear infinite;
                    margin-right: 6px;
                    vertical-align: middle;
                "></span> Generando...
            `;

            try {

                // Obtener valores directamente
                const informeObj = {
                    anio: informeAnio.value,
                    mes: informeMes.value,
                    informe: informeReferenciaInformeSelect.value,
                    tipoDoc: tipoDocumento ?? 0
                };

                // Validar que todos tengan valor antes de continuar
                if (informeObj.anio && informeObj.mes && informeObj.informe) {
                    await EnviarInformeReferencia(informeObj);
                } else {
                    toastr.error("Indique los datos del informe", informeObj);
                }
                

            } catch (error) {
                // En caso de un error inesperado en la lógica del botón
                console.error("Error en el proceso de generación del informe:", error);
                toastr.error("Ocurrió un error inesperado al generar el informe.");
            } finally {
                // 'finally' asegura que el botón siempre se habilite de nuevo,
                // ya sea que la operación termine bien o con error.
                habilitarBoton();
            }
        });
    }

    //
    //
    if(informeCatagoloGenerarBtn){
        informeCatagoloGenerarBtn.addEventListener('click', async function () { 
    
            // Guardamos el contenido original
            const textoOriginal = informeCatagoloGenerarBtn.innerHTML;

            // Subfunción para restaurar el botón a su estado original.
            function habilitarBoton() {
                informeCatagoloGenerarBtn.disabled = false;
                informeCatagoloGenerarBtn.innerHTML = textoOriginal;
            }

            // Desactivamos el botón y mostramos el spinner.
            informeCatagoloGenerarBtn.disabled = true;
            informeCatagoloGenerarBtn.innerHTML = `
                <span class="spinner" style="
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    border: 2px solid #ccc;
                    border-top: 2px solid #333;
                    border-radius: 50%;
                    animation: spin 0.6s linear infinite;
                    margin-right: 6px;
                    vertical-align: middle;
                "></span> Generando...
            `;

            try {

                // Obtener valores directamente
                const informeObj = {
                    fechaIni: fechaInicioCatalogo.value,
                    fechaFin: fechaFinCatalogo.value,
                    catalogo: informeCatalogoSelect.value,
                };

                // Validar que todos tengan valor antes de continuar
                if (informeObj.fechaIni && informeObj.fechaFin && informeObj.catalogo) {
                    await EnviarInformeCatalogo(informeObj);
                } else {
                    toastr.error("Indique los datos del informe", informeObj);
                }
                

            } catch (error) {
                // En caso de un error inesperado en la lógica del botón
                console.error("Error en el proceso de generación del informe:", error);
                toastr.error("Ocurrió un error inesperado al generar el informe.");
            } finally {
                // 'finally' asegura que el botón siempre se habilite de nuevo,
                // ya sea que la operación termine bien o con error.
                habilitarBoton();
            }
        });
    }


    /**
     * Envía los datos del informe al servidor y maneja la respuesta (PDF o JSON).
     * @param {object} reporteData - Datos del reporte a enviar.
     */
    async function EnviarInformeRx(reporteData) {
        const csrfToken = window.CSRF_TOKEN;

        try {
            const response = await fetch(API_URLS.informesImagenologia, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    anio: reporteData.anio,
                    mes: reporteData.mes,
                    informe: reporteData.informe,
                }),
            });

            // ====== ERRORES HTTP ======
            if (!response.ok) {
                const data = await response.json();
                if (data.error) toastr.error(data.error, "Error");
                return;
            }

            const contentType = response.headers.get("Content-Type") || "";

            // ====== PDF ======
            if (contentType.includes("application/pdf")) {
                const blob = await response.blob();
                const pdfUrl = URL.createObjectURL(blob);

                const nuevaVentana = window.open(pdfUrl, "_blank");
                if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                    toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                }

                setTimeout(() => URL.revokeObjectURL(pdfUrl), 10000);
                return;
            }

            // ====== JSON NORMAL ======
            const data = await response.json();

            if (data.error) {
                toastr.error(data.error, "Error");
            } else {
                toastr.warning("No se recibió información válida del servidor.");
            }

        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al generar el informe.");
        }
    }



    /**
     * Envía los datos del informe al servidor y maneja la respuesta (PDF o JSON).
     * @param {object} reporteData - Datos del reporte a enviar.
     */
    async function EnviarInformeReferencia(reporteData) {
        const csrfToken = window.CSRF_TOKEN;

        try {
            const response = await fetch(API_URLS.informesReferencia, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                    anio: reporteData.anio,
                    mes: reporteData.mes,
                    informe: reporteData.informe,
                    tipoDoc: reporteData.tipoDoc
                }),
            });

            // ======= ERRORES HTTP =======
            if (!response.ok) {
                const data = await response.json();
                if (data.error) toastr.error(data.error, "Error");
                return;
            }

            const contentType = response.headers.get("Content-Type") || "";

            // ======= PDF =======
            if (contentType.includes("application/pdf")) {
                const blob = await response.blob();
                const pdfUrl = URL.createObjectURL(blob);

                const nuevaVentana = window.open(pdfUrl, "_blank");
                if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                    toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                }

                setTimeout(() => URL.revokeObjectURL(pdfUrl), 10000);
                return;
            }

            // ======= EXCEL  =======
            if (contentType.includes(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                let filename = response.headers.get("Content-Disposition");
                if (filename) {
                    const match = filename.match(/filename="?(.+)"?/);
                    filename = match ? match[1] : null;
                }

                let downloadName =
                    filename ||
                    `informe_${reporteData.informe}_${reporteData.mes}_${reporteData.anio}.xlsx`;

                downloadName = limpiarNombreArchivo(downloadName);

                const a = document.createElement("a");
                a.href = url;
                a.download = downloadName;
                document.body.appendChild(a);
                a.click();
                a.remove();

                setTimeout(() => URL.revokeObjectURL(url), 10000);
                return;
            }

            // ======= JSON NORMAL =======
            const data = await response.json();

            if (data.error) {
                toastr.error(data.error, "Error");
            }  else {
                toastr.warning("No se recibió información válida del servidor.");
            }

        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al generar el informe.");
        }
    }


    /**
     * Envía los datos del informe al servidor y maneja la respuesta (PDF o JSON).
     * @param {object} reporteData - Datos del reporte a enviar.
     */
    async function EnviarInformeCatalogo(reporteData) {
        const csrfToken = window.CSRF_TOKEN;

        try {
            const response = await fetch(API_URLS.informesCatalogo, {
                method: "POST",
                body: JSON.stringify({
                    fechaIni: reporteData.fechaIni,
                    fechaFin: reporteData.fechaFin,
                    catalogo: reporteData.catalogo,
                }),
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
            });

            //  Manejo de errores de API.
            if (!response.ok) {
                const data = await response.json();

                if (data.error) toastr.error(data.error, "Error");
                return;
            }
            
            const contentType = response.headers.get("Content-Type") || "";

            if (contentType.includes(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                let filename = response.headers.get("Content-Disposition");
                if (filename) {
                    const match = filename.match(/filename="?(.+)"?/);
                    filename = match ? match[1] : null;
                }

                let downloadName = filename
                    || `informe_${reporteData.informe}_${reporteData.fechaInicio}_a_${reporteData.fechaFin}.xlsx`;

                downloadName = limpiarNombreArchivo(downloadName);

                const a = document.createElement("a");
                a.href = url;
                a.download = downloadName;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 10000);
            }

            else {
                const data = await response.json();
                if (!data.success) {
                    toastr.error(data.error || "Ocurrió un error durante el proceso.");}
                else {
                toastr.warning("No se recibió información válida del servidor.");
                }
            }
        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al generar el catologo.");
        }
    }

    
    //#endregion

    // Inicialización: Establece un valor por defecto para el modelo y dispara su evento 'change'.
    modelo.value = 'paciente';
    modelo.dispatchEvent(new Event('change'));

        // Lógica del tab
    document.querySelectorAll('.reporteTabsBoton').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.reporteTabsBoton').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.reporte-tab-contenido').forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            const tabContenido = document.getElementById(tabId);
            tabContenido.classList.add('active');

        });
    });




});