/**
 * BatchCosting Default Change Confirmation & Auto-populate
 * 
 * When a user changes the overhead, salary, or investor/loan costing selection on an existing
 * BatchCosting record, this script shows a confirmation dialog asking whether
 * to update the snapshot values to the new default or keep the current ones.
 * Also handles auto-population of stock prices from production dates.
 */
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('batchcosting_form');
        
        const overheadField = document.querySelector('[name="overhead_costing"]');
        const salaryField = document.querySelector('[name="salary_costing"]');
        const investorLoanField = document.querySelector('[name="investor_loan_costing"]');
        const stockPriceUseField = document.querySelector('[name="stock_item_price_use"]');
        const productionDateField = document.querySelector('[name="production_date"]');
        
        // Set overhead default
        if (overheadField && overheadField.value === '') {
            overheadField.value = '1';
            // Update display after a short delay to ensure everything is ready
            setTimeout(() => {
                if (typeof updateCostingDisplay === 'function') {
                    updateCostingDisplay('overhead', '1');
                }
            }, 150);
        }
        
        // Set salary default
        if (salaryField && salaryField.value === '') {
            salaryField.value = '1';
            // Update display after a short delay to ensure everything is ready
            setTimeout(() => {
                if (typeof updateCostingDisplay === 'function') {
                    updateCostingDisplay('salary', '1');
                }
            }, 150);
        }
        
        // Set investor/loan default
        if (investorLoanField && investorLoanField.value === '') {
            investorLoanField.value = '1';
            console.log('✅ Set investor_loan default to 1');
            // Update display after a short delay to ensure DOM and functions are ready
            setTimeout(() => {
                console.log('Calling updateCostingDisplay for investor_loan...');
                if (typeof updateCostingDisplay === 'function') {
                    updateCostingDisplay('investor_loan', '1');
                } else {
                    console.warn('updateCostingDisplay function not available');
                }
            }, 150);
        }
        
        // Auto-populate stock_item_price_use from API (editable field ONLY)
        if (productionDateField && stockPriceUseField && productionDateField.value) {
            const prodDate = productionDateField.value;
            const currentValue = parseFloat(stockPriceUseField.value) || 0;
            
            // Only populate if empty or zero
            if (currentValue === 0) {
                fetch(`/costing/api/batch-summary-items/${prodDate}/`)
                    .then(r => r.json())
                    .then(data => {
                        const items = data.items || [];
                        const totalBatchUnits = data.total_batch_units || 0;
                        
                        if (items.length > 0 && totalBatchUnits > 0) {
                            const totalUsedCosting = items.reduce((sum, item) => sum + (item.used_costing || 0), 0);
                            const pricePerUnitUsed = totalUsedCosting / totalBatchUnits;
                            
                            stockPriceUseField.value = pricePerUnitUsed.toFixed(2);
                        }
                    })
                    .catch(() => {});
            }
        }
        
        // ===== DYNAMIC COSTING UPDATE LOGIC =====
        if (!form) return;
        
        if (!overheadField && !salaryField && !investorLoanField) return;
        
        // Get original values from server-injected globals
        const originalOverheadId = window.ORIGINAL_OVERHEAD_COSTING_ID || '';
        const originalSalaryId = window.ORIGINAL_SALARY_COSTING_ID || '';
        const originalInvestorLoanId = window.ORIGINAL_INVESTOR_LOAN_COSTING_ID || '';
        const currentOverheadSnapshot = window.OVERHEAD_SNAPSHOT || 0;
        const currentSalarySnapshot = window.SALARY_SNAPSHOT || 0;
        const currentInvestorLoanSnapshot = window.INVESTOR_LOAN_SNAPSHOT || 0;
        
        // Track if defaults have changed
        let overheadChanged = false;
        let salaryChanged = false;
        let investorLoanChanged = false;
        let userConfirmedUpdate = false;
        
        // Create hidden field to communicate with server
        let hiddenField = document.getElementById('update_costing_snapshots');
        if (!hiddenField) {
            hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = 'update_costing_snapshots';
            hiddenField.id = 'update_costing_snapshots';
            hiddenField.value = 'false';
            form.appendChild(hiddenField);
        }
        
        // Monitor overhead changes
        if (overheadField) {
            overheadField.addEventListener('change', function() {
                const currentVal = this.value;
                if (originalOverheadId && currentVal !== originalOverheadId) {
                    overheadChanged = true;
                } else {
                    overheadChanged = false;
                }
                updateCostingDisplay('overhead', currentVal);
            });
        }
        
        // Monitor salary changes
        if (salaryField) {
            salaryField.addEventListener('change', function() {
                const currentVal = this.value;
                if (originalSalaryId && currentVal !== originalSalaryId) {
                    salaryChanged = true;
                } else {
                    salaryChanged = false;
                }
                updateCostingDisplay('salary', currentVal);
            });
        }
        
        // Monitor investor/loan changes
        if (investorLoanField) {
            investorLoanField.addEventListener('change', function() {
                const currentVal = this.value;
                if (originalInvestorLoanId && currentVal !== originalInvestorLoanId) {
                    investorLoanChanged = true;
                } else {
                    investorLoanChanged = false;
                }
                updateCostingDisplay('investor_loan', currentVal);
            });
        }
        
        // Intercept form submission
        form.addEventListener('submit', function(e) {
            // Only show popup if overhead or salary or investor/loan has changed AND this is an edit (not new record)
            if ((overheadChanged || salaryChanged || investorLoanChanged) && (originalOverheadId || originalSalaryId || originalInvestorLoanId)) {
                // Build message for user
                let changedItems = [];
                if (overheadChanged) {
                    changedItems.push('Overhead Costing');
                }
                if (salaryChanged) {
                    changedItems.push('Salary Costing');
                }
                if (investorLoanChanged) {
                    changedItems.push('Investor / Loan Costing');
                }
                
                const message = `You have changed the ${changedItems.join(' and ')}.\n\n` +
                    `Do you want to UPDATE the snapshot price values to the new default?\n\n` +
                    `• Click "OK" to use the NEW default values going forward\n` +
                    `• Click "Cancel" to keep the CURRENT snapshot values\n\n` +
                    `Note: This only affects the stored price per unit snapshots for this record.`;
                
                userConfirmedUpdate = confirm(message);
                hiddenField.value = userConfirmedUpdate ? 'true' : 'false';
            }
            
            // Allow form to submit
            return true;
        });
        
        // Function to update costing display dynamically
        function updateCostingDisplay(costingType, costingId) {
            if (!costingId) return;
            
            const currency = window.COMPANY_CURRENCY || 'R';
            
            // Fetch price per unit for the selected costing
            fetch(`/costing/get-costing-price/${costingType}/${costingId}/`)
                .then(response => response.json())
                .then(data => {
                    if (data.price_per_unit !== undefined) {
                        // Find and update the display field
                        let displayClass = '';
                        if (costingType === 'overhead') {
                            displayClass = 'overhead_price_per_unit_display';
                        } else if (costingType === 'salary') {
                            displayClass = 'salary_price_per_unit_display';
                        } else if (costingType === 'investor_loan') {
                            displayClass = 'investor_loan_price_per_unit_display';
                        }
                        
                        const displayElement = document.querySelector(`.${displayClass} .grp-readonly`);
                        if (displayElement) {
                            displayElement.textContent = `${currency} ${parseFloat(data.price_per_unit).toFixed(2)}`;
                        }
                        
                        // Trigger selling price recalculation
                        if (typeof calculateSellingPrice === 'function') {
                            calculateSellingPrice();
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching costing price:', error);
                });
        }
    });
})();
