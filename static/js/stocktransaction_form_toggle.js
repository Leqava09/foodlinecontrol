// static/js/stocktransaction_form_toggle.js
// Supplier filtering is now handled by smart-selects ChainedForeignKey on sub_category
(function(jQuery) {
    var $ = jQuery;
    $(document).ready(function() {
        
        function toggleSections() {
            var ttype = $('#id_transaction_type').val();
            if (ttype === 'IN') {
                $('.booking-in-section').show();
                $('.booking-out-section').hide();
            } else if (ttype === 'OUT') {
                $('.booking-in-section').hide();
                $('.booking-out-section').show();
            } else {
                $('.booking-in-section').hide();
                $('.booking-out-section').hide();
            }
        }
        
        // Listen for changes
        $('#id_transaction_type').change(toggleSections);
        
        // Initialize on page load
        toggleSections();
    });
})(django.jQuery);

// Force unit display to be visible
document.addEventListener('DOMContentLoaded', function() {
    const unitDiv = document.querySelector('.unit_of_measure_display');
    if (unitDiv) {
        unitDiv.style.display = 'block';
        unitDiv.style.visibility = 'visible';
        unitDiv.style.opacity = '1';
        unitDiv.style.minHeight = '20px';
    }
});
