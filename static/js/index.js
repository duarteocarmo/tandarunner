document.addEventListener("DOMContentLoaded", function () {
  const visualizations = JSON.parse(
    document.getElementById("visualizations").textContent
  );

  const vega_theme = "default";

  Object.keys(visualizations).forEach(function (key) {
    const spec = JSON.parse(visualizations[key]);
    vegaEmbed("#" + key, spec, {
      renderer: "svg",
      actions: false,
      theme: vega_theme,
    });
  });
});
