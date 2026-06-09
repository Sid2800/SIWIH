/* =========================================================================
   Chart: Ocupación por servicio (barras)
   Fecha: 2026-05-28
   ========================================================================= */
(function (global) {
  "use strict";

  let chart = null;
  let containerId = null;

  function ensureApex() {
    if (typeof ApexCharts === "undefined") {
      console.warn("[dashboard] ApexCharts no está cargado");
      return false;
    }
    return true;
  }

  function init(elId) {
    containerId = elId;
    if (!ensureApex()) return;
    const el = document.getElementById(elId);
    if (!el) return;
    chart = new ApexCharts(el, {
      chart: { type: "bar", height: 280, toolbar: { show: false }, animations: { enabled: false } },
      series: [{ name: "Ocupadas", data: [] }, { name: "Disponibles", data: [] }],
      xaxis: { categories: [] },
      colors: ["#ef4444", "#22c55e"],
      plotOptions: { bar: { horizontal: false, columnWidth: "55%", borderRadius: 4 } },
      stroke: { width: 0 },
      dataLabels: { enabled: false },
      legend: { position: "top" },
      noData: { text: "Sin datos" },
    });
    chart.render();
  }

  function update(data) {
    if (!chart || !data) return;
    const items = data.items || [];
    chart.updateOptions({
      xaxis: { categories: items.map((i) => i.servicio) },
    });
    chart.updateSeries([
      { name: "Ocupadas", data: items.map((i) => i.ocupadas) },
      { name: "Disponibles", data: items.map((i) => i.disponibles) },
    ]);
  }

  global.DashboardChartOcupacionServicio = { init, update };
})(window);
