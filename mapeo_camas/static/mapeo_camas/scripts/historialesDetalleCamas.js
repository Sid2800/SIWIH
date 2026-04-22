document.addEventListener("DOMContentLoaded", function () {
  var API_URLS = {
    cards: "/mapeo-camas/api/historiales/cards/"
  };

  var contenedor = document.getElementById("detalle-cards-contenedor");
  var estructuraContenedor = document.getElementById("detalle-estructura-contenedor");
  var metaEl = document.getElementById("detalle-meta");
  var btnCopiar = document.getElementById("btn-copiar-detalle");
  var btnImprimir = document.getElementById("btn-imprimir-detalle");

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
    contenedor.innerHTML = '<div class="historial-card-vacia">' + escaparHtml(texto || "Sin datos para mostrar.") + "</div>";
  }

  function renderEstructuraMapeo(estructura) {
    if (!estructuraContenedor) {
      return;
    }

    if (!estructura || !estructura.length) {
      estructuraContenedor.innerHTML = "";
      return;
    }

    var html = estructura.map(function (servicio) {
      var salasHtml = (servicio.salas || []).map(function (sala) {
        var cubiculosHtml = (sala.cubiculos || []).map(function (cubiculo) {
          var camasHtml = (cubiculo.camas || []).map(function (cama) {
            var estadoCss = estadoCssDesdeTexto(cama.estado);
            return (
              '<div class="detalle-cama-item ' + estadoCss + '">' +
              '<strong>Cama ' + escaparHtml(cama.numero_cama || "") + '</strong>' +
              '<div class="detalle-cama-linea"><strong>Estado:</strong> ' + escaparHtml(cama.estado || "") + '</div>' +
              '<div class="detalle-cama-linea"><strong>Paciente:</strong> ' + escaparHtml(cama.paciente || "Sin paciente") + '</div>' +
              '<div class="detalle-cama-linea"><strong>Accion:</strong> ' + escaparHtml(cama.tipo_accion || "") + '</div>' +
              '<div class="detalle-cama-linea"><strong>Usuario:</strong> ' + escaparHtml(cama.usuario || "") + '</div>' +
              '<div class="detalle-cama-linea"><strong>Fecha:</strong> ' + escaparHtml(formatearFechaHoraCorta(cama.fecha)) + '</div>' +
              (cama.observacion ? ('<div class="detalle-cama-linea"><strong>Observacion:</strong> ' + escaparHtml(cama.observacion) + '</div>') : '') +
              "</div>"
            );
          }).join("");

          return (
            '<div class="detalle-bloque" style="margin-top:0.6rem;">' +
            '<div class="detalle-bloque-titulo">Cubiculo: ' + escaparHtml(cubiculo.nombre || "") + "</div>" +
            '<div class="detalle-bloque-contenido"><div class="detalle-camas-grid">' + camasHtml + "</div></div>" +
            "</div>"
          );
        }).join("");

        var directasHtml = (sala.camas_directas || []).map(function (cama) {
          var estadoCss = estadoCssDesdeTexto(cama.estado);
          return (
            '<div class="detalle-cama-item ' + estadoCss + '">' +
            '<strong>Cama ' + escaparHtml(cama.numero_cama || "") + '</strong>' +
            '<div class="detalle-cama-linea"><strong>Estado:</strong> ' + escaparHtml(cama.estado || "") + '</div>' +
            '<div class="detalle-cama-linea"><strong>Paciente:</strong> ' + escaparHtml(cama.paciente || "Sin paciente") + '</div>' +
            '<div class="detalle-cama-linea"><strong>Accion:</strong> ' + escaparHtml(cama.tipo_accion || "") + '</div>' +
            '<div class="detalle-cama-linea"><strong>Usuario:</strong> ' + escaparHtml(cama.usuario || "") + '</div>' +
            '<div class="detalle-cama-linea"><strong>Fecha:</strong> ' + escaparHtml(formatearFechaHoraCorta(cama.fecha)) + '</div>' +
            (cama.observacion ? ('<div class="detalle-cama-linea"><strong>Observacion:</strong> ' + escaparHtml(cama.observacion) + '</div>') : '') +
            "</div>"
          );
        }).join("");

        return (
          '<div class="detalle-bloque" style="margin-top:0.6rem;">' +
          '<div class="detalle-bloque-titulo">Sala: ' + escaparHtml(sala.nombre || "") + "</div>" +
          '<div class="detalle-bloque-contenido">' +
          (directasHtml ? ('<div><strong>Camas directas</strong></div><div class="detalle-camas-grid">' + directasHtml + '</div>') : "") +
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

    metaEl.textContent = "Tipo: " + (tipo || "-") + " | ID: " + (id || "-");

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
        if (tipo === "mapeo") {
          renderEstructuraMapeo(data.estructura || []);
          contenedor.innerHTML = "";
        } else if (estructuraContenedor) {
          estructuraContenedor.innerHTML = "";
          renderCards(data.cards || []);
        }
      })
      .catch(function () {
        toastr.error("No se pudo cargar el detalle en cards.", "Error");
        renderVacio("Error de conexión al consultar detalle.");
      });
  }

  function copiarResumenVisible() {
    var texto = (document.getElementById("detalle-meta")?.innerText || "") + "\n\n" +
      (document.getElementById("detalle-estructura-contenedor")?.innerText || "") + "\n\n" +
      (document.getElementById("detalle-cards-contenedor")?.innerText || "");

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
