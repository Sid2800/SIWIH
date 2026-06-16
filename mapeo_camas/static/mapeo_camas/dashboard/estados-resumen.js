/* =========================================================================
   Chart: Resumen de estados completo (todos los estados)
   Fecha: 2026-06-15
   ========================================================================= */
(function (global) {
  "use strict";

  let chart = null;

  // 2026-06-15: orden fijo para visualizar siempre todo el catalogo de estados.
  const ORDERED_CODES = [
    "OCUPADA",
    "PRE_ALTA",
    "ALTA",
    "VACIA",
    "LIBRE",
    "FUERA_SERVICIO",
    "MANTENIMIENTO",
    "CONSULTA_EXTERNA",
  ];

  const CODE_ALIASES = {
    PREALTA: "PRE_ALTA",
    "PRE-ALTA": "PRE_ALTA",
    "PRE ALTA": "PRE_ALTA",
    FUERA_DE_SERVICIO: "FUERA_SERVICIO",
    "FUERA-SERVICIO": "FUERA_SERVICIO",
    "FUERA SERVICIO": "FUERA_SERVICIO",
    CONSULTAEXTERNA: "CONSULTA_EXTERNA",
    "CONSULTA-EXTERNA": "CONSULTA_EXTERNA",
    "CONSULTA EXTERNA": "CONSULTA_EXTERNA",
  };

  const LABELS = {
    OCUPADA: "Ocupada",
    VACIA: "Vacia",
    LIBRE: "Libre",
    ALTA: "Alta",
    PRE_ALTA: "Pre alta",
    FUERA_SERVICIO: "Fuera servicio",
    MANTENIMIENTO: "Mantenimiento",
    CONSULTA_EXTERNA: "Consulta externa",
  };

  const COLORS = {
    OCUPADA: "#ef4444",
    VACIA: "#22c55e",
    LIBRE: "#16a34a",
    ALTA: "#facc15",
    PRE_ALTA: "#eab308",
    FUERA_SERVICIO: "#475569",
    MANTENIMIENTO: "#64748b",
    CONSULTA_EXTERNA: "#3b82f6",
  };

  function labelFor(code) {
    return LABELS[code] || String(code || "SIN_ESTADO");
  }

  function colorFor(code) {
    return COLORS[code] || "#94a3b8";
  }

  function normalizeCode(code) {
    const raw = String(code || "").trim().toUpperCase();
    if (!raw) return "SIN_ESTADO";
    if (CODE_ALIASES[raw]) return CODE_ALIASES[raw];
    return raw;
  }

  function init(elId) {
    if (typeof ApexCharts === "undefined") return;
    const el = document.getElementById(elId);
    if (!el) return;

    chart = new ApexCharts(el, {
      chart: { type: "donut", height: 280, animations: { enabled: false } },
      series: [],
      labels: [],
      colors: [],
      legend: { position: "bottom", fontSize: "12px" },
      dataLabels: { enabled: true },
      noData: { text: "Sin datos" },
      tooltip: {
        y: {
          formatter: function (val) {
            return String(val) + " camas";
          }
        }
      }
    });
    chart.render();
  }

  function update(data) {
    if (!chart || !data) return;

    const estados = data.estados || {};
    const merged = {};

    Object.keys(estados).forEach(function (key) {
      const norm = normalizeCode(key);
      merged[norm] = (merged[norm] || 0) + (Number(estados[key]) || 0);
    });

    ORDERED_CODES.forEach(function (code) {
      if (merged[code] === undefined) merged[code] = 0;
    });

    const orderedKnown = ORDERED_CODES.map(function (code) {
      return { estado: code, cantidad: merged[code] || 0 };
    });

    const unknown = Object.keys(merged)
      .filter(function (code) {
        return ORDERED_CODES.indexOf(code) === -1;
      })
      .sort()
      .map(function (code) {
        return { estado: code, cantidad: merged[code] || 0 };
      });

    const entries = orderedKnown.concat(unknown);

    chart.updateOptions({
      labels: entries.map(function (i) { return labelFor(i.estado); }),
      colors: entries.map(function (i) { return colorFor(i.estado); }),
    });
    chart.updateSeries(entries.map(function (i) { return i.cantidad; }));

    const total = Number(data.total_camas) || 0;
    const pill = document.getElementById("estados-resumen-total");
    if (pill) pill.textContent = total + " camas";
  }

  global.DashboardChartEstadosResumen = { init, update };
})(window);
