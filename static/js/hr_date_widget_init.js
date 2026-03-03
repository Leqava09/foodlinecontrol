/**
 * HR Staff - Date Widget Initialization for Grappelli Nested Admin
 * Ensures calendar selections properly populate date fields in inline forms
 */
(function() {
    'use strict';
    
    var $ = django.jQuery || window.jQuery;
    
    function initializeDateShortcuts() {
        console.log('Initializing DateTimeShortcuts for HR forms');
        
        // Initialize all vDateField inputs with DateTimeShortcuts
        if (typeof DateTimeShortcuts !== 'undefined') {
            DateTimeShortcuts.init();
            console.log('✓ DateTimeShortcuts.init() called');
        }
        
        // Also initialize any inline forms
        $('.inline-related input.vDateField').each(function() {
            var $field = $(this);
            if (!$field.data('shortcuts-initialized')) {
                if (typeof DateTimeShortcuts !== 'undefined') {
                    DateTimeShortcuts.init();
                }
                $field.data('shortcuts-initialized', true);
            }
        });
    }
    
    function fixCalendarValueCapture() {
        console.log('Setting up calendar value capture handlers');
        
        // Find all calendar links
        var calendarLinks = document.querySelectorAll('img[alt="Calendar"]');
        console.log('Found ' + calendarLinks.length + ' calendar links');
        
        calendarLinks.forEach(function(link) {
            if (link.dataset.valueFixApplied) {
                return;  // Already patched
            }
            link.dataset.valueFixApplied = 'true';
            
            // Get the input field this calendar is for
            var inputId = link.id.replace('_calendar_link', '');
            var inputField = document.getElementById(inputId);
            
            if (inputField) {
                console.log('Patched calendar link for: ' + inputId);
                
                // Store original onclick
                var originalOnclick = link.onclick;
                
                // Replace with our version that ensures value capture
                link.onclick = function() {
                    console.log('Calendar clicked for: ' + inputId);
                    
                    // Get the current value
                    var oldValue = inputField.value;
                    
                    // Call the original calendar handler
                    if (typeof DateTimeShortcuts !== 'undefined' && 
                        typeof DateTimeShortcuts.handleCalendarQuickLink === 'function') {
                        try {
                            DateTimeShortcuts.handleCalendarQuickLink(this, inputId);
                        } catch (e) {
                            console.error('Error in handleCalendarQuickLink:', e);
                        }
                    } else if (originalOnclick) {
                        originalOnclick.call(this);
                    }
                    
                    // Monitor the field for value changes while calendar is open
                    monitorFieldWhileCalendarOpen(inputField, inputId);
                    
                    return false;
                };
            }
        });
    }
    
    function monitorFieldWhileCalendarOpen(inputField, fieldId) {
        var checkInterval = setInterval(function() {
            // Check if calendar widget exists
            var calendarWidget = document.getElementById('calendar');
            
            // If calendar is gone but field has a value, ensure it's properly set
            if (!calendarWidget) {
                clearInterval(checkInterval);
                
                if (inputField.value) {
                    console.log('Calendar closed. Field ' + fieldId + ' = ' + inputField.value);
                    
                    // Trigger change events
                    inputField.dispatchEvent(new Event('change', { bubbles: true }));
                    inputField.dispatchEvent(new Event('input', { bubbles: true }));
                    inputField.dispatchEvent(new Event('blur', { bubbles: true }));
                    
                    // Force the value to stick by setting it again
                    setTimeout(function() {
                        if (!inputField.value) {
                            console.log('Value was lost! Re-checking...');
                            monitorFieldWhileCalendarOpen(inputField, fieldId);
                        }
                    }, 100);
                }
                
                return;
            }
        }, 100);
        
        // Stop monitoring after 30 seconds
        setTimeout(function() {
            clearInterval(checkInterval);
        }, 30000);
    }
    
    function setupInlineObserver() {
        console.log('Setting up inline form observer');
        
        // Observe for new inline forms being added
        var observer = new MutationObserver(function(mutations) {
            var shouldReinit = false;
            
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    for (var i = 0; i < mutation.addedNodes.length; i++) {
                        var node = mutation.addedNodes[i];
                        if (node.nodeType === 1) {  // Element node
                            if ((node.querySelector && node.querySelector('input.vDateField')) ||
                                (node.classList && node.classList.contains('inline-related'))) {
                                shouldReinit = true;
                            }
                        }
                    }
                }
            });
            
            if (shouldReinit) {
                console.log('New inline form detected - reinitializing date widgets');
                setTimeout(function() {
                    initializeDateShortcuts();
                    fixCalendarValueCapture();
                }, 200);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Main initialization
    $(document).ready(function() {
        console.log('HR date widget initializer started');
        
        // Initial setup
        setTimeout(initializeDateShortcuts, 100);
        setTimeout(fixCalendarValueCapture, 200);
        
        // Setup observer for new inlines
        setupInlineObserver();
        
        // Handle Grappelli's add-row button
        $(document).on('click', '.grp-add-handler, .inline-related .add-row', function() {
            setTimeout(function() {
                console.log('Inline row added - reinitializing');
                initializeDateShortcuts();
                fixCalendarValueCapture();
            }, 300);
        });
        
        // Periodic re-initialization as fallback
        setInterval(function() {
            var uninitialized = document.querySelectorAll('input.vDateField:not([data-shortcuts-initialized])');
            if (uninitialized.length > 0) {
                console.log('Found ' + uninitialized.length + ' uninitialized vDateField inputs');
                initializeDateShortcuts();
            }
            
            var uncaptured = document.querySelectorAll('img[alt="Calendar"]:not([data-value-fix-applied])');
            if (uncaptured.length > 0) {
                console.log('Found ' + uncaptured.length + ' unpatched calendar links');
                fixCalendarValueCapture();
            }
        }, 3000);
    });
    
    // If document is already ready, run immediately
    if (document.readyState !== 'loading') {
        console.log('Document already loaded - initializing immediately');
        initializeDateShortcuts();
        fixCalendarValueCapture();
        setupInlineObserver();
    }
})();



