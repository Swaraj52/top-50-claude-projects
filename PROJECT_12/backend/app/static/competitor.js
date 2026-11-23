/* Competitor Research Dashboard - HTMX interactions */

document.addEventListener('DOMContentLoaded', function() {
  // Handle competitor add success
  document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail && event.detail.successful) {
      // Clear the form after successful add
      var form = event.detail.target;
      if (form && form.querySelector('input[name="name"]')) {
        form.querySelector('input[name="name"]').value = '';
        form.querySelector('input[name="website"]').value = '';
        form.querySelector('textarea[name="positioning"]').value = '';
      }
    }
  });
  
  // Handle competitor delete
  document.body.addEventListener('click', function(event) {
    if (event.target.classList.contains('delete-link')) {
      event.preventDefault();
      if (confirm('Are you sure you want to delete this opportunity note?')) {
        var row = event.target.closest('li');
        if (row) {
          htmx.trigger('deleteEntry', { entryId: row.dataset.entryId });
        }
      }
    }
  });
  
  // Handle deleteEntry event
  document.body.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail && event.detail.successful && event.detail.target.classList.contains('entry-row')) {
      var row = event.detail.target;
      if (row.parentNode) {
        row.parentNode.removeChild(row);
      }
    }
  });
});