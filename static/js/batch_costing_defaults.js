/**
 * Auto-populate BatchCosting defaults
 */
document.addEventListener('DOMContentLoaded', function() {

    const overheadField = document.querySelector('[name="overhead_costing"]');
    const salaryField = document.querySelector('[name="salary_costing"]');
    const stockPriceUseField = document.querySelector('[name="stock_item_price_use"]');
    const productionDateField = document.querySelector('[name="production_date"]');
    
    // Set overhead default
    if (overheadField && overheadField.value === '') {
        overheadField.value = '1';

    }
    
    // Set salary default
    if (salaryField && salaryField.value === '') {
        salaryField.value = '1';

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
                        
                        // Do NOT update read-only display - let it pull from the admin method
                    }
                })
                .catch(() => {});
        }
    }
});
