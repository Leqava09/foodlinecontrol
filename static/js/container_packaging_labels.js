(function() {
    var previousValue = null;

    function updateUnit() {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (!stockItemSelect) return;

        var unitDisplay = document.querySelector('.field-box.unit_of_measure_display .grp-readonly');
        var stockItemId = stockItemSelect.value;

        if (!stockItemId) {
            if (unitDisplay) unitDisplay.textContent = '-';
            return;
        }

        // Make API call
        fetch('/inventory/get-unit/' + stockItemId + '/')
            .then(function(response) { return response.json(); })
            .then(function(data) {
                var unitText = data.unit_abbreviation || data.unit_name || '-';
                
                // Store unit globally for use in booking_live_calc.js
                window.currentStockItemUnit = unitText;
                
                // Trigger price recalculation in booking_live_calc.js after unit is set
                if (typeof window.triggerPriceCalculation === 'function') {
                    window.triggerPriceCalculation();
                }
                
                if (unitDisplay) unitDisplay.textContent = unitText;

            })
            .catch(function(err) {

            });
    }

    function pollForChange() {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (!stockItemSelect) return;

        var currentValue = stockItemSelect.value;
        if (previousValue !== currentValue) {
            previousValue = currentValue;
            updateUnit();
        }
    }

    // On page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            var stockItemSelect = document.querySelector('select[name="stock_item"]');
            if (stockItemSelect) {
                previousValue = stockItemSelect.value;
                updateUnit();
                stockItemSelect.addEventListener('change', updateUnit);
            }
        });
    } else {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (stockItemSelect) {
            previousValue = stockItemSelect.value;
            updateUnit();
            stockItemSelect.addEventListener('change', updateUnit);
        }
    }

    // Poll every 500ms for safety
    setInterval(pollForChange, 500);

})();
