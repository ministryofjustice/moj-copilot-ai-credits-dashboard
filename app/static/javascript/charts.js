// Renders Chart.js charts from a JSON block the server embeds in the page.
//
// The page includes:
//   <script type="application/json" id="chart-data">{ "<name>": <spec>, ... }</script>
//   <canvas data-chart="<name>"></canvas>
// where each <spec> is a normalised Chart.js shape:
//   { "type": "bar"|"line", "labels": [...], "datasets": [{ "label": "...", "data": [...] }] }
//
// No app data lives in JS — the server owns the numbers; this just draws them.
(function () {
  "use strict";

  var GOVUK_BLUE = "#1d70b8";
  var GOVUK_GREEN = "#00703c";

  function dataEl() {
    return document.getElementById("chart-data");
  }

  function colour(i) {
    return [GOVUK_BLUE, GOVUK_GREEN, "#4c2c92", "#d4351c", "#f47738", "#85994b"][
      i % 6
    ];
  }

  function build(canvas, spec) {
    var type = spec.type || "bar";
    var labels = spec.labels || [];
    var datasets = (spec.datasets || []).map(function (ds, i) {
      return {
        type: type,
        label: ds.label || "",
        data: ds.data || [],
        backgroundColor: type === "line" ? "transparent" : colour(i),
        borderColor: colour(i),
        borderWidth: 2,
        tension: 0.2,
        pointRadius: type === "line" ? 2 : 0,
      };
    });

    // Optional dashed reference line at a fixed value (e.g. an allowance limit).
    if (spec.limit && typeof spec.limit.value === "number") {
      datasets.push({
        type: "line",
        label: spec.limit.label || "Limit",
        data: labels.map(function () {
          return spec.limit.value;
        }),
        borderColor: "#d4351c",
        borderDash: [6, 6],
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
      });
    }

    new Chart(canvas.getContext("2d"), {
      type: type,
      data: { labels: spec.labels || [], datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: datasets.length > 1 } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = dataEl();
    if (!el || typeof Chart === "undefined") {
      return;
    }
    var data;
    try {
      data = JSON.parse(el.textContent);
    } catch (e) {
      return;
    }
    document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
      var spec = data[canvas.dataset.chart];
      if (spec) {
        build(canvas, spec);
      }
    });
  });
})();
