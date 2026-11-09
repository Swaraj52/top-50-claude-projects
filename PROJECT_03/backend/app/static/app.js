// Progressive enhancements. Every feature also works without this file.
(function () {
  'use strict';

  function toast(message, tone) {
    var box = document.getElementById('toasts');
    if (!box) return;
    var el = document.createElement('div');
    el.className = 'toast' + (tone ? ' ' + tone : '');
    el.setAttribute('role', tone === 'error' ? 'alert' : 'status');
    el.textContent = message;
    box.appendChild(el);
    setTimeout(function () { el.remove(); }, tone === 'error' ? 6000 : 3000);
  }

  // Server errors on HTMX requests arrive as an "app-error" event (HX-Trigger header).
  document.body.addEventListener('app-error', function (e) {
    toast((e.detail && e.detail.value) || 'Something went wrong', 'error');
  });
  document.body.addEventListener('htmx:sendError', function () {
    toast('Can’t reach the server. Is it running?', 'error');
  });

  // Browser timezone for new accounts.
  document.querySelectorAll('[data-browser-timezone]').forEach(function (input) {
    try { input.value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { /* keep UTC */ }
  });

  // Timezone suggestions in Settings.
  document.querySelectorAll('[data-fill-timezones]').forEach(function (list) {
    if (!Intl.supportedValuesOf) return;
    Intl.supportedValuesOf('timeZone').forEach(function (z) {
      var o = document.createElement('option');
      o.value = z;
      list.appendChild(o);
    });
  });

  // Confirmation for destructive non-HTMX submits (HTMX uses hx-confirm).
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-confirm]');
    if (btn && !window.htmx && !window.confirm(btn.getAttribute('data-confirm'))) e.preventDefault();
  });

  // Picking a date selects the "Later" option for that row.
  document.addEventListener('change', function (e) {
    if (!e.target.classList.contains('later-date')) return;
    var radio = e.target.parentElement.querySelector('input[type=radio]');
    if (radio && e.target.value) radio.checked = true;
  });

  // Small confirmation after HTMX saves.
  document.body.addEventListener('htmx:afterSwap', function (e) {
    var id = e.detail.target && e.detail.target.id;
    if (id === 'checkin') toast('Check-in saved');
  });
})();
