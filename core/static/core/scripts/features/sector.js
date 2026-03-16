
    
    

function AgregarSectorModal(id_municipio) {
    Swal.fire({
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
                            <input type="text" id="modal_agregar_sector-descripcion" name="sectorAldea" placeholder="SECTOR" class="formularioCampo-text">
                            </select>
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
            const inputDescripcion = document.querySelector('#modal_agregar_sector-descripcion');
            const selectAldea = $('#modal_agregar_sector-aldea');
        
            if (inputDescripcion) {
                selectAldea.focus();
            }
            
            
            // Evitar inicialización duplicada de Select2
            if (!selectAldea.hasClass("select2-hidden-accessible")) {  
                selectAldea.select2({
                    ajax: {
                        url: urls["aldeaAutocomplete"],
                        dataType: "json",
                        delay: 250,
                        data: function (params) {
                            return {
                                municipio_id: id_municipio,
                                q: params.term, 
                            };
                        },
                        processResults: function (data) {
                            return {
                                results: data.results,
                            };
                        },
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
        
            const actionsContainer = document.querySelector('.swal2-actions');
            if (actionsContainer) {
                actionsContainer.classList.add('contener-modal-contenedor-botones-min');
            }


        }
    }).then((result) => {
        if (result.isConfirmed) {
            const checkZona = document.querySelector('#modal_agregar_sector-zona');
            const aldea = document.querySelector('#modal_agregar_sector-aldea').value;
            const sectorDescripcion = document.querySelector('#modal_agregar_sector-descripcion').value.trim();
            const zona = checkZona.checked ? 2 : 1;
            const csrfToken = window.CSRF_TOKEN;
            // Enviar el formulario con fetch
            fetch(urls["agregarSector"], {
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
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error HTTP: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.sector_id) {
                    toastr.success("Sector registrado correctamente.");
                    const $sector = $("#id_sector");
                    const newOption = new Option(data.nombre_sector, data.sector_id, true, true);
                    $sector.append(newOption).trigger("change");

                    Swal.close();  // Cerrar la modal manualmente
                } else {
                    toastr.error("Existe un problema al registrar el sector.");
                }
            })
            .catch(error => {
                toastr.error("Existe un error al registrar el sector: " + error.message);
            });
        }
    });
}


    
    







