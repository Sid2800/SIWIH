document.addEventListener('DOMContentLoaded', function () {
    const listaRecepcionIzquierda = document.getElementById('listaRecepcionIzquierda');
    const listaRecepcionDerecha = document.getElementById('listaRecepcionDerecha');

    const confirmBtn = document.getElementById('recepcionIngresoBoton');
    const totalPendiente = document.getElementById('totalPendiente');
    const totalPorRecibir = document.getElementById('totalPorRecibir');
    const SubtotalPendiente = document.getElementById('SubtotalPendiente');
    const SubtotalPorRecibir = document.getElementById('SubtotalPorRecibir');
    //text de busqqueda
    const busquedaPendientes = document.getElementById('busquedaPendientes');
    const busquedaPorRecibir = document.getElementById('busquedaPorRecibir');
    const imprimir = document.getElementById('switchImprimirComprobante');


    

    // mapear lada deata recibida de Bakcend
    const ingresosFormateados = ingresosActivos.map(ingreso => {
        return {
            id: ingreso.id,
            nombre: `${ingreso.paciente__primer_nombre} ${ingreso.paciente__primer_apellido || ''}`.trim(),
            sala: ingreso.sala__nombre_sala,
            dni: ingreso.paciente__dni || '',
            exp: ingreso.expediente_numero,
            fechaIngreso: ingreso.fecha_ingreso,
            fechaEgreso: ingreso.fecha_egreso,  

            idPaciente: ingreso.paciente_id,
        };
    });


            
    let pendientes = [...ingresosFormateados];
    let porRecibir = [];


    //busqueda  delay
    let timeout;


    function formatearTexto(dni, nombre, expediente, fechaEgreso) {
        // Asegurar que dni tenga 13 caracteres, rellenando con espacios si es necesario
        dni = dni ? dni.slice(0, 13).padEnd(13, ' ') : ' '.repeat(13);

        // Normalizar nombre a 15 caracteres: cortar si excede, rellenar si es menor
        nombre = nombre.length > 15 ? nombre.substring(0, 15) : nombre.padEnd(15, ' ');
    
        // Normalizar expediente a 7 dígitos con ceros a la izquierda
        expediente = expediente ? expediente.toString().padStart(6, '0') : '0000000';
    
        // Concatenar todo en una sola cadena simulando una tabla
        return `${expediente} |${dni} |${nombre} |${fechaEgreso}`;
    }

    function mostrarLista(lista, elemento) {
        elemento.innerHTML = '';
        lista.forEach((registro, index) => {
            const li = document.createElement('li');
            li.textContent = formatearTexto(registro.dni, registro.nombre, registro.exp, registro.fechaEgreso);
            li.dataset.id = registro.id;
            li.addEventListener('click', () => {
            li.classList.toggle('selected');
            });
            
            li.addEventListener('dblclick', () => {
                const id = parseInt(li.dataset.id);
                const expediente = pendientes.find(exp => exp.id === id) || porRecibir.find(exp => exp.id === id);
                if (expediente) {
                    moverExpediente(expediente); // Llamar a la función para mover el expediente
                }
            });
            elemento.appendChild(li);
        });
        }

    function filtrarMostrar() {

        let filtrados;  // Aquí almacenaremos los expedientes filtrados
        let filtradosPorRecibir;
    
        // Ordenar por nombre alfabéticamente (ignorando mayúsculas/minúsculas)
        pendientes.sort((a, b) => a.exp - b.exp);
        porRecibir.sort((a, b) => a.exp - b.exp);
                
        filtrados = pendientes;  
        filtradosPorRecibir = porRecibir;
      
        
        
        mostrarLista(filtrados, listaRecepcionIzquierda);  // En la lista de "Pendientes"
        actualizarTotalesSubtotales(totalPendiente,pendientes.length);
        actualizarTotalesSubtotales(SubtotalPendiente,filtrados.length)
        
        mostrarLista(filtradosPorRecibir, listaRecepcionDerecha);  // En la lista de "Por Recibir"
        actualizarTotalesSubtotales(totalPorRecibir,porRecibir.length);
        actualizarTotalesSubtotales(SubtotalPorRecibir,filtradosPorRecibir.length)
        
        busquedaPendientes.value = "";
    }

    function actualizarTotalesSubtotales(span, total){
        span.textContent = total;
    }

    function moverExpediente(expediente) {
        if (pendientes.includes(expediente)) {
            const index = pendientes.indexOf(expediente);
            if (index !== -1) {
                pendientes.splice(index, 1);
                porRecibir.push(expediente);
            }
        } else if (porRecibir.includes(expediente)) {
            const index = porRecibir.indexOf(expediente);
            if (index !== -1) {
                porRecibir.splice(index, 1);
                pendientes.push(expediente);
            }
        }
        filtrarMostrar(); 
    }

    // cuadros de busqueda 
    busquedaPendientes.addEventListener('input', () => {
        clearTimeout(timeout);
        
        timeout = setTimeout(() => {
            const search = busquedaPendientes.value.toLowerCase();

            let filtered = pendientes.filter(exp => {
                const coincideTexto = exp.nombre.toLowerCase().includes(search) || exp.exp.toString().includes(search) || exp.dni.toString().includes(search);
                return coincideTexto;
            });
        
            mostrarLista(filtered, listaRecepcionIzquierda);
            actualizarTotalesSubtotales(SubtotalPendiente, filtered.length)
        }, 300);
    })

    busquedaPendientes.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const valor = busquedaPendientes.value.trim();
        
            // Verificar si es un número válido
            if (!/^\d+$/.test(valor)) {
                toastr.warning("El DNI debe contener solo números.");
                return;
            }

            const indice = pendientes.findIndex(expediente => {
                const coincideDni = expediente.dni == valor;
                return coincideDni;
            });
            
            if (indice !== -1) {
                const [expediente] = pendientes.splice(indice, 1); // eliminar del origen
                porRecibir.push(expediente); // agregar al destino
                busquedaPendientes.value = '';
                filtrarMostrar(); // actualizar vistas
            } else {
                alert(`No se encontró el expediente con número: ${valor}`);
                busquedaPendientes.value = '';
                filtrarMostrar(); // actualizar vistas
            }
        }
        });
    
    busquedaPorRecibir.addEventListener('input', () => {
        // Limpiamos el temporizador anterior si hay alguno
        clearTimeout(timeout);
        
        // Establecemos un nuevo temporizador
        timeout = setTimeout(() => {
            const search = busquedaPorRecibir.value.toLowerCase();
        
            let filtered = porRecibir.filter(exp => {
                const coincideTexto = exp.nombre.toLowerCase().includes(search) || exp.exp.toString().includes(search) || exp.dni.toString().includes(search);
                return coincideTexto;
            });
            mostrarLista(filtered, listaRecepcionDerecha);
            actualizarTotalesSubtotales(SubtotalPorRecibir, filtered.length)
        }, 300);
    });


    busquedaPorRecibir.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        const valor = busquedaPorRecibir.value.trim();
    
        // Verificar si es un número válido
        if (!/^\d+$/.test(valor)) {
            toastr.warning("El DNI debe contener solo números.");
            return;
        }
    
        const indice = porRecibir.findIndex(expediente => {
            const coincideDni = expediente.dni == valor;
            return coincideDni;
        });
    
        if (indice !== -1) {
            const [expediente] = porRecibir.splice(indice, 1); // eliminar del origen
            pendientes.push(expediente); // agregar al destino
            busquedaPorRecibir.value = '';
            filtrarMostrar(); // actualizar vistas
        } else {
            alert(`No se encontró el expediente con número: ${valor}`);
            busquedaPorRecibir.value = '';
            filtrarMostrar(); // actualizar vistas
        }
    }
    });

    function moverSeleccionados(listaOrigen, listaDestino, contenedorOrigen) {
        const seleccionados = contenedorOrigen.querySelectorAll('.selected');
        
        seleccionados.forEach(elemento => {
            const id = parseInt(elemento.dataset.id);
            const indice = listaOrigen.findIndex(expediente => expediente.id === id);
            
            if (indice !== -1) {
                const [expediente] = listaOrigen.splice(indice, 1); // eliminar del origen
                listaDestino.push(expediente); // agregar al destino
            }
        });
        
        filtrarMostrar(); // volver a renderizar listas
        }
    
    document.getElementById('BtnMoverDerecha').onclick = () =>
        moverSeleccionados(pendientes, porRecibir, listaRecepcionIzquierda, );
        
    
    document.getElementById('BtnMoverIzquierda').onclick = () =>
    moverSeleccionados(porRecibir, pendientes, listaRecepcionDerecha);
    

    document.getElementById('BtnMoverTodoDerecha').onclick = () => {
        const visibles = Array.from(listaRecepcionIzquierda.querySelectorAll('li'));
        visibles.forEach(elemento => {
            const id = parseInt(elemento.dataset.id);
            const index = pendientes.findIndex(exp => exp.id === id);
            if (index !== -1) {
                const [expediente] = pendientes.splice(index, 1);
                porRecibir.push(expediente);
            }
        });
        filtrarMostrar();
    };

    document.getElementById('BtnMoverTodoIzquierda').onclick = () => {
        const visibles = Array.from(listaRecepcionDerecha.querySelectorAll('li'));
        visibles.forEach(elemento => {
            const id = parseInt(elemento.dataset.id);
            const index = porRecibir.findIndex(exp => exp.id === id);
            if (index !== -1) {
                const [expediente] = porRecibir.splice(index, 1);
                pendientes.push(expediente);
            }
        });
        filtrarMostrar();
        };


    confirmBtn.addEventListener('click', async function () {
        if (porRecibir.length == 0) {
            toastr.error("NO hay ningun ingreso por rebibir");
            return
        }


        const confirmado = await confirmarAccion(
            '¿Estás seguro?',
            `Estás a punto confirmar la recepcion de ${porRecibir.length} ingresos`
        );
        if (confirmado) {
            await enviarRecepcion();
        }

        });


    async function enviarRecepcion() {
        const csrfToken = window.CSRF_TOKEN;
    
        try {
            const response = await fetch(urls['registrarRecepcionIngresosSDGI'], {
                method: "POST",
                body: JSON.stringify({
                    observaciones: observaciones.value, // pa probar
                    ingresos: porRecibir // lista de diccionarios 
                }),
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
            });
    
            const data = await response.json();
            
            if (!response.ok) {
                // Manejamos errores personalizados del backend
                if (data.error) {
                    toastr.error(data.error, "Error");
                } else if (data.errors) {
                    Object.entries(data.errors).forEach(([campo, mensaje]) => {
                        toastr.error(mensaje, `Error en: ${campo}`);
                    });
                } else {
                    toastr.error("Ocurrió un error inesperado.");
                }
                return;
            }
    
            // Si llega aquí, todo fue bien
            if (data.success) {
                toastr.success(data.message || "Proceso realizado correctamente");
                
                if (imprimir.checked && data.pdf_url) {
                    const nuevaVentana = window.open(data.pdf_url, "_blank");
                    if (!nuevaVentana || nuevaVentana.closed || typeof nuevaVentana.closed === "undefined") {
                        toastr.error("No se pudo abrir la nueva pestaña. Verifica los permisos del navegador.");
                    }
                }

                if (data.redirect_url) {
                    setTimeout(() => {
                        window.location.href = data.redirect_url;
                    }, 1500);
                }

            } else {
                toastr.error(data.error || "Ocurrió un error durante el proceso.");
            }
    
        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al registrar el ingreso.");
        }
    }


    filtrarMostrar();


});