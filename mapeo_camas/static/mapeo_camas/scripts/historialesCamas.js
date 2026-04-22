document.addEventListener("DOMContentLoaded", function () {
  var API_URLS = {
    camas: "/mapeo-camas/api/historiales/camas/",
    data: "/mapeo-camas/api/historiales/data/",
    detalle: "/mapeo-camas/historiales/detalle/",
    mapa: "/mapeo-camas/"
  };

  var filtroTipo = null;
  var filtroCama = null;
  var filtroFechaInicio = null;
  var filtroFechaFin = null;
  var tablaDt = null;

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

  function irADetalle(idRegistro) {
    var tipo = (filtroTipo && filtroTipo.value) ? filtroTipo.value.toLowerCase() : "mapeo";
    var params = new URLSearchParams({ tipo: tipo, id: String(idRegistro || "") });
    window.location.href = API_URLS.detalle + "?" + params.toString();
  }

  function toggleFiltroCama() {
    if (!filtroTipo || !filtroCama) {
      return;
    }
    var tipo = (filtroTipo.value || "mapeo").toLowerCase();
    var deshabilitar = tipo === "mapeo";
    filtroCama.disabled = deshabilitar;
    if (deshabilitar) {
      filtroCama.value = "";
    }
  }

  function paramsBusqueda() {
    var params = new URLSearchParams();
    params.append("tipo", (filtroTipo && filtroTipo.value) ? filtroTipo.value : "mapeo");

    if (filtroFechaInicio && filtroFechaInicio.value) {
      params.append("fecha_inicio", filtroFechaInicio.value);
    }
    if (filtroFechaFin && filtroFechaFin.value) {
      params.append("fecha_fin", filtroFechaFin.value);
    }
    if (filtroCama && filtroCama.value) {
      params.append("cama_id", filtroCama.value);
    }

    return params;
  }

  function renderTabla(results) {
    if (tablaDt) {
      tablaDt.clear();
      if (results && results.length) {
        tablaDt.rows.add(results);
      }
      tablaDt.draw();
      return;
    }

    // Fallback por si DataTables no esta cargado.
    var tablaBody = document.getElementById("tabla-historiales-body");
    if (!tablaBody) {
      return;
    }

    if (!results || !results.length) {
      tablaBody.innerHTML = '<tr><td colspan="8">No hay resultados para los filtros seleccionados.</td></tr>';
      return;
    }

    tablaBody.innerHTML = results.map(function (row) {
      return (
        '<tr data-id="' + escaparHtml(row.id) + '" title="Doble clic para ver detalle">' +
        "<td>" + escaparHtml(row.referencia || "") + "</td>" +
        "<td>" + escaparHtml(row.tipo || "") + "</td>" +
        "<td>" + escaparHtml(row.estado || "") + "</td>" +
        "<td>" + escaparHtml(formatearFechaHoraCorta(row.fecha_principal)) + "</td>" +
        "<td>" + escaparHtml(row.usuario || "") + "</td>" +
        "</tr>"
      );
    }).join("");

    var filas = tablaBody.querySelectorAll("tr[data-id]");
    filas.forEach(function (fila) {
      fila.addEventListener("dblclick", function () {
        irADetalle(this.getAttribute("data-id"));
      });
    });
  }

  function cargarTabla() {
    var params = paramsBusqueda();
    fetch(API_URLS.data + "?" + params.toString())
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (!data.ok) {
          toastr.error(data.error || "Error al consultar historiales.", "Error");
          return;
        }
        renderTabla(data.results || []);
      })
      .catch(function () {
        toastr.error("No se pudo cargar la tabla de historiales.", "Error");
      });
  }

  function limpiarFiltros() {
    if (!filtroTipo || !filtroCama || !filtroFechaInicio || !filtroFechaFin) {
      return;
    }

    var hoyDate = new Date();
    var hace30DiasDate = new Date();
    hace30DiasDate.setDate(hoyDate.getDate() - 30);

    filtroTipo.value = "mapeo";
    filtroCama.value = "";
    filtroFechaInicio.value = hace30DiasDate.toISOString().split("T")[0];
    filtroFechaFin.value = hoyDate.toISOString().split("T")[0];

    toggleFiltroCama();
    cargarTabla();
  }

  function construirControlesFiltro() {
    var fechasFiltro = document.querySelector(".fechasfiltro");
    if (!fechasFiltro || fechasFiltro.dataset.ready === "1") {
      return;
    }

    fechasFiltro.dataset.ready = "1";

    var labelTipo = document.createElement("label");
    labelTipo.textContent = "Tipo";
    labelTipo.htmlFor = "filtro-tipo";
    fechasFiltro.appendChild(labelTipo);

    filtroTipo = document.createElement("select");
    filtroTipo.id = "filtro-tipo";
    filtroTipo.className = "formularioCampo-select";
    filtroTipo.innerHTML = [
      '<option value="mapeo">DetalleMapeoCama</option>',
      '<option value="historial">HistorialEstadoCama</option>',
      '<option value="movimiento">MovimientoCama</option>'
    ].join("");
    fechasFiltro.appendChild(filtroTipo);

    var labelCama = document.createElement("label");
    labelCama.textContent = "Cama";
    labelCama.htmlFor = "filtro-cama";
    fechasFiltro.appendChild(labelCama);

    filtroCama = document.createElement("select");
    filtroCama.id = "filtro-cama";
    filtroCama.className = "formularioCampo-select";
    filtroCama.innerHTML = '<option value="">Todas</option>';
    fechasFiltro.appendChild(filtroCama);

    var hoyDate = new Date();
    var hace30DiasDate = new Date();
    hace30DiasDate.setDate(hoyDate.getDate() - 30);
    var hoy = hoyDate.toISOString().split("T")[0];
    var hace30Dias = hace30DiasDate.toISOString().split("T")[0];

    var labelIni = document.createElement("label");
    labelIni.textContent = "Fecha Ini";
    labelIni.htmlFor = "filtro-fecha-inicio";
    fechasFiltro.appendChild(labelIni);

    filtroFechaInicio = document.createElement("input");
    filtroFechaInicio.type = "date";
    filtroFechaInicio.id = "filtro-fecha-inicio";
    filtroFechaInicio.className = "formularioCampo-date";
    filtroFechaInicio.value = hace30Dias;
    fechasFiltro.appendChild(filtroFechaInicio);

    var labelFin = document.createElement("label");
    labelFin.textContent = "Fecha Fin";
    labelFin.htmlFor = "filtro-fecha-fin";
    fechasFiltro.appendChild(labelFin);

    filtroFechaFin = document.createElement("input");
    filtroFechaFin.type = "date";
    filtroFechaFin.id = "filtro-fecha-fin";
    filtroFechaFin.className = "formularioCampo-date";
    filtroFechaFin.value = hoy;
    fechasFiltro.appendChild(filtroFechaFin);

    filtroTipo.addEventListener("change", function () {
      toggleFiltroCama();
      cargarTabla();
    });
    filtroCama.addEventListener("change", function () {
      cargarTabla();
    });
    filtroFechaInicio.addEventListener("change", function () {
      cargarTabla();
    });
    filtroFechaFin.addEventListener("change", function () {
      cargarTabla();
    });

    toggleFiltroCama();
  }

  function cargarFiltroCamas() {
    fetch(API_URLS.camas)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (!data.ok || !filtroCama) {
          return;
        }

        var opciones = '<option value="">Todas</option>';
        (data.results || []).forEach(function (item) {
          opciones += '<option value="' + escaparHtml(item.id) + '">Cama ' + escaparHtml(item.numero_cama) + " - " + escaparHtml(item.ubicacion) + "</option>";
        });
        filtroCama.innerHTML = opciones;
      })
      .catch(function () {
        // Si falla catálogo, se mantiene la opción por defecto.
      });
  }

  function inicializarDataTable() {
    if (!(window.$ && $.fn && $.fn.DataTable)) {
      return;
    }

    tablaDt = $("#tabla-historiales").DataTable({
      responsive: true,
      processing: true,
      serverSide: false,
      lengthMenu: [10, 25, 50, 100],
      pageLength: 10,
      ordering: false,
      searching: true,
      select: { style: "single" },
      data: [],
      columns: [
        { data: "referencia", defaultContent: "", responsivePriority: 1 },
        { data: "tipo", defaultContent: "", responsivePriority: 2 },
        { data: "estado", defaultContent: "", responsivePriority: 3 },
        {
          data: "fecha_principal",
          defaultContent: "",
          responsivePriority: 4,
          render: function (data) {
            return formatearFechaHoraCorta(data);
          }
        },
        { data: "usuario", defaultContent: "", responsivePriority: 5 }
      ],
      createdRow: function (row, data) {
        row.setAttribute("data-id", String(data.id || ""));
        row.setAttribute("title", "Doble clic para ver detalle");
      },
      language: {
        lengthMenu: "Mostrar _MENU_ por página",
        zeroRecords: "No se encontraron resultados",
        info: "_START_ a _END_ de _TOTAL_ registros",
        infoEmpty: "0 a 0 de 0 registros",
        infoFiltered: "(filtrado de _MAX_)",
        search: "Buscar:",
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
      dom: '<"superior "B<"fechasfiltro">>t<"inferior"lip><"clear">',
      buttons: [
        {
          text: '<i class="bi bi-arrow-left-circle boton-exportacion"></i>',
          titleAttr: "Volver al mapa de camas",
          action: function () {
            window.location.href = API_URLS.mapa;
          }
        },
        {
          text: '<i class="bi bi-search boton-exportacion"></i>',
          titleAttr: "Buscar",
          action: function () {
            cargarTabla();
          }
        },
        {
          text: '<i class="bi bi-eraser boton-exportacion"></i>',
          titleAttr: "Limpiar filtros",
          action: function () {
            limpiarFiltros();
          }
        }
      ],
      columnDefs: [
        { targets: 0, className: "PrimerColumnaAliIzq" },
        { targets: 3, className: "ColumnaFechaCortaIngreso" }
      ]
    });

    construirControlesFiltro();

    $("#tabla-historiales tbody")
      .off("click.historial dblclick.historial")
      .on("click.historial", "tr", function () {
        $("#tabla-historiales tbody tr").removeClass("selected");
        $(this).addClass("selected");
      })
      .on("dblclick.historial", "tr", function () {
        var idRegistro = this.getAttribute("data-id");
        if (idRegistro) {
          irADetalle(idRegistro);
        }
      });
  }

  inicializarDataTable();
  construirControlesFiltro();
  cargarFiltroCamas();
  cargarTabla();
});
