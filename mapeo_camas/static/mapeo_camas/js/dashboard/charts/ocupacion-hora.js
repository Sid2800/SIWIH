/* =========================================================================
   Chart: Ocupación por hora (línea, día actual)
   Fecha: 2026-05-28
   ========================================================================= */
(function (global) {
  "use strict";

  let chart = null;

  function init(elId) {
    if (typeof ApexCharts === "undefined") return;
    const el = document.getElementById(elId);
    if (!el) return;
    chart = new ApexCharts(el, {
      chart: { type: "line", height: 280, toolbar: { show: false }, animations: { enabled: false } },
      series: [{ name: "Ocupación %", data: [] }],
      xaxis: { categories: [] },
      stroke: { curve: "smooth", width: 2 },
      colors: ["#0ea5e9"],
      yaxis: { min: 0, max: 100, labels: { formatter: (v) => Math.round(v) + "%" } },
      dataLabels: { enabled: false },
      markers: { size: 3 },
      noData: { text: "Sin datos" },
    });
    chart.render();
  }

  function update(data) {
    if (!chart || !data) return;
    const items = data.items || [];
    chart.updateOptions({ xaxis: { categories: items.map((i) => i.hora) } });
    chart.updateSeries([{ name: "Ocupación %", data: items.map((i) => i.porcentaje) }]);
  }

  global.DashboardChartOcupacionHora = { init, update };
})(window);
