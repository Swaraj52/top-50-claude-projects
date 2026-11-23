/* Customer Feedback Analyzer - HTMX interactions */
document.addEventListener('DOMContentLoaded', function() {
  // Handle feedback import success
  document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail && event.detail.successful) {
      // Clear the textarea after successful import
      var textarea = document.querySelector('textarea[name="reviews"]');
      if (textarea) {
        textarea.value = '';
      }
    }
  });
  
  // Handle feedback entry deletion
  document.body.addEventListener('click', function(event) {
    if (event.target.classList.contains('delete-entry')) {
      event.preventDefault();
      if (confirm('Are you sure you want to delete this feedback entry?')) {
        var entryId = event.target.dataset.entryId;
        var button = event.target;
        
        htmx.trigger('deleteEntry', { entryId: entryId });
      }
    }
  });
  
  // Handle deleteEntry event
  document.body.addEventListener('htmx:afterRequest', function(event) {
    if (event.detail && event.detail.successful && event.detail.target.classList.contains('entry-row')) {
      // Remove the deleted row from the DOM
      var row = event.detail.target;
      if (row.parentNode) {
        row.parentNode.removeChild(row);
      }
    }
  });
});