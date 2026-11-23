/* Small, dependency-free helpers. Every core action still works without this file. */

(function () {
  "use strict";

  function toast(message) {
    var el = document.getElementById("toast");
    if (!el || !message) return;
    el.textContent = message;
    el.hidden = false;
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      el.hidden = true;
    }, 4200);
  }

  // Confirm destructive submissions once, at the form level.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });

  // Print the brief from a normal button (inline scripts are blocked by CSP).
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (target instanceof Element && target.closest("[data-print]")) {
      event.preventDefault();
      window.print();
    }
  });

  // A tiny status line for query-string outcomes.
  var params = new URLSearchParams(window.location.search);
  if (params.get("saved") === "1") toast("Saved.");

  // HTMX failures should be visible, not silent.
  document.addEventListener("htmx:responseError", function () {
    toast("That action did not go through. Reload and try again.");
  });
  document.body.addEventListener("app-error", function (event) {
    var detail = event.detail || {};
    toast(detail.value || detail.message || "That action did not go through.");
  });

  window.keystoneToast = toast;
})();
