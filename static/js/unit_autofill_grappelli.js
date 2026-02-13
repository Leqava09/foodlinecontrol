(function() {
    var previousValues = {};

    function updateUnit(stockItemSelect) {
        var nameMatch = stockItemSelect.name.match(/^(.+)-(\d+)-stock_item$/);
        if (!nameMatch) {
            return;
        }

        var inlinePrefix = nameMatch[1];
        var rowIndex = nameMatch[2];

        var stockItemId = stockItemSelect.value;

        if (!stockItemId) {
            return;
        }

        fetch('/inventory/get-unit/' + stockItemId + '/')
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                var unitText = data.unit_abbreviation || data.unit_name || '-';
                
                // Find the readonly unit display for this row
                // Pattern: look for .grp-readonly inside the unit_of_measure_display cell
                var row = stockItemSelect.closest('.grp-row, .grp-module, tr');
                if (!row) {

                    return;
                }

                // Try multiple selectors for readonly unit field
                var unitDisplay = 
                    row.querySelector('.field-unit_of_measure_display .grp-readonly') ||
                    row.querySelector('[data-fieldname="unit_of_measure_display"]') ||
                    row.querySelector('.unit_of_measure_display');

                if (unitDisplay) {
                    unitDisplay.textContent = unitText;

                } else {

                }
            })
            .catch(function(err) {

            });
    }

    function pollForChanges() {
        var selects = document.querySelectorAll('select[name$="-stock_item"]');

        selects.forEach(function(select) {
            var currentValue = select.value;
            var previousValue = previousValues[select.name];

            if (currentValue !== previousValue) {
                previousValues[select.name] = currentValue;
                updateUnit(select);
            }
        });
    }

    function attachHandlers() {
        var selects = document.querySelectorAll('select[name$="-stock_item"]');

        selects.forEach(function(select) {
            previousValues[select.name] = select.value;

            select.addEventListener('change', function(e) {
                updateUnit(e.target);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachHandlers);
    } else {
        attachHandlers();
    }

    document.addEventListener('formset:added', function() {
        attachHandlers();
    });

    setInterval(pollForChanges, 500);
})();
