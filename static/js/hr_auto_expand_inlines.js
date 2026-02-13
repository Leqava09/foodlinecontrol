/**
 * HR Staff - Auto-expand new inline forms
 * Ensures when clicking "Add another" the form opens immediately
 */
(function($) {
    $(document).ready(function() {
        console.log('HR auto-expand inlines loaded');
        
        // Watch for new inline forms being added
        $(document).on('DOMNodeInserted', function(e) {
            var $target = $(e.target);
            
            // Check if it's a new Induction or Training inline
            if ($target.hasClass('grp-module') || $target.hasClass('inline-related')) {
                // Find any collapsed groups and open them
                $target.find('.grp-collapse.grp-closed').removeClass('grp-closed').addClass('grp-open');
                
                // Also check if the target itself is collapsed
                if ($target.hasClass('grp-closed')) {
                    $target.removeClass('grp-closed').addClass('grp-open');
                }
            }
        });
        
        // Also handle the "Add another" button clicks directly
        $(document).on('click', '.grp-add-handler', function() {
            setTimeout(function() {
                // Find the last added inline and ensure it's open
                $('.inline-related:last, .grp-module:last').each(function() {
                    $(this).removeClass('grp-closed').addClass('grp-open');
                    $(this).find('.grp-collapse').removeClass('grp-closed').addClass('grp-open');
                });
            }, 100);
        });
        
        // Initial check - open any new empty inlines
        setTimeout(function() {
            $('.inline-related, .grp-module').each(function() {
                // If it's a new inline (no ID yet), open it
                var $idField = $(this).find('input[name$="-id"]');
                if ($idField.length && !$idField.val()) {
                    $(this).removeClass('grp-closed').addClass('grp-open');
                    $(this).find('.grp-collapse').removeClass('grp-closed').addClass('grp-open');
                }
            });
        }, 500);
    });
})(django.jQuery || jQuery);
