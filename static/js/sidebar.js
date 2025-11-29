document.addEventListener('DOMContentLoaded', function() {
  var toggleButtons = document.querySelectorAll('.sidebar-toggle');
  var sidebar = document.getElementById('sidebar');
  toggleButtons.forEach(function(button) {
    button.addEventListener('click', function(event) {
      event.preventDefault();
      sidebar.classList.toggle('is-active');
    });
  });
});
