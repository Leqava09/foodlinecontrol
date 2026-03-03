/**
 * HR Staff - Calendar Picker Value Capture Fix
 * Ensures that when a date is selected from the calendar, it properly updates the form field
 */
(function() {
    'use strict';
    
    // Store original calendar closing handlers
    var originalAddEventListener = HTMLElement.prototype.addEventListener;
    
    function patchCalendarPicker() {
        console.log('Patching calendar picker behavior...');
        
        // Find all calendar links and input fields
        var calendarLinks = document.querySelectorAll('img[alt="Calendar"]');
        var dateFields = document.querySelectorAll('input.vDateField');
        
        console.log('Found ' + calendarLinks.length + ' calendar links and ' + dateFields.length + ' date fields');
        
        // For each calendar link, add a handler that checks the field value after calendar closes
        calendarLinks.forEach(function(link, idx) {
            if (link.hasAttribute('data-calendar-patched')) {
                return;  // Already patched
            }
            
            link.setAttribute('data-calendar-patched', 'true');
            
            // Get the associated input field ID
            var inputId = link.previousElementSibling?.id || null;
            if (!inputId && link.parentElement) {
                var input = link.parentElement.querySelector('input.vDateField');
                if (input) {
                    inputId = input.id;
                }
            }
            
            if (inputId) {
                console.log('Patched calendar link for field: ' + inputId);
                
                // Monitor the field for changes after calendar interaction
                var field = document.getElementById(inputId);
                if (field) {
                    // Store the original onclick handler
                    var originalOnclick = link.onclick;
                    
                    // Replace with our patched version
                    link.onclick = function(e) {
                        console.log('Calendar clicked for: ' + inputId);
                        
                        // Call original handler to open calendar
                        if (typeof DateTimeShortcuts !== 'undefined' && DateTimeShortcuts.handleCalendarQuickLink) {
                            try {
                                DateTimeShortcuts.handleCalendarQuickLink(this, inputId);
                            } catch(err) {
                                console.error('Error opening calendar:', err);
                            }
                        }
                        
                        // After a brief delay, set up a monitor for when calendar closes
                        setTimeout(function() {
                            monitorForCalendarClose(inputId);
                        }, 100);
                        
                        return false;
                    };
                }
            }
        });
    }
    
    function monitorForCalendarClose(fieldId) {
        var field = document.getElementById(fieldId);
        if (!field) return;
        
        var originalValue = field.value;
        var checkCount = 0;
        var maxChecks = 100;  // Check for up to 5 seconds (100 * 50ms)
        
        var monitor = setInterval(function() {
            checkCount++;
            
            // Check if calendar has closed by looking for the calendar widget
            var calendarWidget = document.getElementById('calendar');
            
            // If calendar closed and field value changed, handle it
            if (!calendarWidget && (field.value !== originalValue || field.value)) {
                console.log('Calendar closed. Field ' + fieldId + ' value: ' + field.value);
                clearInterval(monitor);
                
                // Trigger change event to notify form
                if (field.value) {
                    field.dispatchEvent(new Event('change', { bubbles: true }));
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                    field.dispatchEvent(new Event('blur', { bubbles: true }));
                }
                
                return;
            }
            
            // Stop checking after max attempts
            if (checkCount >= maxChecks) {
                console.log('Stopped monitoring calendar for field: ' + fieldId);
                clearInterval(monitor);
            }
        }, 50);
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(patchCalendarPicker, 500);
        });
    } else {
        setTimeout(patchCalendarPicker, 500);
    }
    
    // Re-patch when new content is added (for inlines)
    var observer = new MutationObserver(function(mutations) {
        var shouldPatch = false;
        
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                for (var i = 0; i < mutation.addedNodes.length; i++) {
                    var node = mutation.addedNodes[i];
                    if (node.nodeType === 1) {  // Element node
                        if (node.querySelector && (node.querySelector('input.vDateField') || node.querySelector('img[alt="Calendar"]'))) {
                            shouldPatch = true;
                        }
                    }
                }
            }
        });
        
        if (shouldPatch) {
            console.log('New date fields added - re-patching calendar picker');
            setTimeout(patchCalendarPicker, 200);
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();
