(function($) {
    $(function() {
        $('.vDateField').each(function() {
            var $this = $(this);

            // Read the value rendered by Django (e.g. "14-01-2026")
            var currentVal = $this.val();

            // Ensure datepicker uses dd-mm-yy
            if ($this.hasClass('hasDatepicker')) {
                $this.datepicker('option', 'dateFormat', 'dd-mm-yy');
            } else if ($this.datepicker) {
                $this.datepicker({ dateFormat: 'dd-mm-yy' });
            }

            // Re-apply the current value so the widget keeps it
            if (currentVal) {
                $this.val(currentVal);
            }
        });
    });
})(grp && grp.jQuery ? grp.jQuery : django.jQuery);
