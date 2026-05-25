document.addEventListener("DOMContentLoaded", function () {
  // ========================================================================
  // Configuracion general y referencias DOM
  // ========================================================================

  // Endpoints usados por el mapa para cargar datos, buscar y guardar cambios.
  var API_URLS = {
    estadoMapeo: "/mapeo-camas/api/estado-mapeo/",
    iniciarMapeo: "/mapeo-camas/api/iniciar-mapeo/",
    terminarMapeo: "/mapeo-camas/api/terminar-mapeo/",
    cancelarMapeo: "/mapeo-camas/api/cancelar-mapeo/",
    sincronizarCamas: "/mapeo-camas/api/sincronizar-camas/",
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
    "PRE_ALTA",
    "FUERA_SERVICIO",
    "CONSULTA_EXTERNA"
  ];

  var contenedor = document.getElementById("mapa-servicios");
  var contenedorIndicadores = document.getElementById("mapa-indicadores");
  var contenedorIndicadoresSala = document.getElementById("mapa-indicadores-sala");
  var filtroEstadoMovil = document.getElementById("mapa-filtro-estado-movil");
  var filtroSalaMovil = document.getElementById("mapa-filtro-sala-movil");
  var inputBusqueda = document.getElementById("mapa-busqueda");
  var tipoBusqueda = document.getElementById("mapa-tipo-busqueda");
  var btnLimpiar = document.getElementById("btn-limpiar-busqueda");
  var btnCopiar = document.getElementById("btn-copiar-camas");
  var btnImprimir = document.getElementById("btn-imprimir-camas");
  var btnHistoriales = document.getElementById("btn-historiales-camas");
  var btnSincronizarCamas = document.getElementById("btn-sincronizar-camas");
  var btnIniciarMapeo = document.getElementById("btn-iniciar-mapeo");
  var btnCancelarMapeo = document.getElementById("btn-cancelar-mapeo");
  // [2026-05-20 OPT] Remover btnTerminarMapeoPie; usar selector unificado con data-action="terminar-mapeo"
  // [2026-05-04 FEATURE] Banner pegajoso de mapeo activo (amarillo con pulso)
  var mapaBannerMapeo = document.getElementById("mapa-banner-mapeo");
  var camasRenderizadas = [];
  var serviciosDisponiblesMapeo = [];
  var sesionMapeoActivaId = null;
  var serviciosSesionActivaIds = [];
  var camasMapeadasSesion = new Set();
  var filtroEstadoIndicador = "";
  var filtroSalaIndicador = "";

  var ESTADOS_INDICADORES = [
    { id: "VACIA", etiqueta: "Vacias", icono: "bi bi-door-open-fill" },
    { id: "OCUPADA", etiqueta: "Ocupadas", icono: "bi bi-person-fill" },
    { id: "PRE_ALTA", etiqueta: "Pre alta", icono: "bi bi-hourglass-split" },
    { id: "FUERA_SERVICIO", etiqueta: "Fuera de servicio", icono: "bi bi-tools" },
    { id: "CONSULTA_EXTERNA", etiqueta: "Consulta externa", icono: "bi bi-clipboard2-pulse-fill" }
  ];

  // Constantes de interaccion
  var CLICK_DELAY_MS = 300;  // ms para distinguir simple vs doble clic
  var LONG_PRESS_MS  = 600;  // ms para activar confirmacion por pulsacion larga (tactil)

  // [2026-05-20 OPT] Controla visibilidad de botones según exista o no sesión activa de mapeo.
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

    var tituloPrincipal = document.getElementById("mapa-titulo-principal");
    if (tituloPrincipal) {
      tituloPrincipal.textContent = activo ? "Mapeo de camas en Proceso" : "Mapa de Camas";
    }

    ocultar(btnIniciarMapeo, activo);
    ocultar(btnCopiar, activo);
    ocultar(btnImprimir, activo);
    ocultar(btnHistoriales, activo);
    
    // [2026-05-20 OPT] Consolida btnTerminarMapeo y btnTerminarMapeoPie en selector unificado
    document.querySelectorAll('[data-action="terminar-mapeo"]').forEach(function(btn) {
      ocultar(btn, !activo);
    });
    ocultar(btnCancelarMapeo, !activo);

    // [2026-05-20 OPT] Mostrar/ocultar banner pegajoso según modo mapeo activo.
    if (mapaBannerMapeo) {
      mapaBannerMapeo.style.display = activo ? "flex" : "none";
    }
  }

  async function confirmarCamaSinCambios(camaEl) {
    if (!camaEl || !sesionMapeoActivaId) {
      return;
    }

    var numeroCama = camaEl.dataset.numeroCama || "";
    if (!numeroCama) {
      return;
    }

    var payload = new FormData();
    payload.append("cama_id", numeroCama);
    payload.append("accion", "CONFIRMAR");
    payload.append("sesion_mapeo_id", String(sesionMapeoActivaId));

    var boton = camaEl.querySelector(".mapa-cama-accion-rapida");
    if (boton) {
      boton.disabled = true;
    }

    try {
      var response = await fetch(API_URLS.procesarCamaMapeo, {
        method: "POST",
        headers: { "X-CSRFToken": window.CSRF_TOKEN },
        body: payload,
      });
      var data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "No se pudo confirmar la cama.");
      }

      marcarCamaComoMapeada(camaEl);
      toastr.success(data.mensaje || "Cama confirmada sin cambios.", "Exito");
    } catch (error) {
      toastr.error(error.message || "Error al confirmar cama.", "Error");
    } finally {
      if (boton) {
        boton.disabled = false;
      }
    }
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

  function construirOpcionesServiciosMapeo() {
    return serviciosDisponiblesMapeo.map(function (servicio) {
      return (
        '<label class="ck-formulario modal-mapeo-servicios__item">' +
          '<input type="checkbox" class="ck-formulario__checkbox modal-mapeo-servicios__checkbox" name="mapeo-servicio" value="' + escaparHtml(servicio.id) + '">' +
          '<div class="ck-formulario__base"><div class="ck-formulario__bolita"></div></div>' +
          '<span class="ck-formulario__label modal-mapeo-servicios__texto-item">' +
            '<span class="modal-mapeo-servicios__nombre">' + escaparHtml(servicio.nombre) + '</span>' +
            '<span class="modal-mapeo-servicios__codigo">Codigo: ' + escaparHtml(servicio.nombre_corto || "NA") + '</span>' +
          '</span>' +
        '</label>'
      );
    }).join("");
  }

  function obtenerServiciosSeleccionadosMapeo() {
    return Array.from(document.querySelectorAll('input[name="mapeo-servicio"]:checked')).map(function (item) {
      return Number(item.value);
    }).filter(function (value) {
      return !isNaN(value);
    });
  }

  function actualizarResumenServiciosMapeo() {
    var resumen = document.getElementById("modal-servicios-resumen");
    if (!resumen) {
      return;
    }
    var seleccionados = obtenerServiciosSeleccionadosMapeo().length;
    var total = serviciosDisponiblesMapeo.length;
    resumen.textContent = seleccionados
      ? "Servicios seleccionados: " + seleccionados + " de " + total
      : "Selecciona al menos un servicio para iniciar la sesion.";
  }

  async function abrirModalSeleccionServiciosMapeo() {
    var htmlServicios =
      '<div class="modal-mapeo-servicios">' +
        '<div class="modal-mapeo-servicios__intro">' +
          '<p class="modal-mapeo-servicios__texto">[2026-05-07] Selecciona los servicios que se incluiran en esta sesion de mapeo.</p>' +
          '<p class="modal-mapeo-servicios__resumen" id="modal-servicios-resumen"></p>' +
        '</div>' +
        '<fieldset class="modalAtencionCampos">' +
          '<legend>Servicios incluidos</legend>' +
          '<div class="modal-mapeo-servicios__lista">' +
            construirOpcionesServiciosMapeo() +
          '</div>' +
        '</fieldset>' +
      '</div>';

    return Swal.fire({
      title: "Iniciar mapeo",
      html: htmlServicios,
      showCancelButton: true,
      showCloseButton: true,
      confirmButtonText: 'Iniciar',
      cancelButtonText: 'Cancelar',
      focusConfirm: false,
      customClass: {
        popup: "contener-modal-defuncion",
        title: "contener-modal-titulo",
        content: "contener-modal-contenido",
        confirmButton: "contener-modal-boton-confirmar",
        cancelButton: "contener-modal-boton-cancelar"
      },
      preConfirm: function () {
        var serviciosSeleccionados = obtenerServiciosSeleccionadosMapeo();
        if (!serviciosSeleccionados.length) {
          Swal.showValidationMessage("Debes seleccionar al menos un servicio.");
          return false;
        }
        return { servicio_ids: serviciosSeleccionados };
      },
      didOpen: function () {
        var actionsContainer = document.querySelector(".swal2-actions");
        if (actionsContainer) {
          actionsContainer.classList.add("contener-modal-contenedor-botones-min");
        }

        var checks = Array.from(document.querySelectorAll('input[name="mapeo-servicio"]'));

        checks.forEach(function (check) {
          check.addEventListener("change", actualizarResumenServiciosMapeo);
        });

        actualizarResumenServiciosMapeo();
      }
    });
  }

  // Reaplica marca visual usando el Set en memoria luego de recargar el mapa.
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
    // Consulta backend para recuperar sesion en progreso y restaurar estado de UI.
  async function cargarEstadoSesionMapeo() {
    try {
      var response = await fetch(API_URLS.estadoMapeo);
      var data = await response.json();
      if (!response.ok || !data.ok) {
        return;
      }

      if (data.sesion_activa && data.sesion_activa.id) {
        sesionMapeoActivaId = data.sesion_activa.id;
        serviciosSesionActivaIds = data.servicio_ids || [];
        establecerModoMapeoActivo(true);
      } else {
        sesionMapeoActivaId = null;
        serviciosSesionActivaIds = [];
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
    if (estadoVisual === "PRE_ALTA" || estadoVisual === "ALTA") {
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
      item.dataset.usuarioUltimaActualizacion || "",
    ].join(" ").toLowerCase();
  }

  function formatearFechaHoraCorta(valor) {
    if (!valor) {
      return "Sin registro";
    }
    var fecha = new Date(valor);
    if (isNaN(fecha.getTime())) {
      return "Sin registro";
    }

    var dd = String(fecha.getDate()).padStart(2, "0");
    var mm = String(fecha.getMonth() + 1).padStart(2, "0");
    var yyyy = String(fecha.getFullYear());
    var hh = String(fecha.getHours()).padStart(2, "0");
    var min = String(fecha.getMinutes()).padStart(2, "0");
    return dd + "/" + mm + "/" + yyyy + " " + hh + ":" + min;
  }

  function escaparHtml(valor) {
    return String(valor || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizarEstadoIndicador(estado) {
    // [2026-05-25] Fallback unificado: sin estado explicito se considera VACIA.
    var valor = String(estado || "VACIA").trim().toUpperCase();
    if (!valor) {
      return "VACIA";
    }
    if (valor === "ALTA") {
      return "PRE_ALTA";
    }
    return valor;
  }

  function estadoCoincideIndicador(estado, filtroEstado) {
    if (!filtroEstado) {
      return true;
    }
    return normalizarEstadoIndicador(estado) === filtroEstado;
  }

  // [2026-05-21] El resumen de estados debe respetar el filtro secundario del mapa.
  function obtenerCamasBaseResumenEstados() {
    return camasRenderizadas.filter(function (camaEl) {
      return !filtroSalaIndicador || String(camaEl.dataset.sala || "").trim() === filtroSalaIndicador;
    });
  }

  function resumenEstadosCamas() {
    var camasBase = obtenerCamasBaseResumenEstados();
    var resumen = { TOTAL: camasBase.length };
    camasBase.forEach(function (camaEl) {
      var clave = normalizarEstadoIndicador(camaEl.dataset.estado);
      resumen[clave] = (resumen[clave] || 0) + 1;
    });
    return resumen;
  }

  function actualizarEstadoActivoIndicadores() {
    if (!contenedorIndicadores) {
      return;
    }
    Array.from(contenedorIndicadores.querySelectorAll(".mapa-indicador")).forEach(function (btn) {
      var estadoId = btn.dataset.estadoId || "";
      var activo = estadoId === filtroEstadoIndicador || (!filtroEstadoIndicador && estadoId === "TODAS");
      btn.classList.toggle("mapa-indicador--activo", activo);
      btn.setAttribute("aria-pressed", activo ? "true" : "false");
    });
  }

  function _porcentaje(cantidad, total) {
    if (!total) {
      return "0%";
    }
    return Math.round((cantidad / total) * 100) + "%";
  }

  function _htmlCantidad(cantidad, total) {
    var pct = _porcentaje(cantidad, total);
    return (
      '<span class="mapa-indicador__cantidad">' + String(cantidad) + '</span>' +
      '<span class="mapa-indicador__pct">' + pct + '</span>'
    );
  }

  function resumenSalasCamas() {
    var resumen = { TOTAL: camasRenderizadas.length };
    camasRenderizadas.forEach(function (camaEl) {
      var clave = String(camaEl.dataset.sala || "OTROS").trim() || "OTROS";
      resumen[clave] = (resumen[clave] || 0) + 1;
    });
    return resumen;
  }

  function actualizarEstadoActivoIndicadoresSala() {
    if (!contenedorIndicadoresSala) {
      return;
    }
    Array.from(contenedorIndicadoresSala.querySelectorAll(".mapa-indicador")).forEach(function (btn) {
      var salaId = btn.dataset.salaId || "";
      var activo = salaId === filtroSalaIndicador || (!filtroSalaIndicador && salaId === "TODAS");
      btn.classList.toggle("mapa-indicador--activo", activo);
      btn.setAttribute("aria-pressed", activo ? "true" : "false");
    });
  }

  function sincronizarFiltrosMoviles() {
    if (filtroEstadoMovil) {
      var valorEstado = filtroEstadoIndicador || "TODAS";
      filtroEstadoMovil.value = valorEstado;
    }
    if (filtroSalaMovil) {
      var valorSala = filtroSalaIndicador || "TODAS";
      var opcionExiste = Array.from(filtroSalaMovil.options || []).some(function (opt) {
        return opt.value === valorSala;
      });
      filtroSalaMovil.value = opcionExiste ? valorSala : "TODAS";
    }
  }

  function actualizarSelectEstadoMovil() {
    if (!filtroEstadoMovil) {
      return;
    }
    var resumen = resumenEstadosCamas();
    var etiquetasBase = {};
    ESTADOS_INDICADORES.forEach(function (item) {
      etiquetasBase[item.id] = item.etiqueta;
    });

    var estados = Object.keys(resumen)
      .filter(function (clave) { return clave !== "TOTAL"; })
      .sort(function (a, b) {
        var ca = resumen[a] || 0;
        var cb = resumen[b] || 0;
        return cb - ca;
      });

    var html = ['<option value="TODAS">Todos los estados</option>'];
    estados.forEach(function (estadoId) {
      var etiqueta = etiquetasBase[estadoId] || estadoId;
      html.push('<option value="' + escaparHtml(estadoId) + '">' + escaparHtml(etiqueta) + '</option>');
    });
    filtroEstadoMovil.innerHTML = html.join("");
    sincronizarFiltrosMoviles();
  }

  function actualizarSelectSalaMovil() {
    if (!filtroSalaMovil) {
      return;
    }

    var resumen = resumenSalasCamas();
    var salas = Object.keys(resumen)
      .filter(function (clave) { return clave !== "TOTAL"; })
      .sort(function (a, b) { return a.localeCompare(b, "es", { sensitivity: "base" }); });

    var html = ['<option value="TODAS">Todas las salas</option>'];
    salas.forEach(function (sala) {
      html.push('<option value="' + escaparHtml(sala) + '">' + escaparHtml(sala) + '</option>');
    });
    filtroSalaMovil.innerHTML = html.join("");
    sincronizarFiltrosMoviles();
  }

  function renderIndicadoresEstado() {
    if (!contenedorIndicadores) {
      return;
    }

    var resumen = resumenEstadosCamas();
    var total = resumen.TOTAL || 0;
    var catalogo = {};
    ESTADOS_INDICADORES.forEach(function (item) {
      catalogo[item.id] = item;
    });

    // Construir lista de estados (conocidos + extras) y ordenar por cantidad desc
    var listaEstados = ESTADOS_INDICADORES.map(function (item) {
      return {
        id: item.id,
        etiqueta: item.etiqueta,
        icono: item.icono,
        cantidad: resumen[item.id] || 0,
        claseExtra: "mapa-indicador--" + item.id.toLowerCase().replace(/_/g, "-")
      };
    });

    Object.keys(resumen).forEach(function (estadoId) {
      if (estadoId === "TOTAL" || catalogo[estadoId]) {
        return;
      }
      listaEstados.push({
        id: estadoId,
        etiqueta: estadoId,
        icono: "bi bi-tag-fill",
        cantidad: resumen[estadoId] || 0,
        claseExtra: ""
      });
    });

    // [2026-05-08] Ordenar por cantidad descendente
    listaEstados.sort(function (a, b) { return b.cantidad - a.cantidad; });

    var html = [
      '<button type="button" class="mapa-indicador" data-estado-id="TODAS" aria-pressed="false">' +
        '<span class="mapa-indicador__estado"><i class="bi bi-grid-3x3-gap-fill"></i> Todas</span>' +
        _htmlCantidad(total, total) +
      '</button>'
    ];

    listaEstados.forEach(function (item) {
      html.push(
        '<button type="button" class="mapa-indicador ' + item.claseExtra + '" data-estado-id="' + escaparHtml(item.id) + '" aria-pressed="false">' +
          '<span class="mapa-indicador__estado"><i class="' + item.icono + '"></i> ' + escaparHtml(item.etiqueta) + '</span>' +
          _htmlCantidad(item.cantidad, total) +
        '</button>'
      );
    });

    contenedorIndicadores.innerHTML = html.join("");
    actualizarEstadoActivoIndicadores();
    actualizarSelectEstadoMovil();
  }

  function renderIndicadoresSala() {
    if (!contenedorIndicadoresSala) {
      return;
    }

    var resumen = resumenSalasCamas();
    var total = resumen.TOTAL || 0;
    var listaSalas = Object.keys(resumen)
      .filter(function (clave) { return clave !== "TOTAL"; })
      .map(function (clave) {
        return { id: clave, etiqueta: clave, cantidad: resumen[clave] || 0 };
      });

    listaSalas.sort(function (a, b) { return b.cantidad - a.cantidad; });

    var html = [
      '<button type="button" class="mapa-indicador" data-sala-id="TODAS" aria-pressed="false">' +
        '<span class="mapa-indicador__estado"><i class="bi bi-diagram-3-fill"></i> Todas las salas</span>' +
        _htmlCantidad(total, total) +
      '</button>'
    ];

    listaSalas.forEach(function (item) {
      html.push(
        '<button type="button" class="mapa-indicador" data-sala-id="' + escaparHtml(item.id) + '" aria-pressed="false">' +
          '<span class="mapa-indicador__estado"><i class="bi bi-building"></i> ' + escaparHtml(item.etiqueta) + '</span>' +
          _htmlCantidad(item.cantidad, total) +
        '</button>'
      );
    });

    contenedorIndicadoresSala.innerHTML = html.join("");
    actualizarEstadoActivoIndicadoresSala();
    actualizarSelectSalaMovil();
  }

  // Filtra las cards renderizadas segun tipo de busqueda y texto escrito.
  function aplicarFiltro() {
    var valor = (inputBusqueda.value || "").trim().toLowerCase();
    var tipo = tipoBusqueda.value || "todo";

    camasRenderizadas.forEach(function (item) {
      var coincideBusqueda = true;
      if (valor) {
        var campo = "";
        if (tipo === "cama") {
          campo = item.dataset.numeroCama || "";
        } else if (tipo === "dni") {
          campo = item.dataset.pacienteDni || "";
        } else if (tipo === "paciente") {
          campo = item.dataset.paciente || "";
        } else if (tipo === "estado") {
          campo = item.dataset.estado || "";
        } else if (tipo === "sala") {
          campo = item.dataset.sala || "";
        } else {
          campo = textoBusquedaCama(item);
        }
        coincideBusqueda = campo.toLowerCase().includes(valor);
      }

      var coincideEstado = estadoCoincideIndicador(item.dataset.estado || "", filtroEstadoIndicador);
      var coincideSala = !filtroSalaIndicador || String(item.dataset.sala || "").trim() === filtroSalaIndicador;

      item.style.display = coincideBusqueda && coincideEstado && coincideSala ? "" : "none";
    });

    // Si hay filtros activos, ocultar salas y servicios que no tengan camas visibles
    if (valor || filtroEstadoIndicador || filtroSalaIndicador) {
      document.querySelectorAll(".mapa-cubiculo").forEach(function (cub) {
        var visible = Array.from(cub.querySelectorAll(".mapa-cama")).some(function (c) { return c.style.display !== "none"; });
        cub.style.display = visible ? "" : "none";
      });
      document.querySelectorAll(".mapa-sala").forEach(function (sala) {
        var visible = Array.from(sala.querySelectorAll(".mapa-cama")).some(function (c) { return c.style.display !== "none"; });
        sala.style.display = visible ? "" : "none";
      });
      document.querySelectorAll(".mapa-servicio-card").forEach(function (serv) {
        var visible = Array.from(serv.querySelectorAll(".mapa-cama")).some(function (c) { return c.style.display !== "none"; });
        serv.style.display = visible ? "" : "none";
      });
    } else {
      // Limpiar ocultos al borrar la búsqueda
      document.querySelectorAll(".mapa-cubiculo, .mapa-sala, .mapa-servicio-card").forEach(function (el) {
        el.style.display = "";
      });
    }
  }

  // Sincroniza una card del DOM con la respuesta actualizada del backend.
  function actualizarCardDesdeRespuesta(camaEl, camaActualizada) {
    camaEl.className = "mapa-cama " + claseEstado(camaActualizada.estado_visual);
    camaEl.dataset.paciente = camaActualizada.paciente ? camaActualizada.paciente.nombre : "";
    camaEl.dataset.pacienteId = camaActualizada.paciente ? String(camaActualizada.paciente.id) : "";
    camaEl.dataset.estado = camaActualizada.estado_visual || "";
    camaEl.dataset.pacienteDni = camaActualizada.paciente ? (camaActualizada.paciente.dni || "") : "";
    camaEl.dataset.cambiosRealizados = String(camaActualizada.cambios_realizados || 0);
    camaEl.dataset.maxCambios = camaActualizada.max_cambios != null ? String(camaActualizada.max_cambios) : "";
    camaEl.dataset.ultimaActualizacion = camaActualizada.ultima_actualizacion || "";
    camaEl.dataset.usuarioUltimaActualizacion = camaActualizada.usuario_ultima_actualizacion || "";

    var estadoEl = camaEl.querySelector(".mapa-cama-estado");
    var pacienteEl = camaEl.querySelector(".mapa-cama-paciente");
    var dniEl = camaEl.querySelector(".mapa-cama-dni");
    var actualizacionEl = camaEl.querySelector(".mapa-cama-actualizacion");

    if (estadoEl) {
      estadoEl.textContent = camaActualizada.estado_visual || "VACIA";
    }
    if (pacienteEl) {
      pacienteEl.textContent = camaActualizada.paciente ? camaActualizada.paciente.nombre : "Sin paciente";
    }
    if (dniEl) {
      dniEl.textContent = camaActualizada.paciente ? (camaActualizada.paciente.dni || "") : "";
    }
    if (actualizacionEl) {
      // [2026-05-21] Mostrar fecha y hora en una sola línea en la card.
      actualizacionEl.textContent = "Ult. act.: " + formatearFechaHoraCorta(camaActualizada.ultima_actualizacion || "");
    }

    renderIndicadoresEstado();
    aplicarFiltro();
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
    var estadoActual = camaEl.dataset.estado || "VACIA";
    var pacienteActual = camaEl.dataset.paciente || "";
    var dniActual = camaEl.dataset.pacienteDni || "";
    var cambiosRealizados = parseInt(camaEl.dataset.cambiosRealizados || "0", 10);
    var maxCambios = camaEl.dataset.maxCambios ? parseInt(camaEl.dataset.maxCambios, 10) : null;
    var limiteTexto = maxCambios === null ? "Sin limite" : (cambiosRealizados + " / " + maxCambios);
    var ultimaActualizacion = formatearFechaHoraCorta(camaEl.dataset.ultimaActualizacion || "");
    var usuarioUltimaActualizacion = camaEl.dataset.usuarioUltimaActualizacion || "Sin registro";
    var estadoActualTexto = estadoActual || "VACIA";
    var htmlInformacion =
      '<fieldset class="modalAtencionCampos">' +
      "  <legend>Informacion</legend>" +
      '  <div class="formularioCampoModal">' +
      "    <label>Estado actual</label>" +
      '    <input type="text" class="formularioCampo-text" readonly value="' + escaparHtml(estadoActualTexto) + '">' +
      "  </div>" +
      '  <div class="formularioCampoModal">' +
      "    <label>Ultima actualizacion</label>" +
      '    <input type="text" class="formularioCampo-text" readonly value="' + escaparHtml(ultimaActualizacion) + '">' +
      "  </div>" +
      '  <div class="formularioCampoModal">' +
      "    <label>Actualizado por</label>" +
      '    <input type="text" class="formularioCampo-text" readonly value="' + escaparHtml(usuarioUltimaActualizacion) + '">' +
      "  </div>" +
      "</fieldset>";

    // La cama esta OCUPADA (o PRE_ALTA) cuando tiene paciente asignado.
    // Esta bandera define toda la estructura del modal.
    var esOcupada = estadoActual === "OCUPADA" || estadoActual === "PRE_ALTA";

    if (window.MAPA_ROL_INTENTOS_RESTRINGIDO && !esOcupada) {
      await Swal.fire({
        icon: "warning",
        title: "Accion no permitida",
        text: "Este rol solo puede mover pacientes o manejar pre-altas desde camas ocupadas.",
        confirmButtonText: "Entendido"
      });
      return;
    }

    // ── HTML para cama VACIA (u otro estado sin paciente) ────────────────────
    // Permite cambiar el estado; si se elige OCUPADA aparece busqueda de paciente
    var estadosDisponibles = ESTADOS_CAMA.slice();
    if (window.MAPA_ROL_INTENTOS_RESTRINGIDO && esOcupada) {
      estadosDisponibles = ["VACIA", "PRE_ALTA"];
    }
    var opcionesEstado = estadosDisponibles.map(function (e) {
      var sel = e === estadoActual ? ' selected="selected"' : "";
      return '<option value="' + e + '"' + sel + ">" + e + "</option>";
    }).join("");

    var htmlVacia =
      htmlInformacion +
      '<fieldset class="modalAtencionCampos">' +
      "  <legend>Estado de la cama</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-mapa-estado">Cambiar a estado</label>' +
      '    <select id="modal-mapa-estado" class="formularioCampo-select">' +
      opcionesEstado +
      "    </select>" +
      "  </div>" +
      "</fieldset>" +
      '<fieldset id="bloque-asignar-paciente" class="modalAtencionCampos" style="display:none">' +
      "  <legend>Asignar paciente a esta cama</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-tipo-busqueda-paciente">Buscar por</label>' +
      '    <select id="modal-tipo-busqueda-paciente" class="formularioCampo-select">' +
      '      <option value="dni" selected>DNI</option>' +
      '      <option value="nombre">Nombre</option>' +
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

    // ── HTML para cama OCUPADA ────────────────────────────────────────────
    // Muestra el paciente actual y permite: cambiar estado O mover a otra cama
    var htmlOcupada =
      htmlInformacion +
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
      "  <legend>Nuevo estado</legend>" +
      '  <div class="formularioCampoModal">' +
      '    <label for="modal-mapa-estado">Estado</label>' +
      '    <select id="modal-mapa-estado" class="formularioCampo-select">' +
      opcionesEstado +
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
            if (window.MAPA_ROL_INTENTOS_RESTRINGIDO && ["VACIA", "PRE_ALTA"].indexOf(estadoEl.value) === -1) {
              Swal.showValidationMessage("Este rol solo puede pasar la cama a PRE_ALTA o VACIA desde esta pantalla.");
              return false;
            }
            // Si se mantiene OCUPADA, re-enviar el paciente actual para no romper validacion del backend.
            var pacienteIdActual = camaEl.dataset.pacienteId || "";
            return {
              tipo: "cambiar_estado",
              estado: estadoEl.value,
              paciente_id: estadoEl.value === "OCUPADA" ? pacienteIdActual : ""
            };
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
        // didOpen inicializa listeners y autocompletados dentro del contenido dinamico.
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
            // Cambia el campo de busqueda del TomSelect sin tocar las opciones cargadas.
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
                // Select con busqueda integrada para mantener 2 controles visibles.
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
                // Reinicia input interno y reevalua con nuevo criterio de busqueda.
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

          if (tipoBusquedaPaciente) {
            tipoBusquedaPaciente.value = "dni";
          }

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
            // Fallback para navegadores/situaciones sin TomSelect disponible.
            var tipo = (tipoBusquedaPaciente && tipoBusquedaPaciente.value) ? tipoBusquedaPaciente.value : "dni";
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
            // Select de paciente con carga remota por texto + tipo de busqueda.
            tomPaciente = new TomSelect(selectPaciente, {
              valueField: "id",
              labelField: "text",
              searchField: "text",
              placeholder: "Buscar paciente...",
              preload: false,
              load: function (query, callback) {
                var tipo = (tipoBusquedaPaciente && tipoBusquedaPaciente.value) ? tipoBusquedaPaciente.value : "dni";
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

          function activarBuscadorPacienteParaOcupada() {
            if (!bloquePaciente) {
              return;
            }
            bloquePaciente.style.display = "";

            if (tipoBusquedaPaciente) {
              tipoBusquedaPaciente.value = "dni";
            }

            if (tomPaciente) {
              tomPaciente.clear(true);
              tomPaciente.clearOptions();
              tomPaciente.load("");
              return;
            }

            cargarPacientesFallback("");
          }

          estadoSelect.addEventListener("change", function () {
            if (estadoSelect.value === "OCUPADA") {
              // Solo en OCUPADA se habilita la asignacion de paciente.
              activarBuscadorPacienteParaOcupada();
            } else {
              // Si cambia a un estado no-ocupado, se limpia seleccion previa.
              bloquePaciente.style.display = "none";
              limpiarSeleccionPaciente();
            }
          });

          // Si el estado ya abre en OCUPADA, preparar el buscador inmediatamente.
          if (estadoSelect && estadoSelect.value === "OCUPADA") {
            activarBuscadorPacienteParaOcupada();
          }

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

        // [2026-05-04 IMPROVEMENT] No hacer location.reload().
        // Actualizar cards dinámicamente desde respuesta sin recarga de página.
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
        // [2026-05-04 IMPROVEMENT] Marcar cama como mapeada sin reload de página.
        if (sesionMapeoActivaId) {
          marcarCamaComoMapeada(camaEl);
        }
        toastr.success(data.mensaje || "Cama actualizada.", "Exito");
      }

    } catch (error) {
      // Unifica manejo de errores de red y de validaciones devueltas por backend.
      toastr.error(error.message || "Error al guardar.", "Error");
    }
  }

  // ========================================================================
  // Render del mapa (servicio > sala > cubiculo > cama)
  // ========================================================================

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
          camaEl.dataset.maxCambios = cama.max_cambios != null ? String(cama.max_cambios) : "";
          camaEl.dataset.ultimaActualizacion = cama.ultima_actualizacion || "";
          camaEl.dataset.usuarioUltimaActualizacion = cama.usuario_ultima_actualizacion || "";

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

          var actualizacion = document.createElement("span");
          actualizacion.className = "mapa-cama-actualizacion";
          actualizacion.style.whiteSpace = "nowrap";
          actualizacion.textContent = " " + formatearFechaHoraCorta(cama.ultima_actualizacion || "");

          camaEl.appendChild(numero);
          camaEl.appendChild(estado);
          camaEl.appendChild(paciente);
          camaEl.appendChild(dni);
          camaEl.appendChild(actualizacion);

          // --- Interaccion: doble clic (escritorio) o pulsacion larga (tactil)
          // Simple clic  -> abre modal de edicion
          // Doble clic   -> confirma cama sin cambios (solo en sesion de mapeo activa)
          // Long press   -> idem doble clic en pantallas tactiles
          var _clickTimer = null;
          var _longTimer  = null;
          var _touchWasLong = false;

          camaEl.addEventListener("touchstart", function () {
            // [2026-05-08] En modo solo lectura no activar acciones tactiles de edicion
            if (window.MAPA_SOLO_LECTURA) { return; }
            _longTimer = setTimeout(function () {
              _longTimer = null;
              _touchWasLong = true;
              if (sesionMapeoActivaId) { confirmarCamaSinCambios(camaEl); }
            }, LONG_PRESS_MS);
          }, { passive: true });

          camaEl.addEventListener("touchend", function () {
            if (_longTimer) { clearTimeout(_longTimer); _longTimer = null; }
          });

          camaEl.addEventListener("touchmove", function () {
            if (_longTimer) { clearTimeout(_longTimer); _longTimer = null; }
          });

          camaEl.addEventListener("click", function () {
            if (_touchWasLong) { _touchWasLong = false; return; }
            // [2026-05-08] En modo solo lectura no abrir modal de edicion
            if (window.MAPA_SOLO_LECTURA) { return; }
            if (_clickTimer) {
              clearTimeout(_clickTimer);
              _clickTimer = null;
              if (sesionMapeoActivaId) { confirmarCamaSinCambios(camaEl); }
            } else {
              _clickTimer = setTimeout(function () {
                _clickTimer = null;
                abrirModalEdicionCama(camaEl);
              }, CLICK_DELAY_MS);
            }
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
    renderIndicadoresEstado();
    renderIndicadoresSala();
    aplicarFiltro();
  }

  // Carga inicial del mapa y manejo de errores de red/servidor.
  function cargarMapa() {
    return fetch(API_URLS.mapa)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("No se pudo cargar la informacion del mapa.");
        }
        return response.json();
      })
      .then(function (data) {
        serviciosDisponiblesMapeo = data.servicios || [];
        renderMapa(serviciosDisponiblesMapeo);
      })
      .catch(function () {
        contenedor.innerHTML = '<p class="mapa-vacio">Error cargando mapa de camas.</p>';
      });
  }

  inputBusqueda.addEventListener("input", aplicarFiltro);

  if (filtroEstadoMovil) {
    filtroEstadoMovil.addEventListener("change", function () {
      var valor = filtroEstadoMovil.value || "TODAS";
      filtroEstadoIndicador = valor === "TODAS" ? "" : valor;
      // [2026-05-12] En móvil los selects controlan el filtro principal;
      // limpiar búsqueda de texto evita combinaciones invisibles/confusas.
      if (inputBusqueda) {
        inputBusqueda.value = "";
      }
      if (tipoBusqueda) {
        tipoBusqueda.value = "todo";
        localStorage.setItem(STORAGE_KEY_TIPO, "todo");
      }
      actualizarEstadoActivoIndicadores();
      aplicarFiltro();
    });
  }

  if (filtroSalaMovil) {
    filtroSalaMovil.addEventListener("change", function () {
      var valor = filtroSalaMovil.value || "TODAS";
      filtroSalaIndicador = valor === "TODAS" ? "" : valor;
      // [2026-05-12] En móvil los selects controlan el filtro principal;
      // limpiar búsqueda de texto evita combinaciones invisibles/confusas.
      if (inputBusqueda) {
        inputBusqueda.value = "";
      }
      if (tipoBusqueda) {
        tipoBusqueda.value = "todo";
        localStorage.setItem(STORAGE_KEY_TIPO, "todo");
      }
      renderIndicadoresEstado();
      actualizarEstadoActivoIndicadoresSala();
      aplicarFiltro();
    });
  }

  // [2026-05-05 FEATURE] Persistir tipo de búsqueda en localStorage.
  // Restaura la selección al cargar la página o volver desde otra sección.
  var STORAGE_KEY_TIPO = "mapa_tipo_busqueda";
  if (tipoBusqueda) {
    var tipoPersistido = localStorage.getItem(STORAGE_KEY_TIPO);
    if (tipoPersistido) {
      tipoBusqueda.value = tipoPersistido;
    }
  }

  tipoBusqueda.addEventListener("change", function () {
    // [2026-05-05 FEATURE] Guardar selección al cambiar.
    localStorage.setItem(STORAGE_KEY_TIPO, tipoBusqueda.value);
    aplicarFiltro();
  });

  // ========================================================================
  // Acciones de barra superior (filtros, utilidades y control de sesion)
  // ========================================================================

  // Limpia filtros y devuelve foco al input de busqueda.
  btnLimpiar.addEventListener("click", function () {
    inputBusqueda.value = "";
    tipoBusqueda.value = "todo";
    filtroEstadoIndicador = "";
    filtroSalaIndicador = "";
    // [2026-05-05 FEATURE] Al limpiar, también resetear el valor persistido.
    localStorage.setItem(STORAGE_KEY_TIPO, "todo");
    renderIndicadoresEstado();
    actualizarEstadoActivoIndicadores();
    actualizarEstadoActivoIndicadoresSala();
    sincronizarFiltrosMoviles();
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
    // La vista ya define estilos @media print para exportar el estado visual actual.
    window.print();
  });

  if (btnSincronizarCamas) {
    btnSincronizarCamas.addEventListener("click", async function () {
      // [2026-05-25] Acción administrativa para sincronización inicial masiva.
      var confirmacion = await Swal.fire({
        title: "Sincronizar camas",
        text: "Esto sincronizara asignaciones para ingresos activos con cama. Deseas continuar?",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Sincronizar",
        cancelButtonText: "Cancelar",
        customClass: {
          popup: "contener-modal-defuncion",
          title: "contener-modal-titulo",
          content: "contener-modal-contenido",
          confirmButton: "contener-modal-boton-confirmar",
          cancelButton: "contener-modal-boton-cancelar"
        }
      });
      if (!confirmacion.isConfirmed) {
        return;
      }

      btnSincronizarCamas.disabled = true;
      try {
        var response = await fetch(API_URLS.sincronizarCamas, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN }
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo ejecutar la sincronizacion.");
        }

        toastr.success(data.mensaje || "Sincronizacion completada.", "Exito");
        await cargarMapa();
      } catch (error) {
        toastr.error(error.message || "Error al sincronizar camas.", "Error");
      } finally {
        btnSincronizarCamas.disabled = false;
      }
    });
  }

  if (contenedorIndicadores) {
    contenedorIndicadores.addEventListener("click", function (event) {
      var boton = event.target.closest(".mapa-indicador");
      if (!boton) {
        return;
      }
      var estadoId = boton.dataset.estadoId || "";
      if (!estadoId || estadoId === "TODAS") {
        filtroEstadoIndicador = "";
      } else if (filtroEstadoIndicador === estadoId) {
        filtroEstadoIndicador = "";
      } else {
        filtroEstadoIndicador = estadoId;
      }
      actualizarEstadoActivoIndicadores();
      sincronizarFiltrosMoviles();
      aplicarFiltro();
    });
  }

  if (contenedorIndicadoresSala) {
    contenedorIndicadoresSala.addEventListener("click", function (event) {
      var boton = event.target.closest(".mapa-indicador");
      if (!boton) {
        return;
      }
      var salaId = boton.dataset.salaId || "";
      if (!salaId || salaId === "TODAS") {
        filtroSalaIndicador = "";
      } else if (filtroSalaIndicador === salaId) {
        filtroSalaIndicador = "";
      } else {
        filtroSalaIndicador = salaId;
      }
      renderIndicadoresEstado();
      actualizarEstadoActivoIndicadoresSala();
      sincronizarFiltrosMoviles();
      aplicarFiltro();
    });
  }

  if (btnIniciarMapeo) {
    btnIniciarMapeo.addEventListener("click", async function () {
      try {
        if (!serviciosDisponiblesMapeo.length) {
          throw new Error("No hay servicios disponibles para iniciar el mapeo.");
        }

        var confirmarInicio = await abrirModalSeleccionServiciosMapeo();
        if (!confirmarInicio.isConfirmed) {
          return;
        }

        var response = await fetch(API_URLS.iniciarMapeo, {
          method: "POST",
          headers: {
            "X-CSRFToken": window.CSRF_TOKEN,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ servicio_ids: confirmarInicio.value.servicio_ids })
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo iniciar el mapeo.");
        }

        sesionMapeoActivaId = data.sesion_id || null;
        serviciosSesionActivaIds = data.servicio_ids || [];
        camasMapeadasSesion = new Set((data.camas_mapeadas || []).map(function (v) {
          return String(v);
        }));
        establecerModoMapeoActivo(Boolean(sesionMapeoActivaId));
        await cargarMapa();
        aplicarMarcasSesionEnRender();
        toastr.success(data.mensaje || "Mapeo iniciado.", "Exito");
      } catch (error) {
        toastr.error(error.message || "Error al iniciar mapeo.", "Error");
      }
    });
  }

  function _ejecutarTerminarMapeo() {
    function _abrirModalCamasFaltantes(data) {
      var faltantes = Number(data && data.faltantes ? data.faltantes : 0);
      var listado = Array.isArray(data && data.camas_faltantes) ? data.camas_faltantes : [];
      var htmlLista = listado.length
        ? (
          '<fieldset class="modalAtencionCampos">' +
            '<legend>Camas pendientes</legend>' +
            '<div style="max-height: 18rem; overflow:auto; text-align:left;">' +
              '<table class="tabla-general" style="width:100%; font-size:0.86rem;">' +
                '<thead><tr><th>Cama</th><th>Servicio</th><th>Sala</th><th>Cubículo</th></tr></thead>' +
                '<tbody>' +
                  listado.map(function (item) {
                    return (
                      '<tr>' +
                        '<td>' + escaparHtml(item.numero_cama || '') + '</td>' +
                        '<td>' + escaparHtml(item.servicio || '') + '</td>' +
                        '<td>' + escaparHtml(item.sala || '') + '</td>' +
                        '<td>' + escaparHtml(item.cubiculo || '') + '</td>' +
                      '</tr>'
                    );
                  }).join('') +
                '</tbody>' +
              '</table>' +
            '</div>' +
          '</fieldset>'
        )
        : '<p>No se recibio el detalle de camas pendientes.</p>';

      Swal.fire({
        title: "Mapeo incompleto",
        html:
          '<div class="modal-mapeo-servicios__intro">' +
            '<p class="modal-mapeo-servicios__texto">Faltan ' + escaparHtml(String(faltantes)) + ' cama(s) por mapear antes de finalizar.</p>' +
          '</div>' +
          htmlLista,
        icon: "warning",
        confirmButtonText: "Entendido",
        customClass: {
          popup: "contener-modal-defuncion",
          title: "contener-modal-titulo",
          content: "contener-modal-contenido",
          confirmButton: "contener-modal-boton-confirmar",
          cancelButton: "contener-modal-boton-cancelar"
        }
      });
    }

    Swal.fire({
      title: "Finalizar mapeo",
      text: "Puede agregar observaciones antes de cerrar la sesion.",
      input: "textarea",
      inputLabel: "Observaciones del mapeo",
      inputPlaceholder: "Sin Observaciones",
      inputAttributes: { "aria-label": "Observaciones del mapeo", rows: 4 },
      icon: "question",
      showCancelButton: true,
      confirmButtonText: "Finalizar",
      cancelButtonText: "Cancelar",
    }).then(async function (result) {
      if (!result.isConfirmed) {
        return;
      }
      var observacion = (result.value || "").trim() || "Sin Observaciones";
      try {
        var response = await fetch(API_URLS.terminarMapeo, {
          method: "POST",
          headers: {
            "X-CSRFToken": window.CSRF_TOKEN,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ observacion: observacion }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          if (data && Number(data.faltantes || 0) > 0) {
            _abrirModalCamasFaltantes(data);
            return;
          }
          throw new Error(data.error || "No se pudo terminar el mapeo.");
        }

        sesionMapeoActivaId = null;
        serviciosSesionActivaIds = [];
        establecerModoMapeoActivo(false);
        limpiarMarcasMapeo();
        await cargarMapa();
        toastr.success(data.mensaje || "Mapeo finalizado.", "Exito");
      } catch (error) {
        toastr.error(error.message || "Error al terminar mapeo.", "Error");
      }
    });
  }

  // [2026-05-20 OPT] Consolidar listeners de terminar mapeo (data-action unificado)
  document.querySelectorAll('[data-action="terminar-mapeo"]').forEach(function(btn) {
    btn.addEventListener("click", _ejecutarTerminarMapeo);
  });

  if (btnCancelarMapeo) {
    btnCancelarMapeo.addEventListener("click", async function () {
      try {
        var confirmarCancelacion = await Swal.fire({
          title: "Cancelar mapeo",
          text: "La sesion de mapeo actual se cancelara y no podra retomarse. Desea continuar?",
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "Si, cancelar",
          cancelButtonText: "Volver",
          confirmButtonColor: "#b91c1c",
        });
        if (!confirmarCancelacion.isConfirmed) {
          return;
        }

        var response = await fetch(API_URLS.cancelarMapeo, {
          method: "POST",
          headers: { "X-CSRFToken": window.CSRF_TOKEN }
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "No se pudo cancelar el mapeo.");
        }

        sesionMapeoActivaId = null;
        serviciosSesionActivaIds = [];
        establecerModoMapeoActivo(false);
        limpiarMarcasMapeo();
        await cargarMapa();
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
