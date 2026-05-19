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
  var ultimaFilaSeleccionada = "";

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

  // [2026-05-06 FIX] Primer clic selecciona fila; segundo clic en la misma fila navega al detalle.
  function debeNavegarPorSegundoClick(idRegistro) {
    var id = String(idRegistro || "");
    if (!id) {
      return false;
    }
    if (ultimaFilaSeleccionada === id) {
      return true;
    }
    ultimaFilaSeleccionada = id;
    return false;
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

  function normalizarFiltroCama() {
    if (!filtroCama || !filtroCama.value) {
      return "";
    }
    var valor = String(filtroCama.value).trim();
    var match = valor.match(/\d+/);
    return match ? match[0] : valor;
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
    var camaBuscada = normalizarFiltroCama();
    if (camaBuscada) {
      params.append("cama_id", camaBuscada);
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
      fila.addEventListener("click", function () {
        tablaBody.querySelectorAll("tr[data-id]").forEach(function (tr) { tr.classList.remove("selected"); });
        this.classList.add("selected");
        var idRegistro = this.getAttribute("data-id");
        if (debeNavegarPorSegundoClick(idRegistro)) {
          irADetalle(idRegistro);
        }
      });
      fila.addEventListener("dblclick", function () {
        var idRegistro = this.getAttribute("data-id");
        if (idRegistro) {
          irADetalle(idRegistro);
        }
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
    sessionStorage.setItem("historiales_filtro_tipo", "mapeo");
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
      '<option value="mapeo">Detalle Mapeo</option>',
      '<option value="historial">Historial Estado</option>',
      '<option value="movimiento">Movimientos</option>'
    ].join("");
    // Restaurar tipo guardado en sesión anterior
    var tipoGuardado = sessionStorage.getItem("historiales_filtro_tipo");
    if (tipoGuardado) {
      filtroTipo.value = tipoGuardado;
    }
    fechasFiltro.appendChild(filtroTipo);

    var labelCama = document.createElement("label");
    labelCama.textContent = "Cama";
    labelCama.htmlFor = "filtro-cama";
    fechasFiltro.appendChild(labelCama);

    filtroCama = document.createElement("input");
    filtroCama.type = "text";
    filtroCama.id = "filtro-cama";
    filtroCama.className = "formularioCampo-select";
    filtroCama.placeholder = "Buscar cama (ej: 101)";
    filtroCama.setAttribute("list", "historiales-camas-list");
    fechasFiltro.appendChild(filtroCama);

    // Datalist fuera del grid para no ocupar celda y desalinear los controles
    var listaCamas = document.createElement("datalist");
    listaCamas.id = "historiales-camas-list";
    document.body.appendChild(listaCamas);

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
      sessionStorage.setItem("historiales_filtro_tipo", filtroTipo.value);
      toggleFiltroCama();
      cargarTabla();
    });
    var timerBusquedaCama = null;
    filtroCama.addEventListener("input", function () {
      if (timerBusquedaCama) {
        clearTimeout(timerBusquedaCama);
      }
      timerBusquedaCama = setTimeout(function () {
        cargarTabla();
      }, 260);
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

        var dataList = document.getElementById("historiales-camas-list");
        if (!dataList) {
          return;
        }

        var opciones = "";
        (data.results || []).forEach(function (item) {
          opciones += '<option value="' + escaparHtml(item.numero_cama) + '">Cama ' + escaparHtml(item.numero_cama) + " - " + escaparHtml(item.ubicacion) + "</option>";
        });
        dataList.innerHTML = opciones;
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
      serverSide: false,
      lengthMenu: [10, 25, 50, 100],
      pageLength: 10,
      ordering: false,
      searching: true,
      data: [],
      columns: [
        { data: "referencia", defaultContent: "", className: "all" },
        { data: "tipo", defaultContent: "", className: "all" },
        { data: "estado", defaultContent: "", className: "all" },
        {
          data: "servicios",
          defaultContent: "",
          className: "none",
          orderable: false,
          render: function (data, type) {
            if (type !== "display") {
              return Array.isArray(data) ? data.join(", ") : "";
            }
            if (!data || !data.length) {
              return '<span class="hist-sin-servicios">—</span>';
            }
            return data.map(function (s) {
              return '<span class="hist-servicio-chip">' + escaparHtml(s) + '</span>';
            }).join("");
          }
        },
        {
          data: "fecha_principal",
          defaultContent: "",
          className: "none",
          render: function (data) {
            return formatearFechaHoraCorta(data);
          }
        },
        { data: "usuario", defaultContent: "", className: "none" }
      ],
      createdRow: function (row, data) {
        row.setAttribute("data-id", String(data.id || ""));
        row.setAttribute("title", "Clic para seleccionar · doble clic para abrir detalle");
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

    // Navegar al detalle al hacer clic en una fila, incluyendo filas-child de DataTables responsive.
    // [2026-05-06 FIX] Primer clic selecciona y expande datos ocultos (responsive); segundo clic navega.
    function resolverFilaDt(tr) {
      var targetTr = tr.hasClass("child") ? tr.prev("tr") : tr;
      var row = tablaDt.row(targetTr);
      return row.data() ? row : null;
    }

    function expandirFilaResponsive(row, trPadre) {
      if (!row || !trPadre || !trPadre.length) {
        return;
      }
      if (!row.child.isShown()) {
        row.child.show();
        trPadre.addClass("parent");
      }
    }

    $("#tabla-historiales tbody")
      .off("click.historial dblclick.historial keydown.historial")
      .on("click.historial", "tr", function (e) {
        // Ignorar clic en fila child (el padre ya maneja todo)
        if ($(this).hasClass("child")) {
          $(this).prev("tr").trigger("click.historial");
          return;
        }
        var row = resolverFilaDt($(this));
        if (!row) {
          return;
        }
        $("#tabla-historiales tbody tr").removeClass("selected");
        $(this).addClass("selected");

        var rowData = row.data();
        var idRegistro = String((rowData && rowData.id) || "");
        if (debeNavegarPorSegundoClick(idRegistro)) {
          irADetalle(idRegistro);
        } else {
          expandirFilaResponsive(row, $(this));
        }
      })
      .on("dblclick.historial", "tr", function (e) {
        // Navegar al detalle al hacer doble clic
        var row = resolverFilaDt($(this));
        if (!row) {
          return;
        }
        var rowData = row.data();
        var idRegistro = String(rowData.id || "");
        if (!idRegistro) {
          return;
        }
        irADetalle(idRegistro);
      })
      .on("keydown.historial", "tr", function (event) {
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        event.preventDefault();
        var row = resolverFilaDt($(this));
        if (row && row.data() && row.data().id) {
          irADetalle(String(row.data().id));
        }
      });
  }

  inicializarDataTable();
  cargarFiltroCamas();
  cargarTabla();
});
