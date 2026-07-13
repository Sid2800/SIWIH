/* =========================================================================
  Tabla últimos ingresos (datos de mapeo)
  Fecha: 2026-05-28
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
      .replace(/"/g, "&quot;");
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
      .map(
        (m) => `
        <tr>
          <td>${escapeHtml(m.fecha)}</td>
          <td>${escapeHtml(m.tipo)}</td>
          <td>${escapeHtml(m.cama_destino || m.cama_origen || "—")}</td>
          <td>${escapeHtml(m.paciente || "—")}</td>
          <td>${escapeHtml(m.servicio || "—")}</td>
          <td>${escapeHtml(m.usuario || "—")}</td>
        </tr>`
      )
      .join("");
  }

  global.DashboardTablaMovimientos = { init, update };
})(window);
