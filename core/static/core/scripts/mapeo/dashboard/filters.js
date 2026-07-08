/* =========================================================================
   Dashboard Mapeo de Camas — filtro mensual fase 1
   Fecha: 2026-06-16
   ========================================================================= */
(function (global) {
  "use strict";

  const STORAGE_KEY = "mapeoCamas.dashboard.filtro.mensual";

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function monthVal(d) {
    return d.getFullYear() + "-" + pad(d.getMonth() + 1);
  }

  function parseMonth(v) {
    if (!v) return null;
    const parts = String(v).split("-");
    if (parts.length !== 2) return null;
    const y = Number(parts[0]);
    const m = Number(parts[1]);
    if (!Number.isInteger(y) || !Number.isInteger(m) || m < 1 || m > 12) return null;
    return new Date(y, m - 1, 1);
  }

  function monthStart(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1, 0, 0, 0);
  }

  function monthEnd(d) {
    return new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59);
  }

  function resolveHasta(mesHasta) {
    const finMes = monthEnd(mesHasta);
    const now = new Date();
    // [2026-06-26] Si el mes final es el mes actual, cortar al momento actual
    // para evitar inflar horas/dias con proyeccion de dias futuros.
    if (
      mesHasta.getFullYear() === now.getFullYear() &&
      mesHasta.getMonth() === now.getMonth()
    ) {
      return now;
    }
    return finMes;
  }

  function toLocalISO(d) {
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds())
    );
  }

  let state = {
    mesDesde: null,
    mesHasta: null,
  };

  let onChangeCb = null;
  let inpMesDesde = null;
  let inpMesHasta = null;
  let resumenEl = null;

  function ensureDefaults() {
    const now = new Date();
    if (!state.mesDesde) state.mesDesde = monthStart(now);
    if (!state.mesHasta) state.mesHasta = monthStart(now);
    if (state.mesHasta < state.mesDesde) {
      const t = state.mesDesde;
      state.mesDesde = state.mesHasta;
      state.mesHasta = t;
    }
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        mesDesde: state.mesDesde ? monthVal(state.mesDesde) : null,
        mesHasta: state.mesHasta ? monthVal(state.mesHasta) : null,
      }));
    } catch (e) {
      // ignore
    }
  }

  function loadPersisted() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const parsed = JSON.parse(raw);
      if (!parsed) return false;
      state.mesDesde = parseMonth(parsed.mesDesde);
      state.mesHasta = parseMonth(parsed.mesHasta);
      return true;
    } catch (e) {
      return false;
    }
  }

  function refreshUI() {
    ensureDefaults();
    if (inpMesDesde) inpMesDesde.value = monthVal(state.mesDesde);
    if (inpMesHasta) inpMesHasta.value = monthVal(state.mesHasta);
    if (resumenEl) {
      resumenEl.textContent =
        "Meses: " + monthVal(state.mesDesde) + " -> " + monthVal(state.mesHasta);
    }
  }

  function applyFromUI() {
    const m1 = parseMonth(inpMesDesde && inpMesDesde.value);
    const m2 = parseMonth(inpMesHasta && inpMesHasta.value);
    if (!m1 || !m2) return;
    state.mesDesde = m1 <= m2 ? m1 : m2;
    state.mesHasta = m1 <= m2 ? m2 : m1;
    persist();
    refreshUI();
    if (onChangeCb) onChangeCb();
  }

  function init(opts) {
    onChangeCb = (opts && opts.onChange) || null;

    const root = document.querySelector(".dash-filtros");
    if (!root) {
      if (!loadPersisted()) ensureDefaults();
      return;
    }

    inpMesDesde = document.getElementById("dash-filtro-mes-desde");
    inpMesHasta = document.getElementById("dash-filtro-mes-hasta");
    resumenEl = document.getElementById("dash-filtros-resumen");

    if (!loadPersisted()) ensureDefaults();
    refreshUI();

    [inpMesDesde, inpMesHasta].forEach(function (el) {
      if (el) el.addEventListener("change", applyFromUI);
    });
  }

  function getParams() {
    ensureDefaults();
    return {
      desde: toLocalISO(monthStart(state.mesDesde)),
      hasta: toLocalISO(resolveHasta(state.mesHasta)),
      agrupacion: "mensual",
    };
  }

  function getResumen() {
    ensureDefaults();
    return "Meses: " + monthVal(state.mesDesde) + " -> " + monthVal(state.mesHasta);
  }

  global.DashboardFilters = { init, getParams, getResumen };
})(window);
