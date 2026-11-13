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

  document.body.addEventListener('app-error', function (e) {
    toast((e.detail && e.detail.value) || 'Something went wrong', 'error');
  });
  document.body.addEventListener('htmx:sendError', function () {
    toast('Cannot reach the server. Is it running?', 'error');
  });

  // Browser time zone for new accounts, so "today" starts on the right day.
  document.querySelectorAll('[data-browser-timezone]').forEach(function (input) {
    try { input.value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { /* keep UTC */ }
  });

  // Time zone suggestions in Settings.
  document.querySelectorAll('[data-fill-timezones]').forEach(function (list) {
    if (!Intl.supportedValuesOf) return;
    Intl.supportedValuesOf('timeZone').forEach(function (z) {
      var o = document.createElement('option');
      o.value = z;
      list.appendChild(o);
    });
  });

  // Confirmation before destructive submissions.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    var message = form.getAttribute('data-confirm-form');
    if (!message || form.dataset.confirmed === 'true') return;
    if (!window.confirm(message)) {
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    form.dataset.confirmed = 'true';
  }, true);

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-confirm]');
    if (btn && !window.confirm(btn.getAttribute('data-confirm'))) {
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    var print = e.target.closest('[data-print]');
    if (print) window.print();
  }, true);

  // Let saved reflections and settings notices fade after a while; they stay in the DOM for screen readers.
  var notice = document.querySelector('.notice.success');
  if (notice) {
    setTimeout(function () { notice.classList.add('notice-faded'); }, 6000);
  }
})();
