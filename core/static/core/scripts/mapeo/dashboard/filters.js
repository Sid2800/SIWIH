/* =========================================================================
   Dashboard Mapeo de Camas — filtro temporal
   Fecha: 2026-05-28
   Expone window.DashboardFilters con:
     - init({ onChange })   Inicializa UI, dispara onChange al aplicar
     - getParams()          Devuelve {desde, hasta} en formato ISO local
     - getResumen()         Texto humano del rango activo
   ========================================================================= */
(function (global) {
  "use strict";

  const STORAGE_KEY = "mapeoCamas.dashboard.filtro";

  // --- Helpers de fecha (todo en hora local) ---------------------------------
  function startOfDay(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  function endOfDay(d) {
    const x = new Date(d);
    x.setHours(23, 59, 59, 999);
    return x;
  }
  function addDays(d, n) {
    const x = new Date(d);
    x.setDate(x.getDate() + n);
    return x;
  }
  function startOfWeek(d) {
    // Lunes como inicio (ISO).
    const x = startOfDay(d);
    const day = (x.getDay() + 6) % 7; // 0 = lunes
    x.setDate(x.getDate() - day);
    return x;
  }
  function startOfMonth(d) {
    const x = new Date(d.getFullYear(), d.getMonth(), 1, 0, 0, 0, 0);
    return x;
  }
  function endOfMonth(d) {
    const x = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);
    return x;
  }
  function pad(n) { return String(n).padStart(2, "0"); }
  function toLocalISO(d) {
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds())
    );
  }
  function toInputValue(d) {
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }
  function fromInputValue(v) {
    if (!v) return null;
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }

  // --- Presets ---------------------------------------------------------------
  function rangoPreset(preset) {
    const now = new Date();
    switch (preset) {
      case "hoy":              return [startOfDay(now), now];
      case "ayer": {
        const a = addDays(startOfDay(now), -1);
        return [a, endOfDay(a)];
      }
      case "ultimas-24h":      return [addDays(now, -1), now];
      case "esta-semana":      return [startOfWeek(now), now];
      case "semana-pasada": {
        const inicio = addDays(startOfWeek(now), -7);
        const fin = endOfDay(addDays(inicio, 6));
        return [inicio, fin];
      }
      case "este-mes":         return [startOfMonth(now), now];
      case "mes-pasado": {
        const inicio = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        return [inicio, endOfMonth(inicio)];
      }
      case "ultimos-7":        return [startOfDay(addDays(now, -6)), now];
      case "ultimos-30":       return [startOfDay(addDays(now, -29)), now];
      default:                 return [startOfDay(now), now]; // fallback
    }
  }

  function labelPreset(preset) {
    const labels = {
      "hoy": "Hoy",
      "ayer": "Ayer",
      "ultimas-24h": "Últimas 24h",
      "esta-semana": "Esta semana",
      "semana-pasada": "Semana pasada",
      "este-mes": "Este mes",
      "mes-pasado": "Mes pasado",
      "ultimos-7": "Últimos 7 días",
      "ultimos-30": "Últimos 30 días",
      "personalizado": "Personalizado",
    };
    return labels[preset] || preset;
  }

  function fmtHuman(d) {
    return d.toLocaleString([], {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  }

  // --- Estado y persistencia -------------------------------------------------
  let state = {
    preset: "hoy",
    desde: null,
    hasta: null,
  };

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        preset: state.preset,
        desde: state.desde ? toLocalISO(state.desde) : null,
        hasta: state.hasta ? toLocalISO(state.hasta) : null,
      }));
    } catch (e) { /* ignore */ }
  }

  function loadPersisted() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.preset) return false;
      state.preset = parsed.preset;
      if (parsed.preset === "personalizado" && parsed.desde && parsed.hasta) {
        state.desde = new Date(parsed.desde);
        state.hasta = new Date(parsed.hasta);
      } else {
        const [d, h] = rangoPreset(parsed.preset);
        state.desde = d; state.hasta = h;
      }
      return true;
    } catch (e) { return false; }
  }

  // --- DOM -------------------------------------------------------------------
  let onChangeCb = null;
  let chips = [];
  let rangoWrap = null;
  let inpDesde = null;
  let inpHasta = null;
  let btnAplicar = null;
  let resumenEl = null;

  function refreshUI() {
    chips.forEach((c) => {
      c.classList.toggle("is-active", c.dataset.preset === state.preset);
    });
    if (rangoWrap) rangoWrap.hidden = state.preset !== "personalizado";
    if (state.preset === "personalizado") {
      if (inpDesde && state.desde) inpDesde.value = toInputValue(state.desde);
      if (inpHasta && state.hasta) inpHasta.value = toInputValue(state.hasta);
    }
    if (resumenEl) {
      const titulo = labelPreset(state.preset);
      resumenEl.textContent =
        titulo + " · " + fmtHuman(state.desde) + " → " + fmtHuman(state.hasta);
    }
  }

  function applyPreset(preset) {
    state.preset = preset;
    if (preset !== "personalizado") {
      const [d, h] = rangoPreset(preset);
      state.desde = d; state.hasta = h;
    }
    persist();
    refreshUI();
    if (preset !== "personalizado" && onChangeCb) onChangeCb();
  }

  function applyCustom() {
    const d = fromInputValue(inpDesde && inpDesde.value);
    const h = fromInputValue(inpHasta && inpHasta.value);
    if (!d || !h) return;
    state.preset = "personalizado";
    state.desde = d <= h ? d : h;
    state.hasta = d <= h ? h : d;
    persist();
    refreshUI();
    if (onChangeCb) onChangeCb();
  }

  function init(opts) {
    onChangeCb = (opts && opts.onChange) || null;
    const root = document.querySelector(".dash-filtros");
    if (!root) {
      // Sin UI: usar default hoy.
      if (!loadPersisted()) applyPreset("hoy");
      return;
    }
    chips = Array.from(root.querySelectorAll(".dash-chip"));
    rangoWrap = document.getElementById("dash-filtros-rango");
    inpDesde = document.getElementById("dash-filtro-desde");
    inpHasta = document.getElementById("dash-filtro-hasta");
    btnAplicar = document.getElementById("dash-filtro-aplicar");
    resumenEl = document.getElementById("dash-filtros-resumen");

    if (!loadPersisted()) {
      const [d, h] = rangoPreset("hoy");
      state.desde = d; state.hasta = h;
    }
    refreshUI();

    chips.forEach((c) => {
      c.addEventListener("click", () => applyPreset(c.dataset.preset));
    });
    if (btnAplicar) btnAplicar.addEventListener("click", applyCustom);
  }

  function getParams() {
    return {
      desde: state.desde ? toLocalISO(state.desde) : null,
      hasta: state.hasta ? toLocalISO(state.hasta) : null,
    };
  }

  function getResumen() {
    if (!state.desde || !state.hasta) return "";
    return labelPreset(state.preset) + " · " +
      fmtHuman(state.desde) + " → " + fmtHuman(state.hasta);
  }

  global.DashboardFilters = { init, getParams, getResumen };
})(window);
