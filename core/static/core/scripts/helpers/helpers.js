
var regexNombreApellido = "^[A-Za-zñÑ.\\-\\s]*$"; // Permite letras mayúsculas, minúsculas, puntos y guiones


const regexTelefono = "^[2893][0-9]{3}-[0-9]{4}$";
const formatoTelefono = "____-____";

var regexIdentidad = "^([0-3][0-9])([0-9][0-9])-(1|2)[0-9]{3}-[0-9]{5}$"
//var regexIdentidad = "^([0-3][0-9])([0-8][0-9])-(19[0-9]{0,2}|20[0-9]{0,2})-[0-9]{0,5}$"

var formatoIdentidad = "____-____-_____"

const regexNumeroExpediente = "^[0-9]{1,7}$";  // Solo números, máximo 7 dígi tos
const formatoNumeroExpediente = "_______";

//Funcion para hacer slug un string 
function slugify(text) {
   return text
      .toString()
      .normalize('NFD')                   // Descompone acentos y diacríticos
      .replace(/[\u0300-\u036f]/g, '')   // Elimina los acentos
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')              // Reemplaza espacios por guiones
      .replace(/[^\w\-]+/g, '')          // Elimina caracteres no alfanuméricos o guiones
      .replace(/\-\-+/g, '-');           // Reemplaza múltiples guiones por uno solo
}

/**
      * Realiza una solicitud GET a la API y devuelve los datos en JSON.
      * @param {string} url - URL de la API a la que se va a realizar la solicitud.
      * @param {object} params - Parámetros opcionales para la solicitud.
      * @returns {Promise<object>} - Respuesta en JSON de la API.
      */
async function fetchData(url, params = {}) {
   const queryString = new URLSearchParams(params).toString();
   const response = await fetch(`${url}?${queryString}`);
   if (!response.ok)
      throw new Error(`Error en la red: ${response.statusText}`);
   return response.json();
}


function concatenarLimpio(...args) {
   return args
     .map(arg => arg?.trim())       // Elimina espacios al inicio/final
     .filter(Boolean)               // Elimina null, undefined, "", etc.
     .join(" ");                    // Une con un solo espacio
}




//#region  Busquedas publicas

async function confirmarAccion(titulo, mensaje, botonAfirmativo = "Aceptar", botonNegativo="Cancelar") {
   const resultado = await Swal.fire({
      title: titulo,
      html: mensaje,
      icon: 'question',
      showCancelButton: true,
      confirmButtonText: `<i class="bi bi-check-circle-fill"></i> ${botonAfirmativo}`,
      cancelButtonText: `<i class="bi bi-x-circle-fill"></i> ${botonNegativo}`,
      customClass: {
         icon: 'contenedor-modal-icon',
         popup: 'contenedor-modal',
         title: 'contener-modal-titulo',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar',
      },
      didOpen: () => {
         const actionsContainer = document.querySelector('.swal2-actions');
         if (actionsContainer) {
            actionsContainer.classList.add('contener-modal-contenedor-botones-min');
         }
         const htmlContainer = document.querySelector('.swal2-html-container');
         if (htmlContainer) {
            htmlContainer.classList.add('contener-modal-contenedor-html');
         }
      }
   });

   return resultado.isConfirmed;
}


function renderDatosPaciente(containerId, datos = {}) {
   const header = document.getElementById(containerId);

   if (!header) return;
   header.innerHTML = "";

   Object.entries(datos).forEach(([label, value]) => {

      const fila = document.createElement("div");
      fila.className = "modal-dato";

      fila.innerHTML = `
         <span class="modal-dato-label">${label}</span>
         <span class="modal-dato-valor">${value || ''}</span>
      `;

      header.appendChild(fila);
   });
}

const API_URLS = {
   obtenerPacienteCenso: urls["obtenerPacienteCenso"],
   busquedaCenso: urls["busquedaCenso"],
   busquedaPaciente: urls["busquedaPaciente"],
   busquedaAvanzada: urls["busquedaAvanzada"],
   obtenerDefuncion: urls["obtenerDefuncion"],
   guardarDefuncion: urls["guardarDefuncion"],
   obtenerObito: urls["obtenerObito"],
   guardarObito: urls["guardarObito"],
   obtenerAtencion:  urls["obtenerAtencion"],
   obtenerPacienteExternoDni: urls["obtenerPacienteExternoDni"],
   validarIngresoActivo: urls["validarIngresoActivo"],
   verificarAtencionReciente: urls["verificarAtencionReciente"],
   verificarPacienteInactivo: urls["verificarPacienteInactivo"],
   verificarPacienteSimilar: urls["verificarPacienteSimilar"],
   verificarDefuncion: urls["verificarDefuncion"],
   reporteHojaHospitalizacion: urls["ReporteHojaHospitalizacion"],
   reporteFormatoReferencia: urls["ReporteFormatoReferencia"],
   ReporteFormatoRespuesta: urls["ReporteFormatoRespuesta"],
   obtenerPacienteRegistroExpediente: urls["obtenerPacienteRegistroExpediente"],
   obtenerPacienteRegistroDNI: urls["obtenerPacienteRegistroDNI"],
   agregar_ingreso: urls["agregarIngreso"],
   listarEvalucionesrx: urls["listarEvalucionesrx"],
   obtenerSeguimientoTIC: urls["seguimientoTicObtener"],
   listarObitosPaciente: urls["listarObitosPaciente"],
   listarDependencias: urls["listarDependencias"],
};

/**
 * Muestra un modal de búsqueda de pacientes con una tabla dinámica.
 * Permite buscar por expediente, identidad o nombre, y seleccionar una fila para obtener sus datos.
 * Utiliza DataTables para la visualización y la interacción con los datos.
 * 
 * @returns {Object} resultado - Datos de la fila seleccionada, o `undefined` si no se selecciona ninguna.
 */
async function mostrasBusquedaPaciente() {
   let resultado;
   const modal = await Swal.fire({
   title: "Buscar Paciente",
   html: `
   
            <div style="overflow-x:auto;">
               <table id="modalTablePaciente" class="display" style="width:100%">
                  <thead>
                        <tr>
                           <th>Exp</th>
                           <th>Identidad</th>
                           <th>Tipo</th>
                           <th>Nombres</th>
                           <th>Apellidos</th>
                           <th>Sexo</th>
                           <th>Fecha Nac</th>
                           <th>Telefono</th>
                           <th>Domicilio</th>
                        </tr>
                  </thead>
                  <tbody></tbody>
               </table>
            </div>
      `,
   showCancelButton: true,
   showCloseButton: true,
   confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
   cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
   customClass: {
      popup: 'contener-modal-busqueda',
      title: 'contener-modal-titulo',
      content: 'contener-modal-contenido',
      confirmButton: 'contener-modal-boton-confirmar',
      cancelButton: 'contener-modal-boton-cancelar'
   },
   didOpen: async () => {
   //clases perzonalizadas para no afectar la libreria
      const actionsContainer = document.querySelector('.swal2-actions');
         if (actionsContainer) {
            actionsContainer.classList.add('contener-modal-contenedor-botones');
         }


   // Inicializar DataTable dentro del modal
      const tableModalPaciente = new DataTable("#modalTablePaciente", {
         responsive: true,
         processing: true,
         serverSide: true,
         searchDelay: 900, 
         lengthMenu: [10, 25, 50, 100],
         dom: '<"superior "<"column-select">f>t<"inferior"lip><"clear">',
         select: {
            style: 'single'  // Permitir solo la selección de una fila a la vez
            },
         ajax: {
         url: API_URLS.busquedaPaciente, //API_URLS.busquedaCenso,
         type: "GET",
         data: function(d) {      // parametros de busqueda 
            d.search_value = $('#search-input').val();
            d.search_column = $('#column-selector').val();
         },
         dataSrc: function (json) { //// que hace evalue un error como repuesta del JSOn 
            if (json.Myerror) {
                  toastr.warning(json.Myerror, "Aviso");
                  return [];
            }
            return json.data; 
         },
         },

         columns: [
            {
               data: "expediente_numero",
               responsivePriority: 1,
               render: function (data) {
                  if (data) {
                     data = data.toString().padStart(6, '0');
                  }
                  return data; 
               },
            },
            {  data: "dni", 
               ordenable: true,
               responsivePriority: 2 ,  
               width: "6px",
               render: function(data){
                  if (data) {
                     return data.substring(0, 13); // Retorna solo los primeros 13 caracteres
                  }
                  return "";
               }
            },  
            {  data: "tipo_id",
               width: "6px" ,
               render: function (data, type, row) {
                  
                  let map = {
                     "1": "DNI",  
                     "2": "PAS",   
                     "3": "RN",  
                     "4": "HD",   
                     "5": "DESC",    
                  };
   
                  let tipo = map[data] || "##";
                  return tipo;
               }
            },  // nombreeeee
            {
            data: null,
            responsivePriority: 3,
            render: function (data) {
               let nombre1 = data.primer_nombre || "";
               let nombre2 = data.segundo_nombre || "";
               return nombre1 + " " + nombre2;
               },
            },
            {
               data: null,
               responsivePriority: 3,
               render: function (data) {
                  let apellido1 = data.primer_apellido || "";
                  let apellido2 = data.segundo_apellido || "";
                  return apellido1+ " " + apellido2;
               },
            },            
            { data: "sexo", width: "4px", },
            { 
            data: "fecha_nacimiento",
            width: "7px",
            render: function (data) {
               if (data) {
                  let parts = data.split('-');
                  return `${parts[2]}/${parts[1]}/${parts[0]}`;  // Retorna en formato DD/MM/YYYY
               }
               return data; 
               },
            },
            { data: "telefono", responsivePriority: 4},
            {//DIRECCION
               data: null,
               ordenable: false,
               render: function (data) {
                  let municipio = data.sector__aldea__municipio__nombre_municipio || "";
                  let ubicacion = data.sector__nombre_sector || "";
                  return `${municipio}, ${ubicacion}`;
               },
            },
            {data:"id", visible:false}, 
         ],
         columnDefs: [
            { targets: 0, className: 'PrimerColumnaAliIzq' },
            { targets: 1, className: 'ColumnaDNI' },
            { targets: 8, className: 'ColumnaDireccion' },




         ],
         order: [[9, "desc"]],
         language: {
            lengthMenu: "Mostrar _MENU_ por página",
            zeroRecords: "No se encontraron resultados",
            info: "_START_ a _END_ de _TOTAL_ registros",
            infoEmpty: "0 a 0 de 0 pacientes",
            infoFiltered: "(filtrado de _MAX_)",
            paginate: {
               first: "<<",
               last: ">>",
               next: ">",
               previous: "<",
         },
         loadingRecords: "Cargando...",
         processing: "Procesando...",
         emptyTable: "No hay datos disponibles en la tabla",
         },
         initComplete: function () {
            document.querySelector(".superior").id = "modalBuscarPaciente_contenedor_superior"; // Asigna el ID
         }

      });

       // Agregar campos de búsqueda
      const comboContenedor = document.querySelector(".column-select");

         // Seleccionar el campo de buscaqueda
         const select = document.createElement("select");
         select.id = "column-selector";
         select.className = "formularioCampo-select";
         
         const defaultOption = document.createElement("option");
         defaultOption.value = "2";
         defaultOption.textContent = "Nombre";
         defaultOption.selected = true;
         select.appendChild(defaultOption);

         const opciones = [
            {value: "0", text:"Expediente"},
            {value: "1", text:"Identidad"}
         ] ;

         opciones.forEach(({value, text}) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = text;
            select.appendChild(option)
         });
         
         select.addEventListener("change",function(){
            const searchValue = document.getElementById('dt-search-0').value.trim();
            if (searchValue.length > 0) {
                  tableModalPaciente.ajax.reload();
            }
            
         })
         comboContenedor.appendChild(select);

      // Evento de doble clic en una fila
      document.querySelector('#modalTablePaciente tbody').addEventListener('dblclick', function (e) {
         const selectedRow = e.target.closest('tr'); // Detectar la fila más cercana
         if (selectedRow) {
            // Obtener los datos de la fila seleccionada
            resultado = tableModalPaciente.row(selectedRow).data(); // Almacenar los datos de la fila seleccionada en la variable resultado
            Swal.close(); // Cerrar el modal
         }
      });


      // Manejo de selección de fila en el DataTable
      document.querySelector("#modalTablePaciente tbody").addEventListener("click", (e) => {
         let row = e.target.closest("tr");
      
         // Verificar si se hizo clic en una fila y que no sea una fila "child"
         if (!row || row.classList.contains("child")) {
               return;
         }
      
         // Remueve la selección de otras filas antes de agregar la nueva
         document.querySelectorAll("#modalTablePaciente tbody tr.selected").forEach((el) => {
               el.classList.remove("selected");
         });
      
         // Alternar la clase 'selected'
         row.classList.add("selected");
      });
      
   },
   }).then((result) => {
   if (result.isConfirmed) {
      const table = new DataTable("#modalTablePaciente");
      const selectedRow = table.row(".selected").data(); // Obtén la fila seleccionada

      resultado = selectedRow;
      resultado["nombre_completo"] = concatenarLimpio(resultado.primer_nombre, resultado.segundo_nombre, resultado.primer_apellido, resultado.segundo_apellido)
   }
   });
   return(resultado);
}



/**
 * Muestra un modal de búsqueda de personas del Censo Electoral con una tabla dinámica.
 * * @async
 * @function mostrasBusquedaPersonaCenso
 * @description Crea un modal de SweetAlert2 con una tabla de DataTables para buscar personas por varios criterios y seleccionar una fila.
 * * @returns {Promise<object|null>} Los datos de la fila seleccionada si el usuario confirma,
 * o `null` si se cancela o no se selecciona ninguna fila.
 */
async function mostrasBusquedaPersonaCenso() {
   let resultado = null; // Se inicializa como null para verificar si se seleccionó una fila.

   const modal = await Swal.fire({
      title: "Buscar Persona - Censo Electoral 2025",
      html: `
         <div style="overflow-x:auto;">
         <table id="modalTablePersonaCenso" class="display" style="width:100%">
               <thead>
                  <tr>
                     <th>Identidad</th>
                     <th>Nombre</th>
                     <th>Apellido</th>
                     <th>Sexo</th>
                     <th>Fecha Nac</th>
                     <th>Domicilio</th>
                  </tr>
               </thead>
               <tbody></tbody>
         </table>
         </div>
         `,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
         popup: 'contener-modal-busqueda',
         title: 'contener-modal-titulo',
         content: 'contener-modal-contenido',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar'
      },
      didOpen: async () => {
         // Personalizar clases para el contenedor de botones del modal
         const actionsContainer = document.querySelector('.swal2-actions');
         if (actionsContainer) {
               actionsContainer.classList.add('contener-modal-contenedor-botones');
         }

         // Inicializar DataTable
         const tableModalPersonaCenso = new DataTable("#modalTablePersonaCenso", {
               responsive: true,
               processing: true,
               serverSide: true,
               dom: '<"DatatablesuperiorModal" <"controlesBusqueda"> >t<"inferior"lip><"clear">',
               select: {
                  style: 'single' // Permitir solo la selección de una fila a la vez
               },
               ajax: {
                  url: API_URLS.busquedaCenso,
                  type: "GET",
                  data: function(d) { // Parámetros de búsqueda
                     d.search_sexo = $("#column-selector").val();
                     d.search_nombre1 = $("#primerNombre").val();
                     d.search_nombre2 = $("#segundoNombre").val();
                     d.search_apellido1 = $("#primerApellido").val();
                     d.search_apellido2 = $("#segundoApellido").val();
                  },
                  dataSrc: function(json) { // Manejo de errores desde el JSON
                     if (json.Myerror) {
                           toastr.warning(json.Myerror, "Aviso");
                           return [];
                     }
                     return json.data;
                  },
               },
               columns: [{
                     data: "NUMERO_IDENTIDAD",
                     responsivePriority: 1,
                     width: "20px"
                  },
                  {
                     data: null,
                     responsivePriority: 2,
                     render: function(data) {
                           const primerNombre = data.PRIMER_NOMBRE || "";
                           const segundoNombre = data.SEGUNDO_NOMBRE || "";
                           return `${primerNombre} ${segundoNombre}`;
                     }
                  },
                  {
                     data: null,
                     responsivePriority: 2,
                     render: function(data) {
                           const primerApellido = data.PRIMER_APELLIDO || "";
                           const segundoApellido = data.SEGUNDO_APELLIDO || "";
                           return `${primerApellido} ${segundoApellido}`;
                     }
                  },
                  {
                     data: "SEXO",
                     width: "8px"
                  },
                  {
                     data: "FECHA_NACIMIENTO",
                     width: "8px",
                     render: function(data) {
                           if (data) {
                              const parts = data.split("/");
                              return `${parts[2]}/${parts[1]}/${parts[0]}`;
                           }
                           return data;
                     },
                  },
                  {
                     data: null,
                     ordenable: false,
                     render: function(data) {
                           const municipio = data.MUNI || "";
                           const departamento = data.DEPTO || "";
                           const ubicacion = data.LUGAR || "";
                           return `${departamento}, ${municipio}, ${ubicacion}`;
                     },
                  },
               ],
               order: [
                  [0, "desc"]
               ],
               pageLength: 8,
               lengthChange: false,
               language: {
                  lengthMenu: "Mostrar _MENU_ por página",
                  zeroRecords: "No se encontraron resultados",
                  info: "_START_ a _END_ de _TOTAL_ registros",
                  infoEmpty: "0 a 0 de 0 personas",
                  infoFiltered: "(filtrado de _MAX_)",
                  paginate: {
                     first: "<<",
                     last: ">>",
                     next: ">",
                     previous: "<",
                  },
                  loadingRecords: "Cargando...",
                  processing: "Procesando...",
                  emptyTable: "No hay datos disponibles en la tabla",
               },
         });

         // Crear y agregar campos de búsqueda dinámicamente
         const contenedor = document.querySelector(".controlesBusqueda");

         const input1 = document.createElement("input");
         input1.type = "text";
         input1.id = "primerNombre";
         input1.className = "formularioCampo-text";
         input1.placeholder = "Primer Nombre";
         contenedor.appendChild(input1);

         const input2 = document.createElement("input");
         input2.type = "text";
         input2.id = "segundoNombre";
         input2.className = "formularioCampo-text";
         input2.placeholder = "Segundo Nombre";
         contenedor.appendChild(input2);

         const input3 = document.createElement("input");
         input3.type = "text";
         input3.id = "primerApellido";
         input3.className = "formularioCampo-text";
         input3.placeholder = "Primer Apellido";
         contenedor.appendChild(input3);

         const input4 = document.createElement("input");
         input4.type = "text";
         input4.id = "segundoApellido";
         input4.className = "formularioCampo-text";
         input4.placeholder = "Segundo Apellido";
         contenedor.appendChild(input4);

         const select = document.createElement("select");
         select.id = "column-selector";
         select.className = "formularioCampo-select";
         const option1 = document.createElement("option");
         option1.value = "1";
         option1.textContent = "Hombre";
         const option2 = document.createElement("option");
         option2.value = "2";
         option2.textContent = "Mujer";
         select.appendChild(option1);
         select.appendChild(option2);
         contenedor.appendChild(select);

         const buscarBtn = document.createElement("a");
         buscarBtn.id = "buscarBtn";
         buscarBtn.className = "formularioBotones-boton";
         buscarBtn.innerHTML = '<i class="bi bi-search"></i><span>Buscar</span>';
         contenedor.appendChild(buscarBtn);

         // Manejo de eventos de la tabla
         buscarBtn.addEventListener("click", function() {
               tableModalPersonaCenso.ajax.reload(); // Recargar la tabla con los parámetros de búsqueda
         });

         // Evento de doble clic en una fila (selecciona y cierra el modal)
         document.querySelector('#modalTablePersonaCenso tbody').addEventListener('dblclick', function(e) {
               const selectedRow = e.target.closest('tr');
               if (selectedRow) {
                  resultado = tableModalPersonaCenso.row(selectedRow).data(); // Almacenar los datos de la fila
                  Swal.close(); // Cerrar el modal
               }
         });

         // Manejo de selección de fila (resalta la fila con la clase 'selected')
         document.querySelector("#modalTablePersonaCenso tbody").addEventListener("click", (e) => {
               const row = e.target.closest("tr");
               if (!row || row.classList.contains("child")) {
                  return;
               }
               document.querySelectorAll("#modalTablePersonaCenso tbody tr.selected").forEach((el) => {
                  el.classList.remove("selected");
               });
               row.classList.add("selected");

               // También se puede almacenar el resultado aquí en caso de que se use el botón Aceptar
               resultado = tableModalPersonaCenso.row(row).data();
         });
      },
   }).then((result) => {
      // Lógica final al cerrar el modal
      if (result.isConfirmed) {
         // Verificar si el usuario realmente seleccionó una fila
         if (!resultado) {
               toastr.warning("Debe seleccionar una persona de la tabla", "Aviso");
               return null;
         }
         // Asigna el nombre completo (se corrigieron las claves a mayúsculas)
         // (La función 'concatenarLimpio' debe estar definida en tu código)
         resultado["nombre_completo"] = concatenarLimpio(
               resultado.PRIMER_NOMBRE,
               resultado.SEGUNDO_NOMBRE,
               resultado.PRIMER_APELLIDO,
               resultado.SEGUNDO_APELLIDO
         );
      }
      return resultado; // Retorna el resultado (datos de la persona o null si se canceló/no se seleccionó)
   });
   return resultado;
}


/**
 * Realiza la búsqueda de un paciente por DNI o expediente.
 * @param {string} numero El DNI o número de expediente a buscar.
 * @param {string} indicador El tipo de búsqueda: "DNI" o "EXP".
 * @returns {Promise<Object|null>} Retorna los datos del paciente o null si no se encuentra o hay un error.
 */
async function buscarPaciente(numero, indicador) {
   try {
      let URL = indicador === "DNI" ? API_URLS.obtenerPacienteRegistroDNI : API_URLS.obtenerPacienteRegistroExpediente;
      let parametros = {};

      if (indicador === "DNI") {
            parametros["DNI"] = numero.replace(/-/g, "");
      } else {
            parametros["numero"] = numero;
      }

      const data = await fetchData(URL, parametros);

      // Si el backend responde con un "mensaje" o no hay datos, se considera que no se encontró
      if (data && "mensaje" in data) {
            return null;
      }
      
      return data; // Retorna el objeto de datos del paciente
   } catch (error) {
      console.error("Error en buscarPaciente:", error);
      return null; // Retorna null en caso de error de red o de otro tipo
   }
}


/**
 * Muestra un modal de búsqueda avanzada  de personas con una tabla dinámica.
 * Permite buscar en diferentes entidades  la inforascmion de una persona
 * Utiliza DataTables para la visualización y la interacción con los datos.
 * 
 * @returns {Object} resultado - Datos de la fila seleccionada, o `undefined` si no se selecciona ninguna.
 */
async function mostrasBusquedaPersonaAvanzada() {
   let resultado;
   const modal = await Swal.fire({
   title: "Buscar Avanzada de Personas",
   html: `
   
            <div style="overflow-x:auto;">
               <table id="modalTableAvanzada" class="display" style="width:100%">
                  <thead>
                        <tr>
                           <th>Identidad</th>
                           <th>Nombre 1</th>
                           <th>Nombre 2</th>
                           <th>Apellido 1</th>
                           <th>Apellido 2</th>
                           <th>Telefono</th>
                           <th>Domicilio</th>
                           <th>Origen</th>
                           <th>id</th>
                        </tr>
                  </thead>
                  <tbody></tbody>
               </table>
            </div>
      `,
   showCancelButton: true,
   showCloseButton: true,
   confirmButtonText: '<i class="bi bi-check-circle-fill"></i> Aceptar',
   cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
   customClass: {
      popup: 'contener-modal-busqueda',
      title: 'contener-modal-titulo',
      content: 'contener-modal-contenido',
      confirmButton: 'contener-modal-boton-confirmar',
      cancelButton: 'contener-modal-boton-cancelar'
   },
   didOpen: async () => {
   //clases perzonalizadas para no afectar la libreria
      const actionsContainer = document.querySelector('.swal2-actions');
         if (actionsContainer) {
            actionsContainer.classList.add('contener-modal-contenedor-botones');
         }


   // Inicializar DataTable dentro del modal
      const tableModalAvanzada = new DataTable("#modalTableAvanzada", {
         responsive: true,
         processing: true,
         serverSide: true,
         lengthMenu: [10, 25, 50, 100],
         dom: '<"superior ">t<"inferior"lip><"clear">',
         select: {
            style: 'single'  // Permitir solo la selección de una fila a la vez
            },
         ajax: {
         url: API_URLS.busquedaAvanzada, //API_URLS.busquedaCenso,
         type: "GET",
         data: function(d) {      // parametros de busqueda }
            
            d.search_sexo = $("#sexo-selector").val();
            d.search_base = $("#base-selector").val();
            d.search_nombre1 = $("#primerNombre").val();
            d.search_nombre2 = $("#segundoNombre").val();
            d.search_apellido1 = $("#primerApellido").val();
            d.search_apellido2 = $("#segundoApellido").val();
            
         },
         dataSrc: function (json) { //// que hace evalue un error como repuesta del JSOn 
            if (json.Myerror) {
                  toastr.warning(json.Myerror, "Aviso");
                  return [];
            }
            return json.data; 
         },
         },

         columns: [

            { data: "dni", responsivePriority: 1},
            
            { data: "primer_nombre"},
            { data: "segundo_nombre"},
            { data: "primer_apellido"},
            { data: "segundo_apellido"},

            {
               data: 'telefono',
               render: function(data, type, row) {
               return data ? data : '';
               }
            },
            {//DIRECCION
               data: null,
               ordenable: false,
               render: function (data) {
                  let municipio = data.sector__aldea__municipio__nombre_municipio || "";
                  let departamento = data.sector__aldea__municipio__departamento__nombre_departamento	|| "";
                  let ubicacion = data.sector__nombre_sector || "";
                  return `${departamento}, ${municipio}, ${ubicacion}`;
               },
            },
            {data: "origen", ordenable:false},
            {data:"codigo", visible:false}, 
         ],
         
         columnDefs: [
            { targets: 0, className: 'ColumnaDNI' },
            { targets: 7, className: 'ColumnaDireccion' },

         ],
         order: [[1, "asc"]],
         language: {
            lengthMenu: "Mostrar _MENU_ por página",
            zeroRecords: "No se encontraron resultados",
            info: "_START_ a _END_ de _TOTAL_ registros",
            infoEmpty: "0 a 0 de 0 pacientes",
            infoFiltered: "(filtrado de _MAX_)",
            paginate: {
               first: "<<",
               last: ">>",
               next: ">",
               previous: "<",
         },
         loadingRecords: "Cargando...",
         processing: "Procesando...",
         emptyTable: "No hay datos disponibles en la tabla",
         },
         initComplete: function () {
            document.querySelector(".superior").id = "modalBuscarAvanzada_contenedor_superior"; // 
         }

      });

      // Agregar campos de búsqueda
      const camposBusqueda = document.querySelector(".superior");

      // Crear y configurar el select principal
      const select = document.createElement("select");
      select.id = "base-selector";
      select.className = "formularioCampo-select";

      // Opción por defecto
      const defaultOption = document.createElement("option");
      defaultOption.value = "0";
      defaultOption.textContent = "Base Interna";
      defaultOption.selected = true;
      select.appendChild(defaultOption);

      // Opciones del select
      const opciones = [
         { value: "1", text: "Censo" },
      ];

      opciones.forEach(({ value, text }) => {
         const option = document.createElement("option");
         option.value = value;
         option.textContent = text;
         select.appendChild(option);
      });

      // Evento para recargar la tabla al cambiar el select
      select.addEventListener("change", function () {
         tableModalAvanzada.ajax.reload();
      });

      // Crear y configurar los campos de texto
      const primerNombre = document.createElement("input");
      primerNombre.type = "text";
      primerNombre.id = "primerNombre";
      primerNombre.className = "formularioCampo-text";
      primerNombre.placeholder = "Primer Nombre";

      const segundoNombre = document.createElement("input");
      segundoNombre.type = "text";
      segundoNombre.id = "segundoNombre";
      segundoNombre.className = "formularioCampo-text";
      segundoNombre.placeholder = "Segundo Nombre";

      const primerApellido = document.createElement("input");
      primerApellido.type = "text";
      primerApellido.id = "primerApellido";
      primerApellido.className = "formularioCampo-text";
      primerApellido.placeholder = "Primer Apellido";

      const segundoApellido = document.createElement("input");
      segundoApellido.type = "text";
      segundoApellido.id = "segundoApellido";
      segundoApellido.className = "formularioCampo-text";
      segundoApellido.placeholder = "Segundo Apellido";

      // Crear y configurar el select de sexo
      const selectSexo = document.createElement("select");
      selectSexo.id = "sexo-selector";
      selectSexo.className = "formularioCampo-select";

      const opcionesSexo = [
         { value: "H", text: "Hombre" },
         { value: "M", text: "Mujer" },
         { value: "N", text: "No Identificado" },
      ];

      opcionesSexo.forEach(({ value, text }) => {
         const option = document.createElement("option");
         option.value = value;
         option.textContent = text;
         selectSexo.appendChild(option);
      });

      const botonBuscar = document.createElement("button"); // Usamos 'button' en lugar de 'href'
      botonBuscar.id = "buscarBtn";
      botonBuscar.className = "formularioBotones-boton";
      botonBuscar.innerHTML = `<i class="bi bi-search"></i><span> Buscar</span>`; // Usamos innerHTML para insertar HTML

      botonBuscar.addEventListener("click", function () {
         tableModalAvanzada.ajax.reload(); // Recarga la tabla
      });





      // Agregar los elementos al contenedor
      camposBusqueda.appendChild(select);
      camposBusqueda.appendChild(primerNombre);
      camposBusqueda.appendChild(segundoNombre);
      camposBusqueda.appendChild(primerApellido);
      camposBusqueda.appendChild(segundoApellido);
      camposBusqueda.appendChild(selectSexo);
      camposBusqueda.appendChild(botonBuscar);




      // Evento de doble clic en una fila
      document.querySelector('#modalTableAvanzada tbody').addEventListener('dblclick', function (e) {
         const selectedRow = e.target.closest('tr'); // Detectar la fila más cercana
         if (selectedRow) {
            // Obtener los datos de la fila seleccionada
            resultado = tableModalAvanzada.row(selectedRow).data(); // Almacenar los datos de la fila seleccionada en la variable resultado
            Swal.close(); // Cerrar el modal
         }
      });


      // Manejo de selección de fila en el DataTable
      document.querySelector("#modalTableAvanzada tbody").addEventListener("click", (e) => {
         let row = e.target.closest("tr");
      
         // Verificar si se hizo clic en una fila y que no sea una fila "child"
         if (!row || row.classList.contains("child")) {
               return;
         }
      
         // Remueve la selección de otras filas antes de agregar la nueva
         document.querySelectorAll("#modalTableAvanzada tbody tr.selected").forEach((el) => {
               el.classList.remove("selected");
         });
      
         // Alternar la clase 'selected'
         row.classList.add("selected");
      });
      
   },
   }).then((result) => {
   if (result.isConfirmed) {
      const table = new DataTable("#modalTableAvanzada");
      const selectedRow = table.row(".selected").data(); // Obtén la fila seleccionada
      resultado = selectedRow;
   }
   });

   return(resultado);
}

async function AgregarSectorModal(id_municipio) {
   let resultado = null;

   const modal = await Swal.fire({
      title: "Agregar Nuevo Sector",
      html: `
         <form method="post" class="formulario" id="formulario-model-sector">
               <fieldset class="sectorCamposModal">
               <legend>Registre los datos de nuevo Sector</legend>

               <div class="formularioCampoModalCheck">
                  <input type="checkbox" id="modal_agregar_sector-zona" name="sectorZona">
                  <label for="modal_agregar_sector-zona">Zona rural</label>
               </div>

               <div class="formularioCampoModal">
                  <label for="sectorAldea">Aldea</label>
                  <select id="modal_agregar_sector-aldea" class="formularioCampo-select" name="sectorAldea"></select>
               </div>

               <div class="formularioCampoModal">
                  <label for="SectorDescripcion">Sector</label>
                  <input type="text" id="modal_agregar_sector-descripcion" name="SectorDescripcion" placeholder="SECTOR" class="formularioCampo-text">
               </div>
               </fieldset>
         </form>
      `,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
         popup: 'contenedor-modal-sector',
         title: 'contener-modal-titulo',
         content: 'contener-modal-contenido',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar'
      },
      preConfirm: () => {
         const aldea = document.querySelector('#modal_agregar_sector-aldea');
         const descripcion = document.querySelector('#modal_agregar_sector-descripcion');

         if (!aldea.value) {
               Swal.showValidationMessage('Debe seleccionar una aldea para un sector');
               return false;
         }

         if (!descripcion.value.trim()) {
               Swal.showValidationMessage('La descripción no puede estar en blanco');
               return false;
         }

         return true;
      },
      didOpen: () => {
         

         const selectAldea = $('#modal_agregar_sector-aldea');

         if (!selectAldea.hasClass("select2-hidden-accessible")) {
               selectAldea.select2({
               ajax: {
                  url: urls["aldeaAutocomplete"],
                  dataType: "json",
                  delay: 250,
                  data: (params) => ({
                     municipio_id: id_municipio,
                     q: params.term
                  }),
                  processResults: (data) => ({ results: data.results }),
                  cache: true,
               },
               minimumInputLength: 2,
               placeholder: "Buscar Aldea",
               dropdownParent: $('#formulario-model-sector'),
               allowClear: true,
               language: {
                  errorLoading: () => "Los resultados no se pueden cargar.",
                  inputTooShort: ({ minimum }) => `Ingresa al menos ${minimum} caracteres.`,
                  searching: () => "Buscando...",
                  noResults: () => "No se encontraron resultados.",
               },
               });
         }

         // Ajustar botones dentro del modal
         document.querySelector('.swal2-actions')?.classList.add('contener-modal-contenedor-botones-min');
      }
   });

   if (modal.isConfirmed) {
      const checkZona = document.querySelector('#modal_agregar_sector-zona').checked;
      const aldea = document.querySelector('#modal_agregar_sector-aldea').value;
      const sectorDescripcion = document.querySelector('#modal_agregar_sector-descripcion').value.trim();
      const zona = checkZona ? 2 : 1;

      try {
         const csrfToken = window.CSRF_TOKEN;
         const response = await fetch(urls["agregarSector"], {
               method: "POST",
               headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": csrfToken
               },
               body: JSON.stringify({
               zona: zona,
               aldea_id: aldea,
               descripcion_sector: sectorDescripcion.toUpperCase()
               })
         });

         if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);

         const data = await response.json();
         if (data.sector_id) {
               toastr.success("Sector registrado correctamente.");
               resultado = data;
               Swal.close(); // Cerrar la modal manualmente solo en caso de éxito
         } else {
               toastr.error("Existe un problema al registrar el sector.");
         }
      } catch (error) {
         toastr.error("Error al registrar el sector: " + error.message);
      }
   }

   return resultado;
}


/*Agrega una atencion */
async function AgregarAtencionModal(paciente=null, zona=null, atencionId=null) {
   let resultado = null;

   const modal = await Swal.fire({
      title: `Definir una atencion `,
      html: `
         <form method="post" class="formulario" id="formulario-modal-atencion">
            <fieldset class="modalAtencionCampos">
               <legend id="modal-atencion-leyenda">
                  ${paciente ? `Paciente: <b>${paciente.nombre}</b>` : ''}
               </legend>
   

               <div class="formularioCampoModal">
                  <label for="fecha_atencion">Fecha Ate</label>
                  <input type="date" id="modal-atencion-fecha" name="fecha_atencion" class="formularioCampo-date" required>
               </div>

               <div class="formularioCampoModal" style="display: none;" id="modal-atencion-contenedor-fecha-recepcion">
                  <label for="fecha_recepcion">Recepcion</label>
                  <input type="text" id="modal-atencion-fecha-recepcion" name="fecha_recepcion" class="formularioCampo-date" required>
                              
               </div>


               <div class="formularioCampoModal">
                  <label for="servicio">Servicio</label>
                  <select id="modal-atencion-servicio" class="formularioCampo-select" name="servicio">
                     <option value="50" selected >CONSULTA EXTERNA</option>
                     <option value="1000" >EMERGENCIA</option>
                     <option value="700"  >OBSTETRICIA</option>
                  </select>
               </div>

               <div class="formularioCampoModal">
                  <label for="especialidad">Especialidad</label>
                  <select id="modal-atencion-especialidad" class="formularioCampo-select" name="especialidad">
                  </select>
               </div>

               <div class="formularioCampoModal">
                  <label for="observacion">Observación</label>
                  <textarea id="modal-atencion-observacion" class="formularioCampo-text" name="observacion" rows="2"></textarea>
               </div>

               <input type="hidden" id="modal-atencion-id" name="idAtencion">
               <input 
                  type="hidden" 
                  id="modal-atencion-paciente-id" 
                  name="idPaciente"
                  ${paciente ? `value="${paciente.id}"` : ''}
               >

            </fieldset>

            <fieldset class="modalAtencionCampos" id="modal-campos-atencion-registro" style="display: none;">
               <legend>Detalles del registro</legend>
               <div class="formularioCampoModal">
                  <label for="registro_info">Registrado</label>
                  <input type="text" id="modal-atencion-detalles-registro" class="formularioCampo-text" disabled>
               </div>
               <div class="formularioCampoModal">
                  <label for="modificado_info">Modificado</label>
                  <input type="text" id="modal-atencion-detalles-modificado" class="formularioCampo-text" disabled>
               </div>
            </fieldset>
         </form>
      `,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
         popup: 'contener-modal-defuncion', //usa la misma de defuncion por similitud
         title: 'contener-modal-titulo',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar'
      },
      preConfirm: () => {
         
         const especialidad = document.getElementById("modal-atencion-especialidad").value;

         if (!especialidad) {
            Swal.showValidationMessage('Debe seleccionar una sala');
            return false;
         }
         const fecha = document.getElementById("modal-atencion-fecha").value;
         

         
         if (!fecha) {
            Swal.showValidationMessage('Debe seleccionar una fecha valida');
            return false;
         }
            
         return true;
      },
      didOpen: async function () {
         const confirmBtn = Swal.getConfirmButton();
         const titleElement = Swal.getTitle(); 
         const especialidad = document.getElementById("modal-atencion-especialidad");
         const fecha = document.getElementById("modal-atencion-fecha");
         const servicio = document.getElementById("modal-atencion-servicio");
         const observaciones = document.getElementById("modal-atencion-observacion");
         const idAtencion = document.getElementById("modal-atencion-id");
         const detallesRegistro = document.getElementById("modal-atencion-detalles-registro");        
         const detallesModificado = document.getElementById("modal-atencion-detalles-modificado");
         
         const fieldsetRegistro = document.getElementById("modal-campos-atencion-registro");
         const leyenda = document.getElementById("modal-atencion-leyenda");
         const fechaRecepcion = document.getElementById("modal-atencion-fecha-recepcion");

         const fechaRecepcionContenedor = document.getElementById("modal-atencion-contenedor-fecha-recepcion");
         
         const idPaciente = document.getElementById("modal-atencion-paciente-id");


         // Cargar especialidaes de backed
         async function cargarEspecialidades(zona) {
            try {
               const data = await fetchData(urls["listarEspecialidad"], { id_servicio: zona });

               if (Array.isArray(data) && data.length > 0) {
                  especialidad.innerHTML = '';
                  
                  let tieneId3 = false;

                  data.forEach((item) => {
                     const option = new Option(
                        concatenarLimpio(item.nombre_especialidad, ' | ', item.servicio__nombre_corto),
                        item.id
                     );

                     if (item.id == 3) {
                        tieneId3 = true;
                        option.selected = true;
                     }

                     especialidad.appendChild(option);
                  });

                  if (!tieneId3) {
                     // Si no se encontró el id 3, seleccionar la primera opción como fallback
                     especialidad.selectedIndex = 0;
                  }

               } else {
                  console.warn("No se encontraron especialidades.");
               }

            } catch (error) {
               console.error("Error al cargar especialidades:", error);
            }
         }

         
            
         servicio.addEventListener("change", async function () {
            const zonaSeleccionada = this.value; 
            await cargarEspecialidades(zonaSeleccionada);

         });

         const hoy = new Date();
         const hace100Anios = new Date();
         hace100Anios.setFullYear(hoy.getFullYear() - 100);
         if(!atencionId){
            await cargarEspecialidades(zona);
            servicio.value = `${zona}`;

            //fecha de hoy si no es registro 
            fecha.value = getFechaLocalYYYYMMDD(hoy);
         }
         fecha.max = hoy.toISOString().split('T')[0];
            fecha.min = hace100Anios.toISOString().split('T')[0];
         



         // si recibimos la info de la atencion es porque ya existe
         try {
            let data = null;
            if (atencionId){
               data = await fetchData(API_URLS.obtenerAtencion, { id: atencionId });
            }

            if (data && "mensaje" in data) {
               // No tiene atencion, establecer valores por defecto
            } else if (data) {
               llenarAtencion(data);
            }
         } catch (error) {
            console.error(error);
         }

         
         function llenarAtencion(atencion) {
            titleElement.textContent ="Actualizar atencion"
            observaciones.value = atencion.observaciones || "";
      
            fecha.value = formatearFechaISO(atencion.fecha) || "";
            idAtencion.value = atencion.id || "";
            detallesRegistro.value = concatenarLimpio(atencion.creado_por," | ", formatFecha(atencion.fecha_creado)) || "";
            detallesModificado.value = concatenarLimpio(atencion.modificado_por," | ", formatFecha(atencion.fecha_modificado)) || "";
            fieldsetRegistro.style.display = 'block';
            servicio.value = atencion.idServicio;
            cargarEspecialidades(servicio.value);
            especialidad.value = atencion.idEspecialidad

            //manejar la fecha de recepcion
            if(atencion.fechaRecepcion){
               fechaRecepcionContenedor.style.display = 'flex';
               fechaRecepcion.value = concatenarLimpio( atencion.recibidoPor," | ",formatFecha(atencion.fechaRecepcion) || "");
               soloLectura();
            }

            //revisar si es editable
            if (!atencion.editable){
               //ya que tiene fecha de recepcion no permitir cambios
               soloLectura();
            }
            

            leyenda.innerHTML = `Paciente: <b> ${concatenarLimpio(atencion.pacienteNombre1,atencion.pacienteNombre2,atencion.pacienteApellido1,atencion.pacienteApellido2)}</b>`;
            idPaciente.value = atencion.pacienteId;
            

         }

         function soloLectura(){
            observaciones.disabled = true; 
            fecha.disabled = true;
            fechaRecepcion.disabled = true;
            servicio.disabled = true;
            especialidad.disabled = true;
            confirmBtn.disabled = true;
            toastr.info("Formulario en modo solo lectura");
         }

      }
   });

   if (modal.isConfirmed) {
        // Guardamos las referencias a los elementos
         const especialidad = document.getElementById("modal-atencion-especialidad");
         const fecha = document.getElementById("modal-atencion-fecha");
         const observaciones = document.getElementById("modal-atencion-observacion");
         const idAtencion = document.getElementById("modal-atencion-id");
         const idPaciente = document.getElementById("modal-atencion-paciente-id");

         try {
            const csrfToken = window.CSRF_TOKEN;
            const response = await fetch(urls["guardarAtencion"], {
               method: "POST",
               headers: {
                     "Content-Type": "application/json",
                     "X-CSRFToken": csrfToken
               },
               body: JSON.stringify({
                     especialidad: especialidad.value,
                     fecha: fecha.value,
                     observaciones: observaciones.value.toUpperCase(),
                     idAtencion: idAtencion.value,
                     idPaciente: idPaciente.value
               })
            });

            const data = await response.json();

            if (!response.ok) {
               // Aquí capturamos los errores que vienen del backend
               toastr.error(data.error || "Error desconocido al guardar la atención");
               return;
            }

            if (data.guardo) {
               resultado = data;
               Swal.close();
            } else {
               toastr.success("No se guardaron cambios");
            }

         } catch (error) {
            toastr.error("Error al guardar la atención: " + error.message);
         }
      
         
      
   }
   return resultado;
}

/* verificacion de ingreso previo a envia a backend */

async function verificarIngreso(idPaciente) {

   const response = await fetch(`${API_URLS.validarIngresoActivo}?idP=${idPaciente}`);
   if (!response.ok) {
      throw new Error(`Error HTTP en validarIngresoActivo: ${response.status}`);
   }

   const data = await response.json();
   return !!data.ingresoActivo; // convierte en booleano directamente
}

async function verificarDefuncion(idPaciente) {
   const response = await fetch(`${API_URLS.verificarDefuncion}?idP=${idPaciente}`);
   if (!response.ok) {
      throw new Error(`Error HTTP en validarDefuncion: ${response.status}`);
   }

   const data = await response.json();
   return !!data.defuncion;
}

async function verificarPacienteInactivo(idPaciente) {
   const response = await fetch(`${API_URLS.verificarPacienteInactivo}?idP=${idPaciente}`);
   if (!response.ok) {
      throw new Error(`Error HTTP en verificarPacienteInactivo: ${response.status}`);
   }

   const data = await response.json();
   return !!data.inactivo;
}

function imprimirHojaHospitalizacion(idIngreso){
      if (idIngreso) {
         var URLreporte = API_URLS.reporteHojaHospitalizacion.replace(/0\/$/, idIngreso + "/");
               const nuevaVentana = window.open(URLreporte, "_blank");
               if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                  toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
               }
      } else {
         toastr.error("Se requiere un id para imprimir el ingreso.");
      }
   }


function imprimirFormatoGenerico(id, urlBase, formato) { 
   const idNumerico = Number(id);

   if (!idNumerico || idNumerico <= 0) {
      toastr.error(`Se requiere un id válido para imprimir. (${formato})`);
      return;
   }

   if (!urlBase) {
      toastr.error("No se pudo generar la URL del reporte.");
      return;
   }

   const URLreporte = urlBase.replace('0', idNumerico);
   const nuevaVentana = window.open(URLreporte, "_blank");

   if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
      toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
   }
}



async function verificarAtencionReciente(idPaciente) {
   const response = await fetch(`${API_URLS.verificarAtencionReciente}?idP=${idPaciente}`);
   if (!response.ok) {
      throw new Error(`Error HTTP en verificarAtencionReciente: ${response.status}`);
   }

   const data = await response.json();

   return data.reciente ? data : false;
}

async function agregarAtencion(paciente,servicio,atencionID){
   if (paciente) {

      // Verificar defunción
      const estaMuerto = await verificarDefuncion(paciente.id);
      if (estaMuerto) {
         toastr.warning("No se puede brindar atencion a un paciente fallecido.");
         return;
      }
      // verificar Inactivo
      const inactivo = await verificarPacienteInactivo(paciente.id);
      if (inactivo) {
         toastr.warning("No se puede brindar atencion a un paciente inactivo.");
         return;
      }

       // verificar Inactivo
      
      const reciente = await verificarAtencionReciente(paciente.id);

      if (reciente && reciente.reciente) {
         const nombre = reciente.nombre || '';
         const especialidad = reciente.especialidad || 'No especificada';
         const fecha = reciente.fecha_creado || 'desconocida';

         toastr.warning(
            `El paciente ${nombre} ya tiene una atención reciente.\n` +
            `Especialidad: ${especialidad}\n` +
            `Fecha: ${fecha}`
         );
         return;
      }


      let resultado = await AgregarAtencionModal(paciente,servicio,atencionID);

      if (resultado?.guardo === true) {
            toastr.info(`Atencion procesada correctamente`, "Cambios realizados");
            return resultado;
         } else if (resultado?.guardo === false) {
            toastr.alert(`No se procesó correctamente la atencion`, 'No se guardaron cambios');
         }

   } else {
      toastr.error("Se requiere un id para registrar una atencion");
   }
}

/**
 * Busca los datos de un paciente en el Censo Electoral.
 *
 * @async
 * @function obtenerDatosPacienteCenso
 * @description Realiza una llamada a la API para obtener la información de un paciente
 * a partir de su número de identidad.
 * @param {string} identidad El número de identidad del paciente, que puede incluir guiones.
 * @returns {Promise<object|number|null>} Los datos del paciente en un objeto si se encuentra,
 * `0` si la búsqueda no arroja resultados, o `null` si ocurre un error en la solicitud.
 */
async function obtenerDatosPacienteCenso(identidad){               
   try {
         const data = await fetchData(API_URLS.obtenerPacienteCenso, {
         parametro: identidad.replace(/-/g, ""),
         });
         if (data.data.length > 0) {
               const paciente = data.data[0];
               if (paciente)
               {
                  return paciente
               }
         } else {
            return 0
         }
      
      } catch (error) {
         return null
      }
}



//#endregion


/*Inactivar un ingreso*/
async function inactivarIngreso(idIngreso) {
   let resultado = null;

   try {
      const csrfToken = window.CSRF_TOKEN;
      const response = await fetch(urls["inactivarIngreso"], {
         method: "POST",
         headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken 
         },
         body: JSON.stringify({
            id: idIngreso
         })
      });
      
      const data = await response.json();

      if (!response.ok && response.status === 400) {
         if (data.errors) {
            Object.entries(data.errors).forEach(([campo, mensaje]) => {
               toastr.error(mensaje, `Error de digitación`);
            });
         } else {
            toastr.error("Ocurrió un error de validación.");
         }
         return;
      }

      if (data.success) {
            setTimeout(() => {
               toastr.success("Proceso realizado correctamente");
            }, 700);
            return true;
      } else {
            toastr.warning(data.error || "Algo salió mal.");
            return;
      }

   } catch (error) {
      toastr.error("Error al inactivar el ingreso" + error.message);
   }
   
   return resultado;
}


/*Inactivar un ingreso*/
async function inactivarEvalucionRX(idEvalucion) {
   let resultado = null;

   try {
      const csrfToken = window.CSRF_TOKEN;
      const response = await fetch(urls["inactivarEvaluacionrx"], {
         method: "POST",
         headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken 
         },
         body: JSON.stringify({
            id: idEvalucion
         })
      });
      
      const data = await response.json();

      if (!response.ok && response.status === 400) {
         if (data.errors) {
            Object.entries(data.errors).forEach(([campo, mensaje]) => {
               toastr.error(mensaje, `Error de digitación`);
            });
         } else {
            toastr.error("Ocurrió un error de validación.");
         }
         return false;
      }

      if (data.success) {
            setTimeout(() => {
               toastr.success("Proceso realizado correctamente");
            }, 700);
            return true;
      } else {
            toastr.warning(data.error || "Algo salió mal.");
            return false;
      }

   } catch (error) {
      toastr.error("Error al inactivar la evalucion" + error.message);
   }
   
   return resultado;
}
//#endregion


/**
    * Realiza la búsqueda de un paciente externo por DNI.
    * @param {string} dni El DNI o número de expediente a buscar..
    * @returns {Promise<Object|null>} Retorna los datos del paciente o null si no se encuentra o hay un error.
    */
   async function buscarPacienteExterno(dni) {
      try {
         let URL = API_URLS.obtenerPacienteExternoDni;
         let parametros = {};

         parametros["dni_externo"] = dni;
         

         const data = await fetchData(URL, parametros);

         // Si el backend responde con un "mensaje" o no hay datos, se considera que no se encontró
         if (data && "mensaje" in data) {
               return null;
         }
         
         return data; // Retorna el objeto de datos del paciente
      } catch (error) {
         console.error("Error en buscar Paciente Externo:", error);
         return null; // Retorna null en caso de error de red o de otro tipo
      }
   }


   /**
    * Realiza la búsqueda de pacientes similares.
    */
      async function buscarPacienteSimilar(id, PrimerNombre, PrimerApellido, fechaNacimiento, Sexo) {
         try {
            const URL = API_URLS.verificarPacienteSimilar;
            const parametros = {
               id,
               primerNombre: PrimerNombre,
               primerApellido: PrimerApellido,
               fechaNacimiento,
               Sexo
            };

            const data = await fetchData(URL, parametros);

            // Si el backend devolvió un error explícito
            if (data && data.error) {
               console.warn("Error del backend:", data.error);
               return null;
            }

            // Si no hay duplicados
            if (data && data.duplicado === false) {
               return false;
            }

            // Si hay duplicados, devuelve la lista
            if (data && data.duplicado === true) {
               return data.pacientes;
            }

            // Si algo raro vino del backend
            return null;

         } catch (error) {
            console.error("Error en buscarPacientesSimilares:", error);
            return null;
         }
         }


// SEGUIMIENTO DE LA REFERENCIA ENVIADA
/*Agrega una defunción y marca el paciente como difunto*/
async function agregarEditarSeguimientoTIC(idSeguimiento, idRef, nombrePaciente) {
   let resultado = null;
   let titulo = `<i class="bi-person-check"></i> Agregar Seguimiento TIC`
   if (idSeguimiento != 0){
      titulo = `<i class="bi-person-check"></i> Editar Seguimiento TIC` 
   }

   const modal = await Swal.fire({

      title: titulo,
      html: `
         <form method="post" class="formulario" id="formulario-modal-seguimiento-tic">
            <fieldset class="modalSeguimientoTIC">
               <legend>Seguimiento a la referencia de: <b>${nombrePaciente}</b></legend>

               <div class="formularioCampoModal">
                  <label for="seguimiento-metodo">Método de comunicación</label>
                  <select id="seguimiento-metodo" name="modal_seguimiento_metodo" class="formularioCampo-select" required>
                     <option value="1">LLAMADA TELEFONICA</option>
                     <option value="2">WHATSAPP</option>
                     <option value="3">VISITA DOMICILIARIA</option>
                     <option value="4">CORREO ELECTRONICO</option>
                     <option value="5">OTRO METODO</option>
                  </select>
               </div>

               <div class="modal-seguimiento-checks">       
                  <label class="ck-formulario" for="switch-establecio-comunicacion">
                     <input type="checkbox" id="switch-establecio-comunicacion" name="establecio_comunicacion" class="ck-formulario__checkbox" hidden>
                     <div class="ck-formulario__base">
                        <div class="ck-formulario__bolita"></div>
                     </div>
                     <span class="ck-formulario__label">Estableció comunicación</span>
                  </label>

                  <label class="ck-formulario" for="switch-asistio-referencia">
                     <input type="checkbox" id="switch-asistio-referencia" name="asistio_referencia" class="ck-formulario__checkbox" hidden disabled>
                     <div class="ck-formulario__base">
                        <div class="ck-formulario__bolita"></div>
                     </div>
                     <span class="ck-formulario__label">Asistió a la referencia</span>
                  </label>
               </div>

               <div class="formularioCampoModal">
                  <label for="seguimiento-fuente-info">Fuente de información</label>
                  <select id="seguimiento-fuente-info" name="modal_fuente_informacion" class="formularioCampo-select" required disabled>
                     <option value="1">PACIENTE</option>
                     <option value="2">FAMILIAR</option>
                     <option value="3">AMIGO</option>
                     <option value="4">PROFESIONAL DE SALUD</option>
                     <option value="5">OTRO FUENTE</option>
                  </select>
               </div>

               <div class="formularioCampoModal">
                  <label for="seguimiento-condicion-paciente">Condición actual del paciente</label>
                  <select id="seguimiento-condicion-paciente" name="modal_condicion_paciente" class="formularioCampo-select" required disabled>
                  </select>
               </div>

               <div class="formularioCampoModal">
                  <label for="seguimiento-observacion">Observación</label>
                  <textarea id="seguimiento-observacion" class="formularioCampo-text" name="observacion" rows="2"></textarea>
               </div>

               <input type="hidden" id="seguimiento-id" name="idSeguimiento" value="${idSeguimiento}]">
            </fieldset>

            <fieldset class="modalDefuncionCampos" id="modal-campos-defuncion-registros" style="display: none;">
               <legend>Detalles del registro</legend>
               <div class="formularioCampoModal">
                  <label for="defuncion-registro">Registrado</label>
                  <input type="text" id="defuncion-registro" class="formularioCampo-text" disabled>
               </div>
            </fieldset>
         </form>

      `,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
         popup: 'contener-modal-defuncion',
         title: 'contener-modal-titulo',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar'
      },
      preConfirm: () => {
            const metodo = document.getElementById("seguimiento-metodo");
            const ckComunicacion = document.getElementById("switch-establecio-comunicacion");
            const ckAsistio = document.getElementById("switch-asistio-referencia");

            const condicion = document.getElementById("seguimiento-condicion-paciente");
            const fuente = document.getElementById("seguimiento-fuente-info");
            const observacion = document.getElementById("seguimiento-observacion");

            // Validación obligatoria
            if (!metodo.value) {
               Swal.showValidationMessage('Debe indicar el método de comunicación');
               return false;
            }

            // Datos base
            const metodoValor = metodo.value;
            let asistio = null;
            let fuenteValor = null;
            let condicionValor = null;
            let observacionValor = observacion.value || null;

            // Si se logró comunicación, validar los campos adicionales
            if (ckComunicacion.checked) {

               asistio = ckAsistio.checked ? 1 : 0;

               if (!fuente.value) {
                     Swal.showValidationMessage('Debe indicar la fuente de información');
                     return false;
               }

               if (!condicion.value) {
                     Swal.showValidationMessage('Debe indicar la condición del paciente');
                     return false;
               }

               if (!idRef){
                  Swal.showValidationMessage('NO logramos encontrar la referecina a la cual quiere aplicar el seguimiento');
                  return false;
               }

               fuenteValor = fuente.value;
               condicionValor = condicion.value;
            }

            // Retornar datos listos para guardar
            return {
               idSeguimiento: idSeguimiento,
               idReferencia:idRef,
               metodo: metodoValor,
               establece_comunicacion: ckComunicacion.checked,
               asistio_referencia: asistio,
               fuente_info: fuenteValor,
               condicion_paciente: condicionValor,
               observacion: observacionValor
            };
         },
      didOpen: async function () {
         const metodo = document.getElementById("seguimiento-metodo");
         const condicion = document.getElementById("seguimiento-condicion-paciente");
         const fuente = document.getElementById("seguimiento-fuente-info");
         const ckComunicacion = document.getElementById("switch-establecio-comunicacion");

         const ckAsistio = document.getElementById("switch-asistio-referencia");
         const observacion = document.getElementById("seguimiento-observacion");


         async function cargarCondiciones(){
            try {
               const data = await fetchData(urls["listarCondiciones"]);

               if (Array.isArray(data) && data.length > 0) {
                  condicion.innerHTML = '';

                  data.forEach((item) => {
                     const option = new Option(
                        item.nombre_condicion_paciente,
                        item.id
                     );
                     condicion.appendChild(option);
                  });

               } else {
                  console.warn("No se encontraron condiciones de paciente.");
               }

            } catch (error) {
               console.error("Error al cargar condiciones del paciente:", error);
            }
         }
      
         function llenarSeguimiento(data){
            ckComunicacion.checked = data.establece_comunicacion;
            ckComunicacion.dispatchEvent(new Event("click"));
            metodo.value = data.metodo;
            ckAsistio.checked = data.asistio_referencia;
            fuente.value = data.fuente_info;
            condicion.value = data.condicion_paciente;
            observacion.value = data.observacion;
         }

         ckComunicacion.addEventListener("click",() =>{

            const habilitar = ckComunicacion.checked;
            
            ckAsistio.disabled = !habilitar;
            fuente.disabled = !habilitar;
            condicion.disabled = !habilitar;
            if(!habilitar){
               ckAsistio.checked = false;
            }
            

         })
      


         await cargarCondiciones();

         if (idSeguimiento != 0){
            try {
               // llamar al backend
               const data = await fetchData(API_URLS.obtenerSeguimientoTIC, { id: idSeguimiento });

               if (!data) {
                     console.warn("No se obtuvo respuesta del servidor");
                     return;
               }

               if (data.mensaje === "no_seguimiento") {
                     // no existe seguimiento, no llenamos nada

               } else {
                     // llenar campos en el modal
                     llenarSeguimiento(data);
               }

            } catch (error) {
               console.error("Error cargando seguimiento:", error);
               toastr.error("No se pudo cargar el seguimiento", "Seguimiento TIC");
            }
         }
      }
   });

   if (modal.isConfirmed) {
         const registro = modal.value;
         try {
            const csrfToken = window.CSRF_TOKEN;
            const response = await fetch(urls["seguimientoAgregarEditar"], {
               method: "POST",
               headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": csrfToken 
               },
               body: JSON.stringify({
                  idSeguimiento: registro.idSeguimiento,
                  idReferencia: registro.idReferencia,
                  metodo: registro.metodo,
                  estableceComunicacion: registro.establece_comunicacion,
                  asistioReferencia: registro.asistio_referencia,
                  fuenteInfo: registro.fuente_info,
                  condicionPaciente: registro.condicion_paciente,
                  observaciones: registro.observacion

               })
            });
      
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            resultado = {guardo: data.guardo, idSeguimiento: data.idSeguimiento}

            if (data.guardo) {
               Swal.close();
               toastr.success(data.mensaje, "Seguimiento TIC");
            } else {
               toastr.warning(data.mensaje, "Seguimiento TIC");
            }

      
         } catch (error) {
            toastr.error("Error al guardar el seguimiento " + error.message,"Seguimiento TIC");
         }
         
      
   }
   return resultado;
}


// seleccionar estudio

async function agregarEditarEstudioDetalle(estudio, estudios) {
   let resultado = null;
   const accion = estudio ? "EDITAR ESTUDIO" : "AGREGAR ESTUDIO"
   const titulo = estudio ? estudio.texto : "";

   let imagenActualUrl = null;
   let esImagenReal = false;
   let imagenServer = false;
   let archivo = null;


   const modal = await Swal.fire({
      title: `${accion}`,
      html: `
            <fieldset class="modalAgregarEditarEstudio">
               <legend><b>${accion} :</b> ${titulo}</legend>
               
               <fieldset class="modalAgregarEditarEstudioTexto">
               <legend>Datos Estudio</legend>

                  <div class="formularioCampoModal">
                     <label for="modalAgregarEditarEstudioEstudio">Estudio:</label>
                     <select id="modalAgregarEditarEstudioEstudio" class="formularioCampo-select">
                     </select>
                  </div>
                  
                  <label class="ck-formulario modalAgregarEditarEstudioGridSwitch">
                        <input 
                           type="checkbox"
                           class="ck-formulario__checkbox"
                           id="switchImpreso"
                           hidden
                        >
                        <div class="ck-formulario__base">
                           <div class="ck-formulario__bolita"></div>
                        </div>
                        <span class="ck-formulario__label">Impreso</span>
                  </label>
               </fieldset>

               <fieldset class="modalAgregarEditarEstudioImagenContenedor">
                  <legend>Imagen Estudio</legend>

                  <div class="modalAgregarEditarEstudioImagen f-panzoom" id="myPanzoom">
                     <img src="" 
                        alt="${estudio ? estudio.texto: "Agregar imagen"}" id="modalAgregarEditarEstudioImagenImagen">
                  </div>

                  <div class="modalAgregarEditarEstudioPanelBotones">

                     <button type="button" id="btnVerImagenGrande" class="modalAgregarEditarEstudioBotonIncrustado">
                        <i class="bi bi-search"></i>
                     </button>

                     <button type="button" id="btnEditarImagen" class="modalAgregarEditarEstudioBotonIncrustado">
                        <i class="bi bi-pencil"></i>
                     </button>
                  
                     <button type="button" id="btnQuitarImagen" class="modalAgregarEditarEstudioBotonIncrustado">
                        <i class="bi bi-trash"></i>
                     </button>

                     

                  </div>

               </fieldset>

               <div class="modalAgregarEditarEstudioAcciones">
               
                  <input type="file" id="inputCamara" accept="image/*" capture="environment" hidden>
                  <input type="file" id="inputGaleria" accept="image/*" hidden>

                  <button type="button" id="btnAdjuntarImagen" class="contener-modal-boton-cancelar">
                        <i class="bi bi-image"></i> ADJUNTAR ARCHIVO
                  </button>

                  <button type="button" id="btnCapturarFoto" class="contener-modal-boton-cancelar">
                        <i class="bi bi-camera-fill"></i> CAPTURAR FOTO
                  </button>

               </div>

               <input type="hidden" id="modal-estudio-detalle-id" value="${estudio ? estudio.idDetalle : 0}">
            </fieldset>
      `,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: `<i class="bi bi-floppy-fill"></i> ${estudio ? "ACTUALIZAR": "AGREGAR"}`,
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
         popup: 'contenedor-modal-agregar-editar-estudio',
         title: 'contener-modal-titulo',
         htmlContainer: 'html-modal-agregarEstudio',
         actions: 'botones-modal-agregarEstudio',
         confirmButton: 'contener-modal-boton-confirmar',
         cancelButton: 'contener-modal-boton-cancelar'
         
      },
      preConfirm: () => {
         const impreso = document.getElementById("switchImpreso").checked;
         const selectElement = document.getElementById("modalAgregarEditarEstudioEstudio");
         const tom = selectElement?.tomselect;
         const valueSeleccionado = tom.getValue();


         if (!valueSeleccionado) {
            Swal.showValidationMessage("Debe seleccionar un estudio");
            return false;
         }
      
         const opcion = tom.options[valueSeleccionado];

         let accionImagen = "STAY";
         const tieneArchivoNuevo = Boolean(archivo);
         const quitoImagen = imagenServer && !tieneArchivoNuevo && !esImagenReal;

         if (tieneArchivoNuevo) {
            accionImagen = "SYNC";
         } 
         else if (quitoImagen) {
            accionImagen = "DELETE";
         }

         return {
            idEstudio: opcion.value,
            impreso: impreso,
            texto: opcion.text,
            codigo: opcion.codigo,

            // Estado de imagen
            archivo: archivo,                 // File real 
            imagenUrl: imagenActualUrl,        // URL actual (blob o real)
            esImagenReal: esImagenReal,        // Para saber si hay imagen válida
            accionImagen: accionImagen
         };
      },
      didOpen: async function () {
         // selecion
         const imagen = document.getElementById("modalAgregarEditarEstudioImagenImagen");
         const check = document.getElementById("switchImpreso");
         const btnVer = document.getElementById("btnVerImagenGrande");
         const btnAdjuntar = document.getElementById("btnAdjuntarImagen");
         const btnCapturar = document.getElementById("btnCapturarFoto");
         const btnQuitar = document.getElementById("btnQuitarImagen");
         const btnEditar = document.getElementById("btnEditarImagen");
         const inputCamara = document.getElementById("inputCamara");
         const inputGaleria = document.getElementById("inputGaleria");

         let estudioTomSelect = null;
         let info={}

         // TomSelect
         if (estudios){
               estudioTomSelect = new TomSelect("#modalAgregarEditarEstudioEstudio", {
               options: estudios.map(est => ({
                     value: est.id,
                     text: `${est.descripcion_estudio}`,
                     codigo: est.codigo
               })),
               placeholder: "SELECCIONE UN ESTUDIO"
            });
         }

         // Colocar imagen y actualizar estado
         function colocarIMG(url, esReal = false) {
            if (!imagen) return;

            imagen.src = url;
            imagenActualUrl = url;
            esImagenReal = esReal;

            btnEditar.style.display = (archivo instanceof File) ? "flex" : "none";
         }


         // Botón Adjuntar
         btnCapturar.addEventListener("click", () => inputCamara.click());
         btnAdjuntar.addEventListener("click", () => inputGaleria.click());


         inputCamara.addEventListener("change", () => manejarArchivo(inputCamara));
         inputGaleria.addEventListener("change", () => manejarArchivo(inputGaleria));


         btnEditar.addEventListener("click", () => abrirEditor());

         // Boton Quitar 
         btnQuitar.addEventListener("click", () =>{
            colocarIMG(window.APP_CONFIG.estudioDefaultImg, false);
            archivo = null;
         });


         function construirInfoDesdeTomSelect(tomSelect, estudio) {

            const info = {};

            const value = tomSelect?.getValue();

            if (!value) return info;

            const opcion = tomSelect.options[value];

            info.subtitulo = opcion?.text || "";
            info.titulo = estudio?.paciente?.trim() || "";

            return info;
         }


         async function manejarArchivo(input) {
            archivo = input.files[0];
            if (!archivo) return;

            const resultado = AdjuntarImagenHelper.validarArchivo(archivo);
            if (!resultado.valido) {
               toastr.error(resultado.error);
               input.value = "";
               return;
            }

            let info = construirInfoDesdeTomSelect(estudioTomSelect, estudio);
         
            
            const archivoEditado = await ImageEditor.open(archivo,info);

            if (!archivoEditado) return;

            if (imagenActualUrl?.startsWith("blob:")) {
               AdjuntarImagenHelper.quitarUrlPreview(imagenActualUrl);
            }
            archivo = archivoEditado;

            const url = AdjuntarImagenHelper.crearUrlPreview(archivo);
            colocarIMG(url, true);
         }


          // Verificar si viene contenido si esa ahi llenar
         if (estudio){

            if (estudioTomSelect) {
               estudioTomSelect.setValue(estudio.id);
            }

            if (estudio.url_imagen) {
               colocarIMG(estudio.url_imagen, true);
               imagenServer = true;
            } else {
               colocarIMG(window.APP_CONFIG.estudioDefaultImg, false);
            }

            check.checked = estudio.impreso;

         } else {
            colocarIMG(window.APP_CONFIG.estudioDefaultImg, false);
         }


         // Abrir visor (imagen o botón)
         function abrirVisor() {
            if (imagenActualUrl && esImagenReal) {
                  let info = construirInfoDesdeTomSelect(estudioTomSelect, estudio);
                  
                  ImageViewer.open(
                     imagenActualUrl,
                     0,
                     info?.titulo || "",
                     [info?.subtitulo || ""]
                  );
            }
         }

         async function abrirEditor(){
            if (!(archivo instanceof File)) return;

            const info = construirInfoDesdeTomSelect(estudioTomSelect, estudio);

            const archivoEditado = await ImageEditor.open(archivo, info);

            if (!archivoEditado) return;

            // limpiar preview anterior
            if (imagenActualUrl?.startsWith("blob:")) {
               AdjuntarImagenHelper.quitarUrlPreview(imagenActualUrl);
            }

            archivo = archivoEditado;

            const url = AdjuntarImagenHelper.crearUrlPreview(archivo);

            colocarIMG(url, true);
         }



         if (imagen) {
            imagen.addEventListener("click", abrirVisor);
         }

         if (btnVer) {
            btnVer.addEventListener("click", abrirVisor);
         }
      }
   });

   if (modal.isConfirmed) {
         const registro = modal.value;
         resultado = {
            idEstudio: registro.idEstudio,
            impreso: registro.impreso,
            archivo: registro.archivo,
            imagenUrl: registro.imagenUrl,
            esImagenReal: registro.esImagenReal,
            texto: registro.texto,
            codigo: registro.codigo,
            frontendId: estudio ? estudio.frontendId : null,
            accionImagen: registro.accionImagen
         }
      
   }
   return resultado;
}
//#endregion