(function() {
    // Trigger unit fetch on page load if stock_item is already set
    document.addEventListener('DOMContentLoaded', function() {
        var stockItemSelect = document.querySelector('select[name="stock_item"]');
        if (stockItemSelect && stockItemSelect.value) {
            // Trigger the updateUnit function from unit_autofill_stocktransaction.js
            var event = new Event('change', { bubbles: true });
            stockItemSelect.dispatchEvent(event);
        }
    });
})();