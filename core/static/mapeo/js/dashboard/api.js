/* =========================================================================
   Dashboard Mapeo de Camas — capa API
   Fecha: 2026-05-28
   Punto único de acceso a backend. Contrato pensado para reemplazar
   fetchJson por una capa subscribe(topic, cb) cuando se migre a WebSocket
   sin tocar los módulos de chart/kpi.
   ========================================================================= */
(function (global) {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 12000;

  function getCsrfToken() {
    const cookie = document.cookie
      .split(";")
      .map((c) => c.trim())
      .find((c) => c.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  /**
   * fetchJson — wrapper de Fetch con timeout, abort y JSON parsing.
   * @param {string} url
   * @param {object} [opts]
   * @param {AbortSignal} [opts.signal]
   * @param {number} [opts.timeout]
   * @returns {Promise<object>}
   */
  async function fetchJson(url, opts = {}) {
    const { signal: externalSignal, timeout = DEFAULT_TIMEOUT_MS, ...rest } = opts;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(new DOMException("timeout", "AbortError")), timeout);

    if (externalSignal) {
      if (externalSignal.aborted) controller.abort();
      else externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }

    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": getCsrfToken(),
          ...(rest.headers || {}),
        },
        ...rest,
        signal: controller.signal,
      });

      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error("Respuesta no JSON (" + response.status + ")");
      }

      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        const msg = (payload && payload.error) || ("HTTP " + response.status);
        const err = new Error(msg);
        err.status = response.status;
        err.payload = payload;
        throw err;
      }
      return payload;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // [2026-05-28] Helper para concatenar querystring sin pisar params existentes.
  function withParams(url, params) {
    if (!params) return url;
    const qs = Object.keys(params)
      .filter((k) => params[k] !== null && params[k] !== undefined && params[k] !== "")
      .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(params[k]))
      .join("&");
    if (!qs) return url;
    return url + (url.indexOf("?") >= 0 ? "&" : "?") + qs;
  }

  // Endpoints centralizados del dashboard.
  // Cualquier cambio de ruta se hace acá. Inyectados al window por dashboard.js.
  function makeEndpoints(baseUrl) {
    const u = (path) => baseUrl.replace(/\/$/, "") + path;
    return {
      kpis: () => u("/kpis/"),
      ocupacionServicio: () => u("/ocupacion-servicio/"),
      distribucionCamas: () => u("/distribucion-camas/"),
      ocupacionHora: () => u("/ocupacion-hora/"),
      saturacionSala: () => u("/saturacion-sala/"),
      ultimosMovimientos: (limit = 30) => u("/ultimos-movimientos/?limit=" + encodeURIComponent(limit)),
    };
  }

  global.DashboardAPI = {
    fetchJson,
    makeEndpoints,
    withParams,
    // Punto de extensión futura para WebSocket:
    // subscribe(topic, cb) → reemplazo de fetchJson en cada módulo.
    subscribe: null,
  };
})(window);
