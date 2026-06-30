// Progressive enhancement: make filter forms apply on change.
//
// Forms marked with `data-auto-submit` resubmit (GET) as soon as any <select>
// inside them changes, so admins don't have to reach for the "Apply" button.
// The button stays in the markup as a no-JS fallback; we hide any element
// tagged `data-auto-submit-hide` once this script runs.
(function () {
  "use strict";

  function enhance(form) {
    form.querySelectorAll("select").forEach(function (select) {
      select.addEventListener("change", function () {
        form.submit();
      });
    });
    form.querySelectorAll("[data-auto-submit-hide]").forEach(function (el) {
      el.hidden = true;
    });
  }

  document.querySelectorAll("form[data-auto-submit]").forEach(enhance);
})();
