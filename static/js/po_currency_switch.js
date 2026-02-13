/**
 * PO Admin - Switch currency default based on order type
 */
(function($) {
    $(document).ready(function() {
        
        var $orderType = $('select[name="order_type"]');
        var $currency = $('select[name="currency"]');
        
        if (!$orderType.length || !$currency.length) return;
        
        // Set initial currency based on order type
        function updateCurrencyDefault() {
            var orderType = $orderType.val();
            var currentCurrency = $currency.val();
            
            // Only auto-switch if currency is at default values
            if (orderType === 'Import' && (currentCurrency === 'R' || currentCurrency === '')) {
                $currency.val('USD');
            } else if (orderType === 'Local' && (currentCurrency === 'USD' || currentCurrency === '')) {
                $currency.val('R');
            }
        }
        
        // Listen for order type changes
        $orderType.on('change', updateCurrencyDefault);
        
        // Initial check on page load (for new records)
        if (!$currency.val() || $currency.val() === '') {
            updateCurrencyDefault();
        }
        
    });
})(django.jQuery || jQuery);
