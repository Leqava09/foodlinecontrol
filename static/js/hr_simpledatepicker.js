(function() {
    'use strict';
    
    console.log('[HR DatePicker] Starting');
    
    // Try to bind calendar initialization to vDateField inputs
    function initCalendar() {
        var fields = document.querySelectorAll('input.vDateField');
        
        fields.forEach(function(field) {
            // Skip template prefix fields
            if (field.name && field.name.includes('__prefix__')) {
                return;
            }
            
            // Mark as initialized
            if (field.hasAttribute('data-calendar-init')) {
                return;
            }
            
            field.setAttribute('data-calendar-init', 'true');
            
            // For Grappelli - just ensure the field is ready
            // The calendar.js should auto-init vDateField inputs
            console.log('[HR DatePicker] Initialized field: ' + (field.name || field.id || field.className));
        });
    }
    
    // Run on document ready
    function init() {
        console.log('[HR DatePicker] DOM ready');
        
        // Initial setup
        setTimeout(function() {
            initCalendar();
            
            // Watch for new inline rows
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'childList') {
                        setTimeout(initCalendar, 100);
                    }
                });
            });
            
            observers.observe(document.body, { childList: true, subtree: true });
            
            console.log('[HR DatePicker] Initialized');
        }, 500);
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
