/**
 * PO Line Item - Auto-fetch price when stock item is selected
 * Also calculates line total dynamically
 */
(function($) {
    $(document).ready(function() {
        console.log('=== PO LINE ITEM PRICE JS LOADED ===');
        
        /**
         * Extract the row prefix from a field name (e.g., "line_items-0-stock_item" -> "line_items-0-")
         */
        function getRowPrefix(fieldName) {
            var match = fieldName.match(/^(.+-\d+-)/);
            return match ? match[1] : null;
        }
        
        /**
         * Calculate and display line total for a row by prefix
         */
        function calculateLineTotalByPrefix(prefix) {
            var $qtyField = $('input[name="' + prefix + 'quantity"]');
            var $priceField = $('input[name="' + prefix + 'unit_price"]');
            
            var qty = parseFloat($qtyField.val()) || 0;
            var price = parseFloat($priceField.val()) || 0;
            var total = qty * price;
            
            console.log('Line calc for', prefix, '- qty:', qty, 'price:', price, 'total:', total);
            
            // Get currency
            var currency = $('select[name="currency"]').val() || 'R';
            var symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'};
            var symbol = symbols[currency] || currency;
            
            // Format with thousand separators
            var formatted = symbol + ' ' + total.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            
            // Find the Line Total cell - look for a cell/element near the price field
            // In Grappelli, find the row container and look for line_total display
            var $priceContainer = $priceField.closest('.grp-td, .grp-row, td, tr, .form-row');
            var $rowContainer = $priceContainer.parent().closest('.grp-tr, .grp-row, tr, .form-row');
            
            console.log('Price container:', $priceContainer.length, 'Row container:', $rowContainer.length);
            
            // Try to find line_total_display_field in the same row
            var $lineTotalField = $rowContainer.find('.field-line_total_display_field p, .grp-readonly');
            if ($lineTotalField.length) {
                $lineTotalField.first().text(formatted);
                console.log('Updated line total field to:', formatted);
            } else {
                // Alternative: Find by looking at siblings of the price cell
                var $allCells = $rowContainer.find('.grp-td, td');
                $allCells.each(function() {
                    if ($(this).hasClass('field-line_total_display_field') || 
                        $(this).find('[class*="line_total"]').length) {
                        $(this).find('p, .grp-readonly').first().text(formatted);
                        console.log('Updated line total via cell search to:', formatted);
                    }
                });
            }
            
            // Update Grand Total AFTER line total is calculated
            setTimeout(updateGrandTotal, 50);
        }
        
        /**
         * Update the grand total display
         */
        function updateGrandTotal() {
            console.log('=== UPDATING GRAND TOTAL ===');
            var subtotal = 0;
            
            // Sum all line totals - find all quantity fields that are NOT the template
            $('input[name*="-quantity"]').not('[name*="__prefix__"]').each(function() {
                var prefix = getRowPrefix($(this).attr('name'));
                if (prefix) {
                    var $priceField = $('input[name="' + prefix + 'unit_price"]');
                    var qty = parseFloat($(this).val()) || 0;
                    var price = parseFloat($priceField.val()) || 0;
                    var lineTotal = qty * price;
                    console.log('Line:', prefix, 'qty:', qty, 'price:', price, 'lineTotal:', lineTotal);
                    subtotal += lineTotal;
                }
            });
            
            console.log('Subtotal:', subtotal);
            
            // Get VAT percentage
            var vatPercent = parseFloat($('input[name="vat_percentage"]').val()) || 0;
            var vatAmount = subtotal * (vatPercent / 100);
            var totalWithVat = subtotal + vatAmount;
            
            console.log('VAT %:', vatPercent, 'VAT amount:', vatAmount, 'Total with VAT:', totalWithVat);
            
            // Get currency
            var currency = $('select[name="currency"]').val() || 'R';
            var symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'};
            var symbol = symbols[currency] || currency;
            
            // Format with thousand separators
            var formatted = symbol + ' ' + totalWithVat.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            console.log('Formatted total:', formatted);
            
            // Update the specific span with ID
            var $totalSpan = $('#po-grand-total-display');
            if ($totalSpan.length > 0) {
                $totalSpan.text(formatted);
                console.log('✓ Updated #po-grand-total-display to:', formatted);
            } else {
                console.warn('⚠ Could not find #po-grand-total-display element');
            }
            
            console.log('=== END GRAND TOTAL UPDATE ===');
        }
        
        // Watch for stock_item changes in inline rows - fetch price
        $(document).on('change', 'select[name*="-stock_item"]', function() {
            var $select = $(this);
            var fieldName = $select.attr('name');
            
            // Skip template row
            if (fieldName.indexOf('__prefix__') > -1) return;
            
            console.log('Stock item change event fired for:', fieldName);
            
            // ✅ POLL for value instead of fixed timeout - chained select may take varying time
            var attempts = 0;
            var maxAttempts = 20; // 20 attempts * 100ms = 2 seconds max wait
            
            var checkInterval = setInterval(function() {
                attempts++;
                var stockItemId = $select.val();
                
                console.log('Polling attempt', attempts, '- Stock item value:', stockItemId);
                
                // If we got a value, process it
                if (stockItemId) {
                    clearInterval(checkInterval);
                    console.log('✓ Stock item value found:', stockItemId, 'field:', fieldName);
                    
                    // Get the row prefix
                    var prefix = getRowPrefix(fieldName);
                    if (!prefix) {
                        console.log('Could not extract prefix from:', fieldName);
                        return;
                    }
                    
                    // Find the unit_price field by name
                    var $priceField = $('input[name="' + prefix + 'unit_price"]');
                    
                    console.log('Looking for price field:', prefix + 'unit_price', 'Found:', $priceField.length);
                    
                    if (!$priceField.length) {
                        console.log('Price field not found');
                        return;
                    }
                    
                    // Fetch the price from server
                    console.log('Fetching price for stock item:', stockItemId);
                    
                    // Build site-aware URL
                    var currentPath = window.location.pathname;
                    var baseUrl = '/admin/inventory/purchaseorder/get-stock-item-price/';
                    
                    // Check if we're in a site context (/hq/{site}/admin/)
                    var siteMatch = currentPath.match(/^\/hq\/([^\/]+)\/admin\//);
                    if (siteMatch) {
                        baseUrl = '/hq/' + siteMatch[1] + '/admin/inventory/purchaseorder/get-stock-item-price/';
                        console.log('Using site-aware URL:', baseUrl);
                    }
                    
                $.ajax({
                    url: baseUrl,
                    data: { stock_item_id: stockItemId },
                    dataType: 'json',
                    success: function(data) {
                        console.log('Price response:', data);
                        if (data.price !== undefined) {
                            // Always update the price with the stock item's default price
                            $priceField.val(data.price.toFixed(2));
                            console.log('Set price to:', data.price.toFixed(2));
                            // Recalculate line total after setting price
                            calculateLineTotalByPrefix(prefix);
                        } else {
                            console.log('No price in response');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.log('Error fetching stock item price:', error);
                    }
                });
                }
                
                // If max attempts reached without value, stop polling
                if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    console.log('⚠ Max polling attempts reached, no stock item value found');
                }
            }, 100); // Poll every 100ms for up to 2 seconds
        });
        
        // Watch for quantity and price changes - recalculate line total
        $(document).on('input change', 'input[name*="-quantity"], input[name*="-unit_price"]', function() {
            var fieldName = $(this).attr('name');
            // Skip template row
            if (fieldName.indexOf('__prefix__') > -1) return;
            
            var prefix = getRowPrefix(fieldName);
            if (prefix) {
                calculateLineTotalByPrefix(prefix);
            }
        });
        
        // Watch for VAT percentage changes
        $(document).on('input change', 'input[name="vat_percentage"]', function() {
            updateGrandTotal();
        });
        
        // Watch for currency changes - update all totals
        $(document).on('change', 'select[name="currency"]', function() {
            // Recalculate all lines with new currency
            $('input[name*="-quantity"]').not('[name*="__prefix__"]').each(function() {
                var prefix = getRowPrefix($(this).attr('name'));
                if (prefix) {
                    calculateLineTotalByPrefix(prefix);
                }
            });
            // Also update grand total
            updateGrandTotal();
        });
        
        // Watch for inline row additions (when user clicks Add another PO Line Item)
        $(document).on('formset:added', function(event, $row, formsetName) {
            if (formsetName && formsetName.indexOf('line_items') > -1) {
                console.log('New line item row added');
                // Recalculate grand total when new row added
                setTimeout(updateGrandTotal, 100);
            }
        });
        
        // Watch for inline row removals
        $(document).on('formset:removed', function(event, $row, formsetName) {
            if (formsetName && formsetName.indexOf('line_items') > -1) {
                console.log('Line item row removed');
                updateGrandTotal();
            }
        });
        
        // Initial calculation on page load
        setTimeout(function() {
            $('input[name*="-quantity"]').not('[name*="__prefix__"]').each(function() {
                var prefix = getRowPrefix($(this).attr('name'));
                if (prefix) {
                    calculateLineTotalByPrefix(prefix);
                }
            });
            // Initial grand total
            updateGrandTotal();
        }, 1000);
        
    });
})(django.jQuery || jQuery);
