
//FUncion para retornar la fecha en formato 02 dic 24 - 09:26
function fechaActualAmigable(){

    let fechaActual = new Date();
    let dia = String(fechaActual.getDate()).padStart(2, '0');
    let mes = fechaActual.toLocaleString('default', { month: 'short' }); 
    let anio = String(fechaActual.getFullYear()).slice(-2); 
    let horas = String(fechaActual.getHours()).padStart(2, '0'); 
    let minutos = String(fechaActual.getMinutes()).padStart(2, '0');

    let fechaFormateada = `${dia} ${mes} ${anio} - ${horas}:${minutos}`;
    return  fechaFormateada;
}


function fechaActualParaInput(conHora = true) {
    const fecha = new Date();
    const dia = String(fecha.getDate()).padStart(2,'0');
    const mes = String(fecha.getMonth() + 1).padStart(2,'0'); // enero = 0
    const anio = fecha.getFullYear();

    if (conHora) {
        const horas = String(fecha.getHours()).padStart(2,'0');
        const minutos = String(fecha.getMinutes()).padStart(2,'0');
        return `${anio}-${mes}-${dia}T${horas}:${minutos}`;
    } else {
        return `${anio}-${mes}-${dia}`;
    }
}


//Para obtener la fecha local sin que te cambie el día,
function getFechaLocalYYYYMMDD(fecha) {
    const año = fecha.getFullYear();
    const mes = (fecha.getMonth() + 1).toString().padStart(2, '0'); // Mes va de 0 a 11
    const dia = fecha.getDate().toString().padStart(2, '0');
    return `${año}-${mes}-${dia}`;
}


/**
 * Calcula la edad en años, meses y días según la fecha de nacimiento.
 * @param {string} fechaNacimiento - La fecha de nacimiento en formato "YYYY-MM-DD".
 * @returns {string} - La edad en formato "X años, Y meses, Z días".
 */
function calcularEdadComoTexto(fechaNacimiento) {

    const hoy = new Date();

    // Crear fecha como local, no UTC
    const partes = fechaNacimiento.split("-");
    const fechaNac = new Date(partes[0], partes[1] - 1, partes[2]);

    let anios = hoy.getFullYear() - fechaNac.getFullYear();
    let meses = hoy.getMonth() - fechaNac.getMonth();
    let dias = hoy.getDate() - fechaNac.getDate();

    // Ajuste de días negativos
    if (dias < 0) {
        const mesAnterior = new Date(hoy.getFullYear(), hoy.getMonth(), 0); // Último día del mes anterior
        dias += mesAnterior.getDate();
        meses -= 1;
    }

    // Ajuste de meses negativos
    if (meses < 0) {
        anios -= 1;
        meses += 12;
    }

    const partesTexto = [];
    if (anios > 0) partesTexto.push(`${anios} ${anios === 1 ? "año" : "años"}`);
    if (meses > 0) partesTexto.push(`${meses} ${meses === 1 ? "mes" : "meses"}`);
    if (dias > 0) partesTexto.push(`${dias} ${dias === 1 ? "día" : "días"}`);

    return partesTexto.join(", ") || "0 días";
}


/**
 * Formatea una fecha en un formato corto y amigable para el usuario.
 * @param {string} fechaISO - La fecha en formato ISO (YYYY-MM-DDTHH:mm:ss.sssZ).
 * @returns {string} - La fecha formateada en el estilo "DD Mes AA, HH:MM".
 */
function formatFecha(fechaISO) {
    if (!fechaISO) return ""; // Si no hay fecha, devolver vacío

    let fecha = new Date(fechaISO);
    return fecha.toLocaleDateString("es-HN", { 
            day: "2-digit", 
            month: "short",
            year: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
    }).replace(".", ""); 
}

/**
 * Formatea una fecha en el formato "dd/mm/yyyy - hh:mm".
 * @param {string} fechaISO - Fecha en formato ISO (YYYY-MM-DDTHH:mm:ss.sssZ).
 * @returns {string} - Fecha formateada.
 */
function formatoFecha_dd_mm_yy_hh_mm(fechaISO, hora=null) {
    if (!fechaISO) return "";

    const fecha = new Date(fechaISO);

    const dia = String(fecha.getDate()).padStart(2, '0');
    const mes = String(fecha.getMonth() + 1).padStart(2, '0'); // Mes de 0 a 11
    const año = String(fecha.getFullYear()).slice(-2); // Últimos dos dígitos del año
    if (hora){
        const horas = String(fecha.getHours()).padStart(2, '0');
        const minutos = String(fecha.getMinutes()).padStart(2, '0');
        return `${dia}/${mes}/${año} - ${horas}:${minutos}`
    }

    return `${dia}/${mes}/${año}`
}


function formatearFechaSimple(fechaStr) {
    const fecha = new Date(fechaStr);

    if (isNaN(fecha)) {
        throw new Error("La fecha proporcionada no es válida.");
    }

    const opciones = { day: "2-digit", month: "long", year: "numeric" };
    return fecha.toLocaleDateString("es-ES", opciones);
}


function formatearFechaLocal(isoString) {
    const fecha = new Date(isoString);
    if (isNaN(fecha)) return ''; // por si viene mal
    return fecha.toLocaleDateString('es-HN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}


function formatearFechaISO(fechaISO) {
    if (!fechaISO) return "";
    const fechaObj = new Date(fechaISO);
    const year = fechaObj.getFullYear();
    const month = String(fechaObj.getMonth() + 1).padStart(2, '0');
    const day = String(fechaObj.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// "YYYY-MM-DD" → "dd/mm/yyyy"
function formatearFechaYYYYMMDD_a_DDMMYYYY(fechaStr) {
    if (!fechaStr) return "";
    const [anio, mes, dia] = fechaStr.split("-");
    return `${dia}/${mes}/${anio}`;
}