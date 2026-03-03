/**
 * HR Date Picker - Uses jQuery UI from Admin or Grappelli
 * Falls back to HTML5 date input if jQuery UI unavailable
 */
(function() {
    'use strict';
    
    // Detect jQuery
    var $ = window.django && window.django.jQuery ? window.django.jQuery : 
            (window.grp && window.grp.jQuery ? window.grp.jQuery : 
             (typeof jQuery !== 'undefined' ? jQuery : null));
    
    console.log('[HR DatePicker] jQuery:', $ ? $.fn.jquery : 'NOT FOUND');
    
    function initializeFromDjangoAdmin() {
        console.log('[HR DatePicker] Searching for DateTimeShortcuts');
        
        // Try to use Django's built-in DateTimeShortcuts if available
        if (typeof DateTimeShortcuts !== 'undefined' && DateTimeShortcuts.init) {
            console.log('[HR DatePicker] Found DateTimeShortcuts');
            try {
                DateTimeShortcuts.init();
                console.log('[HR DatePicker] ✓ DateTimeShortcuts initialized');
                return true;
            } catch (e) {
                console.error('[HR DatePicker] DateTimeShortcuts error:', e);
            }
        }
        
        // Try calendar.js
        if (typeof Calendar !== 'undefined') {
            console.log('[HR DatePicker] Found Calendar');
            try {
                Calendar._openCalendar();
                return true;
            } catch (e) {
                console.error('[HR DatePicker] Calendar error:', e);
            }
        }
        
        return false;
    }
    
    function initializeJQueryUI() {
        if (!$) {
            console.error('[HR DatePicker] jQuery not available');
            return false;
        }
        
        if (!$.ui || !$.ui.datepicker) {
            console.warn('[HR DatePicker] jQuery UI datepicker not available');
            return false;
        }
        
        console.log('[HR DatePicker] Using jQuery UI datepicker');
        
        var initiatedCount = 0;
        $('.vDateField').each(function() {
            var $field = $(this);
            var name = $field.attr('name') || 'unknown';
            
            // Skip __prefix__ template fields
            if (name.includes('__prefix__')) {
                console.log('[HR DatePicker] Skipping template field: ' + name);
                return;
            }
            
            if ($field.attr('data-hp-init')) {
                return;
            }
            
            try {
                // Destroy if already initialized
                if ($field.hasClass('hasDatepicker')) {
                    $field.datepicker('destroy');
                }
                
                $field.datepicker({
                    dateFormat: 'dd-mm-yy',
                    changeMonth: true,
                    changeYear: true,
                    onSelect: function(dateText) {
                        console.log('[HR DatePicker] Selected for ' + name + ':', dateText);
                        $(this).val(dateText).change();
                    }
                });
                
                initiatedCount++;
                $field.attr('data-hp-init', 'true');  // Set as attribute, not data
                console.log('[HR DatePicker] ✓ Initialized:', name);
            } catch (err) {
                console.error('[HR DatePicker] Error on ' + name + ':', err.message);
            }
        });
        
        return initiatedCount > 0;
    }
    
    function initializeHTML5Fallback() {
        console.log('[HR DatePicker] Using HTML5 date input fallback');
        
        $('.vDateField').each(function() {
            if ($(this).data('hp-init')) return;
            
            // Convert to date input
            $(this).attr('type', 'date');
            $(this).on('change', function() {
                console.log('[HR DatePicker] HTML5 change:', $(this).val());
            });
            
            $(this).data('hp-init', true);
        });
    }
    
    function initializeDatepickers() {
        console.log('[HR DatePicker] Initializing date pickers');
        
        var fieldCount = document.querySelectorAll('.vDateField').length;
        console.log('[HR DatePicker] Found ' + fieldCount + ' date fields');
        
        if (fieldCount === 0) return;
        
        // Try strategies in order
        if (initializeFromDjangoAdmin()) {
            return;
        }
        
        initializeJQueryUI();
        // Don't fall back to HTML5 - jQuery UI should handle everything
    }
    
    function setupWatchers() {
        // Mutation observer for new inlines
        var observer = new MutationObserver(function(mutations) {
            var shouldInit = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    if (mutation.addedNodes.length > 0) {
                        for (var i = 0; i < mutation.addedNodes.length; i++) {
                            var el = mutation.addedNodes[i];
                            if (el.nodeType === 1 && el.querySelector && el.querySelector('.vDateField')) {
                                shouldInit = true;
                            }
                        }
                    }
                }
            });
            
            if (shouldInit) {
                console.log('[HR DatePicker] New inline detected');
                setTimeout(initializeDatepickers, 300);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // Periodic check for uninitialized fields - less frequently
        setInterval(function() {
            var uninit = document.querySelectorAll('.vDateField:not([data-hp-init])').length;
            if (uninit > 0) {
                console.log('[HR DatePicker] Found ' + uninit + ' uninitialized fields');
                initializeDatepickers();
            }
        }, 5000);
    }
    
    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initializeDatepickers, 200);
            setupWatchers();
        });
    } else {
        initializeDatepickers();
        setupWatchers();
    }
})();
