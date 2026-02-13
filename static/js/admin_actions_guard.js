// Guard for Django admin actions.js on changelist pages
document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('changelist-form');
    if (!form) return;  // not a changelist

    // Ensure select-all checkbox with id="action-toggle" exists
    var toggle = document.getElementById('action-toggle');
    if (!toggle) {
        toggle = document.createElement('input');
        toggle.type = 'checkbox';
        toggle.id = 'action-toggle';
        toggle.className = 'action-select';  // matches Django CSS, harmless
        toggle.style.display = 'none';
        form.insertBefore(toggle, form.firstChild);

    }

    // Optional: ensure an <select name="action"> exists
    var select = form.querySelector('select[name="action"]');
    if (!select) {
        select = document.createElement('select');
        select.name = 'action';
        select.style.display = 'none';
        form.insertBefore(select, toggle.nextSibling);

    }
});
