/**
 * JavaScript to filter batch autocomplete by selected site in BillingLineItem inline
 * and dynamically populate Product and Size when batch is selected
 */
(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Billing line item filter loaded');
        
        // Function to fetch and display batch details (product, size)
        function fetchBatchDetails(batchId, row) {
            if (!batchId) {
                updateProductSizeDisplay(row, '-', '-');
                return;
            }
            
            console.log('Fetching batch details for:', batchId);
            
            $.ajax({
                url: '/api/batch/' + batchId + '/details/',
                method: 'GET',
                dataType: 'json',
                success: function(data) {
                    console.log('API response:', data);
                    if (data.success) {
                        updateProductSizeDisplay(row, data.product, data.size);
                    } else {
                        updateProductSizeDisplay(row, '-', '-');
                    }
                },
                error: function(xhr, status, error) {
                    console.log('API error:', status, error);
                    updateProductSizeDisplay(row, '-', '-');
                }
            });
        }
        
        // Function to update the product and size display in the row
        function updateProductSizeDisplay(row, product, size) {
            var productCell = row.find('.grp-td.get_product .grp-readonly');
            var sizeCell = row.find('.grp-td.get_size .grp-readonly');
            
            if (productCell.length) {
                productCell.text(product);
            }
            if (sizeCell.length) {
                sizeCell.text(size);
            }
            
            console.log('Updated product/size:', product, size);
        }
        
        // Track batch values per row to detect actual changes
        var batchTracker = {};
        
        function getRowId(row) {
            // Get a unique identifier for the row
            var input = row.find('input[name$="-id"]');
            if (input.length && input.val()) {
                return 'id-' + input.val();
            }
            // For new rows, use the row index
            return 'row-' + row.index();
        }
        
        function checkForBatchChanges() {
            $('select[name$="-batch"]').each(function() {
                var $select = $(this);
                var row = $select.closest('.grp-tr');
                var rowId = getRowId(row);
                var currentValue = $select.val();
                
                // Initialize if not tracked
                if (!(rowId in batchTracker)) {
                    batchTracker[rowId] = currentValue;
                    // Don't fetch on initial load - server already rendered the values
                    return;
                }
                
                // Check if value changed
                if (currentValue !== batchTracker[rowId]) {
                    console.log('Batch changed in row', rowId, ':', batchTracker[rowId], '->', currentValue);
                    batchTracker[rowId] = currentValue;
                    
                    if (currentValue) {
                        fetchBatchDetails(currentValue, row);
                    } else {
                        updateProductSizeDisplay(row, '-', '-');
                    }
                }
            });
        }
        
        // Poll for changes every 300ms (catches Select2 AJAX selections)
        setInterval(checkForBatchChanges, 300);
        
        // Also handle site changes - clear batch when site changes
        var siteTracker = {};
        
        $(document).on('change', 'select[name$="-site"]', function() {
            var $this = $(this);
            var row = $this.closest('.grp-tr');
            var rowId = getRowId(row);
            var currentValue = $this.val();
            
            // Initialize if not tracked
            if (!(rowId in siteTracker)) {
                siteTracker[rowId] = currentValue;
                return;
            }
            
            // Only clear batch if site actually changed
            if (currentValue !== siteTracker[rowId]) {
                siteTracker[rowId] = currentValue;
                
                var batchSelect = row.find('select[name$="-batch"]');
                if (batchSelect.length && batchSelect.hasClass('select2-hidden-accessible')) {
                    batchSelect.val(null).trigger('change');
                }
                updateProductSizeDisplay(row, '-', '-');
            }
        });
    });
})(django.jQuery || jQuery);
