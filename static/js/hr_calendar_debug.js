/**
 * HR Staff - Calendar Debug & Value Persistence
 * Traces calendar behavior and ensures selected dates persist
 */
(function() {
    'use strict';
    
    // Hook into calendar closing to ensure values are saved
    function setupValuePersistence() {
        // Monitor all vDateField inputs for value changes
        var dateFields = document.querySelectorAll('input.vDateField');
        
        dateFields.forEach(function(field) {
            if (field.hasAttribute('data-value-monitor')) {
                return;  // Already monitoring
            }
            
            field.setAttribute('data-value-monitor', 'true');
            field.setAttribute('data-last-value', field.value);
            
            // Track value changes
            field.addEventListener('change', function() {
                console.log('✓ Date field changed: ' + field.name + ' = ' + field.value);
                field.setAttribute('data-last-value', field.value);
            });
            
            field.addEventListener('input', function() {
                console.log('Date field input: ' + field.name + ' = ' + field.value);
                field.setAttribute('data-last-value', field.value);
            });
        });
    }
    
    // Monkey-patch the calendar to log when it's used
    if (typeof window.DateTimeShortcuts !== 'undefined') {
        console.log('DateTimeShortcuts available');
        
        var originalHandleCalendarQuickLink = DateTimeShortcuts.handleCalendarQuickLink;
        if (originalHandleCalendarQuickLink) {
            DateTimeShortcuts.handleCalendarQuickLink = function() {
                console.log('Calendar opened via handleCalendarQuickLink');
                console.log('Arguments:', arguments);
                return originalHandleCalendarQuickLink.apply(this, arguments);
            };
        }
        
        var originalCalendarDone = DateTimeShortcuts.calendarDone;
        if (originalCalendarDone) {
            DateTimeShortcuts.calendarDone = function() {
                console.log('Calendar done called');
                console.log('Arguments:', arguments);
                var result = originalCalendarDone.apply(this, arguments);
                
                // After calendar is done, verify the field got the value
                setTimeout(function() {
                    setupValuePersistence();
                }, 100);
                
                return result;
            };
        }
    }
    
    // Initial setup
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupValuePersistence);
    } else {
        setupValuePersistence();
    }
    
    // Re-setup after inlines are added
    var observer = new MutationObserver(function(mutations) {
        var shouldSetup = false;
        
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                for (var i = 0; i < mutation.addedNodes.length; i++) {
                    var node = mutation.addedNodes[i];
                    if (node.nodeType === 1 && node.querySelector && node.querySelector('input.vDateField')) {
                        shouldSetup = true;
                    }
                }
            }
        });
        
        if (shouldSetup) {
            console.log('New inline added - setting up value persistence');
            setTimeout(setupValuePersistence, 200);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Periodic re-setup
    setInterval(setupValuePersistence, 5000);
})();
