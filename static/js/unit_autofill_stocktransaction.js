(function() {
    var previousValue = null;

    // Packaging label configs
    const packagingLabels = {
        'KG': {
            'meat': {
                kg_per_box: 'kg/Box',
                total_boxes: 'Total Amount of Boxes',
                gross_weight: 'Gross Weight (kg)',
                net_weight: 'Net Weight (kg)'
            },
            'default': {
                kg_per_box: 'kg/Unit',
                total_boxes: 'Total Amount of Units',
                gross_weight: 'Gross Weight (kg)',
                net_weight: 'Net Weight (kg)'
            }
        },
        'L': {
            'concentrate': {
                kg_per_box: 'L/Bag',
                total_boxes: 'Total Amount of Bags',
                gross_weight: 'Gross Weight (L)',
                net_weight: 'Net Weight (L)'
            },
            'default': {
                kg_per_box: 'L/Container',
                total_boxes: 'Total Amount of Containers',
                gross_weight: 'Gross Weight (L)',
                net_weight: 'Net Weight (L)'
            }
        },
        'UNIT': {
            'starch': {
                kg_per_box: 'Units/Bottle',
                total_boxes: 'Total Amount of Bottles',
                gross_weight: 'Gross Weight (Units)',
                net_weight: 'Net Weight (Units)'
            },
            'default': {
                kg_per_box: 'Units/Package',
                total_boxes: 'Total Amount of Packages',
                gross_weight: 'Gross Weight (Units)',
                net_weight: 'Net Weight (Units)'
            }
        }
    };

    function updateUnitAndPackaging() {

		var stockItemSelect = document.querySelector('select[name="stock_item"]');
		if (!stockItemSelect) {

			return;
		}

		// Try multiple selectors - added more options for readonly fields
		var unitDisplay = document.querySelector('.field-box.unit_of_measure_display .grp-readonly');
		if (!unitDisplay) {
			unitDisplay = document.querySelector('[data-fieldname="unit_of_measure_display"] .grp-readonly');
		}
		if (!unitDisplay) {
			unitDisplay = document.querySelector('.unit_of_measure_display');
		}
		// ✅ ADD THESE NEW SELECTORS FOR BOOKING OUT SHEET
		if (!unitDisplay) {
			unitDisplay = document.querySelector('input[name="unit_of_measure_display"]');
		}
		if (!unitDisplay) {
			// Look for any readonly field with this name
			unitDisplay = document.querySelector('[name="unit_of_measure_display"]');
		}
		if (!unitDisplay) {
			// Last resort: find the field by label
			const labels = Array.from(document.querySelectorAll('label'));
			const unitLabel = labels.find(l => l.textContent.includes('Unit'));
			if (unitLabel) {
				unitDisplay = unitLabel.parentElement.querySelector('[readonly], [disabled]');
			}
		}

		var stockItemId = stockItemSelect.value;

		if (!stockItemId) {

			return;
		}

		fetch('/inventory/get-unit/' + stockItemId + '/')
			.then(r => r.json())
			.then(data => {

				var unitText = data.unit_abbreviation || data.unit_name || '-';
				
				// Store unit globally for use in other scripts like booking_live_calc.js
				window.currentStockItemUnit = unitText;
				
				// Trigger price recalculation in booking_live_calc.js after unit is set
				if (typeof window.triggerPriceCalculation === 'function') {
					window.triggerPriceCalculation();
				}

				if (unitDisplay) {

					// Check if it's an input field (has .value property)
					if (unitDisplay.tagName === 'INPUT' || unitDisplay.value !== undefined) {
						unitDisplay.value = unitText;
					} else {
						// It's a div - find the text node and update only that
						// This preserves the label element
						const textNode = Array.from(unitDisplay.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
						if (textNode) {
							textNode.textContent = unitText;
						} else {
							// No text node, append one
							unitDisplay.appendChild(document.createTextNode(unitText));
						}
					}

				} else {


					document.querySelectorAll('[readonly], [disabled]').forEach((el, i) => {

					});
				}
			})
			.catch(() => {});
	}

    function applyPackagingLabels(unitKey, categoryKey) {
        var unitConfig = packagingLabels[unitKey] || packagingLabels['UNIT'];
        var labels = unitConfig[categoryKey] || unitConfig['default'];

        setLabel('id_kg_per_box', labels.kg_per_box);
        setLabel('id_total_boxes', labels.total_boxes);
        setLabel('id_gross_weight', labels.gross_weight);
        setLabel('id_net_weight', labels.net_weight);
    }

    function resetPackagingLabels() {
        setLabel('id_kg_per_box', 'kg/Box');
        setLabel('id_total_boxes', 'Total Amount of Boxes');
        setLabel('id_gross_weight', 'Gross Weight (kg)');
        setLabel('id_net_weight', 'Net Weight (kg)');
    }

    function setLabel(fieldId, text) {
        var label = document.querySelector('label[for="' + fieldId + '"]');
        if (label) {
            label.textContent = text;
        }
    }

    function pollForChange() {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (!stockItemSelect) return;

        var currentValue = stockItemSelect.value;
        if (previousValue !== currentValue) {
            previousValue = currentValue;
            updateUnitAndPackaging();   // runs on every change
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            var stockItemSelect = document.querySelector('select[name="stock_item"]');
            if (stockItemSelect) {
                previousValue = stockItemSelect.value;
                updateUnitAndPackaging();                      // run once on load
                stockItemSelect.addEventListener('change', updateUnitAndPackaging); // and on change
            }
        });
    } else {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (stockItemSelect) {
            previousValue = stockItemSelect.value;
            updateUnitAndPackaging();
            stockItemSelect.addEventListener('change', updateUnitAndPackaging);
        }
    }

    // safety net in case Grappelli replaces the select dynamically
    setInterval(pollForChange, 500);

})();

