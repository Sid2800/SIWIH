/* =========================================================================
   Dashboard Mapeo de Camas — KPIs fase 1 (filtro mensual)
   Fecha: 2026-06-16
   ========================================================================= */
(function (global) {
  "use strict";

  const FIELD_TO_ID = {
    total_camas: "kpi-total-camas",
    ocupadas: "kpi-ocupadas",
    disponibles: "kpi-disponibles",
    fuera_servicio: "kpi-fuera-servicio",
    porcentaje_ocupacion: "kpi-porcentaje-ocupacion",
    movimientos: "kpi-movimientos",
    cambios_mapeo: "kpi-cambios-mapeo",
    camas_validadas: "kpi-camas-validadas",
  };

  function fmt(value, suffix) {
    if (value === null || value === undefined) return "—";
    return String(value) + (suffix || "");
  }

  function updateFocusLabels() {
    const l1 = document.getElementById("kpi-label-total-camas");
    const l2 = document.getElementById("kpi-label-ocupadas");
    const l3 = document.getElementById("kpi-label-disponibles");
    if (l1) l1.textContent = "Total camas";
    if (l2) l2.textContent = "Ocupadas";
    if (l3) l3.textContent = "Disponibles";
  }

  function update(data) {
    if (!data) return;

    Object.keys(FIELD_TO_ID).forEach(function (field) {
      const el = document.getElementById(FIELD_TO_ID[field]);
      if (!el) return;
      if (field === "porcentaje_ocupacion") el.textContent = fmt(data[field], "%");
      else el.textContent = fmt(data[field]);
    });

    const bar = document.getElementById("kpi-ocupacion-bar");
    const wrap = document.getElementById("kpi-ocupacion-progress-wrap");
    const pct = Number(data.porcentaje_ocupacion) || 0;
    if (bar) bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
    if (wrap) wrap.setAttribute("aria-valuenow", String(pct));

    updateFocusLabels();
  }

  function showError(msg) {
    Object.keys(FIELD_TO_ID).forEach(function (field) {
      const el = document.getElementById(FIELD_TO_ID[field]);
      if (el) el.textContent = "—";
    });
    const err = document.getElementById("dash-kpis-error");
    if (err) {
      err.textContent = msg || "Error cargando KPIs";
      err.classList.add("is-active");
    }
  }

  function clearError() {
    const err = document.getElementById("dash-kpis-error");
    if (err) err.classList.remove("is-active");
  }

  global.DashboardKpis = { update, showError, clearError, updateFocusLabels };
})(window);
