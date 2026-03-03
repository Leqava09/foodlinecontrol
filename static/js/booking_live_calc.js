var doPriceCalculation = null;  // Will be set inside function
var siteCurrency = 'NAD';  // Global currency that gets fetched

// Fetch site currency FIRST before initializing calculations
function fetchSiteCurrency() {
    console.log('[BookingCalc] Starting currency fetch...');
    fetch('/inventory/get-currency/')
        .then(function(r) {
            console.log('[BookingCalc] Fetch response status:', r.status);
            return r.json();
        })
        .then(function(data) {
            console.log('[BookingCalc] Fetched data:', data);
            siteCurrency = data.currency || 'NAD';
            window.currentSiteCurrency = siteCurrency;
            console.log('[BookingCalc] Site currency set to:', siteCurrency);
            // After currency is fetched, initialize calculations
            initBookingCalculation();
        })
        .catch(function(e) {
            console.error('[BookingCalc] Error fetching site currency:', e);
            console.error('[BookingCalc] Initializing with default currency NAD');
            // Still initialize even if fetch fails
            initBookingCalculation();
        });
}

function initBookingCalculation() {
    // Get the packaging fields
    var kgPerBoxEl = document.getElementById('id_kg_per_box');
    var totalBoxesEl = document.getElementById('id_total_boxes');
    var totalAmountEl = document.getElementById('id_booking_in_total_qty') || 
                        document.getElementById('id_total_weight_container');
    
    // Get price display element - look for "per" or "NAD" ONLY (not just "Unit")
    var priceDisplayEl = null;
    var readonlyFields = document.querySelectorAll('[class*="readonly"], .grp-readonly');
    for (var i = 0; i < readonlyFields.length; i++) {
        var text = readonlyFields[i].textContent || readonlyFields[i].innerText;
        // Only match if it contains "per" or "NAD" - this ensures we get price, not unit
        if (text && (text.includes('per') || text.includes('NAD') || text.includes('per ') || text.includes('R '))) {
            if (!priceDisplayEl) {
                priceDisplayEl = readonlyFields[i];
            }
        }
    }

    // Make the packaging calculated field read-only to prevent manual editing
    if (totalAmountEl) {
        totalAmountEl.setAttribute('readonly', 'readonly');
        totalAmountEl.style.backgroundColor = '#f0f0f0';
        totalAmountEl.style.cursor = 'not-allowed';

    }
    
    // Function to calculate packaging total
    function doPackagingCalculation() {
        if (!kgPerBoxEl || !totalBoxesEl || !totalAmountEl) return;
        
        var kg = parseFloat(kgPerBoxEl.value) || 0;
        var boxes = parseFloat(totalBoxesEl.value) || 0;
        var total = (kg * boxes).toFixed(2);

        totalAmountEl.removeAttribute('readonly');
        totalAmountEl.value = total;
        totalAmountEl.setAttribute('readonly', 'readonly');
        
        var event = new Event('change', { bubbles: true });
        totalAmountEl.dispatchEvent(event);
    }
    
    // Function to calculate price per unit display
    doPriceCalculation = function() {
        if (!priceDisplayEl) return;
        
        var newPrice = '';
        var newTotalCost = '';
        
        // Use globally stored currency or default
        var currency = window.currentSiteCurrency || siteCurrency || 'NAD';
        console.log('[BookingCalc::doPriceCalculation] Using currency:', currency, 'window.currentSiteCurrency:', window.currentSiteCurrency, 'siteCurrency:', siteCurrency);
        
        // Try StockTransaction first (has booking_in_total_qty and total_invoice_amount_excl)
        var bookingTotalEl = document.getElementById('id_booking_in_total_qty');
        var invoiceEl = document.getElementById('id_total_invoice_amount_excl');
        var transportEl = document.getElementById('id_transport_cost');
        
        if (bookingTotalEl && invoiceEl) {
            var qty = parseFloat(bookingTotalEl.value) || 0;
            var invoice = parseFloat(invoiceEl.value) || 0;
            var transport = parseFloat(transportEl ? transportEl.value : 0) || 0;
            
            // Calculate price per unit - NO FALLBACK, use actual unit or show placeholder
            var unitDisplay = window.currentStockItemUnit || '---';
            if (qty > 0) {
                var totalCost = invoice + transport;
                var pricePerUnit = totalCost / qty;
                newPrice = currency + ' ' + pricePerUnit.toFixed(2) + ' per ' + unitDisplay;
                newTotalCost = currency + ' ' + totalCost.toFixed(2);
            } else {
                newPrice = currency + ' 0.00 per ' + unitDisplay;
                var totalCost = invoice + transport;
                newTotalCost = currency + ' ' + totalCost.toFixed(2);
            }
        } 
        // Try Container (has net_weight and all cost fields with exchange rates)
        else {
            // Use total_weight_container (auto-calculated from kg_per_box × total_boxes) for price divisor
            var weightEl = document.getElementById('id_total_weight_container') || document.getElementById('id_net_weight');
            var depositEl = document.getElementById('id_deposit_amount');
            var depositRateEl = document.getElementById('id_deposit_exchange_rate');
            var finalEl = document.getElementById('id_final_amount');
            var finalRateEl = document.getElementById('id_final_exchange_rate');
            var transportCostEl = document.getElementById('id_transport_cost');
            var transportRateEl = document.getElementById('id_transport_exchange_rate');
            var commissionEl = document.getElementById('id_commission');
            var commissionRateEl = document.getElementById('id_commission_exchange_rate');
            var dutyEl = document.getElementById('id_duty');
            var clearingEl = document.getElementById('id_clearing');
            
            if (weightEl) {
                var weight = parseFloat(weightEl.value) || 0;
                
                // Calculate each cost in NAD with exchange rates (mirrors backend logic)
                var depositAmount = parseFloat(depositEl?.value) || 0;
                var depositRate = parseFloat(depositRateEl?.value) || 1;
                var depositNad = depositAmount * depositRate;
                
                var finalAmount = parseFloat(finalEl?.value) || 0;
                var finalRate = parseFloat(finalRateEl?.value) || 1;
                var finalNad = finalAmount * finalRate;
                
                var transportAmount = parseFloat(transportCostEl?.value) || 0;
                var transportRate = parseFloat(transportRateEl?.value) || 1;
                var transportNad = transportAmount * transportRate;
                
                var commissionAmount = parseFloat(commissionEl?.value) || 0;
                var commissionRate = parseFloat(commissionRateEl?.value) || 1;
                var commissionNad = commissionAmount * commissionRate;
                
                var dutyAmount = parseFloat(dutyEl?.value) || 0;  // Already in NAD
                var clearingAmount = parseFloat(clearingEl?.value) || 0;  // Already in NAD
                
                // Sum all costs in NAD (same as backend total_cost_nad calculation)
                var totalCostNad = depositNad + finalNad + transportNad + commissionNad + dutyAmount + clearingAmount;
                
                // Format total cost display using site currency
                newTotalCost = currency + ' ' + totalCostNad.toFixed(2);
                
                // Use unit from stock item - NO FALLBACK, only use actual unit
                var unitDisplay = window.currentStockItemUnit || '---';
                if (weight > 0) {
                    var pricePerUnit = totalCostNad / weight;
                    newPrice = currency + ' ' + pricePerUnit.toFixed(2) + ' per ' + unitDisplay;
                } else {
                    newPrice = currency + ' 0.00 per ' + unitDisplay;
                }
            }
        }
        
        // Update price per unit display AND total cost display - search by label text to ensure correct field
        if (newPrice || newTotalCost) {
            var allFieldBoxes = document.querySelectorAll('.field-box');
            
            for (var i = 0; i < allFieldBoxes.length; i++) {
                var fieldBox = allFieldBoxes[i];
                var labels = fieldBox.querySelectorAll('label');
                
                for (var j = 0; j < labels.length; j++) {
                    var labelText = (labels[j].textContent || labels[j].innerText || '').toLowerCase();
                    
                    // Update price per unit display
                    if (newPrice && labelText.includes('price') && labelText.includes('per') && labelText.includes('unit')) {
                        var priceDiv = fieldBox.querySelector('.c-2 .grp-readonly');
                        if (priceDiv) {
                            priceDiv.textContent = newPrice;

                        }
                    }
                    
                    // Update total cost display
                    if (newTotalCost && labelText.includes('total') && labelText.includes('cost') && 
                        !labelText.includes('price') && !labelText.includes('per') && !labelText.includes('unit')) {
                        var costDiv = fieldBox.querySelector('.c-2 .grp-readonly');
                        if (costDiv) {
                            costDiv.textContent = newTotalCost;

                        }
                    }
                }
            }
        }
    };
    
    // Listen to packaging fields - trigger BOTH packaging AND price calculation
    if (kgPerBoxEl) {
        kgPerBoxEl.addEventListener('input', function() {
            doPackagingCalculation();
            doPriceCalculation();  // Also update price when packaging changes
        });
        kgPerBoxEl.addEventListener('change', function() {
            doPackagingCalculation();
            doPriceCalculation();
        });
        kgPerBoxEl.addEventListener('blur', function() {
            doPackagingCalculation();
            doPriceCalculation();
        });
    }
    
    if (totalBoxesEl) {
        totalBoxesEl.addEventListener('input', function() {
            doPackagingCalculation();
            doPriceCalculation();  // Also update price when packaging changes
        });
        totalBoxesEl.addEventListener('change', function() {
            doPackagingCalculation();
            doPriceCalculation();
        });
        totalBoxesEl.addEventListener('blur', function() {
            doPackagingCalculation();
            doPriceCalculation();
        });
    }
    
    // Listen to price calculation fields - StockTransaction
    var bookingTotalEl = document.getElementById('id_booking_in_total_qty');
    var invoiceEl = document.getElementById('id_total_invoice_amount_excl');
    var transportEl = document.getElementById('id_transport_cost');
    var currencyEl = document.getElementById('id_currency');
    
    if (bookingTotalEl) {
        bookingTotalEl.addEventListener('input', doPriceCalculation);
        bookingTotalEl.addEventListener('change', doPriceCalculation);
        bookingTotalEl.addEventListener('blur', doPriceCalculation);
    }
    if (invoiceEl) {
        invoiceEl.addEventListener('input', doPriceCalculation);
        invoiceEl.addEventListener('change', doPriceCalculation);
        invoiceEl.addEventListener('blur', doPriceCalculation);
    }
    if (transportEl) {
        transportEl.addEventListener('input', doPriceCalculation);
        transportEl.addEventListener('change', doPriceCalculation);
        transportEl.addEventListener('blur', doPriceCalculation);
    }
    if (currencyEl) {
        currencyEl.addEventListener('change', doPriceCalculation);
    }
    
    // Listen to price calculation fields - Container
    var weightEl = document.getElementById('id_total_weight_container') || document.getElementById('id_net_weight');
    var depositEl = document.getElementById('id_deposit_amount');
    var depositRateEl = document.getElementById('id_deposit_exchange_rate');
    var finalEl = document.getElementById('id_final_amount');
    var finalRateEl = document.getElementById('id_final_exchange_rate');
    var transportCostEl = document.getElementById('id_transport_cost');
    var transportRateEl = document.getElementById('id_transport_exchange_rate');
    var commissionEl = document.getElementById('id_commission');
    var commissionRateEl = document.getElementById('id_commission_exchange_rate');
    var dutyEl = document.getElementById('id_duty');
    var clearingEl = document.getElementById('id_clearing');
    
    var costFields = [
        weightEl, depositEl, depositRateEl, finalEl, finalRateEl, 
        transportCostEl, transportRateEl, commissionEl, commissionRateEl, 
        dutyEl, clearingEl
    ];
    for (var i = 0; i < costFields.length; i++) {
        if (costFields[i]) {
            costFields[i].addEventListener('input', doPriceCalculation);
            costFields[i].addEventListener('change', doPriceCalculation);
            costFields[i].addEventListener('blur', doPriceCalculation);
        }
    }
    
    // Do initial calculations
    doPackagingCalculation();
    doPriceCalculation();

}

// Expose trigger function globally so unit_autofill_stocktransaction.js can call it
window.triggerPriceCalculation = function() {
    if (typeof doPriceCalculation === 'function') {
        doPriceCalculation();
    }
};

// Run when document loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fetchSiteCurrency);
} else {
    fetchSiteCurrency();
}

// Also run after a delay for dynamic content
setTimeout(initBookingCalculation, 500);
setTimeout(initBookingCalculation, 2000);
