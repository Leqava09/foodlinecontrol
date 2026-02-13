/**
 * Overhead Costing - Dynamic calculation for all fields
 * Updates totals, per-unit costs, and percentages in real-time
 */
(function($) {
    $(document).ready(function() {
        console.log('=== OVERHEAD COSTING DYNAMIC CALCULATIONS LOADED ===');
        
        // Only run on add/change form pages, not on list pages
        // Check if inline formset exists (items inline)
        if ($('input[name*="-per_month"]').not('[name*="__prefix__"]').length === 0) {
            console.log('⊗ Overhead calc: Not on change/add form - skipping calculations');
            return;
        }
        
        // Add CSS to vertically center percentage column content
        $('<style>' +
            '.grp-td.percentage_column { vertical-align: middle !important; }' +
            '.grp-table .grp-tbody .grp-tr .grp-td.percentage_column { vertical-align: middle !important; }' +
        '</style>').appendTo('head');
        
        /**
         * Get the row prefix from a field name (e.g., "items-0-per_month" -> "items-0-")
         */
        function getRowPrefix(fieldName) {
            var match = fieldName.match(/^(.+-\d+-)/);
            return match ? match[1] : null;
        }
        
        /**
         * Calculate all overhead item fields for a given row
         */
        function calculateOverheadItem(prefix) {
            var $perMonthField = $('input[name="' + prefix + 'per_month"]');
            var perMonth = parseFloat($perMonthField.val()) || 0;
            
            // Get production units from the header
            var productionUnits = parseFloat($('input[name="production_units"]').val()) || 1;
            
            // Calculate derived values
            var perWeek = perMonth / 4.333;
            var perDay = perMonth / 30;
            var perHour = perDay / 8;
            var perUnit = productionUnits > 0 ? perMonth / productionUnits : 0;
            
            // Find the row container
            var $row = $perMonthField.closest('tr, .grp-tr');
            
            // Update per week display
            var $perWeekCell = $row.find('[class*="per_week_display"] span, .field-per_week_display span');
            if ($perWeekCell.length) {
                $perWeekCell.text('NAD ' + perWeek.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update per day display
            var $perDayCell = $row.find('[class*="per_day_display"] span, .field-per_day_display span');
            if ($perDayCell.length) {
                $perDayCell.text('NAD ' + perDay.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update per hour display
            var $perHourCell = $row.find('[class*="per_hour_display"] span, .field-per_hour_display span');
            if ($perHourCell.length) {
                $perHourCell.text('NAD ' + perHour.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update per unit display
            var $perUnitCell = $row.find('[class*="per_unit_display"] span, .field-per_unit_display span');
            if ($perUnitCell.length) {
                $perUnitCell.text('NAD ' + perUnit.toLocaleString('en-ZA', {minimumFractionDigits: 4, maximumFractionDigits: 4}));
            }
            
            console.log('Calculated item:', prefix, 'perMonth:', perMonth, 'perUnit:', perUnit);
        }
        
        /**
         * Calculate grand totals and update header displays
         */
        function calculateGrandTotals() {
            console.log('=== CALCULATING GRAND TOTALS ===');
            
            var fixedTotal = 0;
            var variableTotal = 0;
            
            // Sum all per_month values by type
            $('input[name*="-per_month"]').not('[name*="__prefix__"]').each(function() {
                var perMonth = parseFloat($(this).val()) || 0;
                var prefix = getRowPrefix($(this).attr('name'));
                if (!prefix) return;
                
                // Find the item_type field
                var $itemType = $('select[name="' + prefix + 'item_type"]');
                var itemType = $itemType.val();
                
                console.log('Item:', prefix, 'Type:', itemType, 'Amount:', perMonth);
                
                if (itemType === 'Fixed') {
                    fixedTotal += perMonth;
                } else if (itemType === 'Variable') {
                    variableTotal += perMonth;
                }
            });
            
            var grandTotal = fixedTotal + variableTotal;
            var productionUnits = parseFloat($('input[name="production_units"]').val()) || 1;
            var pricePerUnit = productionUnits > 0 ? grandTotal / productionUnits : 0;
            
            console.log('Fixed:', fixedTotal, 'Variable:', variableTotal, 'Grand Total:', grandTotal, 'Price/Unit:', pricePerUnit);
            
            // Update Fixed total display using specific ID
            var $fixedDisplay = $('#overhead-fixed-total');
            if ($fixedDisplay.length) {
                $fixedDisplay.text('NAD ' + fixedTotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                console.log('✓ Updated Fixed total');
            } else {
                console.warn('⚠ Fixed total field not found');
            }
            
            // Update Variable total display using specific ID
            var $variableDisplay = $('#overhead-variable-total');
            if ($variableDisplay.length) {
                $variableDisplay.text('NAD ' + variableTotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                console.log('✓ Updated Variable total');
            } else {
                console.warn('⚠ Variable total field not found');
            }
            
            // Update Grand Total display using specific ID
            var $grandTotalDisplay = $('#overhead-grand-total');
            if ($grandTotalDisplay.length) {
                var color = grandTotal > 100000 ? 'darkred' : 'black';
                $grandTotalDisplay.css('color', color).text('NAD ' + grandTotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                console.log('✓ Updated Grand Total');
            } else {
                console.warn('⚠ Grand Total field not found');
            }
            
            // Update Price per Unit display using specific ID
            var $pricePerUnitDisplay = $('#overhead-price-per-unit');
            if ($pricePerUnitDisplay.length) {
                var formattedPrice = pricePerUnit > 0 ? 'NAD ' + pricePerUnit.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '-';
                $pricePerUnitDisplay.text(formattedPrice);
                console.log('✓ Updated Price per Unit');
            } else {
                console.warn('⚠ Price per Unit field not found');
            }
            
            // Update percentages for all items
            $('input[name*="-per_month"]').not('[name*="__prefix__"]').each(function() {
                var perMonth = parseFloat($(this).val()) || 0;
                var prefix = getRowPrefix($(this).attr('name'));
                if (!prefix) return;
                
                var percentage = grandTotal > 0 ? (perMonth / grandTotal * 100) : 0;
                var $row = $(this).closest('.grp-tr');
                var $percentageCell = $row.find('.percentage_column');
                if ($percentageCell.length) {
                    $percentageCell.text(percentage.toFixed(2) + '%');
                }
            });
            
            console.log('=== END GRAND TOTALS ===');
        }
        
        // Watch for changes in per_month fields
        $(document).on('input change', 'input[name*="-per_month"]', function() {
            var fieldName = $(this).attr('name');
            if (fieldName.indexOf('__prefix__') > -1) return;
            
            var prefix = getRowPrefix(fieldName);
            if (prefix) {
                calculateOverheadItem(prefix);
                calculateGrandTotals();
            }
        });
        
        // Watch for changes in item_type dropdown
        $(document).on('change', 'select[name*="-item_type"]', function() {
            calculateGrandTotals();
        });
        
        // Watch for changes in production_units
        $(document).on('input change', 'input[name="production_units"]', function() {
            // Recalculate all items
            $('input[name*="-per_month"]').not('[name*="__prefix__"]').each(function() {
                var prefix = getRowPrefix($(this).attr('name'));
                if (prefix) {
                    calculateOverheadItem(prefix);
                }
            });
            calculateGrandTotals();
        });
        
        // Watch for row additions/removals
        $(document).on('formset:added formset:removed', function() {
            calculateGrandTotals();
        });
        
        // Initial calculation on page load
        $('input[name*="-per_month"]').not('[name*="__prefix__"]').each(function() {
            var prefix = getRowPrefix($(this).attr('name'));
            if (prefix) {
                calculateOverheadItem(prefix);
            }
        });
        calculateGrandTotals();
        
    });
})(django.jQuery || jQuery);
