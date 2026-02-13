/**
 * Batch Costing Pricing Calculation - MATCHED TO PRODUCT COSTING PATTERN
 * Formula: (stock_price × 1.15) + overhead + salary + (markup_per_unit / % markup)
 */

(function() {

    // Get currency from company settings (injected by Django), fallback to 'R'
    function getCurrency() {
        return window.COMPANY_CURRENCY || 'R';
    }

    // HELPER FUNCTION - Extract read-only field values by field-name in class
    function getReadOnlyValue(fieldName) {
        const CURRENCY = getCurrency();
        let el = document.querySelector(`.field-${fieldName} .grp-readonly`);
        if (!el) {
            el = document.querySelector(`.field-${fieldName} .readonly`);
        }

        // Fallback: search any .grp-readonly that is inside a row mentioning this label
        if (!el) {
            const allReadonly = document.querySelectorAll('.grp-readonly, .readonly');
            for (let div of allReadonly) {
                const row = div.closest('.form-row');
                if (!row) continue;
                if (row.innerHTML.includes(fieldName)) {
                    el = div;
                    break;
                }
            }
        }

        if (!el) {

            return 0;
        }

        const text = el.textContent
            .replace(CURRENCY, '')
            .replace(/NAD/g, '')
            .replace(/R/g, '')
            .replace(/\$/g, '')
            .replace(/€/g, '')
            .replace(/,/g, '')
            .trim();
        const value = parseFloat(text) || 0;
        return value;
    }

    // NEW: Update "Selling Price" display - show currency prefix as label, not in input value
    function updatePriceDisplayReadonly(sellingPrice) {
        const CURRENCY = getCurrency();
        const priceInput = document.querySelector('input[name="price"]');
        if (!priceInput) return;

        // Store numeric value only (for Django form submission)
        priceInput.value = sellingPrice.toFixed(2);
        
        // Add/update a visual currency label before the input if not already present
        let currencyLabel = priceInput.previousElementSibling;
        if (!currencyLabel || !currencyLabel.classList.contains('currency-prefix')) {
            currencyLabel = document.createElement('span');
            currencyLabel.classList.add('currency-prefix');
            currencyLabel.style.cssText = 'margin-right: 5px; font-weight: bold;';
            priceInput.parentNode.insertBefore(currencyLabel, priceInput);
        }
        currencyLabel.textContent = CURRENCY;
    }

    // MAIN CALCULATION FUNCTION
    function calculateSellingPrice() {
        const CURRENCY = getCurrency();

        const stockPriceInput       = document.querySelector('input[name="stock_item_price_use"]');
        const useMarkupCheck        = document.querySelector('input[name="use_markup"]');
        const useMarkupPerUnitCheck = document.querySelector('input[name="use_markup_per_unit"]');
        const markupPercentInput    = document.querySelector('input[name="markup_percentage"]');
        const markupPerUnitInput    = document.querySelector('input[name="markup_per_unit"]');
        const priceField            = document.querySelector('input[name="price"]');

        if (!priceField) {

            return;
        }

        let stockPrice = 0;
        if (stockPriceInput) {
            stockPrice = parseFloat(stockPriceInput.value) || 0;
        }

        const overhead = getReadOnlyValue('overhead_price_per_unit_display');
        const salary   = getReadOnlyValue('salary_price_per_unit_display');

        let sellingPrice = (stockPrice * 1.15) + overhead + salary;

        if (useMarkupCheck && useMarkupCheck.checked) {
            const markupPerUnit  = parseFloat(markupPerUnitInput.value) || 0;
            const markupPercent  = parseFloat(markupPercentInput.value) || 1;
            const markupAdjustment = markupPerUnit / markupPercent;
            sellingPrice += markupAdjustment;
        } else if (useMarkupPerUnitCheck && useMarkupPerUnitCheck.checked) {
            const amount = parseFloat(markupPerUnitInput.value) || 0;
            sellingPrice += amount;
        }

        const finalPrice = parseFloat(sellingPrice.toFixed(2));

        // Store numeric for server-side save if needed
        priceField.value = finalPrice;
        priceField.readOnly = true;


        // Format the visible box as "NAD 32.67"
        updatePriceDisplayReadonly(finalPrice);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const priceField = document.querySelector('input[name="price"]');
        if (!priceField) {
            return;
        }

        const useMarkupCheck        = document.querySelector('input[name="use_markup"]');
        const useMarkupPerUnitCheck = document.querySelector('input[name="use_markup_per_unit"]');
        const markupPercentInput    = document.querySelector('input[name="markup_percentage"]');
        const markupPerUnitInput    = document.querySelector('input[name="markup_per_unit"]');
        const stockPriceInput       = document.querySelector('input[name="stock_item_price_use"]');

        function attachListener(el) {
            if (!el) return;
            el.addEventListener('change', calculateSellingPrice);
            if (el.type === 'text' || el.type === 'number') {
                el.addEventListener('keyup', calculateSellingPrice);
            }
        }

        attachListener(useMarkupCheck);
        attachListener(useMarkupPerUnitCheck);
        attachListener(markupPercentInput);
        attachListener(markupPerUnitInput);
        attachListener(stockPriceInput);

        if (useMarkupCheck && useMarkupPerUnitCheck) {
            useMarkupCheck.addEventListener('change', function() {
                if (this.checked) {
                    useMarkupPerUnitCheck.checked = false;
                    calculateSellingPrice();
                }
            });
            useMarkupPerUnitCheck.addEventListener('change', function() {
                if (this.checked) {
                    useMarkupCheck.checked = false;
                    calculateSellingPrice();
                }
            });
        }

        // Run after initial data/default scripts
        setTimeout(calculateSellingPrice, 500);

    });
})();
