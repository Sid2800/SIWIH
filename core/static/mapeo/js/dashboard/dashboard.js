/* =========================================================================
   Dashboard Mapeo de Camas — orquestador
   Fecha: 2026-05-28

   Punto de inyección para WebSocket:
   ----------------------------------
   Hoy cada panel se actualiza con DashboardAPI.fetchJson(url).
   Para migrar a WebSocket en el futuro, reemplazar dentro de loadAll()
   las llamadas a fetchJson por DashboardAPI.subscribe(topic, callback)
   y registrar los mismos módulos (KPIs, Charts, Tabla). Los módulos
   exponen `update(data)`, por lo que el contrato no cambia.
   ========================================================================= */
(function () {
  "use strict";

  const REFRESH_MS = 30000;

  // El template inyecta window.DASHBOARD_CFG con la URL base de la API.
  const cfg = window.DASHBOARD_CFG || {};
  const api = window.DashboardAPI;
  if (!api) {
    console.error("[dashboard] DashboardAPI no disponible");
    return;
  }
  const endpoints = api.makeEndpoints(cfg.apiBase || "");

  let timer = null;
  let inflight = null;

  function setState(cardId, state) {
    const card = document.getElementById(cardId);
    if (!card) return;
    ["loading", "empty", "err"].forEach((s) => {
      const node = card.querySelector('.dash-state[data-state="' + s + '"]');
      if (node) node.classList.toggle("is-active", s === state);
    });
  }

  async function load(panel, url, onOk) {
    const cards = [panel.card].concat(panel.extraCards || []);
    cards.forEach((c) => setState(c, "loading"));
    try {
      const payload = await api.fetchJson(url, { signal: inflight && inflight.signal });
      const data = (payload && payload.data) || payload;
      onOk(data);
      const empty = panel.isEmpty ? panel.isEmpty(data) : false;
      cards.forEach((c) => setState(c, empty ? "empty" : null));
    } catch (err) {
      console.error("[dashboard]", panel.card, err);
      cards.forEach((c) => {
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

    // [2026-05-28] Inyectar filtro temporal en cada endpoint.
    const params = (window.DashboardFilters && window.DashboardFilters.getParams()) || {};
    const withP = (url) => api.withParams ? api.withParams(url, params) : url;

    await Promise.allSettled([
      load(
        { card: "card-kpis", extraCards: ["card-estados-resumen"] },
        withP(endpoints.kpis()),
        (data) => {
          // KPIs y resumen radial comparten el mismo payload de /kpis/.
          window.DashboardKpis && window.DashboardKpis.update(data);
          window.DashboardChartEstadosResumen && window.DashboardChartEstadosResumen.update(data);
        }
      ),
      load(
        { card: "card-ocupacion-servicio", isEmpty: (d) => !d || !(d.items || []).length },
        withP(endpoints.ocupacionServicio()),
        (data) => window.DashboardChartOcupacionServicio && window.DashboardChartOcupacionServicio.update(data)
      ),
      load(
        { card: "card-distribucion-camas", isEmpty: (d) => !d || !(d.items || []).length },
        withP(endpoints.distribucionCamas()),
        (data) => window.DashboardChartDistribucionCamas && window.DashboardChartDistribucionCamas.update(data)
      ),
      load(
        { card: "card-ocupacion-hora", isEmpty: (d) => !d || !(d.items || []).length },
        withP(endpoints.ocupacionHora()),
        (data) => window.DashboardChartOcupacionHora && window.DashboardChartOcupacionHora.update(data)
      ),
      load(
        { card: "card-saturacion-sala", isEmpty: (d) => !d || !(d.series || []).length },
        withP(endpoints.saturacionSala()),
        (data) => window.DashboardChartSaturacionSala && window.DashboardChartSaturacionSala.update(data)
      ),
      load(
        { card: "card-tabla-movimientos", isEmpty: (d) => !d || !(d.items || []).length },
        withP(endpoints.ultimosMovimientos(30)),
        (data) => window.DashboardTablaMovimientos && window.DashboardTablaMovimientos.update(data)
      ),
    ]);

    if (updatedAt) {
      const now = new Date();
      updatedAt.textContent = "Actualizado " + now.toLocaleTimeString();
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

  function bootstrap() {
    // Inicializar charts
    window.DashboardChartEstadosResumen && window.DashboardChartEstadosResumen.init("chart-estados-resumen");
    window.DashboardChartOcupacionServicio && window.DashboardChartOcupacionServicio.init("chart-ocupacion-servicio");
    window.DashboardChartDistribucionCamas && window.DashboardChartDistribucionCamas.init("chart-distribucion-camas");
    window.DashboardChartOcupacionHora && window.DashboardChartOcupacionHora.init("chart-ocupacion-hora");
    window.DashboardChartSaturacionSala && window.DashboardChartSaturacionSala.init("chart-saturacion-sala");
    window.DashboardTablaMovimientos && window.DashboardTablaMovimientos.init("tabla-movimientos-body");

    // Botón refrescar manual
    const btn = document.getElementById("dash-refresh-btn");
    if (btn) btn.addEventListener("click", loadAll);

    // [2026-05-28] Filtro temporal: recarga al cambiar el rango.
    if (window.DashboardFilters) {
      window.DashboardFilters.init({ onChange: loadAll });
    }

    // Pausar cuando la pestaña está oculta
    document.addEventListener("visibilitychange", () => {
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
