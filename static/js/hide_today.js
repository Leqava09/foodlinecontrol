document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        var shortcuts = document.querySelectorAll('span.datetimeshortcuts');

        shortcuts.forEach(function (el) {
            el.style.display = 'none';
        });
    }, 50);  // 0.05 seconds
});