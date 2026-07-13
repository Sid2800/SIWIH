/* =========================================================================
   Dashboard Mapeo de Camas — tabla de ultimos ingresos
   Fecha: 2026-06-16
   ========================================================================= */
(function (global) {
  "use strict";

  let tbodyId = null;

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function init(elId) {
    tbodyId = elId;
  }

  function update(data) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    const items = (data && data.items) || [];
    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="dash-muted" style="text-align:center;padding:1rem;">Sin ingresos recientes</td></tr>';
      return;
    }

    tbody.innerHTML = items
      .map(function (m) {
        return (
          "<tr>" +
            "<td>" + escapeHtml(m.fecha) + "</td>" +
            "<td>" + escapeHtml(m.tipo || "OCUPADA") + "</td>" +
            "<td>" + escapeHtml(m.cama_destino || "-") + "</td>" +
            "<td>" + escapeHtml(m.paciente || "-") + "</td>" +
            "<td>" + escapeHtml(m.servicio || "-") + "</td>" +
            "<td>" + escapeHtml(m.usuario || "-") + "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  global.DashboardTablaIngresos = { init, update };
})(window);
