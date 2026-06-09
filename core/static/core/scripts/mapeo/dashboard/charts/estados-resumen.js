/* =========================================================================
   Chart: Resumen de estados de camas (radialBar)
   Fecha: 2026-05-28
   Reutiliza datos del endpoint /kpis/ (sin llamadas extra).
   Customizing DataLabels: nombre + valor en el centro, leyenda con colores
   alineados a la paleta del sistema (mapa-cama--*).
   ========================================================================= */
(function (global) {
  "use strict";

  // Paleta de estados (alineada con /memories/repo/colores-estado-cama.md)
  const SERIES = [
    { key: "ocupadas",       label: "Ocupadas",        color: "#ef4444" },
    { key: "disponibles",    label: "Disponibles",     color: "#22c55e" },
    { key: "fuera_servicio", label: "Fuera servicio",  color: "#475569" },
  ];

  let chart = null;
  let totalCamas = 0;

  function ensureApex() {
    return typeof ApexCharts !== "undefined";
  }

  function init(elId) {
    if (!ensureApex()) return;
    const el = document.getElementById(elId);
    if (!el) return;

    chart = new ApexCharts(el, {
      chart: {
        type: "radialBar",
        height: 260,
        sparkline: { enabled: false },
        animations: { enabled: false },
      },
      series: SERIES.map(() => 0),
      labels: SERIES.map((s) => s.label),
      colors: SERIES.map((s) => s.color),
      plotOptions: {
        radialBar: {
          startAngle: -135,
          endAngle: 135,
          hollow: {
            margin: 5,
            size: "42%",
            background: "transparent",
          },
          track: {
            background: "#e2e8f0",
            strokeWidth: "100%",
            margin: 4,
          },
          // Customizing the DataLabels appearance (estilo doc ApexCharts).
          dataLabels: {
            name: {
              show: true,
              fontSize: "13px",
              fontWeight: 600,
              color: "#0f172a",
              offsetY: -4,
            },
            value: {
              show: true,
              fontSize: "16px",
              fontWeight: 700,
              color: "#0f172a",
              formatter: function (val) {
                // val es el % de la serie activa.
                return parseFloat(val).toFixed(1) + "%";
              },
            },
            total: {
              show: true,
              label: "Ocupación",
              fontSize: "12px",
              fontWeight: 600,
              color: "#475569",
              formatter: function (w) {
                // Mostramos el % de la serie "Ocupadas" como referencia central.
                const idx = 0; // OCUPADAS
                const v = (w && w.globals && w.globals.series && w.globals.series[idx]) || 0;
                return parseFloat(v).toFixed(1) + "%";
              },
            },
          },
        },
      },
      stroke: { lineCap: "round" },
      legend: {
        show: true,
        position: "bottom",
        fontSize: "12px",
        labels: { colors: "#334155" },
        markers: { radius: 4 },
        itemMargin: { horizontal: 6, vertical: 2 },
        formatter: function (seriesName, opts) {
          const pct = opts.w.globals.series[opts.seriesIndex];
          return seriesName + " · " + parseFloat(pct).toFixed(0) + "%";
        },
      },
      tooltip: {
        enabled: true,
        y: {
          formatter: function (val, opts) {
            const count = Math.round((val / 100) * (totalCamas || 1));
            return parseFloat(val).toFixed(1) + "%  (" + count + " camas)";
          },
        },
      },
    });
    chart.render();
  }

  // Recibe el payload del endpoint /kpis/
  function update(data) {
    if (!chart || !data) return;
    totalCamas = data.total_camas || 0;
    const pct = (n) => totalCamas ? Math.round((n / totalCamas) * 1000) / 10 : 0;

    chart.updateSeries(SERIES.map((s) => pct(data[s.key] || 0)));

    const pill = document.getElementById("estados-resumen-total");
    if (pill) pill.textContent = totalCamas + " camas";
  }

  global.DashboardChartEstadosResumen = { init, update };
})(window);
