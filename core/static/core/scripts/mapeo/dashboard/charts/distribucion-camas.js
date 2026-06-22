/* =========================================================================
   Chart: Distribución global por estado (donut)
   Fecha: 2026-05-28
   ========================================================================= */
(function (global) {
  "use strict";

  let chart = null;

  // Colores alineados con la paleta de estados del repo (mapa-cama--*).
  const COLOR_POR_ESTADO = {
    OCUPADA: "#ef4444",
    VACIA: "#22c55e",
    LIBRE: "#22c55e",
    ALTA: "#facc15",
    PRE_ALTA: "#facc15",
    FUERA_SERVICIO: "#475569",
    MANTENIMIENTO: "#475569",
    CONSULTA_EXTERNA: "#3b82f6",
  };

  function colorPara(estado) {
    return COLOR_POR_ESTADO[estado] || "#94a3b8";
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
      legend: { position: "bottom" },
      dataLabels: { enabled: true },
      noData: { text: "Sin datos" },
    });
    chart.render();
  }

  function update(data) {
    if (!chart || !data) return;
    const items = data.items || [];
    chart.updateOptions({
      labels: items.map((i) => i.estado),
      colors: items.map((i) => colorPara(i.estado)),
    });
    chart.updateSeries(items.map((i) => i.cantidad));
  }

  global.DashboardChartDistribucionCamas = { init, update };
})(window);
