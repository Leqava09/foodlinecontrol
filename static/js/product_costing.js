(function() {
    document.addEventListener('DOMContentLoaded', function() {

        // Get currency from company settings (injected by Django), fallback to 'R'
        function getCurrency() {
            return window.COMPANY_CURRENCY || 'R';
        }
        const CURRENCY = getCurrency();

        function syncTableWithInline() {
            const htmlTable = document.getElementById('stock-items-table');

            const form = document.getElementById('productcosting_form');
            if (!form) {

                return;
            }

            if (htmlTable) {
                const usepriceInputs = htmlTable.querySelectorAll('.use-price-input');
                const wasteInputs = htmlTable.querySelectorAll('.waste-input');


                // SYNC USE PRICE
                usepriceInputs.forEach((input, idx) => {
                    const inlineUsePrice = form.querySelector(
                        `input[name="stock_items-${idx}-use_price_per_unit"]`
                    );

                    if (inlineUsePrice) {
                        input.value = inlineUsePrice.value;

                        input.addEventListener('change', function() {

                            inlineUsePrice.value = this.value;
                            inlineUsePrice.dispatchEvent(
                                new Event('change', { bubbles: true })
                            );

                            calculateTotals();
                        });

                        input.addEventListener('keyup', function() {
                            inlineUsePrice.value = this.value;
                        });
                    } else {

                    }
                });

                // SYNC WASTE %
                wasteInputs.forEach((input, idx) => {
                    const inlineWaste = form.querySelector(
                        `input[name="stock_items-${idx}-waste_percentage"]`
                    );

                    if (inlineWaste) {
                        input.value = inlineWaste.value;

                        input.addEventListener('change', function() {

                            inlineWaste.value = this.value;
                            inlineWaste.dispatchEvent(
                                new Event('change', { bubbles: true })
                            );

                            calculateTotals();
                        });

                        input.addEventListener('keyup', function() {
                            inlineWaste.value = this.value;
                        });
                    } else {

                    }
                });

                // Setup mutual exclusive checkboxes
                const useMarkupCheck = form.querySelector('input[name="use_markup"]');
                const usePercentMarkupCheck = form.querySelector(
                    'input[name="use_markup_percentage"]'
                );

                if (useMarkupCheck && usePercentMarkupCheck) {
                    useMarkupCheck.addEventListener('change', function() {
                        if (this.checked) {
                            usePercentMarkupCheck.checked = false;

                            calculateTotals();
                        }
                    });

                    usePercentMarkupCheck.addEventListener('change', function() {
                        if (this.checked) {
                            useMarkupCheck.checked = false;

                            calculateTotals();
                        }
                    });
                }

                const markupPercentInput = form.querySelector(
                    'input[name="markup_percentage"]'
                );
                if (markupPercentInput) {
                    markupPercentInput.addEventListener('change', calculateTotals);
                    markupPercentInput.addEventListener('keyup', calculateTotals);
                }

                const markupPerUnitInput = form.querySelector(
                    'input[name="markup_per_unit"]'
                );
                if (markupPerUnitInput) {
                    markupPerUnitInput.addEventListener('change', calculateTotals);
                    markupPerUnitInput.addEventListener('keyup', calculateTotals);
                }

                calculateTotals();
            }
        }

        function calculateTotals() {
            const form = document.getElementById('productcosting_form');
            if (!form) return;

            const usepriceInputs = form.querySelectorAll(
                'input[name*="use_price_per_unit"]'
            );
            const wasteInputs = form.querySelectorAll(
                'input[name*="waste_percentage"]'
            );

            let totalExclVat = 0;
            let lineCount = 0;

            usepriceInputs.forEach((input, idx) => {
                const usePrice = parseFloat(input.value) || 0;
                const wasteInput = wasteInputs[idx];
                const waste = wasteInput ? parseFloat(wasteInput.value) || 0 : 0;

                const wasteAmount = usePrice * (waste / 100);
                const lineTotal = usePrice + wasteAmount;

                totalExclVat += lineTotal;
                lineCount++;

            });

            const totalInclVat = totalExclVat * 1.15;


            updateDisplayTotals(totalExclVat, totalInclVat);
            calculateSellingPrice(totalInclVat);
        }

        function updateDisplayTotals(exclVat, inclVat) {
            const allReadonlyDivs = document.querySelectorAll('.grp-readonly');

            allReadonlyDivs.forEach((div) => {
                const parent = div.closest('.form-row');
                if (parent) {
                    const labelText = parent.textContent;

                    if (
                        labelText.includes('Total Stock Items Excl VAT') &&
                        labelText.includes('Total Stock Items Incl VAT')
                    ) {
                        const readonlyDivs = parent.querySelectorAll(
                            '.grp-readonly'
                        );
                        if (readonlyDivs.length === 2) {
                            readonlyDivs[0].textContent = `${CURRENCY} ${exclVat.toFixed(
                                2
                            )}`;
                            readonlyDivs[1].textContent = `${CURRENCY} ${inclVat.toFixed(
                                2
                            )}`;

                        }
                    }
                }
            });
        }

        function calculateSellingPrice(totalInclVat) {
            const form = document.getElementById('productcosting_form');
            if (!form) return;

            const useMarkupCheck = form.querySelector('input[name="use_markup"]');
            const usePercentMarkupCheck = form.querySelector(
                'input[name="use_markup_percentage"]'
            );
            const markupPercentInput = form.querySelector(
                'input[name="markup_percentage"]'
            );
            const markupPerUnitInput = form.querySelector(
                'input[name="markup_per_unit"]'
            );
            const sellingPriceField = form.querySelector('input[name="price"]');

            // Extract overhead from display text
            let overhead = 0;
            const overheadDisplay =
                document.querySelector(
                    '.overhead_price_per_unit_display .grp-readonly'
                ) ||
                Array.from(document.querySelectorAll('.grp-readonly')).find(
                    (el) =>
                        el.textContent.includes(CURRENCY) &&
                        el.parentElement.textContent.includes('Price per Unit')
                );
            if (overheadDisplay) {
                const text = overheadDisplay.textContent
                    .replace(CURRENCY, '')
                    .trim();
                overhead = parseFloat(text) || 0;
            }

            // Extract salary from display text
            let salary = 0;
            const salaryDisplay =
                document.querySelector(
                    '.salary_price_per_unit_display .grp-readonly'
                ) ||
                Array.from(document.querySelectorAll('.grp-readonly')).find(
                    (el) =>
                        el.textContent.includes(CURRENCY) &&
                        el.parentElement.parentElement.textContent.includes(
                            'Salary'
                        )
                );
            if (salaryDisplay) {
                const text = salaryDisplay.textContent
                    .replace(CURRENCY, '')
                    .trim();
                salary = parseFloat(text) || 0;
            }

            const baseCost = totalInclVat + overhead + salary;

            let sellingPrice = baseCost;

            // Determine which markup method is active
            if (useMarkupCheck && useMarkupCheck.checked) {
                // Use % Markup
                const markupPercent =
                    parseFloat(markupPercentInput.value) || 0;
                const markupAmount = baseCost * (markupPercent / 100);
                sellingPrice = baseCost + markupAmount;
            } else if (usePercentMarkupCheck && usePercentMarkupCheck.checked) {
                // Use Fixed Markup per Unit
                const markupPerUnit =
                    parseFloat(markupPerUnitInput.value) || 0;
                sellingPrice = baseCost + markupPerUnit;
            }

            if (sellingPriceField) {
                sellingPriceField.value = sellingPrice.toFixed(2);
            }

            // Update readonly display by label text, not via the input
            const allReadonlyDivs = document.querySelectorAll('.grp-readonly');
            allReadonlyDivs.forEach((div) => {
                const row = div.closest('.form-row');
                if (!row) return;

                const label = row.querySelector('label');
                if (!label) return;

                const labelText = (label.textContent || '').trim();
                if (labelText === 'Selling Price') {
                    div.textContent = CURRENCY + ' ' + sellingPrice.toFixed(2);
                }
            });
        }

        syncTableWithInline();
    });
})();
