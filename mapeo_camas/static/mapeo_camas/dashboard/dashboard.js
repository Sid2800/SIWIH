/* =========================================================================
   Dashboard Mapeo de Camas — orquestador local sin comparaciones
   Fecha: 2026-06-15
   ========================================================================= */
(function () {
  "use strict";

  const REFRESH_MS = 30000;
  const cfg = window.DASHBOARD_CFG || {};
  const api = window.DashboardAPI;
  if (!api) {
    console.error("[dashboard] DashboardAPI no disponible");
    return;
  }
  const endpoints = api.makeEndpoints(cfg.urls || {});

  let timer = null;
  let inflight = null;

  function setState(cardId, state) {
    const card = document.getElementById(cardId);
    if (!card) return;
    ["loading", "empty", "err"].forEach(function (s) {
      const node = card.querySelector('.dash-state[data-state="' + s + '"]');
      if (node) node.classList.toggle("is-active", s === state);
    });
  }

  async function load(panel, url, onOk) {
    const cards = [panel.card].concat(panel.extraCards || []);
    cards.forEach(function (c) { setState(c, "loading"); });
    try {
      const payload = await api.fetchJson(url, { signal: inflight && inflight.signal });
      const data = (payload && payload.data) || payload;
      onOk(data);
      const empty = panel.isEmpty ? panel.isEmpty(data) : false;
      cards.forEach(function (c) { setState(c, empty ? "empty" : null); });
    } catch (err) {
      console.error("[dashboard]", panel.card, err);
      cards.forEach(function (c) {
        const node = document.querySelector('#' + c + ' .dash-state[data-state="err"]');
        if (node) node.textContent = "Error: " + (err.message || "desconocido");
        setState(c, "err");
      });
    }
  }

  async function loadAll() {
    if (inflight) inflight.abort();
    inflight = new AbortController();

    const updatedAt = document.getElementById("dash-updated-at");
    if (updatedAt) updatedAt.textContent = "Actualizando…";

    const params = (window.DashboardFilters && window.DashboardFilters.getParams()) || {};
    const withP = function (url) {
      return api.withParams ? api.withParams(url, params) : url;
    };
    const ultimosIngresosUrl = ((cfg.urls && cfg.urls.ultimosIngresos) || "") + "?limit=30";

    await Promise.allSettled([
      load(
        { card: "card-kpis", extraCards: ["card-estados-resumen"] },
        withP(endpoints.kpis()),
        function (data) {
          window.DashboardKpis && window.DashboardKpis.update(data);
          window.DashboardChartEstadosResumen && window.DashboardChartEstadosResumen.update(data);
        }
      ),
      load(
        { card: "card-ocupacion-hora", isEmpty: function (d) { return !d || !(d.items || []).length; } },
        withP(endpoints.ocupacionHora()),
        function (data) {
          window.DashboardChartOcupacionHora && window.DashboardChartOcupacionHora.update(data);
        }
      ),
      load(
        { card: "card-tabla-ingresos", isEmpty: function (d) { return !d || !(d.items || []).length; } },
        withP(ultimosIngresosUrl),
        function (data) {
          window.DashboardTablaIngresos && window.DashboardTablaIngresos.update(data);
        }
      ),
      load(
        { card: "card-tabla-movimientos", isEmpty: function (d) { return !d || !(d.items || []).length; } },
        withP(endpoints.ultimosMovimientos(30)),
        function (data) {
          window.DashboardTablaMovimientos && window.DashboardTablaMovimientos.update(data);
        }
      )
    ]);

    if (updatedAt) {
      updatedAt.textContent = "Actualizado " + new Date().toLocaleTimeString();
    }
  }

  function start() {
    stop();
    loadAll();
    timer = setInterval(loadAll, REFRESH_MS);
  }

  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  function initCardCollapse() {
    // 2026-06-16: Replica patrón de mapa para colapsar/expandir cards del dashboard.
    const buttons = document.querySelectorAll("[data-card-collapse]");
    buttons.forEach(function (btn) {
      const controlsId = btn.getAttribute("aria-controls");
      const body = controlsId ? document.getElementById(controlsId) : null;
      const card = btn.closest(".dash-card");
      if (!body || !card) return;

      btn.addEventListener("click", function () {
        const collapsed = card.classList.toggle("dash-card--colapsado");
        body.style.display = collapsed ? "none" : "";
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        btn.title = collapsed ? "Expandir card" : "Colapsar card";
        btn.innerHTML = collapsed
          ? '<i class="bi bi-chevron-down" aria-hidden="true"></i><span>Expandir</span>'
          : '<i class="bi bi-chevron-up" aria-hidden="true"></i><span>Colapsar</span>';
      });
    });
  }

  function bootstrap() {
    initCardCollapse();
    window.DashboardChartEstadosResumen && window.DashboardChartEstadosResumen.init("chart-estados-resumen");
    window.DashboardChartOcupacionHora && window.DashboardChartOcupacionHora.init("chart-ocupacion-hora");
    window.DashboardTablaIngresos && window.DashboardTablaIngresos.init("tabla-ingresos-body");
    window.DashboardTablaMovimientos && window.DashboardTablaMovimientos.init("tabla-movimientos-body");

    const btn = document.getElementById("dash-refresh-btn");
    if (btn) btn.addEventListener("click", loadAll);

    const btnExcel = document.getElementById("dash-export-excel-btn");
    if (btnExcel) {
      btnExcel.addEventListener("click", function () {
        const params = (window.DashboardFilters && window.DashboardFilters.getParams()) || {};
        const exportUrl = (cfg.urls && cfg.urls.exportOcupacionExcel) || "";
        if (!exportUrl) return;
        const finalUrl = api.withParams ? api.withParams(exportUrl, params) : exportUrl;
        window.location.href = finalUrl;
      });
    }

    if (window.DashboardFilters) {
      window.DashboardFilters.init({ onChange: loadAll });
    }

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop();
      else start();
    });

    start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
