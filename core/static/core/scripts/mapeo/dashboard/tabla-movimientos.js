/* =========================================================================
  Tabla últimos movimientos (datos de mapeo)
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

  function formatoCama(m) {
    const origen = m && m.cama_origen ? String(m.cama_origen) : "";
    const destino = m && m.cama_destino ? String(m.cama_destino) : "";
    if (origen && destino) return origen + " -> " + destino;
    return destino || origen || "-";
  }

  function update(data) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;
    const items = (data && data.items) || [];
    if (!items.length) {
      // [2026-07-10] Mensaje coherente con el card activo de movimientos.
      tbody.innerHTML =
        '<tr><td colspan="6" class="dash-muted" style="text-align:center;padding:1rem;">Sin movimientos recientes</td></tr>';
      return;
    }
    tbody.innerHTML = items
      .map(
        (m) => `
        <tr>
          <td>${escapeHtml(m.fecha)}</td>
          <td>${escapeHtml(m.tipo || "MOVIMIENTO")}</td>
          <td>${escapeHtml(formatoCama(m))}</td>
          <td>${escapeHtml(m.paciente || "—")}</td>
          <td>${escapeHtml(m.servicio || "—")}</td>
          <td>${escapeHtml(m.usuario || "—")}</td>
        </tr>`
      )
      .join("");
  }

  global.DashboardTablaMovimientos = { init, update };
})(window);
