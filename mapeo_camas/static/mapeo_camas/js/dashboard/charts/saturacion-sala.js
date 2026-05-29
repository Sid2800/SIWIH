/* =========================================================================
   Chart: Saturación por sala (heatmap)
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
      chart: { type: "heatmap", height: 280, toolbar: { show: false }, animations: { enabled: false } },
      series: [],
      dataLabels: { enabled: true, style: { fontSize: "10px" } },
      colors: ["#0ea5e9"],
      plotOptions: {
        heatmap: {
          shadeIntensity: 0.5,
          radius: 4,
          useFillColorAsStroke: false,
          colorScale: {
            ranges: [
              { from: 0, to: 25, color: "#dcfce7", name: "Bajo" },
              { from: 26, to: 60, color: "#fef9c3", name: "Medio" },
              { from: 61, to: 85, color: "#fed7aa", name: "Alto" },
              { from: 86, to: 100, color: "#fee2e2", name: "Saturado" },
            ],
          },
        },
      },
      noData: { text: "Sin datos" },
    });
    chart.render();
  }

  function update(data) {
    if (!chart || !data) return;
    const series = (data.series || []).map((s) => ({
      name: s.servicio,
      data: (s.salas || []).map((sala) => ({ x: sala.sala, y: sala.porcentaje })),
    }));
    chart.updateSeries(series);
  }

  global.DashboardChartSaturacionSala = { init, update };
})(window);
