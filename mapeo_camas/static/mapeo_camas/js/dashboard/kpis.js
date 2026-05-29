/* =========================================================================
   Dashboard Mapeo de Camas — render de KPIs
   Fecha: 2026-05-28
   ========================================================================= */
(function (global) {
  "use strict";

  const FIELD_TO_ID = {
    total_camas: "kpi-total-camas",
    ocupadas: "kpi-ocupadas",
    disponibles: "kpi-disponibles",
    fuera_servicio: "kpi-fuera-servicio",
    porcentaje_ocupacion: "kpi-porcentaje-ocupacion",
    altas_dia: "kpi-altas-dia",
    traslados: "kpi-traslados",
    cambios_mapeo: "kpi-cambios-mapeo",
    camas_validadas: "kpi-camas-validadas",
    tiempo_promedio: "kpi-tiempo-promedio",
  };

  function fmt(value, suffix = "") {
    if (value === null || value === undefined) return "—";
    return String(value) + suffix;
  }

  function update(data) {
    if (!data) return;
    Object.entries(FIELD_TO_ID).forEach(([field, id]) => {
      const el = document.getElementById(id);
      if (!el) return;
      let val = data[field];
      if (field === "porcentaje_ocupacion") val = fmt(val, "%");
      else if (field === "tiempo_promedio") val = fmt(val);
      else val = fmt(val);
      el.textContent = val;
    });

    // Barra de ocupación
    const bar = document.getElementById("kpi-ocupacion-bar");
    const wrap = document.getElementById("kpi-ocupacion-progress-wrap");
    const pct = Number(data.porcentaje_ocupacion) || 0;
    if (bar) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
    if (wrap) wrap.setAttribute("aria-valuenow", String(pct));
  }

  function showError(msg) {
    Object.values(FIELD_TO_ID).forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = "—";
    });
    const errBox = document.getElementById("dash-kpis-error");
    if (errBox) {
      errBox.textContent = msg || "Error cargando KPIs";
      errBox.classList.add("is-active");
    }
  }

  function clearError() {
    const errBox = document.getElementById("dash-kpis-error");
    if (errBox) errBox.classList.remove("is-active");
  }

  global.DashboardKpis = { update, showError, clearError };
})(window);
