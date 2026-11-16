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

  // A tiny status line for query-string outcomes.
  var params = new URLSearchParams(window.location.search);
  if (params.get("saved") === "1") toast("Saved.");

  // HTMX failures should be visible, not silent.
  document.addEventListener("htmx:responseError", function () {
    toast("That action did not go through. Reload and try again.");
  });

  // "/" focuses search, unless the user is already typing somewhere.
  document.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) return;
    var search = document.getElementById("q-top") || document.getElementById("q-home") || document.getElementById("q");
    if (search) {
      event.preventDefault();
      search.focus();
    }
  });

  window.loomToast = toast;
})();
