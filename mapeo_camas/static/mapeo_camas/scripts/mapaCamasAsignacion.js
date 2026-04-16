document.addEventListener("DOMContentLoaded", function () {
  // Endpoints usados por el mapa para cargar datos, buscar y guardar cambios.
  var API_URLS = {
    estadoMapeo: "/mapeo-camas/api/estado-mapeo/",
    iniciarMapeo: "/mapeo-camas/api/iniciar-mapeo/",
    terminarMapeo: "/mapeo-camas/api/terminar-mapeo/",
    cancelarMapeo: "/mapeo-camas/api/cancelar-mapeo/",
    mapa: "/mapeo-camas/api/mapa-camas/",
    buscarPacientes: "/mapeo-camas/api/buscar-pacientes/",
    actualizarCama: "/mapeo-camas/api/actualizar-cama/",
    camasDisponibles: "/mapeo-camas/api/camas-disponibles/",
    moverPaciente: "/mapeo-camas/api/mover-paciente/",
    procesarCamaMapeo: "/mapeo-camas/api/procesar-cama-mapeo/"
  };

  var ESTADOS_CAMA = [
    "VACIA",
    "OCUPADA",
    "ALTA",
    "FUERA_SERVICIO",
    "CONSULTA_EXTERNA"
  ];

  var contenedor = document.getElementById("mapa-servicios");
  var inputBusqueda = document.getElementById("mapa-busqueda");
  var tipoBusqueda = document.getElementById("mapa-tipo-busqueda");
  var btnLimpiar = document.getElementById("btn-limpiar-busqueda");
  var btnCopiar = document.getElementById("btn-copiar-camas");
  var btnImprimir = document.getElementById("btn-imprimir-camas");
  var btnIniciarMapeo = document.getElementById("btn-iniciar-mapeo");
  var btnTerminarMapeo = document.getElementById("btn-terminar-mapeo");
  var btnCancelarMapeo = document.getElementById("btn-cancelar-mapeo");
  var camasRenderizadas = [];
  var sesionMapeoActivaId = null;
  var camasMapeadasSesion = new Set();

  function establecerModoMapeoActivo(activo) {
    var ocultar = function (el, debeOcultar) {
      if (!el) {
        return;
      }
      if (debeOcultar) {
        el.style.display = "none";
        return;
      }
      el.classList.remove("mapa-control-mapeo--oculto");
      el.style.display = "inline-flex";
    };

    ocultar(btnIniciarMapeo, activo);
    ocultar(btnCopiar, activo);
    ocultar(btnImprimir, activo);
    ocultar(btnTerminarMapeo, !activo);
    ocultar(btnCancelarMapeo, !activo);
  }

  function marcarCamaComoMapeada(camaEl) {
    if (!camaEl) {
      return;
    }
    camaEl.classList.add("mapa-cama--mapeada");
    if (camaEl.dataset && camaEl.dataset.numeroCama) {
      camasMapeadasSesion.add(String(camaEl.dataset.numeroCama));
    }
  }

  function limpiarMarcasMapeo() {
    camasRenderizadas.forEach(function (item) {
      item.classList.remove("mapa-cama--mapeada");
    });
    camasMapeadasSesion.clear();
  }

  function aplicarMarcasSesionEnRender() {
    if (!camasMapeadasSesion.size) {
      return;
    }
    camasRenderizadas.forEach(function (item) {
      if (camasMapeadasSesion.has(String(item.dataset.numeroCama || ""))) {
        item.classList.add("mapa-cama--mapeada");
      }
    });
  }

  async function cargarEstadoSesionMapeo() {
    try {
      var response = await fetch(API_URLS.estadoMapeo);
      var data = await response.json();
      if (!response.ok || !data.ok) {
        return;
      }

      if (data.sesion_activa && data.sesion_activa.id) {
        sesionMapeoActivaId = data.sesion_activa.id;
        establecerModoMapeoActivo(true);
      } else {
        sesionMapeoActivaId = null;
        establecerModoMapeoActivo(false);
      }

      camasMapeadasSesion = new Set((data.camas_mapeadas || []).map(function (v) {
        return String(v);
      }));
      aplicarMarcasSesionEnRender();
    } catch (error) {
      // Si falla la consulta, mantener UI base sin bloquear el mapa.
    }
  }

  // Traduce el estado de negocio a la clase CSS visual de cada card de cama.
  function claseEstado(estadoVisual) {
    if (estadoVisual === "VACIA") {
      return "mapa-cama--vacia";
    }
    if (estadoVisual === "OCUPADA") {
      return "mapa-cama--ocupada";
    }
    if (estadoVisual === "ALTA") {
      return "mapa-cama--alta";
    }
    if (estadoVisual === "FUERA_SERVICIO") {
      return "mapa-cama--fuera-servicio";
    }
    if (estadoVisual === "CONSULTA_EXTERNA") {
      return "mapa-cama--consulta-externa";
    }
    return "mapa-cama--sin-asignacion";
  }

  // Arma una cadena de texto completa para busqueda global en una cama.
  function textoBusquedaCama(item) {
    return [
      item.dataset.numeroCama || "",
      item.dataset.paciente || "",
      item.dataset.estado || "",
      item.dataset.sala || "",
      item.dataset.servicio || "",
      item.dataset.cubiculo || "",
    ].join(" ").toLowerCase();
  }

  // Filtra las cards renderizadas segun tipo de busqueda y texto escrito.
  function aplicarFiltro() {
    var valor = (inputBusqueda.value || "").trim().toLowerCase();
    var tipo = tipoBusqueda.value || "todo";

    camasRenderizadas.forEach(function (item) {
      if (!valor) {
        item.style.display = "";
        return;
      }

      var campo = "";
      if (tipo === "cama") {
        campo = item.dataset.numeroCama || "";
      } else if (tipo === "paciente") {
        campo = item.dataset.paciente || "";
      } else if (tipo === "estado") {
        campo = item.dataset.estado || "";
      } else {
        campo = textoBusquedaCama(item);
      }

      item.style.display = campo.toLowerCase().includes(valor) ? "" : "none";
    });
  }

  // Sincroniza una card del DOM con la respuesta actualizada del backend.
  function actualizarCardDesdeRespuesta(camaEl, camaActualizada) {
    camaEl.className = "mapa-cama " + claseEstado(camaActualizada.estado_visual);
    camaEl.dataset.paciente = camaActualizada.paciente ? camaActualizada.paciente.nombre : "";
    camaEl.dataset.pacienteId = camaActualizada.paciente ? String(camaActualizada.paciente.id) : "";
    camaEl.dataset.estado = camaActualizada.estado_visual || "";
    camaEl.dataset.pacienteDni = camaActualizada.paciente ? (camaActualizada.paciente.dni || "") : "";
    camaEl.dataset.cambiosRealizados = String(camaActualizada.cambios_realizados || 0);
    camaEl.dataset.maxCambios = String(camaActualizada.max_cambios || 5);

    var estadoEl = camaEl.querySelector(".mapa-cama-estado");
    var pacienteEl = camaEl.querySelector(".mapa-cama-paciente");
    var dniEl = camaEl.querySelector(".mapa-cama-dni");

    if (estadoEl) {
      estadoEl.textContent = camaActualizada.estado_visual || "SIN_ASIGNACION";
    }
    if (pacienteEl) {
      pacienteEl.textContent = camaActualizada.paciente ? camaActualizada.paciente.nombre : "Sin paciente";
    }
    if (dniEl) {
      dniEl.textContent = camaActualizada.paciente ? (camaActualizada.paciente.dni || "") : "";
    }
  }

  // Rellena un <select> con las camas disponibles (VACIA) para mover un paciente
  function renderCamaDestinoSelect(camas, selectEl) {
    selectEl.innerHTML = camas.length
      ? '<option value="">-- Seleccionar cama --</option>'
      : '<option value="">Sin camas disponibles</option>';
    camas.forEach(function (cama) {
      var option = document.createElement("option");
      option.value = String(cama.numero_cama);
      var etiqueta = "Cama " + cama.numero_cama + " \u2014 " + cama.sala;
      if (cama.cubiculo) {
        etiqueta += " / Cub. " + cama.cubiculo;
      }
      etiqueta += " (" + cama.servicio + ")";
      option.textContent = etiqueta;
      selectEl.appendChild(option);
    });
  }

  // Convierte camas disponibles al formato esperado por TomSelect.
  function mapCamasTomSelect(camas) {
    return (camas || []).map(function (cama) {
      var etiqueta = "Cama " + cama.numero_cama + " \u2014 " + cama.sala;
      if (cama.cubiculo) {
        etiqueta += " / Cub. " + cama.cubiculo;
      }
      etiqueta += " (" + cama.servicio + ")";
      return {
        id: String(cama.numero_cama),
        text: etiqueta,
        numero: String(cama.numero_cama || ""),
        sala: String(cama.sala || ""),
        servicio: String(cama.servicio || ""),
        cubiculo: String(cama.cubiculo || "")
      };
    });
  }

  // Convierte resultados de pacientes al formato esperado por TomSelect.
  function mapPacientesTomSelect(pacientes) {
    return (pacientes || []).map(function (paciente) {
      var etiqueta = (paciente.nombre || "Sin nombre") + (paciente.dni ? " (" + paciente.dni + ")" : "");
      return {
        id: String(paciente.id),
        text: etiqueta
      };
    });
  }

  // Modal principal para operar una cama: cambio de estado o movimiento de paciente.
  async function abrirModalEdicionCama(camaEl) {
    // Datos base tomados de la card seleccionada.
    // Se usan para:
    // 1) precargar el modal,
    // 2) decidir el flujo (ocupada vs vacia),
    // 3) mostrar el contador de limite.
    var numeroCama = camaEl.dataset.numeroCama || "";
    var estadoActual = camaEl.dataset.estado || "SIN_ASIGNACION";
    var pacienteActual = camaEl.dataset.paciente || "";
    var dniActual = camaEl.dataset.pacienteDni || "";
    var cambiosRealizados = parseInt(camaEl.dataset.cambiosRealizados || "0", 10);
    var maxCambios = parseInt(camaEl.dataset.maxCambios || "5", 10);
    var limiteTexto = cambiosRealizados + " / " + maxCambios;

    // La cama esta OCUPADA cuando el estado visual actual es OCUPADA.
    // Esta bandera define toda la estructura del modal.
    var esOcupada = estadoActual === "OCUPADA";

    // ── HTML para cama VACIA (u otro estado sin paciente) ────────────────────
    // Permite cambiar el estado; si se elige OCUPADA aparece busqueda de paciente
    var opcionesEstadoVacia = ESTADOS_CAMA.map(function (e) {
      var sel = e === estadoActual ? ' selected="selected"' : "";
      return '<option value="' + e + '"' + sel + ">" + e + "</option>";
    }).join("");

    var htmlVacia =
      '<fieldset class="modalAtencionCampos">' +
      "  <legend>Estado de la cama</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-mapa-estado">Cambiar a estado</label>' +
      '    <select id="modal-mapa-estado" class="formularioCampo-select">' +
      opcionesEstadoVacia +
      "    </select>" +
      "  </div>" +
      "</fieldset>" +
      '<fieldset id="bloque-asignar-paciente" class="modalAtencionCampos" style="display:none">' +
      "  <legend>Asignar paciente a esta cama</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-tipo-busqueda-paciente">Buscar por</label>' +
      '    <select id="modal-tipo-busqueda-paciente" class="formularioCampo-select">' +
      '      <option value="nombre" selected>Nombre</option>' +
      '      <option value="dni">DNI</option>' +
      "    </select>" +
      "  </div>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-mapa-paciente">Buscar paciente</label>' +
      '    <select id="modal-mapa-paciente" class="formularioCampo-select">' +
      '      <option value="">-- Seleccionar paciente --</option>' +
      '    </select>' +
      "  </div>" +
      "</fieldset>" +
      '<p class="modal-cama-limite">Cambios realizados: ' + limiteTexto + "</p>";

    // ── HTML para cama OCUPADA ───────────────────────────────────────────────
    // Muestra el paciente actual y permite: cambiar estado O mover a otra cama
    var htmlOcupada =
      '<fieldset class="modalAtencionCampos">' +
      "  <legend>Paciente actual de la cama</legend>" +
      '  <div class="formularioCampoModal">' +
      "    <label>Nombre</label>" +
      '    <input type="text" id="modal-pac-nombre" class="formularioCampo-text" readonly>' +
      "  </div>" +
      '  <div class="formularioCampoModal">' +
      "    <label>Identidad</label>" +
      '    <input type="text" id="modal-pac-dni" class="formularioCampo-text" readonly>' +
      "  </div>" +
      "</fieldset>" +
      '<fieldset class="modalAtencionCampos">' +
      "  <legend>Accion a realizar</legend>" +
      '  <div class="modal-no-atencion-checks">' +
      '    <label class="ck-formulario" for="modal-accion-cambiar-estado">' +
      '      <input type="checkbox" id="modal-accion-cambiar-estado" class="ck-formulario__checkbox" hidden checked>' +
      '      <div class="ck-formulario__base"><div class="ck-formulario__bolita"></div></div>' +
      '      <span class="ck-formulario__label">Cambiar estado de la cama</span>' +
      "    </label>" +
      '    <label class="ck-formulario" for="modal-accion-mover-cama">' +
      '      <input type="checkbox" id="modal-accion-mover-cama" class="ck-formulario__checkbox" hidden>' +
      '      <div class="ck-formulario__base"><div class="ck-formulario__bolita"></div></div>' +
      '      <span class="ck-formulario__label">Mover paciente a otra cama disponible</span>' +
      "    </label>" +
      "  </div>" +
      "</fieldset>" +
      '<fieldset id="bloque-cambiar-estado" class="modalAtencionCampos">' +
      "  <legend>Nuevo estado (el paciente quedara sin cama asignada)</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-mapa-estado">Estado</label>' +
      '    <select id="modal-mapa-estado" class="formularioCampo-select">' +
      '      <option value="VACIA">VACIA (desocupar)</option>' +
      '      <option value="ALTA">ALTA</option>' +
      '      <option value="FUERA_SERVICIO">FUERA_SERVICIO</option>' +
      '      <option value="CONSULTA_EXTERNA">CONSULTA_EXTERNA</option>' +
      "    </select>" +
      "  </div>" +
      "</fieldset>" +
      '<fieldset id="bloque-mover-cama" class="modalAtencionCampos" style="display:none">' +
      "  <legend>Seleccionar cama destino disponible</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-tipo-busqueda-cama">Buscar por</label>' +
      '    <select id="modal-tipo-busqueda-cama" class="formularioCampo-select">' +
      '      <option value="numero" selected>Numero de cama</option>' +
      '      <option value="sala">Sala</option>' +
      '      <option value="servicio">Servicio</option>' +
      '      <option value="cubiculo">Cubiculo</option>' +
      "    </select>" +
      "  </div>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-cama-destino">Cama disponible</label>' +
      '    <select id="modal-cama-destino" class="formularioCampo-select">' +
      '      <option value="">-- Cargando... --</option>' +
      "    </select>" +
      "  </div>" +
      "</fieldset>" +
      '<p class="modal-cama-limite">Cambios realizados: ' + limiteTexto + "</p>";

    var modal = await Swal.fire({
      title: "Cama " + numeroCama,
      html: esOcupada ? htmlOcupada : htmlVacia,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: '<i class="bi bi-floppy-fill"></i> Guardar',
      cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
      customClass: {
        popup: "contener-modal-defuncion",
        title: "contener-modal-titulo",
        content: "contener-modal-contenido",
        confirmButton: "contener-modal-boton-confirmar",
        cancelButton: "contener-modal-boton-cancelar"
      },
      preConfirm: function () {
        // preConfirm centraliza validacion y armado del payload logico.
        // Si retorna false, SweetAlert bloquea el cierre y muestra mensaje.
        if (esOcupada) {
          var accionCambiarEstado = document.getElementById("modal-accion-cambiar-estado");
          var accionMoverCama = document.getElementById("modal-accion-mover-cama");

          // Seguridad defensiva: si no existen controles, el modal no puede continuar.
          if (!accionCambiarEstado || !accionMoverCama) {
            Swal.showValidationMessage("No se pudo leer la accion seleccionada.");
            return false;
          }

          // Rama A: mantener la cama actual y solo cambiar su estado.
          if (accionCambiarEstado.checked) {
            var estadoEl = document.getElementById("modal-mapa-estado");
            if (!estadoEl || !estadoEl.value) {
              Swal.showValidationMessage("Debe seleccionar el nuevo estado.");
              return false;
            }
            return { tipo: "cambiar_estado", estado: estadoEl.value };
          } else {
            // Rama B: mover el paciente actual a una cama destino.
            var camaDestinoEl = document.getElementById("modal-cama-destino");
            if (!camaDestinoEl || !camaDestinoEl.value) {
              Swal.showValidationMessage("Debe seleccionar la cama destino.");
              return false;
            }
            return { tipo: "mover_cama", cama_destino_id: camaDestinoEl.value };
          }
        } else {
          // Cama VACIA: se permite cambiar estado y opcionalmente asignar paciente.
          // Regla clave: si termina en OCUPADA, paciente es obligatorio.
          var estadoEl = document.getElementById("modal-mapa-estado");
          var estado = estadoEl ? estadoEl.value : "";
          var pacienteSelectEl = document.getElementById("modal-mapa-paciente");
          var pacienteId = pacienteSelectEl ? (pacienteSelectEl.value || "") : "";
          if (estado === "OCUPADA" && !pacienteId) {
            Swal.showValidationMessage("Para estado OCUPADA debe seleccionar un paciente.");
            return false;
          }
          return { tipo: "cambiar_estado", estado: estado, paciente_id: pacienteId };
        }
      },
      didOpen: function () {
        // Ajuste visual de botones para que use el estilo compacto del sistema.
        var actionsContainer = document.querySelector(".swal2-actions");
        if (actionsContainer) {
          actionsContainer.classList.add("contener-modal-contenedor-botones-min");
        }

        if (esOcupada) {
          // Rellenar datos de solo lectura del paciente actual
          var inputNombre = document.getElementById("modal-pac-nombre");
          var inputDni = document.getElementById("modal-pac-dni");
          if (inputNombre) { inputNombre.value = pacienteActual; }
          if (inputDni) { inputDni.value = dniActual; }

          // Alternar bloques segun la accion seleccionada con checks exclusivos.
          // - cambiar_estado => muestra selector de estado
          // - mover_cama => muestra buscador + selector de cama destino
          var bloqueCambiarEstado = document.getElementById("bloque-cambiar-estado");
          var bloqueMoverCama = document.getElementById("bloque-mover-cama");
          var accionCambiarEstado = document.getElementById("modal-accion-cambiar-estado");
          var accionMoverCama = document.getElementById("modal-accion-mover-cama");

          function sincronizarAccion(origen) {
            // Los dos checks se comportan como seleccion exclusiva.
            if (origen === "cambiar_estado") {
              accionCambiarEstado.checked = true;
              accionMoverCama.checked = false;
              bloqueCambiarEstado.style.display = "";
              bloqueMoverCama.style.display = "none";
              return;
            }
            accionCambiarEstado.checked = false;
            accionMoverCama.checked = true;
            bloqueCambiarEstado.style.display = "none";
            bloqueMoverCama.style.display = "";
          }

          accionCambiarEstado.addEventListener("change", function () {
            sincronizarAccion(accionCambiarEstado.checked ? "cambiar_estado" : "mover_cama");
          });

          accionMoverCama.addEventListener("change", function () {
            sincronizarAccion(accionMoverCama.checked ? "mover_cama" : "cambiar_estado");
          });

          sincronizarAccion("cambiar_estado");

          // Cargar camas disponibles; excluir la cama actual del listado
          var selectCamaDestino = document.getElementById("modal-cama-destino");
          var tipoBusquedaCama = document.getElementById("modal-tipo-busqueda-cama");
          var todasCamasDisponibles = [];
          var tomCamaDestino = null;

          function obtenerCampoBusquedaCama() {
            var tipo = tipoBusquedaCama ? tipoBusquedaCama.value : "numero";
            if (tipo === "numero") {
              return ["numero", "text"];
            }
            if (tipo === "sala") {
              return ["sala", "text"];
            }
            if (tipo === "servicio") {
              return ["servicio", "text"];
            }
            if (tipo === "cubiculo") {
              return ["cubiculo", "text"];
            }
            return ["text"];
          }

          fetch(API_URLS.camasDisponibles + "?excluir=" + encodeURIComponent(numeroCama))
            .then(function (r) { return r.ok ? r.json() : Promise.reject("Error al cargar camas."); })
            .then(function (data) {
              // Cache local para filtrar en memoria sin pegar al backend por tecla.
              todasCamasDisponibles = data.results || [];
              if (selectCamaDestino && window.TomSelect) {
                tomCamaDestino = new TomSelect(selectCamaDestino, {
                  valueField: "id",
                  labelField: "text",
                  searchField: obtenerCampoBusquedaCama(),
                  placeholder: "Buscar cama disponible...",
                  options: mapCamasTomSelect(todasCamasDisponibles)
                });
              } else {
                renderCamaDestinoSelect(todasCamasDisponibles, selectCamaDestino);
              }
            })
            .catch(function () {
              selectCamaDestino.innerHTML = '<option value="">Error al cargar camas disponibles</option>';
            });

          if (tipoBusquedaCama) {
            tipoBusquedaCama.addEventListener("change", function () {
              if (tomCamaDestino) {
                tomCamaDestino.settings.searchField = obtenerCampoBusquedaCama();
                tomCamaDestino.clear(true);
                tomCamaDestino.clearTextbox();
                tomCamaDestino.refreshOptions(false);
              }
            });
          }

        } else {
          // Cama VACIA (u otro estado sin paciente): mostrar/ocultar busqueda de paciente
          var estadoSelect = document.getElementById("modal-mapa-estado");
          var tipoBusquedaPaciente = document.getElementById("modal-tipo-busqueda-paciente");
          var bloquePaciente = document.getElementById("bloque-asignar-paciente");
          var selectPaciente = document.getElementById("modal-mapa-paciente");
          var tomPaciente = null;

          function limpiarSeleccionPaciente() {
            if (tomPaciente) {
              tomPaciente.clear(true);
              tomPaciente.clearOptions();
              tomPaciente.addOption({ id: "", text: "-- Seleccionar paciente --" });
              tomPaciente.refreshOptions(false);
            } else if (selectPaciente) {
              selectPaciente.innerHTML = '<option value="">-- Seleccionar paciente --</option>';
              selectPaciente.value = "";
            }
          }

          function cargarPacientesFallback(query) {
            var tipo = (tipoBusquedaPaciente && tipoBusquedaPaciente.value) ? tipoBusquedaPaciente.value : "nombre";
            var params = [];
            if (query) {
              params.push("q=" + encodeURIComponent(query));
            }
            params.push("tipo=" + encodeURIComponent(tipo));
            var queryString = params.length ? ("?" + params.join("&")) : "";

            fetch(API_URLS.buscarPacientes + queryString)
              .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
              .then(function (data) {
                var items = mapPacientesTomSelect(data.results || []);
                selectPaciente.innerHTML = '<option value="">-- Seleccionar paciente --</option>';
                items.forEach(function (item) {
                  var option = document.createElement("option");
                  option.value = item.id;
                  option.textContent = item.text;
                  selectPaciente.appendChild(option);
                });
              })
              .catch(function () {
                selectPaciente.innerHTML = '<option value="">Sin resultados</option>';
              });
          }

          if (selectPaciente && window.TomSelect) {
            tomPaciente = new TomSelect(selectPaciente, {
              valueField: "id",
              labelField: "text",
              searchField: "text",
              placeholder: "Buscar paciente...",
              preload: false,
              load: function (query, callback) {
                var tipo = (tipoBusquedaPaciente && tipoBusquedaPaciente.value) ? tipoBusquedaPaciente.value : "nombre";
                var params = [];
                if (query) {
                  params.push("q=" + encodeURIComponent(query));
                }
                params.push("tipo=" + encodeURIComponent(tipo));
                var queryString = params.length ? ("?" + params.join("&")) : "";

                fetch(API_URLS.buscarPacientes + queryString)
                  .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
                  .then(function (data) { callback(mapPacientesTomSelect(data.results || [])); })
                  .catch(function () { callback([]); });
              }
            });
          }

          estadoSelect.addEventListener("change", function () {
            if (estadoSelect.value === "OCUPADA") {
              // Solo en OCUPADA se habilita la asignacion de paciente.
              bloquePaciente.style.display = "";
            } else {
              // Si cambia a un estado no-ocupado, se limpia seleccion previa.
              bloquePaciente.style.display = "none";
              limpiarSeleccionPaciente();
            }
          });

          if (tipoBusquedaPaciente) {
            tipoBusquedaPaciente.addEventListener("change", function () {
              limpiarSeleccionPaciente();
              if (!tomPaciente) {
                cargarPacientesFallback("");
              }
            });
          }
        }
      }
    });

    if (!modal.isConfirmed || !modal.value) {
      // El usuario cancelo o cerro el modal sin confirmar.
      return;
    }

    try {
      if (modal.value.tipo === "mover_cama") {
        // Flujo 1: mover paciente entre camas.
        // Envia cama origen + cama destino y el backend resuelve la transaccion.
        var payloadMover = new FormData();
        payloadMover.append("cama_origen_id", numeroCama);
        payloadMover.append("cama_destino_id", modal.value.cama_destino_id);

        var responseMover = await fetch(API_URLS.moverPaciente, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN },
          body: payloadMover
        });
        var dataMover = await responseMover.json();
        if (!responseMover.ok || !dataMover.ok) {
          throw new Error(dataMover.error || "No se pudo mover al paciente.");
        }

        // Actualizar la card de la cama origen (queda VACIA)
        actualizarCardDesdeRespuesta(camaEl, dataMover.cama_origen);
        if (sesionMapeoActivaId) {
          marcarCamaComoMapeada(camaEl);
        }

        // Actualizar la card de la cama destino (queda OCUPADA con el paciente)
        var camaDestinoCard = camasRenderizadas.find(function (el) {
          return el.dataset.numeroCama === String(dataMover.cama_destino.numero_cama);
        });
        if (camaDestinoCard) {
          actualizarCardDesdeRespuesta(camaDestinoCard, dataMover.cama_destino);
          if (sesionMapeoActivaId) {
            marcarCamaComoMapeada(camaDestinoCard);
          }
        }

        // Reaplica filtro actual para mantener coherencia visual tras el cambio.
        aplicarFiltro();
        toastr.success(dataMover.mensaje || "Paciente movido correctamente.", "Exito");

      } else {
        // Flujo 2: actualizar estado de la cama actual
        // (y paciente, solo si el estado seleccionado es OCUPADA).
        var payload = new FormData();
        payload.append("cama_id", numeroCama);
        payload.append("estado", modal.value.estado);
        if (modal.value.paciente_id) {
          payload.append("paciente_id", modal.value.paciente_id);
        }

        var response = await fetch(API_URLS.actualizarCama, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN },
          body: payload
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo actualizar la cama.");
        }

        actualizarCardDesdeRespuesta(camaEl, data.cama);
        if (sesionMapeoActivaId) {
          marcarCamaComoMapeada(camaEl);
        }
        // Reaplica filtro actual para mantener coherencia visual tras el cambio.
        aplicarFiltro();
        toastr.success(data.mensaje || "Cama actualizada.", "Exito");
      }

    } catch (error) {
      // Unifica manejo de errores de red y de validaciones devueltas por backend.
      toastr.error(error.message || "Error al guardar.", "Error");
    }
  }

  // Pinta toda la jerarquia recibida desde backend: servicio > sala > cubiculo > cama.
  function renderMapa(servicios) {
    contenedor.innerHTML = "";
    camasRenderizadas = [];

    if (!servicios.length) {
      contenedor.innerHTML = '<p class="mapa-vacio">No hay servicios activos para mostrar.</p>';
      return;
    }

    servicios.forEach(function (servicio) {
      var cardServicio = document.createElement("section");
      cardServicio.className = "mapa-servicio-card";

      var tituloServicio = document.createElement("h3");
      tituloServicio.className = "mapa-servicio-titulo";
      tituloServicio.textContent = servicio.nombre + " (" + (servicio.nombre_corto || "NA") + ")";
      cardServicio.appendChild(tituloServicio);

      if (!servicio.salas.length) {
        var sinSalas = document.createElement("p");
        sinSalas.className = "mapa-vacio";
        sinSalas.textContent = "Sin salas activas.";
        cardServicio.appendChild(sinSalas);
      }

      servicio.salas.forEach(function (sala) {
        var bloqueSala = document.createElement("div");
        bloqueSala.className = "mapa-sala";

        var tituloSala = document.createElement("h4");
        tituloSala.className = "mapa-sala-titulo";
        tituloSala.textContent = sala.nombre;
        bloqueSala.appendChild(tituloSala);

        function crearCamaCard(cama, nombreCubiculo) {
          // Cada card guarda metadata en dataset para filtro, modal y actualizaciones.
          var camaEl = document.createElement("div");
          camaEl.className = "mapa-cama " + claseEstado(cama.estado_visual);
          camaEl.style.cursor = "pointer";

          camaEl.dataset.numeroCama = String(cama.numero_cama || "");
          camaEl.dataset.paciente = cama.paciente ? cama.paciente.nombre : "";
          camaEl.dataset.pacienteId = cama.paciente ? String(cama.paciente.id) : "";
          camaEl.dataset.pacienteDni = cama.paciente ? (cama.paciente.dni || "") : "";
          camaEl.dataset.estado = cama.estado_visual || "";
          camaEl.dataset.sala = sala.nombre || "";
          camaEl.dataset.servicio = servicio.nombre || "";
          camaEl.dataset.cubiculo = nombreCubiculo || "";
          camaEl.dataset.cambiosRealizados = String(cama.cambios_realizados || 0);
          camaEl.dataset.maxCambios = String(cama.max_cambios || 5);

          var numero = document.createElement("span");
          numero.className = "mapa-cama-numero";
          numero.textContent = "Cama " + cama.numero_cama;

          var estado = document.createElement("span");
          estado.className = "mapa-cama-estado";
          estado.textContent = cama.estado_visual;

          var paciente = document.createElement("span");
          paciente.className = "mapa-cama-paciente";
          paciente.textContent = cama.paciente ? cama.paciente.nombre : "Sin paciente";

          var dni = document.createElement("span");
          dni.className = "mapa-cama-dni";
          dni.textContent = cama.paciente && cama.paciente.dni ? cama.paciente.dni : "";

          camaEl.appendChild(numero);
          camaEl.appendChild(estado);
          camaEl.appendChild(paciente);
          camaEl.appendChild(dni);
          camaEl.addEventListener("click", function () {
            abrirModalEdicionCama(camaEl);
          });
          camasRenderizadas.push(camaEl);
          return camaEl;
        }

        if (sala.cubiculos.length) {
          sala.cubiculos.forEach(function (cubiculo) {
            var bloqueCubiculo = document.createElement("div");
            bloqueCubiculo.className = "mapa-cubiculo";

            var tituloCubiculo = document.createElement("h5");
            tituloCubiculo.className = "mapa-cubiculo-titulo";
            tituloCubiculo.textContent = "Cubiculo " + cubiculo.numero + " - " + cubiculo.nombre;
            bloqueCubiculo.appendChild(tituloCubiculo);

            var gridCubiculo = document.createElement("div");
            gridCubiculo.className = "mapa-camas-grid";

            cubiculo.camas.forEach(function (cama) {
              gridCubiculo.appendChild(crearCamaCard(cama, cubiculo.nombre));
            });

            bloqueCubiculo.appendChild(gridCubiculo);
            bloqueSala.appendChild(bloqueCubiculo);
          });
        }

        if (sala.camas_directas.length) {
          var tituloDirectas = document.createElement("h5");
          tituloDirectas.className = "mapa-cubiculo-titulo";
          tituloDirectas.textContent = "Camas directas de sala";
          bloqueSala.appendChild(tituloDirectas);

          var gridDirectas = document.createElement("div");
          gridDirectas.className = "mapa-camas-grid";

          sala.camas_directas.forEach(function (cama) {
            gridDirectas.appendChild(crearCamaCard(cama, "SIN_CUBICULO"));
          });

          bloqueSala.appendChild(gridDirectas);
        }

        cardServicio.appendChild(bloqueSala);
      });

      contenedor.appendChild(cardServicio);
    });

    // Reaplicar marca visual de camas ya mapeadas cuando se vuelve a renderizar.
    aplicarMarcasSesionEnRender();
  }

  // Carga inicial del mapa y manejo de errores de red/servidor.
  function cargarMapa() {
    fetch(API_URLS.mapa)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("No se pudo cargar la informacion del mapa.");
        }
        return response.json();
      })
      .then(function (data) {
        renderMapa(data.servicios || []);
      })
      .catch(function () {
        contenedor.innerHTML = '<p class="mapa-vacio">Error cargando mapa de camas.</p>';
      });
  }

  inputBusqueda.addEventListener("input", aplicarFiltro);
  tipoBusqueda.addEventListener("change", aplicarFiltro);

  // Limpia filtros y devuelve foco al input de busqueda.
  btnLimpiar.addEventListener("click", function () {
    inputBusqueda.value = "";
    tipoBusqueda.value = "todo";
    aplicarFiltro();
    inputBusqueda.focus();
  });

  btnCopiar.addEventListener("click", function () {
    // Copia solo las camas actualmente visibles (respeta filtros activos).
    var filas = [];
    camasRenderizadas.forEach(function (item) {
      if (item.style.display === "none") {
        return;
      }
      filas.push(
        "Cama " + (item.dataset.numeroCama || "") +
        " | Estado: " + (item.dataset.estado || "") +
        " | Paciente: " + (item.dataset.paciente || "Sin paciente") +
        " | Sala: " + (item.dataset.sala || "") +
        " | Servicio: " + (item.dataset.servicio || "")
      );
    });

    var contenido = filas.join("\n") || "Sin resultados visibles.";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(contenido);
    }
  });

  btnImprimir.addEventListener("click", function () {
    window.print();
  });

  if (btnIniciarMapeo) {
    btnIniciarMapeo.addEventListener("click", async function () {
      try {
        var response = await fetch(API_URLS.iniciarMapeo, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN }
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo iniciar el mapeo.");
        }

        sesionMapeoActivaId = data.sesion_id || null;
        camasMapeadasSesion = new Set((data.camas_mapeadas || []).map(function (v) {
          return String(v);
        }));
        establecerModoMapeoActivo(Boolean(sesionMapeoActivaId));
        aplicarMarcasSesionEnRender();
        toastr.success(data.mensaje || "Mapeo iniciado.", "Exito");
      } catch (error) {
        toastr.error(error.message || "Error al iniciar mapeo.", "Error");
      }
    });
  }

  if (btnTerminarMapeo) {
    btnTerminarMapeo.addEventListener("click", async function () {
      try {
        var response = await fetch(API_URLS.terminarMapeo, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN }
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo terminar el mapeo.");
        }

        sesionMapeoActivaId = null;
        establecerModoMapeoActivo(false);
        limpiarMarcasMapeo();
        toastr.success(data.mensaje || "Mapeo finalizado.", "Exito");
      } catch (error) {
        toastr.error(error.message || "Error al terminar mapeo.", "Error");
      }
    });
  }

  if (btnCancelarMapeo) {
    btnCancelarMapeo.addEventListener("click", async function () {
      try {
        var response = await fetch(API_URLS.cancelarMapeo, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN }
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo cancelar el mapeo.");
        }

        sesionMapeoActivaId = null;
        establecerModoMapeoActivo(false);
        limpiarMarcasMapeo();
        toastr.success(data.mensaje || "Mapeo cancelado.", "Exito");
      } catch (error) {
        toastr.error(error.message || "Error al cancelar mapeo.", "Error");
      }
    });
  }

  establecerModoMapeoActivo(false);

  // Arranque inicial del modulo.
  cargarMapa();
  cargarEstadoSesionMapeo();
});
