document.addEventListener("DOMContentLoaded", function () {
  var API_URLS = {
    cards: "/mapeo-camas/api/historiales/cards/"
  };

  var contenedor = document.getElementById("detalle-cards-contenedor");
  var estructuraContenedor = document.getElementById("detalle-estructura-contenedor");
  var tablaContenedor = document.getElementById("detalle-tabla-contenedor");
  var tablaBody = document.getElementById("tabla-detalle-camas-body");
  var metaEl = document.getElementById("detalle-meta");
  var resumenComunEl = document.getElementById("detalle-resumen-comun");
  var btnCopiar = document.getElementById("btn-copiar-detalle");
  var btnImprimir = document.getElementById("btn-imprimir-detalle");
  var btnVistaEstructura = document.getElementById("btn-vista-estructura");
  var btnVistaTabla = document.getElementById("btn-vista-tabla");
  var paginacionWrap = document.getElementById("detalle-paginacion");
  var btnPageFirst = document.getElementById("detalle-page-first");
  var btnPagePrev = document.getElementById("detalle-page-prev");
  var btnPageNext = document.getElementById("detalle-page-next");
  var btnPageLast = document.getElementById("detalle-page-last");
  var pageInfoEl = document.getElementById("detalle-page-info");
  var pageSizeEl = document.getElementById("detalle-page-size");

  var tablaDt = null;
  var dtfFechaInicio = document.getElementById("dtf-fecha-inicio");
  var dtfFechaFin = document.getElementById("dtf-fecha-fin");
  var dtfLimpiar = document.getElementById("dtf-btn-limpiar");

  var estructuraCache = [];
  var flatItemsCache = [];
  var vistaActual = sessionStorage.getItem("detalle_vista") || "estructura";
  var tipoDetalleActual = "";
  var detallePageActual = 1;
  var detalleTotalPages = 1;
  var detallePageSize = parseInt(sessionStorage.getItem("detalle_page_size") || "50", 10);

  if ([25, 50, 100, 200].indexOf(detallePageSize) === -1) {
    detallePageSize = 50;
  }
  if (pageSizeEl) {
    pageSizeEl.value = String(detallePageSize);
  }

  function escaparHtml(valor) {
    return String(valor || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
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

  function extraerFechaHora(valor) {
    if (!valor) {
      return { fecha: "", hora: "" };
    }
    var fecha = new Date(valor);
    if (isNaN(fecha.getTime())) {
      return { fecha: "", hora: "" };
    }
    var dd = String(fecha.getDate()).padStart(2, "0");
    var mm = String(fecha.getMonth() + 1).padStart(2, "0");
    var yyyy = String(fecha.getFullYear());
    var hh = String(fecha.getHours()).padStart(2, "0");
    var min = String(fecha.getMinutes()).padStart(2, "0");
    return {
      fecha: dd + "/" + mm + "/" + yyyy,
      hora: hh + ":" + min
    };
  }

  function resumenComunEstructura(estructura) {
    var usuarios = new Set();
    var fechas = new Set();

    (estructura || []).forEach(function (servicio) {
      (servicio.salas || []).forEach(function (sala) {
        (sala.camas_directas || []).forEach(function (cama) {
          if (cama.usuario) {
            usuarios.add(String(cama.usuario).trim());
          }
          var fechaHora = extraerFechaHora(cama.fecha);
          if (fechaHora.fecha) {
            fechas.add(fechaHora.fecha);
          }
        });
        (sala.cubiculos || []).forEach(function (cubiculo) {
          (cubiculo.camas || []).forEach(function (cama) {
            if (cama.usuario) {
              usuarios.add(String(cama.usuario).trim());
            }
            var fechaHora = extraerFechaHora(cama.fecha);
            if (fechaHora.fecha) {
              fechas.add(fechaHora.fecha);
            }
          });
        });
      });
    });

    return {
      usuario: usuarios.size === 1 ? Array.from(usuarios)[0] : (usuarios.size > 1 ? "Varios usuarios" : "Sin registro"),
      fecha: fechas.size === 1 ? Array.from(fechas)[0] : (fechas.size > 1 ? "Varias fechas" : "Sin registro")
    };
  }

  function actualizarResumenComun(estructura) {
    if (!resumenComunEl) {
      return;
    }
    if (!estructura || !estructura.length) {
      resumenComunEl.style.display = "none";
      resumenComunEl.innerHTML = "";
      return;
    }
    var resumen = resumenComunEstructura(estructura);
    resumenComunEl.innerHTML =
      '<span><strong>Usuario:</strong> ' + escaparHtml(resumen.usuario) + '</span>' +
      '<span><strong>Fecha:</strong> ' + escaparHtml(resumen.fecha) + '</span>';
    resumenComunEl.style.display = "flex";
  }

  function configurarTablaSegunTipo() {
    var esMapeo = tipoDetalleActual === "mapeo";
    var thFecha = document.getElementById("detalle-th-fecha");
    var thTotalMapeadas = document.getElementById("detalle-th-total-mapeadas");
    var thUsuario = document.getElementById("detalle-th-usuario");

    if (thFecha) {
      thFecha.textContent = esMapeo ? "Hora" : "Fecha";
    }
    if (thTotalMapeadas) {
      thTotalMapeadas.style.display = esMapeo ? "" : "none";
    }
    if (thUsuario) {
      thUsuario.style.display = esMapeo ? "none" : "";
    }

    if (tablaDt) {
      tablaDt.column(6).visible(esMapeo, false);
      tablaDt.column(7).visible(!esMapeo, false);
      tablaDt.columns.adjust().draw(false);
    }
  }

  function aplicarVisibilidadUsuarioFallback() {
    if (!tablaBody) {
      return;
    }
    var esMapeo = tipoDetalleActual === "mapeo";
    Array.from(tablaBody.querySelectorAll("tr")).forEach(function (row) {
      var celdaTotalMapeadas = row.children[6];
      if (celdaTotalMapeadas) {
        celdaTotalMapeadas.style.display = esMapeo ? "" : "none";
      }

      var celdaUsuario = row.children[7];
      if (celdaUsuario) {
        celdaUsuario.style.display = esMapeo ? "none" : "";
      }
    });
  }

  function estadoCssDesdeTexto(estado) {
    var valor = String(estado || "").trim().toUpperCase();
    if (valor === "VACIA" || valor === "LIBRE") {
      return "mapa-cama--vacia";
    }
    if (valor === "OCUPADA") {
      return "mapa-cama--ocupada";
    }
    if (valor === "PRE_ALTA" || valor === "ALTA") {
      return "mapa-cama--alta";
    }
    if (valor === "FUERA_SERVICIO" || valor === "MANTENIMIENTO") {
      return "mapa-cama--fuera-servicio";
    }
    if (valor === "CONSULTA_EXTERNA") {
      return "mapa-cama--consulta-externa";
    }
    return "mapa-cama--sin-asignacion";
  }

  function renderVacio(texto) {
    if (estructuraContenedor) {
      estructuraContenedor.innerHTML = "";
    }
    if (resumenComunEl) {
      resumenComunEl.style.display = "none";
      resumenComunEl.innerHTML = "";
    }
    if (tablaDt) {
      tablaDt.clear().draw();
    } else if (tablaBody) {
      tablaBody.innerHTML = "";
    }
    contenedor.innerHTML = '<div class="historial-card-vacia">' + escaparHtml(texto || "Sin datos para mostrar.") + "</div>";
    actualizarPaginacion(null);
  }

  function actualizarPaginacion(meta) {
    var mostrar = meta && (tipoDetalleActual === "historial" || tipoDetalleActual === "movimiento");
    if (!paginacionWrap) {
      return;
    }
    if (!mostrar) {
      paginacionWrap.style.display = "none";
      return;
    }

    detallePageActual = parseInt(meta.page || 1, 10);
    detalleTotalPages = Math.max(parseInt(meta.total_pages || 1, 10), 1);
    detallePageSize = parseInt(meta.page_size || detallePageSize, 10);
    if ([25, 50, 100, 200].indexOf(detallePageSize) === -1) {
      detallePageSize = 50;
    }
    if (pageSizeEl) {
      pageSizeEl.value = String(detallePageSize);
    }

    var totalItems = parseInt(meta.total_items || 0, 10);
    var inicio = totalItems ? ((detallePageActual - 1) * detallePageSize + 1) : 0;
    var fin = totalItems ? Math.min(detallePageActual * detallePageSize, totalItems) : 0;

    paginacionWrap.style.display = "flex";
    if (pageInfoEl) {
      pageInfoEl.textContent = inicio + "-" + fin + " de " + totalItems + " | Página " + detallePageActual + " de " + detalleTotalPages;
    }
    if (btnPageFirst) {
      btnPageFirst.disabled = detallePageActual <= 1;
    }
    if (btnPagePrev) {
      btnPagePrev.disabled = detallePageActual <= 1;
    }
    if (btnPageNext) {
      btnPageNext.disabled = detallePageActual >= detalleTotalPages;
    }
    if (btnPageLast) {
      btnPageLast.disabled = detallePageActual >= detalleTotalPages;
    }
  }

  // [2026-05-05 FEATURE] Construye el HTML de una tarjeta de cama con estilo visual del mapa.
  // Muestra 4 datos principales (estado, paciente, DNI, acción) y oculta el resto (usuario,
  // fecha, observación) que se revela al hacer clic en la tarjeta.
  // [2026-05-18] En mapeo muestra solo hora; en otros tipos muestra fecha completa.
  function buildCamaItemHtml(cama) {
    var estadoCss = estadoCssDesdeTexto(cama.estado);
    var fechaHora = extraerFechaHora(cama.fecha);
    var dniHtml = cama.dni
      ? '<div class="detalle-cama-dni-txt">DNI: ' + escaparHtml(cama.dni) + "</div>"
      : "";
    
    // [2026-05-18] Mostrar solo hora en mapeo, fecha completa en otros tipos
    var fechaTextoHtml = "";
    var usuarioTextoHtml = "";
    if (tipoDetalleActual === "mapeo") {
      fechaTextoHtml = fechaHora.hora
        ? '<div class="detalle-cama-hora-txt">Hora: ' + escaparHtml(fechaHora.hora) + "</div>"
        : "";
      usuarioTextoHtml = "";
    } else {
      fechaTextoHtml = cama.fecha
        ? '<div class="detalle-cama-fecha-txt">Fecha: ' + escaparHtml(formatearFechaHoraCorta(cama.fecha)) + "</div>"
        : "";
      usuarioTextoHtml = cama.usuario
        ? '<div class="detalle-cama-usuario-txt">Usuario: ' + escaparHtml(cama.usuario) + "</div>"
        : '<div class="detalle-cama-usuario-txt">Usuario: Sin registro</div>';
    }
    
    // [2026-05-26 AUDIT] La observacion se muestra visible en el detalle de mapeo.
    var obsHtml = cama.observacion
      ? '<div class="detalle-cama-obs-txt">Obs: ' + escaparHtml(cama.observacion) + "</div>"
      : "";
    var esExpandible = !!obsHtml;
    var extraHtml = obsHtml
      ? ('<div class="detalle-cama-extra">' + obsHtml + "</div>")
      : "";
    return (
      '<div class="detalle-cama-item ' + estadoCss + '" role="button" aria-expanded="false" tabindex="0" title="' + (esExpandible ? 'Clic para ver más' : '') + '">' +
      '<div class="detalle-cama-numero">Cama ' + escaparHtml(cama.numero_cama || "") + "</div>" +
      '<div class="detalle-cama-estado-txt">' + escaparHtml(cama.estado || "") + "</div>" +
      '<div class="detalle-cama-paciente-txt">' + escaparHtml(cama.paciente || "Sin paciente") + "</div>" +
      dniHtml +
      '<div class="detalle-cama-accion-txt">' + escaparHtml(cama.tipo_accion || "") + "</div>" +
      obsHtml +
      usuarioTextoHtml +
      fechaTextoHtml +
      extraHtml +
      "</div>"
    );
  }

  function renderEstructuraMapeo(estructura) {
    if (!estructuraContenedor) {
      return;
    }

    if (!estructura || !estructura.length) {
      actualizarResumenComun([]);
      estructuraContenedor.innerHTML = '<div class="historial-card-vacia">Sin resultados para los filtros seleccionados.</div>';
      return;
    }
    actualizarResumenComun(estructura);

    var html = (estructura || []).map(function (servicio) {
      var salasHtml = (servicio.salas || []).map(function (sala) {
        var cubiculosHtml = (sala.cubiculos || []).map(function (cubiculo) {
          var camasHtml = (cubiculo.camas || []).map(buildCamaItemHtml).join("");
          return (
            '<div class="detalle-bloque" style="margin-top:0.6rem;">' +
            '<div class="detalle-bloque-titulo">Cubículo: ' + escaparHtml(cubiculo.nombre || "") + "</div>" +
            '<div class="detalle-bloque-contenido"><div class="detalle-camas-grid">' + camasHtml + "</div></div>" +
            "</div>"
          );
        }).join("");

        var directasHtml = (sala.camas_directas || []).map(buildCamaItemHtml).join("");

        return (
          '<div class="detalle-bloque" style="margin-top:0.6rem;">' +
          '<div class="detalle-bloque-titulo">Sala: ' + escaparHtml(sala.nombre || "") + "</div>" +
          '<div class="detalle-bloque-contenido">' +
          (directasHtml ? ('<div class="detalle-camas-grid">' + directasHtml + "</div>") : "") +
          cubiculosHtml +
          "</div>" +
          "</div>"
        );
      }).join("");

      return (
        '<section class="detalle-bloque">' +
        '<div class="detalle-bloque-titulo">Servicio: ' + escaparHtml(servicio.nombre || "") + "</div>" +
        '<div class="detalle-bloque-contenido">' + salasHtml + "</div>" +
        "</section>"
      );
    }).join("");

    estructuraContenedor.innerHTML = html;
  }

  // [2026-05-05 FEATURE] Delegación de evento para expandir/colapsar datos extra al hacer clic en la tarjeta.
  if (estructuraContenedor) {
    estructuraContenedor.addEventListener("click", function (e) {
      var card = e.target.closest(".detalle-cama-item");
      if (!card) return;
      var extra = card.querySelector(".detalle-cama-extra");
      if (!extra) return;
      var abierto = card.getAttribute("aria-expanded") === "true";
      card.setAttribute("aria-expanded", !abierto);
      extra.style.display = abierto ? "none" : "block";
    });
  }

  var notaServiciosEl = document.getElementById("detalle-nota-servicios");

  function renderNotaServicios(servicios) {
    if (!notaServiciosEl) {
      return;
    }
    if (!servicios || !servicios.length) {
      notaServiciosEl.style.display = "none";
      return;
    }
    var chips = servicios.map(function (s) {
      return '<span class="detalle-nota-chip">' + escaparHtml(s) + '</span>';
    }).join("");
    notaServiciosEl.innerHTML =
      '<i class="bi bi-info-circle-fill detalle-nota-icono"></i>' +
      '<span class="detalle-nota-texto">Servicios incluidos en esta sesión:</span>' +
      '<span class="detalle-nota-chips">' + chips + '</span>';
    notaServiciosEl.style.display = "flex";
  }

  function cargarDetalle(pageObjetivo) {
    var params = new URLSearchParams(window.location.search || "");
    var tipo = (params.get("tipo") || "").toLowerCase();
    var id = (params.get("id") || "").trim();
    tipoDetalleActual = tipo;
    if (typeof pageObjetivo === "number" && !isNaN(pageObjetivo)) {
      detallePageActual = Math.max(1, pageObjetivo);
    }

    var labelTipo = tipo === "mapeo" ? "Sección Mapeo"
      : tipo === "historial" ? "Sección Historial Estado"
      : tipo === "movimiento" ? "Sección Movimiento de Cama"
      : "Detalle";
    metaEl.textContent = labelTipo + (id ? " — #" + id : "");

    if (!tipo || !id) {
      renderVacio("Faltan parámetros de tipo o id en la URL.");
      return;
    }

    var query = new URLSearchParams({ tipo: tipo, id: id });
    if (tipo === "historial" || tipo === "movimiento") {
      query.set("page", String(detallePageActual));
      query.set("page_size", String(detallePageSize));
    }
    fetch(API_URLS.cards + "?" + query.toString())
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (!data.ok) {
          toastr.error(data.error || "No se pudo cargar el detalle.", "Error");
          renderVacio("No se pudo cargar el detalle solicitado.");
          return;
        }
        // [2026-05-08] Mostrar nota de servicios solo para mapeos
        renderNotaServicios(tipo === "mapeo" ? (data.servicios_sesion || []) : []);
        if (tipo === "mapeo" && metaEl) {
          var sesionObs = (data.sesion_observacion || "").trim();
          metaEl.innerHTML = '<span>' + escaparHtml(labelTipo + (id ? " — #" + id : "")) + '</span>' +
            (sesionObs ? '<span><strong>Observación:</strong> ' + escaparHtml(sesionObs) + '</span>' : '');
        }
        actualizarPaginacion(data.paginacion || null);
        estructuraCache = data.estructura || [];
        flatItemsCache = aplanarEstructura(estructuraCache);
        renderEstructuraMapeo(estructuraCache);
        contenedor.innerHTML = "";
        inicializarTablaDetalle();
        configurarTablaSegunTipo();
        aplicarFiltrosCompartidos();
        aplicarVista(vistaActual);
      })
      .catch(function () {
        toastr.error("No se pudo cargar el detalle en cards.", "Error");
        renderVacio("Error de conexión al consultar detalle.");
      });
  }

  function obtenerFiltrosActivos() {
    var fechaIni = dtfFechaInicio && dtfFechaInicio.value ? new Date(dtfFechaInicio.value + "T00:00:00") : null;
    var fechaFin = dtfFechaFin && dtfFechaFin.value ? new Date(dtfFechaFin.value + "T23:59:59") : null;
    return { fechaInicio: fechaIni, fechaFin: fechaFin };
  }

  function cumpleFiltrosItem(item, filtros) {
    var fechaItem = item.fecha ? new Date(item.fecha) : null;
    if ((filtros.fechaInicio || filtros.fechaFin) && (!fechaItem || isNaN(fechaItem.getTime()))) {
      return false;
    }
    if (filtros.fechaInicio && fechaItem < filtros.fechaInicio) {
      return false;
    }
    if (filtros.fechaFin && fechaItem > filtros.fechaFin) {
      return false;
    }
    return true;
  }

  function filtrarEstructura(estructura, filtros) {
    return (estructura || []).map(function (servicio) {
      var salas = (servicio.salas || []).map(function (sala) {
        var camasDirectas = (sala.camas_directas || []).filter(function (cama) {
          return cumpleFiltrosItem(cama, filtros);
        });
        var cubiculos = (sala.cubiculos || []).map(function (cubiculo) {
          var camas = (cubiculo.camas || []).filter(function (cama) {
            return cumpleFiltrosItem(cama, filtros);
          });
          return {
            nombre: cubiculo.nombre,
            camas: camas
          };
        }).filter(function (cubiculo) {
          return cubiculo.camas.length > 0;
        });

        return {
          nombre: sala.nombre,
          cubiculos: cubiculos,
          camas_directas: camasDirectas
        };
      }).filter(function (sala) {
        return sala.camas_directas.length > 0 || sala.cubiculos.length > 0;
      });

      return {
        nombre: servicio.nombre,
        salas: salas
      };
    }).filter(function (servicio) {
      return servicio.salas.length > 0;
    });
  }

  // ── Vista tabla ──────────────────────────────────────────────────────────

  function aplanarEstructura(estructura) {
    var items = [];
    (estructura || []).forEach(function (servicio) {
      (servicio.salas || []).forEach(function (sala) {
        (sala.camas_directas || []).forEach(function (cama) {
          items.push(Object.assign({}, cama, {
            _sala: sala.nombre || "",
            _cubiculo: "",
            _servicio: servicio.nombre || ""
          }));
        });
        (sala.cubiculos || []).forEach(function (cubiculo) {
          (cubiculo.camas || []).forEach(function (cama) {
            items.push(Object.assign({}, cama, {
              _sala: sala.nombre || "",
              _cubiculo: cubiculo.nombre || "",
              _servicio: servicio.nombre || ""
            }));
          });
        });
      });
    });
    return items;
  }

  // [2026-05-21] Total único de camas mapeadas según el conjunto visible en la sección.
  function calcularTotalCamasMapeadas(items) {
    var camasUnicas = new Set();
    (items || []).forEach(function (item) {
      var cama = String(item.numero_cama || "").trim();
      if (cama) {
        camasUnicas.add(cama);
      }
    });
    return camasUnicas.size;
  }

  // [2026-05-21] Inserta el total de camas mapeadas para mostrarlo en su columna de tabla.
  function anexarTotalCamasMapeadas(items) {
    var total = calcularTotalCamasMapeadas(items);
    return (items || []).map(function (item) {
      return Object.assign({}, item, { total_camas_mapeadas: total });
    });
  }

  function inicializarTablaDetalle() {
    if (tablaDt || !(window.$ && $.fn && $.fn.DataTable)) {
      return;
    }

    tablaDt = $("#tabla-detalle-camas").DataTable({
      responsive: true,
      serverSide: false,
      paging: true,
      lengthMenu: [10, 25, 50, 100],
      pageLength: 10,
      ordering: false,
      searching: false,
      data: [],
      columns: [
        { data: "numero_cama", defaultContent: "" },
        { data: "estado", defaultContent: "" },
        { data: "paciente", defaultContent: "" },
        { data: "dni", defaultContent: "" },
        { data: "tipo_accion", defaultContent: "" },
        {
          data: "fecha",
          defaultContent: "",
          render: function (data) {
            if (tipoDetalleActual === "mapeo") {
              var fechaHora = extraerFechaHora(data);
              return fechaHora.hora || "Sin registro";
            }
            return formatearFechaHoraCorta(data);
          }
        },
        { data: "total_camas_mapeadas", defaultContent: "" },
        { data: "usuario", defaultContent: "" }
      ],
      language: {
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 registros",
        infoFiltered: "(filtrado de _MAX_)",
        paginate: {
          first: "<<",
          last: ">>",
          next: ">",
          previous: "<"
        },
        loadingRecords: "Cargando...",
        processing: "Procesando...",
        emptyTable: "No hay datos disponibles en la tabla"
      },
      dom: 't<"inferior"lip><"clear">',
      columnDefs: [
        { targets: 0, className: "PrimerColumnaAliIzq" },
        { targets: 5, className: "ColumnaFechaCortaIngreso" }
      ]
    });
  }

  function renderTabla(items) {
    var itemsConTotal = anexarTotalCamasMapeadas(items || []);

    if (tablaDt) {
      tablaDt.clear();
      if (itemsConTotal.length) {
        tablaDt.rows.add(itemsConTotal);
      }
      tablaDt.draw();
      return;
    }

    if (!tablaBody) {
      return;
    }

    tablaBody.innerHTML = itemsConTotal.length
      ? itemsConTotal.map(function (item) {
          var celdaFecha = tipoDetalleActual === "mapeo"
            ? (extraerFechaHora(item.fecha).hora || "Sin registro")
            : formatearFechaHoraCorta(item.fecha);
          return (
            "<tr>" +
            "<td>" + escaparHtml(item.numero_cama || "") + "</td>" +
            "<td>" + escaparHtml(item.estado || "") + "</td>" +
            "<td>" + escaparHtml(item.paciente || "Sin paciente") + "</td>" +
            "<td>" + escaparHtml(item.dni || "") + "</td>" +
            "<td>" + escaparHtml(item.tipo_accion || "") + "</td>" +
            "<td>" + escaparHtml(celdaFecha) + "</td>" +
            "<td>" + escaparHtml(item.total_camas_mapeadas || "") + "</td>" +
            "<td>" + escaparHtml(item.usuario || "") + "</td>" +
            "</tr>"
          );
        }).join("")
      : '<tr><td colspan="' + (tipoDetalleActual === "mapeo" ? "7" : "8") + '">Sin resultados para los filtros seleccionados.</td></tr>';

    aplicarVisibilidadUsuarioFallback();
  }

  function aplicarFiltrosCompartidos() {
    var filtros = obtenerFiltrosActivos();
    var estructuraFiltrada = filtrarEstructura(estructuraCache, filtros);
    var itemsFiltrados = aplanarEstructura(estructuraFiltrada);

    renderEstructuraMapeo(estructuraFiltrada);
    renderTabla(itemsFiltrados);
  }

  function aplicarVista(vista) {
    vistaActual = vista;
    sessionStorage.setItem("detalle_vista", vista);

    var esTabla = vista === "tabla";
    if (estructuraContenedor) estructuraContenedor.style.display = esTabla ? "none" : "";
    if (contenedor) contenedor.style.display = esTabla ? "none" : "";
    if (tablaContenedor) tablaContenedor.style.display = esTabla ? "" : "none";

    if (btnVistaEstructura) {
      btnVistaEstructura.classList.toggle("active", !esTabla);
    }
    if (btnVistaTabla) {
      btnVistaTabla.classList.toggle("active", esTabla);
    }

    if (esTabla && tablaDt) {
      tablaDt.columns.adjust();
      if (tablaDt.responsive && typeof tablaDt.responsive.recalc === "function") {
        tablaDt.responsive.recalc();
      }
    }
  }

  // Eventos toggle
  if (btnVistaEstructura) {
    btnVistaEstructura.addEventListener("click", function () { aplicarVista("estructura"); });
  }
  if (btnVistaTabla) {
    btnVistaTabla.addEventListener("click", function () { aplicarVista("tabla"); });
  }

  // Eventos filtros
  [dtfFechaInicio, dtfFechaFin].forEach(function (el) {
    if (el) el.addEventListener("change", aplicarFiltrosCompartidos);
  });
  if (dtfLimpiar) {
    dtfLimpiar.addEventListener("click", function () {
      if (dtfFechaInicio) dtfFechaInicio.value = "";
      if (dtfFechaFin) dtfFechaFin.value = "";
      aplicarFiltrosCompartidos();
    });
  }

  function copiarResumenVisible() {
    var texto = (document.getElementById("detalle-meta")?.innerText || "") + "\n\n" +
      (document.getElementById("detalle-estructura-contenedor")?.innerText || "") + "\n\n" +
      (document.getElementById("detalle-cards-contenedor")?.innerText || "") + "\n\n" +
      (document.getElementById("detalle-tabla-contenedor")?.innerText || "");

    if (!texto.trim()) {
      toastr.warning("No hay contenido visible para copiar.", "Copiar");
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto)
        .then(function () {
          toastr.success("Resumen copiado al portapapeles.", "Copiar");
        })
        .catch(function () {
          toastr.error("No se pudo copiar el resumen.", "Copiar");
        });
      return;
    }

    var tmp = document.createElement("textarea");
    tmp.value = texto;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
    toastr.success("Resumen copiado al portapapeles.", "Copiar");
  }

  function imprimirDetalle() {
    window.print();
  }

  if (btnCopiar) {
    btnCopiar.addEventListener("click", copiarResumenVisible);
  }
  if (btnImprimir) {
    btnImprimir.addEventListener("click", imprimirDetalle);
  }

  if (btnPagePrev) {
    btnPagePrev.addEventListener("click", function () {
      if (detallePageActual > 1) {
        cargarDetalle(detallePageActual - 1);
      }
    });
  }

  if (btnPageFirst) {
    btnPageFirst.addEventListener("click", function () {
      if (detallePageActual > 1) {
        cargarDetalle(1);
      }
    });
  }

  if (btnPageNext) {
    btnPageNext.addEventListener("click", function () {
      if (detallePageActual < detalleTotalPages) {
        cargarDetalle(detallePageActual + 1);
      }
    });
  }

  if (btnPageLast) {
    btnPageLast.addEventListener("click", function () {
      if (detallePageActual < detalleTotalPages) {
        cargarDetalle(detalleTotalPages);
      }
    });
  }

  if (pageSizeEl) {
    pageSizeEl.addEventListener("change", function () {
      var nuevo = parseInt(pageSizeEl.value || "50", 10);
      if ([25, 50, 100, 200].indexOf(nuevo) === -1) {
        nuevo = 50;
      }
      detallePageSize = nuevo;
      sessionStorage.setItem("detalle_page_size", String(detallePageSize));
      cargarDetalle(1);
    });
  }

  cargarDetalle();
});
