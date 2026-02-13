/**
 * Salary Costing - Dynamic calculation for all fields
 * Updates totals, percentages in real-time
 */
(function($) {
    $(document).ready(function() {
        console.log('=== SALARY COSTING DYNAMIC CALCULATIONS LOADED ===');
        
        // Only run on add/change form pages, not on list pages
        // Check if inline formset exists (positions inline)
        if ($('input[name*="positions-"][name$="-general_workers"]').not('[name*="__prefix__"]').length === 0) {
            console.log('⊗ Salary calc: Not on change/add form - skipping calculations');
            return;
        }
        
        // Add CSS to center column headings and vertically center display columns and center input field columns
        $('<style>' +
            '.grp-td.total_per_hour_display, .grp-td.total_per_month_display, .grp-td.percentage_display { vertical-align: middle !important; }' +
            '.grp-td.general_workers, .grp-td.qa_workers, .grp-td.shifts, .grp-td.shift_hours, .grp-td.rate_per_hour, .grp-td.qa_rate_per_hour, .grp-td.days_worked { text-align: center !important; }' +
            '.grp-table .grp-thead th, .grp-thead .grp-th { text-align: center !important; }' +
            'th.column-position_name, th.column-total_per_hour_display { text-align: center !important; }' +
        '</style>').appendTo('head');
        
        function getRowPrefix(fieldName) {
            var match = fieldName.match(/^(.+-\d+-)/);
            return match ? match[1] : null;
        }
        
        function calculateSalaryPosition(prefix) {
            var generalWorkers = parseFloat($('input[name="' + prefix + 'general_workers"]').val()) || 0;
            var ratePerHour = parseFloat($('input[name="' + prefix + 'rate_per_hour"]').val()) || 0;
            var qaWorkers = parseFloat($('input[name="' + prefix + 'qa_workers"]').val()) || 0;
            var qaRatePerHour = parseFloat($('input[name="' + prefix + 'qa_rate_per_hour"]').val()) || 0;
            var shifts = parseFloat($('input[name="' + prefix + 'shifts"]').val()) || 0;
            var shiftHours = parseFloat($('input[name="' + prefix + 'shift_hours"]').val()) || 0;
            var daysWorked = parseFloat($('input[name="' + prefix + 'days_worked"]').val()) || 0;
            
            var totalPerHour = (generalWorkers * ratePerHour) + (qaWorkers * qaRatePerHour);
            var totalPerMonth = totalPerHour * shifts * shiftHours * daysWorked;
            
            var $row = $('input[name="' + prefix + 'general_workers"]').closest('.grp-tr');
            console.log('Row found:', $row.length, 'Row HTML classes:', $row.attr('class'));
            var $perHourCell = $row.find('.total_per_hour_display');
            console.log('Per hour cell found:', $perHourCell.length);
            if ($perHourCell.length) {
                $perHourCell.text('NAD ' + totalPerHour.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            var $perMonthCell = $row.find('.total_per_month_display');
            console.log('Per month cell found:', $perMonthCell.length);
            if ($perMonthCell.length) {
                $perMonthCell.text('NAD ' + totalPerMonth.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            console.log('Calculated position:', prefix, 'perHour:', totalPerHour, 'perMonth:', totalPerMonth);
        }
        // Helper to parse SA-formatted numbers like "NAD 19 200,00" -> 19200.00
        function parseSANumber(text) {
            // Remove currency prefix and trim
            var clean = text.replace(/^[A-Z]{3}\s*/i, '').trim();
            // Remove spaces (thousands separator)
            clean = clean.replace(/\s/g, '');
            // Replace comma with period (decimal separator)
            clean = clean.replace(',', '.');
            return parseFloat(clean) || 0;
        }
        
        function calculateGrandTotals() {
            console.log('=== CALCULATING GRAND TOTALS ===');
            
            // Fixed subtotal = Management + Office input fields
            var managementSalary = parseFloat($('input[name="management_salary"]').val()) || 0;
            var officeSalary = parseFloat($('input[name="office_salary"]').val()) || 0;
            var fixedSubtotal = managementSalary + officeSalary;
            
            // Production subtotal = Sum of all position "Total for Month" values
            var productionSubtotal = 0;
            $('input[name*="positions-"][name$="-general_workers"]').not('[name*="__prefix__"]').each(function() {
                var $row = $(this).closest('.grp-tr');
                var monthText = $row.find('.total_per_month_display').text();
                var monthVal = parseSANumber(monthText);
                console.log('Row month text:', monthText, '-> parsed:', monthVal);
                productionSubtotal += monthVal;
            });
            
            // Grand Total = Fixed subtotal + Production subtotal
            var grandTotal = fixedSubtotal + productionSubtotal;
            
            // Price per Unit = Grand Total / Production Units
            var productionUnits = parseFloat($('input[name="production_units"]').val()) || 1;
            var pricePerUnit = productionUnits > 0 ? grandTotal / productionUnits : 0;
            
            console.log('Management:', managementSalary, 'Office:', officeSalary, 'Fixed:', fixedSubtotal);
            console.log('Production:', productionSubtotal, 'Grand:', grandTotal, 'Units:', productionUnits, 'Price/Unit:', pricePerUnit);
            
            // Update Fixed subtotal display
            var $fixedDisplay = $('#salary-fixed-total');
            if ($fixedDisplay.length) {
                $fixedDisplay.text('NAD ' + fixedSubtotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update Production subtotal display
            var $productionDisplay = $('#salary-production-total');
            if ($productionDisplay.length) {
                $productionDisplay.text('NAD ' + productionSubtotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update Grand Total display
            var $grandDisplay = $('#salary-grand-total');
            if ($grandDisplay.length) {
                $grandDisplay.text('NAD ' + grandTotal.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update Price per Unit display
            var $priceDisplay = $('#salary-price-per-unit');
            if ($priceDisplay.length) {
                $priceDisplay.text('NAD ' + pricePerUnit.toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            }
            
            // Update percentage for each position (% of Production subtotal - should add up to 100%)
            $('input[name*="positions-"][name$="-general_workers"]').not('[name*="__prefix__"]').each(function() {
                var $row = $(this).closest('.grp-tr');
                var monthText = $row.find('.total_per_month_display').text();
                var monthVal = parseSANumber(monthText);
                var percentage = productionSubtotal > 0 ? (monthVal / productionSubtotal * 100) : 0;
                
                var $percentageCell = $row.find('.percentage_display');
                if ($percentageCell.length) {
                    $percentageCell.text(percentage.toFixed(2) + '%');
                }
            });
            
            console.log('=== END GRAND TOTALS ===');
        }
        
        // Watch for changes in any salary input fields (positions + header fields)
        $(document).on('input change keyup', 'input[name*="positions-"], input[name="management_salary"], input[name="office_salary"], input[name="production_units"]', function() {
            console.log('=== INPUT CHANGED ===', $(this).attr('name'), $(this).val());
            var fieldName = $(this).attr('name');
            if (fieldName.indexOf('__prefix__') > -1) return;
            
            // If it's a management/office/production_units field, just update totals
            if (fieldName === 'management_salary' || fieldName === 'office_salary' || fieldName === 'production_units') {
                calculateGrandTotals();
                return;
            }
            
            var prefix = getRowPrefix(fieldName);
            console.log('Prefix found:', prefix);
            if (prefix) {
                calculateSalaryPosition(prefix);
                setTimeout(calculateGrandTotals, 50);
            }
        });
        
        // Watch for changes in production units
        $(document).on('input change', 'input[name="production_units_month"]', function() {
            setTimeout(calculateGrandTotals, 50);
        });
        
        // Initial calculation on page load
        setTimeout(function() {
            console.log('=== INITIAL CALCULATION STARTING ===');
            var $inputs = $('input[name*="positions-"][name$="-general_workers"]').not('[name*="__prefix__"]');
            console.log('Found ' + $inputs.length + ' salary position rows');
            $inputs.each(function() {
                var prefix = getRowPrefix($(this).attr('name'));
                console.log('Processing row with prefix:', prefix);
                if (prefix) {
                    calculateSalaryPosition(prefix);
                }
            });
            calculateGrandTotals();
        }, 100);
        
        console.log('=== SALARY CALC EVENT HANDLERS ATTACHED ===');
    });
})(django.jQuery);
