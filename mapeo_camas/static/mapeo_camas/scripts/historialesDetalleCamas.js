document.addEventListener("DOMContentLoaded", function () {
  var API_URLS = {
    cards: "/mapeo-camas/api/historiales/cards/"
  };

  var contenedor = document.getElementById("detalle-cards-contenedor");
  var estructuraContenedor = document.getElementById("detalle-estructura-contenedor");
  var tablaContenedor = document.getElementById("detalle-tabla-contenedor");
  var tablaFiltros = document.getElementById("detalle-tabla-filtros");
  var tablaBody = document.getElementById("tabla-detalle-camas-body");
  var metaEl = document.getElementById("detalle-meta");
  var btnCopiar = document.getElementById("btn-copiar-detalle");
  var btnImprimir = document.getElementById("btn-imprimir-detalle");
  var btnVistaEstructura = document.getElementById("btn-vista-estructura");
  var btnVistaTabla = document.getElementById("btn-vista-tabla");

  var tablaDt = null;
  // [2026-05-06 FIX] Filtro Estado eliminado; solo se filtra por fecha.
  var dtfFechaInicio = document.getElementById("dtf-fecha-inicio");
  var dtfFechaFin = document.getElementById("dtf-fecha-fin");
  var dtfLimpiar = document.getElementById("dtf-btn-limpiar");

  var estructuraCache = [];
  var flatItemsCache = [];
  var vistaActual = sessionStorage.getItem("detalle_vista") || "estructura";

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
    if (tablaDt) {
      tablaDt.clear().draw();
    } else if (tablaBody) {
      tablaBody.innerHTML = "";
    }
    contenedor.innerHTML = '<div class="historial-card-vacia">' + escaparHtml(texto || "Sin datos para mostrar.") + "</div>";
  }

  // [2026-05-05 FEATURE] Construye el HTML de una tarjeta de cama con estilo visual del mapa.
  // Muestra 4 datos principales (estado, paciente, DNI, acción) y oculta el resto (usuario,
  // fecha, observación) que se revela al hacer clic en la tarjeta.
  function buildCamaItemHtml(cama) {
    var estadoCss = estadoCssDesdeTexto(cama.estado);
    var dniHtml = cama.dni
      ? '<div class="detalle-cama-dni-txt">DNI: ' + escaparHtml(cama.dni) + "</div>"
      : "";
    var obsHtml = cama.observacion
      ? '<div class="detalle-cama-obs-txt">' + escaparHtml(cama.observacion) + "</div>"
      : "";
    return (
      '<div class="detalle-cama-item ' + estadoCss + '" role="button" aria-expanded="false" tabindex="0" title="Clic para ver más">' +
      '<div class="detalle-cama-numero">Cama ' + escaparHtml(cama.numero_cama || "") + "</div>" +
      '<div class="detalle-cama-estado-txt">' + escaparHtml(cama.estado || "") + "</div>" +
      '<div class="detalle-cama-paciente-txt">' + escaparHtml(cama.paciente || "Sin paciente") + "</div>" +
      dniHtml +
      '<div class="detalle-cama-accion-txt">' + escaparHtml(cama.tipo_accion || "") + "</div>" +
      '<div class="detalle-cama-extra">' +
        '<div class="detalle-cama-linea-extra"><strong>Usuario:</strong> ' + escaparHtml(cama.usuario || "") + "</div>" +
        '<div class="detalle-cama-linea-extra"><strong>Fecha:</strong> ' + escaparHtml(formatearFechaHoraCorta(cama.fecha)) + "</div>" +
        obsHtml +
      "</div>" +
      "</div>"
    );
  }

  function renderEstructuraMapeo(estructura) {
    if (!estructuraContenedor) {
      return;
    }

    if (!estructura || !estructura.length) {
      estructuraContenedor.innerHTML = '<div class="historial-card-vacia">Sin resultados para los filtros seleccionados.</div>';
      return;
    }

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

  function renderCards(cards) {
    if (!cards || !cards.length) {
      renderVacio("No hay cards para este registro.");
      return;
    }

    var params = new URLSearchParams(window.location.search || "");
    var tipoActual = (params.get("tipo") || "").toLowerCase();

    if (tipoActual === "historial") {
      var htmlTimeline = '<div class="historial-timeline">' + cards.map(function (card) {
        var estadoCss = escaparHtml(card.estado_css || "mapa-cama--sin-asignacion");
        return (
          '<article class="historial-card historial-card-timeline ' + estadoCss + '">' +
          '<div class="historial-card-time">' + escaparHtml(formatearFechaHoraCorta(card.fecha)) + "</div>" +
          "<h4>" + escaparHtml(card.titulo || "") + "</h4>" +
          '<div class="historial-card-subtitulo">' + escaparHtml(card.subtitulo || "") + "</div>" +
          '<div class="historial-card-linea"><strong>Estado:</strong> ' + escaparHtml(card.estado || "") + "</div>" +
          '<div class="historial-card-linea"><strong>Paciente:</strong> ' + escaparHtml(card.paciente || "Sin paciente") + "</div>" +
          '<div class="historial-card-linea"><strong>Usuario:</strong> ' + escaparHtml(card.usuario || "") + "</div>" +
          '<div class="historial-card-linea">' + escaparHtml(card.detalle_1 || "") + "</div>" +
          '<div class="historial-card-linea">' + escaparHtml(card.detalle_2 || "") + "</div>" +
          '<div class="historial-card-linea">' + escaparHtml(card.detalle_3 || "") + "</div>" +
          (card.observacion ? '<div class="historial-card-observacion">' + escaparHtml(card.observacion) + "</div>" : "") +
          "</article>"
        );
      }).join("") + "</div>";

      contenedor.innerHTML = htmlTimeline;
      return;
    }

    var html = cards.map(function (card) {
      var estadoCss = estadoCssDesdeTexto(card.estado);
      return (
        '<article class="historial-card ' + estadoCss + '">' +
        "<h4>" + escaparHtml(card.titulo || "") + "</h4>" +
        '<div class="historial-card-subtitulo">' + escaparHtml(card.subtitulo || "") + "</div>" +
        '<div class="historial-card-linea"><strong>Estado:</strong> ' + escaparHtml(card.estado || "") + "</div>" +
        '<div class="historial-card-linea"><strong>Paciente:</strong> ' + escaparHtml(card.paciente || "Sin paciente") + "</div>" +
        '<div class="historial-card-linea"><strong>Usuario:</strong> ' + escaparHtml(card.usuario || "") + "</div>" +
        '<div class="historial-card-linea"><strong>Fecha:</strong> ' + escaparHtml(formatearFechaHoraCorta(card.fecha)) + "</div>" +
        '<div class="historial-card-linea">' + escaparHtml(card.detalle_1 || "") + "</div>" +
        '<div class="historial-card-linea">' + escaparHtml(card.detalle_2 || "") + "</div>" +
        '<div class="historial-card-linea">' + escaparHtml(card.detalle_3 || "") + "</div>" +
        (card.observacion ? '<div class="historial-card-observacion">' + escaparHtml(card.observacion) + "</div>" : "") +
        "</article>"
      );
    }).join("");

    contenedor.innerHTML = html;
  }

  function cargarDetalle() {
    var params = new URLSearchParams(window.location.search || "");
    var tipo = (params.get("tipo") || "").toLowerCase();
    var id = (params.get("id") || "").trim();

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
    fetch(API_URLS.cards + "?" + query.toString())
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (!data.ok) {
          toastr.error(data.error || "No se pudo cargar el detalle.", "Error");
          renderVacio("No se pudo cargar el detalle solicitado.");
          return;
        }
        estructuraCache = data.estructura || [];
        flatItemsCache = aplanarEstructura(estructuraCache);
        renderEstructuraMapeo(estructuraCache);
        contenedor.innerHTML = "";
        inicializarTablaDetalle();
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
    return {
      fechaInicio: fechaIni,
      fechaFin: fechaFin,
      estado: ""
    };
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
    if (filtros.estado && String(item.estado || "").toLowerCase() !== filtros.estado) {
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

  function poblarFiltroEstado(items) {
    if (!dtfEstado) return;
    var estados = [];
    items.forEach(function (item) {
      var e = String(item.estado || "").trim();
      if (e && estados.indexOf(e) === -1) estados.push(e);
    });
    estados.sort();
    var opciones = '<option value="">Todos</option>';
    estados.forEach(function (e) {
      opciones += '<option value="' + escaparHtml(e) + '">' + escaparHtml(e) + '</option>';
    });
    dtfEstado.innerHTML = opciones;
  }

  function inicializarTablaDetalle() {
    if (tablaDt || !(window.$ && $.fn && $.fn.DataTable)) {
      return;
    }

    tablaDt = $("#tabla-detalle-camas").DataTable({
      responsive: true,
      processing: false,
      serverSide: false,
      paging: true,
      lengthMenu: [10, 25, 50, 100],
      pageLength: 10,
      ordering: false,
      searching: false,
      info: true,
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
            return formatearFechaHoraCorta(data);
          }
        },
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
    if (tablaDt) {
      tablaDt.clear();
      if (items && items.length) {
        tablaDt.rows.add(items);
      }
      tablaDt.draw();
      return;
    }

    if (!tablaBody) {
      return;
    }

    tablaBody.innerHTML = (items || []).length
      ? (items || []).map(function (item) {
          return (
            "<tr>" +
            "<td>" + escaparHtml(item.numero_cama || "") + "</td>" +
            "<td>" + escaparHtml(item.estado || "") + "</td>" +
            "<td>" + escaparHtml(item.paciente || "Sin paciente") + "</td>" +
            "<td>" + escaparHtml(item.dni || "") + "</td>" +
            "<td>" + escaparHtml(item.tipo_accion || "") + "</td>" +
            "<td>" + escaparHtml(formatearFechaHoraCorta(item.fecha)) + "</td>" +
            "<td>" + escaparHtml(item.usuario || "") + "</td>" +
            "</tr>"
          );
        }).join("")
      : '<tr><td colspan="7">Sin resultados para los filtros seleccionados.</td></tr>';
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

  cargarDetalle();
});
