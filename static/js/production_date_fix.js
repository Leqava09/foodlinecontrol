// Override AJAX at the lowest level before anything else loads
(function() {
    var checkJQuery = setInterval(function() {
        if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
            clearInterval(checkJQuery);
            
            var $ = django.jQuery;

            var originalAjax = $.ajax;
            
            $.ajax = function(settings) {
                var url = settings.url || '';
                
                if (url.indexOf('/chaining/filter/') !== -1) {

                    if (url.match(/\/\d{2}-\d{2}-\d{4}\//)) {
                        settings.url = url.replace(/\/(\d{2})-(\d{2})-(\d{4})\//, '/$3-$2-$1/');

                    }
                }
                
                return originalAjax.call(this, settings);
            };

        }
    }, 10);
})();

// User interaction handler
(function($) {
    $(document).ready(function() {

        var prodDateInput = $('#id_production_date');
        var batchSelect = $('#id_batch');
        var siteSelect = $('#id_site');
        
        // Trigger on any change to production date or site
        function updateBatches() {
            var displayValue = prodDateInput.val().trim();

            // Match both DD-MM-YYYY and DD.MM.YYYY formats
            var dateMatch = displayValue.match(/^(\d{2})[-.](\d{2})[-.](\d{4})$/);
            
            if (dateMatch) {
                var isoDate = dateMatch[3] + '-' + dateMatch[2] + '-' + dateMatch[1];

                // Build our custom endpoint URL with site filtering
                var path = window.location.pathname || '';
                var adminIndex = path.indexOf('/admin/');
                var baseUrl = '/admin/incident_management/incident/batch-options/';
                if (adminIndex !== -1) {
                    baseUrl = path.substring(0, adminIndex + 7) + 'incident_management/incident/batch-options/';
                }
                
                var siteId = siteSelect.val() || '';
                var chainUrl = baseUrl + '?production_date=' + isoDate;
                if (siteId) {
                    chainUrl += '&site_id=' + siteId;
                }
                
                console.log('DEBUG: Fetching batches from:', chainUrl);

                $.ajax({
                    url: chainUrl,
                    dataType: 'json',
                    success: function(data) {
                        console.log('DEBUG: Batch data received:', data);

                        // Store current selected value AND text
                        var currentValue = batchSelect.val();
                        var currentText = batchSelect.find('option:selected').text();
                        
                        // Clear existing options
                        batchSelect.empty();
                        batchSelect.append('<option value="">---------</option>');
                        
                        // Check if current value is in the new data
                        var currentInData = false;
                        if (currentValue && data && data.length > 0) {
                            currentInData = data.some(function(item) {
                                return item.value === currentValue;
                            });
                        }
                        
                        // If current selection is not in filtered data, add it first (to preserve it)
                        if (currentValue && !currentInData && currentText !== '---------') {
                            var preservedOption = $('<option></option>')
                                .attr('value', currentValue)
                                .text(currentText);
                            batchSelect.append(preservedOption);
                            console.log('DEBUG: Preserved current selection:', currentValue, currentText);
                        }
                        
                        // Add new options from filtered data
                        if (data && data.length > 0) {
                            $.each(data, function(i, item) {
                                var option = $('<option></option>')
                                    .attr('value', item.value)
                                    .text(item.display);
                                batchSelect.append(option);
                            });
                            console.log('DEBUG: Added ' + data.length + ' batch options');
                        }
                        
                        // Restore selection
                        if (currentValue) {
                            batchSelect.val(currentValue);
                            console.log('DEBUG: Restored selection to:', currentValue);
                        }
                        
                        // Verify options are in DOM
                        console.log('DEBUG: Dropdown now has ' + batchSelect.find('option').length + ' options total');
                        console.log('DEBUG: Dropdown options:', batchSelect.find('option').map(function() { 
                            return $(this).text(); 
                        }).get());
                        
                        // Trigger change event
                        batchSelect.trigger('change');
                    },
                    error: function(jqXHR, textStatus, errorThrown) {
                        console.error('DEBUG: Error fetching batches:', textStatus, errorThrown);
                    }
                });
            } else {
                console.log('DEBUG: Production date not in correct format:', displayValue);
            }
        }
        
        // Call updateBatches on page load if production_date is already filled
        // BUT: Don't do this if batch already has options or a value (form resubmission/edit)
        if (prodDateInput.val() && prodDateInput.val().trim()) {
            // Check if batch dropdown already has actual batch options (not just placeholder)
            var batchOptions = batchSelect.find('option').length;
            var currentBatchValue = batchSelect.val();
            var hasActualOptions = batchOptions > 1; // More than just the "------"  placeholder
            
            if (!hasActualOptions && (!currentBatchValue || currentBatchValue === '')) {
                // Only update if dropdown is empty AND no batch is selected
                console.log('DEBUG: Page load - production date present, no batch options, calling updateBatches');
                updateBatches();
            } else {
                // Batch options already present (form resubmission/edit), don't overwrite
                console.log('DEBUG: Page load - batch already has', batchOptions, 'options or value:', currentBatchValue, '- skipping updateBatches');
            }
        } else {
            // New form with no production date: ensure batch dropdown is empty
            console.log('DEBUG: Page load - no production date, clearing batch dropdown');
            batchSelect.empty();
            batchSelect.append('<option value="">---------</option>');
        }
        
        prodDateInput.on('change blur', function() {
            var displayValue = $(this).val().trim();

            // Match both DD-MM-YYYY and DD.MM.YYYY formats
            var dateMatch = displayValue.match(/^(\d{2})[-.](\d{2})[-.](\d{4})$/);

            if (dateMatch) {
                console.log('DEBUG: Production date changed, updating batches');
                updateBatches();
            }
        });
        
        // Also update when site changes
        siteSelect.on('change', function() {
            if (prodDateInput.val()) {
                console.log('DEBUG: Site changed, updating batches');
                updateBatches();
            }
        });
    });
})(django.jQuery);
