/* =========================================================================
   Dashboard Mapeo de Camas — tabla de movimientos local
   Fecha: 2026-06-16
  Ajusta render para mostrar origen -> destino y lenguaje de movimientos.
   ========================================================================= */
(function (global) {
  "use strict";

  if (!global.DashboardTablaMovimientos) return;

  const base = global.DashboardTablaMovimientos;

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function formatoCama(m) {
    const origen = m && m.cama_origen ? String(m.cama_origen) : "";
    const destino = m && m.cama_destino ? String(m.cama_destino) : "";
    if (origen && destino) return origen + " -> " + destino;
    return destino || origen || "-";
  }

  function update(data) {
    const tbodyId = (function () {
      // No expone internals; buscamos el tbody por id estandar del dashboard.
      return "tabla-movimientos-body";
    })();
    const tbody = document.getElementById(tbodyId);
    if (!tbody) {
      base.update && base.update(data);
      return;
    }

    const items = (data && data.items) || [];
    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="dash-muted" style="text-align:center;padding:1rem;">Sin movimientos recientes</td></tr>';
      return;
    }

    tbody.innerHTML = items
      .map(function (m) {
        return (
          "<tr>" +
            "<td>" + escapeHtml(m.fecha) + "</td>" +
            "<td>" + escapeHtml(m.tipo || "MOVIMIENTO") + "</td>" +
            "<td>" + escapeHtml(formatoCama(m)) + "</td>" +
            "<td>" + escapeHtml(m.paciente || "-") + "</td>" +
            "<td>" + escapeHtml(m.servicio || "-") + "</td>" +
            "<td>" + escapeHtml(m.usuario || "-") + "</td>" +
          "</tr>"
        );
      })
      .join("");
  }

  global.DashboardTablaMovimientos = {
    init: base.init,
    update: update,
  };
})(window);
