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
  var GOVUK_RED = "#d4351c";

  function dataEl() {
    return document.getElementById("chart-data");
  }

  function colour(i) {
    return [GOVUK_BLUE, GOVUK_GREEN, "#4c2c92", "#d4351c", "#f47738", "#85994b"][
      i % 6
    ];
  }

  function build(canvas, spec) {
    if (spec.type === "treemap") {
      buildTreemap(canvas, spec);
      return;
    }
    var type = spec.type || "bar";
    var labels = spec.labels || [];
    // Optional: a single point (e.g. the selected day) drawn as a larger red
    // marker. Chart.js reads point styling per-index when given arrays.
    var highlight =
      type === "line" && typeof spec.highlight === "number"
        ? spec.highlight
        : null;

    var datasets = (spec.datasets || []).map(function (ds, i) {
      var data = ds.data || [];
      // A dataset may override its series colour (e.g. a muted grey for a
      // prior-period comparison line); otherwise fall back to the palette.
      var col = ds.color || colour(i);
      var ds_out = {
        type: type,
        label: ds.label || "",
        data: data,
        backgroundColor: type === "line" ? "transparent" : col,
        borderColor: col,
        borderWidth: 2,
        tension: 0.2,
        pointRadius: type === "line" ? 2 : 0,
      };
      if (ds.dash) {
        ds_out.borderDash = [6, 6];
      }
      if (ds.spanGaps) {
        ds_out.spanGaps = true;
      }
      if (highlight !== null) {
        ds_out.pointRadius = data.map(function (_, j) {
          return j === highlight ? 5 : 2;
        });
        ds_out.pointBackgroundColor = data.map(function (_, j) {
          return j === highlight ? GOVUK_RED : col;
        });
        ds_out.pointBorderColor = ds_out.pointBackgroundColor;
      }
      return ds_out;
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

    // The x-axis labels are terse so a whole month fits across the chart. When
    // the server also sends full dates, the tooltip shows those instead — it
    // has the room, and "Mon 01 Jun 2026" beats a bare "1".
    var tips = spec.tooltip_labels;
    var tooltip = Array.isArray(tips)
      ? {
          callbacks: {
            title: function (items) {
              var i = items.length ? items[0].dataIndex : -1;
              return tips[i] !== undefined ? tips[i] : "";
            },
          },
        }
      : {};

    new Chart(canvas.getContext("2d"), {
      type: type,
      data: { labels: spec.labels || [], datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: datasets.length > 1 },
          tooltip: tooltip,
        },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  function buildTreemap(canvas, spec) {
    var tiles = spec.tiles || [];
    var total =
      spec.total ||
      tiles.reduce(function (s, t) {
        return s + t.amount;
      }, 0);

    // The treemap plugin sorts tiles by value, so ctx.dataIndex does NOT match
    // the original `tiles` order — read the source object from ctx.raw._data.
    function tileData(ctx) {
      return ctx && ctx.raw && ctx.raw._data ? ctx.raw._data : null;
    }

    function tileLine(t) {
      var pct = total ? (t.amount / total) * 100 : 0;
      var lines = [t.name];
      if (t.users !== null && t.users !== undefined) {
        lines.push(t.users + " users");
      }
      lines.push(pct.toFixed(1) + "%");
      lines.push(
        Math.round(t.amount).toLocaleString() +
          " AI Credits · $" +
          Math.round(t.amount / 100).toLocaleString()
      );
      return lines;
    }

    new Chart(canvas.getContext("2d"), {
      type: "treemap",
      data: {
        datasets: [
          {
            tree: tiles,
            key: "amount",
            borderColor: "#ffffff",
            borderWidth: 2,
            spacing: 1,
            backgroundColor: function (ctx) {
              var t = tileData(ctx);
              return ctx.type === "data" && t ? t.colour : "transparent";
            },
            labels: {
              display: true,
              color: "#ffffff",
              font: { size: 14 },
              formatter: function (ctx) {
                var t = tileData(ctx);
                return t ? tileLine(t) : "";
              },
            },
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: { display: !!spec.root, text: spec.root || "" },
          tooltip: {
            callbacks: {
              title: function () {
                return "";
              },
              label: function (ctx) {
                var t = tileData(ctx);
                return t ? tileLine(t).join(" · ") : "";
              },
            },
          },
        },
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
